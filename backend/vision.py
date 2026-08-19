"""
Módulo de Visão Computacional e Processamento de Vídeo.

Contém:
- CameraStream: leitor de frames em thread própria (RTSP/ONVIF ou webcam local),
  sempre entregando o frame mais recente (evita acúmulo de latência em RTSP).
- VideoProcessor: detecção + rastreamento de pessoas (YOLOv8 + ByteTrack),
  anonimização por blur (LGPD) e a lógica avançada de análise por perfil de
  câmera (atendimento de balcão, inatividade de escritório, estagnação em
  estoque) — ver docstrings de cada `_atualizar_*` abaixo para o algoritmo.
- CameraManager: registry singleton de VideoProcessor por camera_id.

Arquitetura de threads (importante para performance/robustez):
- Cada câmera tem exatamente UMA thread de processamento dedicada (iniciada em
  `VideoProcessor.__init__`), que lê o frame mais recente do `CameraStream`,
  roda a inferência YOLO+ByteTrack, atualiza as métricas e guarda o JPEG já
  processado em um buffer protegido por lock.
- `generate_mjpeg()` (chamado uma vez por viewer HTTP, em `routes.video_feed`)
  é um CONSUMIDOR puro: só lê o último JPEG do buffer. Múltiplas pessoas
  assistindo a mesma câmera não duplicam inferência nem competem pelo mesmo
  modelo/tracker — e como o FastAPI executa geradores síncronos de
  StreamingResponse em thread própria (via `iterate_in_threadpool`), nada
  disso bloqueia o event loop que atende as demais requisições da API.
- Cada câmera tem sua PRÓPRIA instância de modelo YOLO e de detector facial
  (nada de singleton global): o `model.track(..., persist=True)` do Ultralytics
  mantém estado de rastreamento por instância, então compartilhar um modelo
  entre câmeras diferentes corromperia a continuidade dos IDs do ByteTrack de
  uma câmera com a de outra rodando em paralelo. O custo é mais memória (um
  YOLOv8n por câmera, ~alguns MB) — uma troca deliberada em favor de correção.

Conformidade LGPD: nenhum frame bruto, recorte facial ou embedding biométrico é
persistido em disco/banco. Apenas contadores/tempos agregados (métricas) são
gravados nas tabelas metricas_atendimento / metricas_ocupacao.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import config
import models

Pessoa = Tuple[int, Optional[int], Tuple[int, int, int, int]]  # (classe, track_id, box)
Centro = Tuple[float, float, float, float]  # (cx_pixel, cy_pixel, cx_normalizado, cy_normalizado)


# ----------------------------------------------------------------------------
# Captura de vídeo (RTSP/ONVIF ou webcam local) em thread dedicada
# ----------------------------------------------------------------------------
class CameraStream:
    """
    Lê continuamente frames de uma fonte de vídeo em uma thread separada e mantém
    apenas o frame mais recente disponível — essencial para RTSP, onde o buffer
    interno do OpenCV acumula atraso se não for drenado constantemente.

    `source` aceita:
      - "0", "1", ... (string ou int): índice de webcam local, para testes.
      - "rtsp://usuario:senha@ip:porta/caminho": URL RTSP de câmera IP/ONVIF.
    """

    def __init__(self, source: str):
        self.source = int(source) if str(source).isdigit() else source
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.connected = False

    def start(self) -> "CameraStream":
        self._open_capture()
        self._running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        return self

    def _open_capture(self) -> None:
        # CAP_FFMPEG lida bem com RTSP; para webcam local o backend padrão é usado.
        backend = cv2.CAP_FFMPEG if isinstance(self.source, str) else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(self.source, backend)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.connected = self._cap.isOpened()

    def _update_loop(self) -> None:
        falhas_consecutivas = 0
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                self.connected = False
                time.sleep(2.0)
                self._open_capture()
                continue

            ok, frame = self._cap.read()
            if not ok:
                falhas_consecutivas += 1
                self.connected = False
                if falhas_consecutivas > 10:
                    # Tenta reconectar (comum em RTSP instável)
                    self._cap.release()
                    time.sleep(1.5)
                    self._open_capture()
                    falhas_consecutivas = 0
                continue

            falhas_consecutivas = 0
            self.connected = True
            with self._lock:
                self._frame = frame

    def read(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()


# ----------------------------------------------------------------------------
# Zonas geométricas
# ----------------------------------------------------------------------------
@dataclass
class ZonaRuntime:
    id: int
    tipo_zona: str
    pontos_normalizados: List[Tuple[float, float]]

    def poligono_absoluto(self, largura: int, altura: int) -> np.ndarray:
        pts = [(x * largura, y * altura) for x, y in self.pontos_normalizados]
        return np.array(pts, dtype=np.int32)

    def contem_ponto(self, x: float, y: float, largura: int, altura: int) -> bool:
        """`x, y` em coordenadas de PIXEL (mesmo espaço da bbox do YOLO)."""
        poligono = self.poligono_absoluto(largura, altura)
        return cv2.pointPolygonTest(poligono, (float(x), float(y)), False) >= 0


# ----------------------------------------------------------------------------
# Estado de rastreamento por pessoa (ByteTrack ID) — usado pelas análises de
# postura/movimento (escritório e estoque) e para o grid de estagnação.
# ----------------------------------------------------------------------------
@dataclass
class TrackMovimento:
    ultima_posicao_normalizada: Tuple[float, float]
    ultima_vez_moveu: float  # time.monotonic() da última vez com deslocamento perceptível
    ultima_vez_visto: float
    celula_atual: Optional[Tuple[int, int]] = None
    tempo_na_celula: float = 0.0
    estagnacao_registrada: bool = False


@dataclass
class ParAtendimento:
    """Um par (atendente presente, cliente sendo atendido) com cronômetro ativo."""

    atendente_track_id: int
    inicio: float  # time.monotonic()
    confirmado: bool = False  # True assim que a presença conjunta atinge o limiar


# ----------------------------------------------------------------------------
# Processador principal: detecção + rastreamento + blur + análise por perfil
# ----------------------------------------------------------------------------
class VideoProcessor:
    """
    Processa o vídeo de UMA câmera: detecta e rastreia pessoas com YOLOv8 + ByteTrack,
    aplica blur de anonimização (LGPD) e roda a lógica de análise específica do
    `perfil_ativo` da câmera (balcao_loja / escritorio / estoque), persistindo os
    resultados via `session_factory`. Roda em thread própria — ver docstring do módulo.
    """

    def __init__(
        self,
        camera_id: int,
        empresa_id: int,
        source: str,
        perfil: str,
        zonas: List[ZonaRuntime],
        session_factory,
    ):
        self.camera_id = camera_id
        self.empresa_id = empresa_id
        self.perfil = perfil
        self.zonas = zonas
        self.session_factory = session_factory

        self.stream = CameraStream(source).start()

        # Modelo e detector facial são carregados sob demanda, DENTRO da thread de
        # processamento (evita bloquear quem chamou CameraManager.get_or_create).
        self._modelo = None
        self._detector_facial = None

        # --- Estado de rastreamento (tocado só pela thread de processamento) ---
        self._tracks: Dict[int, TrackMovimento] = {}

        # --- Perfil balcão/loja: atendimento por par atendente+cliente ---
        self._pares_atendimento: Dict[int, ParAtendimento] = {}
        self._cooldown_clientes: Dict[int, float] = {}  # track_id -> quando saiu

        agora = time.monotonic()
        # --- Perfil escritório: inatividade na zona de trabalho ---
        self._escritorio_ultima_atividade_em = agora
        self._escritorio_evento_registrado = False
        # --- Perfil estoque: movimentação geral no espaço monitorado ---
        self._estoque_ultima_movimentacao_em = agora
        # --- Ocupação genérica (comum a todos os perfis) ---
        self._ultima_deteccao_com_pessoa = agora
        self._ultima_amostra_ocupacao = agora
        self._ultimo_frame_processado_em: Optional[float] = None

        # --- Buffer do frame já processado (o que os viewers HTTP consomem) ---
        self._frame_lock = threading.Lock()
        self._ultimo_jpeg: Optional[bytes] = None

        self._rodando = True
        self._thread = threading.Thread(target=self._loop_processamento, daemon=True)
        self._thread.start()

    # -------------------- zonas --------------------
    def atualizar_zonas(self, zonas: List[ZonaRuntime]) -> None:
        self.zonas = zonas

    def _zonas_do_tipo(self, tipo: str) -> List[ZonaRuntime]:
        return [z for z in self.zonas if z.tipo_zona == tipo]

    # -------------------- geometria auxiliar --------------------
    @staticmethod
    def _centro(box: Tuple[int, int, int, int], w: int, h: int) -> Centro:
        """Base da bbox (pés da pessoa) — em pixel (p/ testar zonas) e normalizado (p/ movimento)."""
        x1, y1, x2, y2 = box
        cx, cy = (x1 + x2) / 2, y2
        return cx, cy, cx / w, cy / h

    @staticmethod
    def _celula_grid(nx: float, ny: float) -> Tuple[int, int]:
        col = min(config.ESTOQUE_GRID_COLUNAS - 1, max(0, int(nx * config.ESTOQUE_GRID_COLUNAS)))
        lin = min(config.ESTOQUE_GRID_LINHAS - 1, max(0, int(ny * config.ESTOQUE_GRID_LINHAS)))
        return col, lin

    # -------------------- anonimização (LGPD) --------------------
    @staticmethod
    def _blur_regiao(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return
        k = config.BLUR_KERNEL if config.BLUR_KERNEL % 2 == 1 else config.BLUR_KERNEL + 1
        roi = frame[y1:y2, x1:x2]
        frame[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)

    def _anonimizar(self, frame: np.ndarray, pessoas_boxes: List[Tuple[int, int, int, int]]) -> None:
        """Borra toda a bounding box de cada pessoa detectada (cobre rosto e corpo)."""
        for x1, y1, x2, y2 in pessoas_boxes:
            self._blur_regiao(frame, x1, y1, x2, y2)

        # Camada extra: detector facial dedicado, para cobrir rostos que escapem
        # das boxes de pessoa (ex.: detecção parcial). Nenhum recorte é salvo.
        try:
            if self._detector_facial is None:
                import mediapipe as mp

                self._detector_facial = mp.solutions.face_detection.FaceDetection(
                    model_selection=0, min_detection_confidence=0.5
                )
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resultado = self._detector_facial.process(rgb)
            if resultado.detections:
                h, w = frame.shape[:2]
                for det in resultado.detections:
                    bbox = det.location_data.relative_bounding_box
                    x1 = int(bbox.xmin * w)
                    y1 = int(bbox.ymin * h)
                    x2 = int((bbox.xmin + bbox.width) * w)
                    y2 = int((bbox.ymin + bbox.height) * h)
                    self._blur_regiao(frame, x1, y1, x2, y2)
        except Exception:
            # Detector facial é uma camada extra best-effort; falhas aqui não podem
            # interromper o streaming (o blur das boxes de pessoa já é a proteção principal).
            pass

    # -------------------- detecção + rastreamento --------------------
    def _detectar_pessoas(self, frame: np.ndarray) -> List[Pessoa]:
        """Retorna lista de (classe=pessoa, track_id, (x1,y1,x2,y2)) usando o modelo desta câmera."""
        if self._modelo is None:
            from ultralytics import YOLO

            self._modelo = YOLO(config.YOLO_MODEL_PATH)

        resultados = self._modelo.track(
            frame,
            persist=True,
            classes=[0],  # 0 = "person" no COCO
            conf=config.YOLO_CONF_THRESHOLD,
            tracker=config.YOLO_TRACKER,
            verbose=False,
        )

        pessoas: List[Pessoa] = []
        if not resultados:
            return pessoas

        boxes = resultados[0].boxes
        if boxes is None:
            return pessoas

        ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
        for box, track_id in zip(boxes.xyxy.cpu().tolist(), ids):
            x1, y1, x2, y2 = map(int, box)
            pessoas.append((0, track_id, (x1, y1, x2, y2)))
        return pessoas

    # -------------------- bookkeeping de rastreamento (todos os perfis) --------------------
    def _atualizar_estado_tracks(
        self, pessoas: List[Pessoa], centros: Dict[int, Centro], agora: float, dt: float
    ) -> None:
        """
        Atualiza, por track_id: posição normalizada, há quanto tempo não se move de
        forma perceptível, e em qual célula do grid de estagnação está (e há quanto
        tempo). Base tanto da análise de escritório (estática/ausente) quanto de
        estoque (movimentação contínua / áreas de estagnação).
        """
        for _, track_id, _ in pessoas:
            if track_id is None or track_id not in centros:
                continue
            _, _, nx, ny = centros[track_id]

            estado = self._tracks.get(track_id)
            if estado is None:
                estado = TrackMovimento(
                    ultima_posicao_normalizada=(nx, ny), ultima_vez_moveu=agora, ultima_vez_visto=agora
                )
                self._tracks[track_id] = estado
            else:
                deslocamento = math.hypot(nx - estado.ultima_posicao_normalizada[0], ny - estado.ultima_posicao_normalizada[1])
                if deslocamento >= config.MOVIMENTO_MINIMO_NORMALIZADO:
                    estado.ultima_vez_moveu = agora
                estado.ultima_posicao_normalizada = (nx, ny)
                estado.ultima_vez_visto = agora

            celula = self._celula_grid(nx, ny)
            if celula == estado.celula_atual:
                estado.tempo_na_celula += dt
            else:
                estado.celula_atual = celula
                estado.tempo_na_celula = 0.0
                estado.estagnacao_registrada = False

        # Limpeza: remove tracks não vistos há muito tempo (evita crescimento ilimitado
        # do dicionário ao longo de horas/dias de streaming contínuo).
        expirados = [tid for tid, e in self._tracks.items() if agora - e.ultima_vez_visto > 120]
        for tid in expirados:
            del self._tracks[tid]

    def _moveu_recentemente(self, track_id: int, agora: float, janela_segundos: float = 2.0) -> bool:
        estado = self._tracks.get(track_id)
        return estado is not None and (agora - estado.ultima_vez_moveu) < janela_segundos

    # -------------------- Perfil BALCÃO/LOJA: atendimento por par atendente+cliente --------------------
    def _atualizar_atendimento_balcao(
        self, centros: Dict[int, Centro], w: int, h: int, agora: float
    ) -> None:
        """
        Algoritmo (spec):
        1. Monitora 'Zona do Atendente' e 'Zona do Cliente' simultaneamente.
        2. Quando há pelo menos um ID em cada zona AO MESMO TEMPO, inicia um
           cronômetro para aquele cliente (associado ao atendente presente no momento).
        3. Se a presença conjunta permanece contínua por >= ATENDIMENTO_MIN_SEGUNDOS,
           o par é confirmado como "Atendimento Em Andamento" (sinalizado no overlay).
        4. Quando o cliente sai da zona, o cronômetro é encerrado: grava-se +1
           atendimento com a duração exata; concluído=True somente se chegou a ser
           confirmado (>= limiar), senão é registrado como abandono/passagem rápida.
        5. Anti-duplicação: ao encerrar, o track_id do cliente entra em cooldown por
           CLIENTE_COOLDOWN_SEGUNDOS — se reaparecer na zona nesse intervalo (comum em
           oclusões breves que causam flicker de detecção), não inicia um novo par.
        """
        zonas_atendente = self._zonas_do_tipo("atendente")
        zonas_cliente = self._zonas_do_tipo("cliente")
        if not zonas_atendente or not zonas_cliente:
            return  # perfil balcão sem as duas zonas configuradas: nada a rastrear ainda

        tracks_em_atendente = set()
        tracks_em_cliente = set()
        for track_id, (cx, cy, _, _) in centros.items():
            if any(z.contem_ponto(cx, cy, w, h) for z in zonas_atendente):
                tracks_em_atendente.add(track_id)
            if any(z.contem_ponto(cx, cy, w, h) for z in zonas_cliente):
                tracks_em_cliente.add(track_id)

        # Purga cooldowns expirados
        expirados = [
            tid for tid, saiu_em in self._cooldown_clientes.items()
            if agora - saiu_em > config.CLIENTE_COOLDOWN_SEGUNDOS
        ]
        for tid in expirados:
            del self._cooldown_clientes[tid]

        # Inicia cronômetro para clientes novos na zona — exige atendente presente
        # NO MESMO INSTANTE (presença simultânea, conforme a especificação).
        if tracks_em_atendente:
            atendente_ref = next(iter(tracks_em_atendente))
            for tid in tracks_em_cliente:
                if tid in self._pares_atendimento or tid in self._cooldown_clientes:
                    continue
                self._pares_atendimento[tid] = ParAtendimento(atendente_track_id=atendente_ref, inicio=agora)

        # Atualiza/encerra pares ativos
        for tid in list(self._pares_atendimento.keys()):
            par = self._pares_atendimento[tid]
            if tid in tracks_em_cliente:
                if not par.confirmado and (agora - par.inicio) >= config.ATENDIMENTO_MIN_SEGUNDOS:
                    par.confirmado = True  # validado como "Atendimento Em Andamento"
            else:
                # Cliente saiu da zona: encerra o cronômetro e persiste o atendimento.
                duracao = agora - par.inicio
                self._salvar_metrica_atendimento(duracao, concluido=par.confirmado)
                del self._pares_atendimento[tid]
                self._cooldown_clientes[tid] = agora

    def _salvar_metrica_atendimento(self, duracao_segundos: float, concluido: bool) -> None:
        db = self.session_factory()
        try:
            registro = models.MetricaAtendimento(
                camera_id=self.camera_id,
                empresa_id=self.empresa_id,
                timestamp=datetime.utcnow(),
                duracao_segundos=round(duracao_segundos, 2),
                concluido=concluido,
            )
            db.add(registro)
            db.commit()
        finally:
            db.close()

    # -------------------- Perfil ESCRITÓRIO: inatividade na zona de trabalho --------------------
    def _atualizar_escritorio(self, centros: Dict[int, Centro], w: int, h: int, agora: float) -> None:
        """
        Mede o tempo acumulado que alguém permanece na 'Zona de Trabalho' (mesa/estação)
        e monitora atividade real (deslocamento perceptível), não só presença: uma
        pessoa parada e uma zona vazia contam igualmente como inatividade. Ao cruzar
        ESCRITORIO_INATIVIDADE_SEGUNDOS sem atividade, registra um evento (uma linha
        em metricas_ocupacao) — e não repete o registro até a atividade retomar.
        """
        zonas_trabalho = self._zonas_do_tipo("trabalho")
        if not zonas_trabalho:
            return  # sem zona de trabalho configurada, não há o que medir

        presentes = [
            tid for tid, (cx, cy, _, _) in centros.items() if any(z.contem_ponto(cx, cy, w, h) for z in zonas_trabalho)
        ]
        houve_atividade = any(self._moveu_recentemente(tid, agora) for tid in presentes)

        if presentes and houve_atividade:
            self._escritorio_ultima_atividade_em = agora
            self._escritorio_evento_registrado = False

        inatividade = agora - self._escritorio_ultima_atividade_em
        if inatividade >= config.ESCRITORIO_INATIVIDADE_SEGUNDOS and not self._escritorio_evento_registrado:
            self._persistir_ocupacao(pessoas_detectadas=len(presentes), tempo_inatividade_segundos=inatividade)
            self._escritorio_evento_registrado = True

    # -------------------- Perfil ESTOQUE: movimentação contínua e estagnação --------------------
    def _atualizar_estoque(self, centros: Dict[int, Centro], w: int, h: int, agora: float) -> None:
        """
        Mede movimentação contínua no espaço monitorado (a 'Zona de Trabalho', se
        configurada, senão o frame inteiro) e identifica áreas de estagnação: células
        de um grid (ESTOQUE_GRID_COLUNAS x ESTOQUE_GRID_LINHAS) onde uma pessoa
        permanece parada por tempo igual ou superior a ESTOQUE_ESTAGNACAO_SEGUNDOS
        (bookkeeping de célula/tempo já mantido por `_atualizar_estado_tracks`).
        """
        zonas_trabalho = self._zonas_do_tipo("trabalho")

        tracks_no_espaco = []
        for tid, (cx, cy, _, _) in centros.items():
            if zonas_trabalho and not any(z.contem_ponto(cx, cy, w, h) for z in zonas_trabalho):
                continue
            tracks_no_espaco.append(tid)

        # Movimentação geral: o relógio de inatividade só reseta quando alguém se
        # desloca de forma perceptível dentro do espaço monitorado.
        if any(self._moveu_recentemente(tid, agora) for tid in tracks_no_espaco):
            self._estoque_ultima_movimentacao_em = agora

        # Áreas de estagnação: uma pessoa parada na mesma célula por tempo demais.
        for tid in tracks_no_espaco:
            estado = self._tracks.get(tid)
            if not estado or estado.estagnacao_registrada:
                continue
            if estado.tempo_na_celula >= config.ESTOQUE_ESTAGNACAO_SEGUNDOS:
                self._persistir_ocupacao(
                    pessoas_detectadas=len(tracks_no_espaco),
                    tempo_inatividade_segundos=estado.tempo_na_celula,
                )
                estado.estagnacao_registrada = True

    # -------------------- Ocupação genérica (amostragem periódica, todos os perfis) --------------------
    def _calcular_inatividade_atual(self, agora: float) -> float:
        """
        O significado de "inatividade" muda por perfil:
        - escritorio: segundos desde a última atividade real na zona de trabalho.
        - estoque: segundos desde a última movimentação perceptível no espaço.
        - balcao_loja / demais: segundos desde a última detecção de qualquer pessoa
          (definição genérica original, adequada para lojas/vitrines).
        """
        if self.perfil == "escritorio":
            return agora - self._escritorio_ultima_atividade_em
        if self.perfil == "estoque":
            return agora - self._estoque_ultima_movimentacao_em
        return agora - self._ultima_deteccao_com_pessoa

    def _atualizar_ocupacao_periodica(self, pessoas: List[Pessoa], agora: float) -> None:
        if pessoas:
            self._ultima_deteccao_com_pessoa = agora

        if agora - self._ultima_amostra_ocupacao < config.OCUPACAO_AMOSTRA_SEGUNDOS:
            return
        self._ultima_amostra_ocupacao = agora
        self._persistir_ocupacao(len(pessoas), self._calcular_inatividade_atual(agora))

    def _persistir_ocupacao(self, pessoas_detectadas: int, tempo_inatividade_segundos: float) -> None:
        db = self.session_factory()
        try:
            registro = models.MetricaOcupacao(
                camera_id=self.camera_id,
                empresa_id=self.empresa_id,
                timestamp=datetime.utcnow(),
                pessoas_detectadas=pessoas_detectadas,
                tempo_inatividade_segundos=round(tempo_inatividade_segundos, 2),
            )
            db.add(registro)
            db.commit()
        finally:
            db.close()

    # -------------------- desenho de apoio (zonas + pessoas) --------------------
    def _desenhar_zonas(self, frame: np.ndarray) -> None:
        cores = {
            "atendente": (255, 140, 0),
            "cliente": (0, 200, 0),
            "trabalho": (0, 165, 255),
            "neutra": (128, 128, 128),
        }
        h, w = frame.shape[:2]
        for zona in self.zonas:
            poligono = zona.poligono_absoluto(w, h)
            cor = cores.get(zona.tipo_zona, (200, 200, 200))
            cv2.polylines(frame, [poligono], isClosed=True, color=cor, thickness=2)

    def _desenhar_pessoas(self, frame: np.ndarray, pessoas: List[Pessoa]) -> None:
        for _, track_id, (x1, y1, x2, y2) in pessoas:
            par = self._pares_atendimento.get(track_id) if track_id is not None else None
            if par and par.confirmado:
                cor, rotulo, espessura = (0, 220, 0), "ATENDIMENTO EM ANDAMENTO", 2
            elif track_id is not None:
                cor, rotulo, espessura = (0, 255, 255), f"ID {track_id}", 1
            else:
                cor, rotulo, espessura = (0, 255, 255), "", 1

            cv2.rectangle(frame, (x1, y1), (x2, y2), cor, espessura)
            if rotulo:
                cv2.putText(
                    frame, rotulo, (x1, max(0, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 1, cv2.LINE_AA,
                )

    # -------------------- pipeline por frame --------------------
    def processar_frame(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        agora = time.monotonic()
        dt = 0.0 if self._ultimo_frame_processado_em is None else max(0.0, agora - self._ultimo_frame_processado_em)
        self._ultimo_frame_processado_em = agora

        pessoas = self._detectar_pessoas(frame)
        boxes = [box for _, _, box in pessoas]
        centros: Dict[int, Centro] = {
            track_id: self._centro(box, w, h) for _, track_id, box in pessoas if track_id is not None
        }

        # 1) Anonimização SEMPRE antes de qualquer desenho/exposição do frame (LGPD)
        self._anonimizar(frame, boxes)

        # 2) Bookkeeping de rastreamento (posição/movimento/célula do grid)
        self._atualizar_estado_tracks(pessoas, centros, agora, dt)

        # 3) Lógica específica do perfil ativo da câmera
        if self.perfil == "balcao_loja":
            self._atualizar_atendimento_balcao(centros, w, h, agora)
        elif self.perfil == "escritorio":
            self._atualizar_escritorio(centros, w, h, agora)
        elif self.perfil == "estoque":
            self._atualizar_estoque(centros, w, h, agora)

        # 4) Amostragem periódica de ocupação (comum a todos os perfis)
        self._atualizar_ocupacao_periodica(pessoas, agora)

        # 5) Overlays visuais
        self._desenhar_zonas(frame)
        self._desenhar_pessoas(frame, pessoas)

        return frame

    # -------------------- thread de processamento + streaming --------------------
    def _loop_processamento(self) -> None:
        """
        Roda em background, uma vez por câmera, independente de quantos viewers HTTP
        existem. É aqui — e não em `generate_mjpeg` — que a inferência de IA acontece,
        então requisições concorrentes da API nunca disputam o modelo desta câmera.
        """
        intervalo = 1.0 / max(1, config.STREAM_TARGET_FPS)
        while self._rodando:
            inicio = time.monotonic()
            frame = self.stream.read()
            if frame is None:
                time.sleep(0.1)
                continue

            try:
                processado = self.processar_frame(frame)
            except Exception:
                # Uma falha pontual (ex.: frame corrompido) não pode derrubar a
                # thread de processamento da câmera — só pula esse frame.
                continue

            ok, buffer = cv2.imencode(
                ".jpg", processado, [int(cv2.IMWRITE_JPEG_QUALITY), config.STREAM_JPEG_QUALITY]
            )
            if ok:
                with self._frame_lock:
                    self._ultimo_jpeg = buffer.tobytes()

            decorrido = time.monotonic() - inicio
            time.sleep(max(0.0, intervalo - decorrido))

    def generate_mjpeg(self):
        """
        Consumidor puro (um por viewer HTTP): só lê o último JPEG já processado.
        Não roda IA — ver docstring do módulo sobre a thread de processamento dedicada.
        """
        intervalo = 1.0 / max(1, config.STREAM_TARGET_FPS)
        while True:
            with self._frame_lock:
                jpeg = self._ultimo_jpeg
            if jpeg is None:
                time.sleep(0.1)
                continue

            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            time.sleep(intervalo)

    def stop(self) -> None:
        self._rodando = False
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.stream.stop()


# ----------------------------------------------------------------------------
# Registry de processadores ativos (1 por câmera, compartilhado entre viewers)
# ----------------------------------------------------------------------------
class CameraManager:
    def __init__(self):
        self._processadores: Dict[int, VideoProcessor] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        camera: models.Camera,
        zonas: List[models.Zona],
        session_factory,
    ) -> VideoProcessor:
        with self._lock:
            processador = self._processadores.get(camera.id)
            if processador is not None:
                return processador

            zonas_runtime = [
                ZonaRuntime(
                    id=z.id,
                    tipo_zona=z.tipo_zona.value if hasattr(z.tipo_zona, "value") else z.tipo_zona,
                    pontos_normalizados=_parse_coordenadas(z.coordenadas_json),
                )
                for z in zonas
            ]

            processador = VideoProcessor(
                camera_id=camera.id,
                empresa_id=camera.empresa_id,
                source=camera.rtsp_url,
                perfil=camera.perfil_ativo.value if hasattr(camera.perfil_ativo, "value") else camera.perfil_ativo,
                zonas=zonas_runtime,
                session_factory=session_factory,
            )
            self._processadores[camera.id] = processador
            return processador

    def stop(self, camera_id: int) -> None:
        with self._lock:
            processador = self._processadores.pop(camera_id, None)
        if processador:
            processador.stop()

    def stop_all(self) -> None:
        with self._lock:
            processadores = list(self._processadores.values())
            self._processadores.clear()
        for p in processadores:
            p.stop()


def _parse_coordenadas(coordenadas_json: str) -> List[Tuple[float, float]]:
    import json

    pontos = json.loads(coordenadas_json)
    return [(float(p[0]), float(p[1])) for p in pontos]


# Instância única compartilhada pela aplicação (importada nas rotas)
camera_manager = CameraManager()
