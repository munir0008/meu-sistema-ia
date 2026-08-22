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

import logging
import math
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

import config
import models

logger = logging.getLogger("vision")

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
        # CAP_FFMPEG lida bem com RTSP. Para webcam local no Windows, CAP_ANY cai no
        # backend MSMF, que é instável para leitura contínua em thread própria (trava
        # com "can't grab frame. Error: -1072873821" e o stream fica vazio para
        # sempre) — CAP_DSHOW é o backend confiável para esse caso nesta plataforma.
        if isinstance(self.source, str):
            backend = cv2.CAP_FFMPEG
        elif sys.platform == "win32":
            backend = cv2.CAP_DSHOW
        else:
            backend = cv2.CAP_ANY
        self._cap = cv2.VideoCapture(self.source, backend)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.connected = self._cap.isOpened()
        if self.connected:
            logger.info("[camera source=%s] cap.isOpened()=True — captura aberta com sucesso.", self.source)
        else:
            # Causa mais comum em produção: `source` é um índice de webcam local
            # ("0", "1", ...) mas o processo do backend está rodando num servidor
            # remoto (ex.: Render) sem NENHUM dispositivo de câmera físico — não hà
            # webcam para o OpenCV abrir aí, então isso vai falhar sempre, não é
            # intermitente. Para RTSP, normalmente é URL/credencial/porta erradas ou
            # a câmera fora da mesma rede que o servidor consegue alcançar.
            logger.warning(
                "[camera source=%s] cap.isOpened()=False — não foi possível abrir a fonte de vídeo. "
                "Se `source` é um índice de webcam local (\"0\", \"1\"...), confirme que o processo do "
                "backend está rodando na MESMA máquina que tem a câmera — um servidor remoto (Render, "
                "por ex.) não enxerga webcam nenhuma. Se é RTSP, confirme URL/credenciais e que o "
                "servidor tem rota de rede até a câmera.",
                self.source,
            )

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
                estava_conectado = self.connected
                self.connected = False
                if estava_conectado:
                    logger.warning("[camera source=%s] cap.read() passou a falhar (ok=False) — sem frame novo.", self.source)
                if falhas_consecutivas > 10:
                    # Tenta reconectar (comum em RTSP instável)
                    logger.warning(
                        "[camera source=%s] %d falhas de leitura consecutivas — reabrindo a captura.",
                        self.source, falhas_consecutivas,
                    )
                    self._cap.release()
                    time.sleep(1.5)
                    self._open_capture()
                    falhas_consecutivas = 0
                continue

            if not self.connected:
                logger.info("[camera source=%s] voltou a ler frames com sucesso.", self.source)
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


# Valor de `Camera.rtsp_url` que sinaliza "esta câmera não é aberta pelo
# backend via OpenCV — os frames chegam por push do NAVEGADOR do usuário, via
# WebSocket" (ver BrowserPushStream e routes.camera_ingest). Necessário porque
# um backend rodando num servidor remoto (ex.: Render) não tem acesso a
# NENHUMA webcam local: quem tem a câmera de verdade é o navegador de quem
# está com o notebook/PC na mão, então é ele quem precisa capturar e enviar.
FONTE_WEBCAM_NAVEGADOR = "browser"


class BrowserPushStream:
    """
    Fonte de frames alimentada por PUSH externo (via WebSocket), em vez de aberta
    pelo próprio backend via OpenCV como o CameraStream. Usada quando
    `Camera.rtsp_url == FONTE_WEBCAM_NAVEGADOR`: o navegador do usuário captura a
    própria webcam (getUserMedia) e envia os frames prontos (JPEG) pra cá — ver
    routes.camera_ingest, que decodifica e chama `push_frame`.

    Implementa a mesma interface pública que VideoProcessor espera de
    CameraStream (start/read/connected/stop), então o resto do pipeline
    (detecção, zonas, blur, streaming de saída) não precisa saber a diferença
    entre as duas fontes.
    """

    def __init__(self, timeout_sem_frame: Optional[float] = None):
        self._timeout_sem_frame = timeout_sem_frame or config.CAMERA_NAVEGADOR_FRAME_TIMEOUT_SEGUNDOS
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._ultimo_frame_recebido_em = 0.0

    def start(self) -> "BrowserPushStream":
        return self  # nada a abrir aqui — os frames chegam via push_frame()

    def push_frame(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame
            self._ultimo_frame_recebido_em = time.monotonic()

    def _frame_fresco(self) -> bool:
        return self._frame is not None and (time.monotonic() - self._ultimo_frame_recebido_em) < self._timeout_sem_frame

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._frame_fresco()

    def read(self) -> Optional[np.ndarray]:
        # Some (não devolve o último frame indefinidamente) depois de
        # CAMERA_NAVEGADOR_FRAME_TIMEOUT_SEGUNDOS sem push novo — do contrário o
        # feed pareceria "ao vivo" pra sempre com um frame congelado, mesmo com a
        # aba do navegador que captura já fechada há minutos.
        with self._lock:
            return self._frame.copy() if self._frame_fresco() else None

    def stop(self) -> None:
        with self._lock:
            self._frame = None


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
class DebouncePresenca:
    """
    Debounce/histerese de presença de UMA pessoa (track_id) numa zona: só
    confirma uma entrada/saída depois que o estado bruto observado (dentro/fora
    do polígono) se mantém estável por ZONA_DEBOUNCE_SEGUNDOS — filtra flicker de
    detecção (oscilação de confiança na borda do polígono, oclusão de 1-2
    frames) sem atrasar demais os eventos de telemetria. Ver
    VideoProcessor._atualizar_debounce.
    """

    confirmado: bool = False  # último estado CONFIRMADO (dentro=True/fora=False)
    candidato: bool = False  # estado bruto observado no frame atual
    candidato_desde: float = 0.0  # time.monotonic() de quando `candidato` começou
    confirmado_desde: Optional[float] = None  # time.monotonic() da última entrada confirmada (p/ medir duração na saída)


@dataclass
class SessaoFilaCliente:
    """
    Uma pessoa na zona 'Cliente', do momento em que entra até sair — usada para
    calcular tempo de espera, desistência e "Atendimento Em Andamento" (Dashboard
    Analytics Tópico 1). Ver vision.VideoProcessor._atualizar_atendimento_balcao.
    """

    inicio: float  # time.monotonic() da entrada na zona 'Cliente'
    # time.monotonic() da primeira vez que um atendente foi visto presente na
    # zona 'Atendente' enquanto esta sessão estava ativa. None = ainda não atendido.
    momento_atendente_chegou: Optional[float] = None
    # True assim que a presença conjunta (atendente + este cliente) atinge o limiar
    # ATENDIMENTO_MIN_SEGUNDOS — "Atendimento Em Andamento".
    confirmado: bool = False


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

        if str(source).strip().lower() == FONTE_WEBCAM_NAVEGADOR:
            self.stream = BrowserPushStream().start()
        else:
            self.stream = CameraStream(source).start()

        # Modelo e detector facial são carregados sob demanda, DENTRO da thread de
        # processamento (evita bloquear quem chamou CameraManager.get_or_create).
        self._modelo = None
        self._detector_facial = None

        # --- Estado de rastreamento (tocado só pela thread de processamento) ---
        self._tracks: Dict[int, TrackMovimento] = {}

        # --- Perfil balcão/loja: debounce de presença por zona (ver DebouncePresenca) ---
        self._debounce_atendente: Dict[int, DebouncePresenca] = {}
        self._debounce_cliente: Dict[int, DebouncePresenca] = {}

        # --- Perfil balcão/loja: sessões de fila (cliente na zona 'Cliente') ---
        self._sessoes_fila: Dict[int, SessaoFilaCliente] = {}
        self._cooldown_clientes: Dict[int, float] = {}  # track_id -> quando saiu

        # --- Perfil balcão/loja: alerta "Pico de Fila Sem Atendente" ---
        self._fila_atendente_ausente_desde: Optional[float] = None
        self._fila_pico_registrado = False

        agora = time.monotonic()
        # --- Perfil balcão/loja: amostragem periódica de ocupação das zonas
        # 'Atendente'/'Trabalho' e 'Cliente' (Dashboard Analytics Tópico 2) ---
        self._ultima_amostra_balcao = agora

        # --- Resiliência a queda de conexão da câmera (ver _verificar_desconexao_prolongada) ---
        self._ultima_leitura_ok_em = agora
        self._estado_resetado_por_desconexao = False
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

        # --- Status real da câmera (models.Camera.status), refletindo se a captura
        # está de fato entregando frames — ver _atualizar_status_camera. None força a
        # primeira persistência mesmo que `stream.connected` já nasça False (default
        # da coluna já é "offline", mas queremos o log da primeira checagem mesmo assim).
        self._ultimo_status_persistido: Optional[bool] = None

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
    def _carregar_modelo(self) -> None:
        """
        Carrega o YOLO desta câmera (import do ultralytics + pesos do disco) — em
        CPU, especialmente em servidores com pouco CPU (ex.: instância free/starter
        do Render), isso é lento: medimos localmente ~6s numa máquina razoável, e
        já vimos relatos de bem mais que isso em produção. Chamada logo no início
        de `_loop_processamento` (não mais só na primeira `_detectar_pessoas`) pra
        acontecer EM PARALELO com a conexão da fonte de vídeo (CameraStream/
        BrowserPushStream), em vez de serializado depois do primeiro frame chegar
        — é essa serialização que fazia o carregamento do modelo comer o orçamento
        de CAMERA_PRIMEIRO_FRAME_TIMEOUT_SEGUNDOS de generate_mjpeg() inteiro,
        fechando o streaming ANTES do primeiro frame processado existir (o
        sintoma: ingest via WebSocket "funcionando", mas o <img> de saída nunca
        carrega — ver routes.camera_ingest vs. generate_mjpeg). Idempotente: seguro
        chamar de novo (ex.: de dentro de `_detectar_pessoas`, como rede de
        segurança) uma vez já carregado.
        """
        if self._modelo is not None:
            return
        inicio = time.monotonic()
        logger.info("[camera %s] carregando modelo YOLO (%s)...", self.camera_id, config.YOLO_MODEL_PATH)
        from ultralytics import YOLO

        self._modelo = YOLO(config.YOLO_MODEL_PATH)
        logger.info("[camera %s] modelo YOLO carregado em %.1fs.", self.camera_id, time.monotonic() - inicio)

    def _detectar_pessoas(self, frame: np.ndarray) -> List[Pessoa]:
        """Retorna lista de (classe=pessoa, track_id, (x1,y1,x2,y2)) usando o modelo desta câmera."""
        self._carregar_modelo()  # normalmente já carregado — ver _loop_processamento

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

    # -------------------- debounce genérico de presença por zona --------------------
    def _atualizar_debounce(
        self, estados: Dict[int, DebouncePresenca], tracks_no_raw: Set[int], agora: float
    ) -> Tuple[Set[int], Set[int], Dict[int, float]]:
        """
        Atualiza o debounce de presença (ver DebouncePresenca) para todo track_id
        visto neste frame OU com estado pendente, e devolve:
          - confirmados_dentro: quem está CONFIRMADO dentro da zona agora (já
            debounced — é isso que o resto da lógica de negócio deve usar, nunca
            `tracks_no_raw` diretamente);
          - entradas: track_ids cuja entrada acabou de ser confirmada neste frame;
          - saidas: track_ids cuja saída acabou de ser confirmada neste frame, com
            a duração (segundos) que passaram confirmados dentro da zona.
        """
        entradas: Set[int] = set()
        saidas: Dict[int, float] = {}

        for tid in set(estados.keys()) | tracks_no_raw:
            raw = tid in tracks_no_raw
            estado = estados.get(tid)
            if estado is None:
                estado = DebouncePresenca(candidato=raw, candidato_desde=agora)
                estados[tid] = estado
            elif estado.candidato != raw:
                estado.candidato = raw
                estado.candidato_desde = agora

            if estado.confirmado != estado.candidato and (agora - estado.candidato_desde) >= config.ZONA_DEBOUNCE_SEGUNDOS:
                estado.confirmado = estado.candidato
                if estado.confirmado:
                    estado.confirmado_desde = agora
                    entradas.add(tid)
                else:
                    saidas[tid] = agora - estado.confirmado_desde if estado.confirmado_desde is not None else 0.0
                    estado.confirmado_desde = None

        # Limpeza: descarta quem está estável fora da zona (nada pendente a confirmar).
        expirados = [
            tid for tid, e in estados.items() if not e.confirmado and not e.candidato and tid not in tracks_no_raw
        ]
        for tid in expirados:
            del estados[tid]

        confirmados_dentro = {tid for tid, e in estados.items() if e.confirmado}
        return confirmados_dentro, entradas, saidas

    def _registrar_evento_zona(
        self,
        tipo_evento: "models.TipoEventoZona",
        track_id: Optional[int] = None,
        duracao_segundos: Optional[float] = None,
    ) -> None:
        db = self.session_factory()
        try:
            registro = models.EventoZona(
                camera_id=self.camera_id,
                empresa_id=self.empresa_id,
                timestamp=datetime.utcnow(),
                tipo_evento=tipo_evento,
                track_id=track_id,
                duracao_segundos=round(duracao_segundos, 2) if duracao_segundos is not None else None,
            )
            db.add(registro)
            db.commit()
        finally:
            db.close()

    # -------------------- Perfil BALCÃO/LOJA: sessões de fila (cliente x atendente) --------------------
    def _atualizar_atendimento_balcao(
        self, centros: Dict[int, Centro], w: int, h: int, agora: float
    ) -> None:
        """
        Algoritmo (spec — Dashboard Analytics Tópico 1: Perda de Vendas & Gargalos):
        1. Monitora 'Zona do Atendente' e 'Zona do Cliente' simultaneamente. A
           presença bruta em cada zona passa primeiro pelo debounce
           (_atualizar_debounce/ZONA_DEBOUNCE_SEGUNDOS) antes de virar evento —
           filtra flicker de detecção/oclusão breve na borda do polígono.
        2. Toda pessoa cuja entrada na 'Zona Cliente' é CONFIRMADA abre uma sessão
           de fila (não depende de um atendente já estar presente — só assim dá
           pra medir tempo de espera e desistência de quem nunca é atendido) e
           dispara CLIENT_ENTERED_ZONE. O mesmo vale para ATTENDANT_ENTERED_ZONE
           na 'Zona Atendente', independente de sessão de cliente.
        3. Assim que um atendente está confirmado presente ENQUANTO a sessão está
           ativa, marca-se `momento_atendente_chegou` (uma vez só, a primeira vez) —
           a diferença para `inicio` é o tempo de espera na fila. Se a presença
           conjunta seguir por >= ATENDIMENTO_MIN_SEGUNDOS, a sessão é confirmada
           como "Atendimento Em Andamento" e dispara SERVICE_STARTED.
        4. Quando a saída do cliente da zona é CONFIRMADA, a sessão é encerrada:
           grava-se em MetricaAtendimento a duração total, o tempo de espera
           (nulo se nunca houve atendente), `concluido` e `desistiu`; dispara
           CLIENT_EXITED_ZONE sempre, mais SERVICE_ENDED (se houve SERVICE_STARTED)
           ou ABANDONMENT_DETECTED (se nunca atendido e permaneceu
           >= DESISTENCIA_MIN_SEGUNDOS). Mesma saída confirmada para o atendente
           dispara ATTENDANT_EXITED_ZONE.
        5. Anti-duplicação extra: ao encerrar, o track_id do cliente entra em
           cooldown por CLIENTE_COOLDOWN_SEGUNDOS — se a entrada reaparecer
           confirmada nesse intervalo (pessoa realmente saiu e voltou rápido, não
           flicker — isso o debounce já filtra sozinho), não abre nova sessão.
        6. Alerta "Pico de Fila Sem Atendente": quando a zona 'Cliente' atinge
           PICO_FILA_MIN_PESSOAS simultâneas (confirmados) com a zona 'Atendente'
           vazia por PICO_FILA_ATENDENTE_AUSENTE_SEGUNDOS contínuos, registra um
           alerta (uma vez por ocorrência contínua).

        Nenhum evento é gravado frame a frame: tudo aqui só dispara em transições
        de estado já confirmadas — ver EventoZona e MetricaAtendimento.
        """
        zonas_atendente = self._zonas_do_tipo("atendente")
        zonas_cliente = self._zonas_do_tipo("cliente")
        if not zonas_atendente or not zonas_cliente:
            return  # perfil balcão sem as duas zonas configuradas: nada a rastrear ainda

        raw_em_atendente = {
            tid for tid, (cx, cy, _, _) in centros.items() if any(z.contem_ponto(cx, cy, w, h) for z in zonas_atendente)
        }
        raw_em_cliente = {
            tid for tid, (cx, cy, _, _) in centros.items() if any(z.contem_ponto(cx, cy, w, h) for z in zonas_cliente)
        }

        tracks_em_atendente, entradas_atendente, saidas_atendente = self._atualizar_debounce(
            self._debounce_atendente, raw_em_atendente, agora
        )
        tracks_em_cliente, entradas_cliente, saidas_cliente = self._atualizar_debounce(
            self._debounce_cliente, raw_em_cliente, agora
        )

        for tid in entradas_atendente:
            self._registrar_evento_zona(models.TipoEventoZona.attendant_entered_zone, track_id=tid)
        for tid, duracao in saidas_atendente.items():
            self._registrar_evento_zona(
                models.TipoEventoZona.attendant_exited_zone, track_id=tid, duracao_segundos=duracao
            )

        # Purga cooldowns expirados
        expirados = [
            tid for tid, saiu_em in self._cooldown_clientes.items()
            if agora - saiu_em > config.CLIENTE_COOLDOWN_SEGUNDOS
        ]
        for tid in expirados:
            del self._cooldown_clientes[tid]

        # Abre sessão de fila para toda entrada confirmada na 'Zona Cliente'.
        for tid in entradas_cliente:
            if tid in self._cooldown_clientes:
                continue
            self._sessoes_fila[tid] = SessaoFilaCliente(inicio=agora)
            self._registrar_evento_zona(models.TipoEventoZona.client_entered_zone, track_id=tid)

        # Atualiza sessões ativas: chegada do atendente + confirmação de atendimento.
        atendente_presente_agora = bool(tracks_em_atendente)
        for tid in tracks_em_cliente:
            sessao = self._sessoes_fila.get(tid)
            if sessao is None:
                continue
            if atendente_presente_agora and sessao.momento_atendente_chegou is None:
                sessao.momento_atendente_chegou = agora
            if (
                sessao.momento_atendente_chegou is not None
                and not sessao.confirmado
                and (agora - sessao.momento_atendente_chegou) >= config.ATENDIMENTO_MIN_SEGUNDOS
            ):
                sessao.confirmado = True  # validado como "Atendimento Em Andamento"
                self._registrar_evento_zona(models.TipoEventoZona.service_started, track_id=tid)

        # Encerra sessões cuja saída da 'Zona Cliente' acabou de ser confirmada.
        for tid in saidas_cliente:
            sessao = self._sessoes_fila.pop(tid, None)
            if sessao is None:
                continue

            duracao_total = agora - sessao.inicio
            atendido = sessao.momento_atendente_chegou is not None
            tempo_espera = (sessao.momento_atendente_chegou - sessao.inicio) if atendido else None
            desistiu = (not atendido) and duracao_total >= config.DESISTENCIA_MIN_SEGUNDOS

            self._salvar_metrica_atendimento(
                duracao_segundos=duracao_total,
                concluido=sessao.confirmado,
                tempo_espera_segundos=tempo_espera,
                desistiu=desistiu,
            )
            self._registrar_evento_zona(
                models.TipoEventoZona.client_exited_zone, track_id=tid, duracao_segundos=duracao_total
            )
            if sessao.confirmado:
                self._registrar_evento_zona(
                    models.TipoEventoZona.service_ended,
                    track_id=tid,
                    duracao_segundos=agora - sessao.momento_atendente_chegou,
                )
            if desistiu:
                self._registrar_evento_zona(
                    models.TipoEventoZona.abandonment_detected, track_id=tid, duracao_segundos=duracao_total
                )

            self._cooldown_clientes[tid] = agora

        self._atualizar_pico_fila_sem_atendente(atendente_presente_agora, len(tracks_em_cliente), agora)

    def _atualizar_pico_fila_sem_atendente(
        self, atendente_presente: bool, pessoas_na_fila: int, agora: float
    ) -> None:
        if atendente_presente:
            self._fila_atendente_ausente_desde = None
            self._fila_pico_registrado = False
            return

        if self._fila_atendente_ausente_desde is None:
            self._fila_atendente_ausente_desde = agora

        ausente_ha = agora - self._fila_atendente_ausente_desde
        if (
            pessoas_na_fila >= config.PICO_FILA_MIN_PESSOAS
            and ausente_ha >= config.PICO_FILA_ATENDENTE_AUSENTE_SEGUNDOS
            and not self._fila_pico_registrado
        ):
            self._salvar_alerta_fila(pessoas_na_fila)
            self._fila_pico_registrado = True  # não repete enquanto a condição persistir

    def _salvar_metrica_atendimento(
        self,
        duracao_segundos: float,
        concluido: bool,
        tempo_espera_segundos: Optional[float] = None,
        desistiu: bool = False,
    ) -> None:
        db = self.session_factory()
        try:
            registro = models.MetricaAtendimento(
                camera_id=self.camera_id,
                empresa_id=self.empresa_id,
                timestamp=datetime.utcnow(),
                duracao_segundos=round(duracao_segundos, 2),
                concluido=concluido,
                tempo_espera_segundos=(
                    round(tempo_espera_segundos, 2) if tempo_espera_segundos is not None else None
                ),
                desistiu=desistiu,
            )
            db.add(registro)
            db.commit()
        finally:
            db.close()

    def _salvar_alerta_fila(self, pessoas_na_fila: int) -> None:
        db = self.session_factory()
        try:
            registro = models.AlertaFila(
                camera_id=self.camera_id,
                empresa_id=self.empresa_id,
                timestamp=datetime.utcnow(),
                pessoas_na_fila=pessoas_na_fila,
            )
            db.add(registro)
            db.commit()
        finally:
            db.close()

    # -------------------- Perfil BALCÃO/LOJA: amostragem de ocupação (Tópico 2) --------------------
    def _atualizar_amostra_balcao(self, centros: Dict[int, Centro], w: int, h: int, agora: float) -> None:
        """
        Amostra periodicamente (mesma cadência de OCUPACAO_AMOSTRA_SEGUNDOS usada
        pela ocupação genérica) quantas pessoas estão nas zonas 'Atendente' (ou
        'Trabalho', se a câmera não tiver zona 'Atendente' dedicada) e 'Cliente'.
        Base do Tópico 2 (ociosidade do balcão, tempo no posto vs. em atendimento e
        distribuição de presença por horário) — calculado no backend a partir dessas
        amostras (ver routes.dashboard_metrics), não há um relógio contínuo por
        atendente.
        """
        zonas_atendente = self._zonas_do_tipo("atendente") or self._zonas_do_tipo("trabalho")
        zonas_cliente = self._zonas_do_tipo("cliente")
        if not zonas_atendente:
            return  # nada configurado para medir presença de atendente

        if agora - self._ultima_amostra_balcao < config.OCUPACAO_AMOSTRA_SEGUNDOS:
            return
        self._ultima_amostra_balcao = agora

        atendentes = sum(
            1 for cx, cy, _, _ in centros.values() if any(z.contem_ponto(cx, cy, w, h) for z in zonas_atendente)
        )
        clientes = sum(
            1 for cx, cy, _, _ in centros.values() if any(z.contem_ponto(cx, cy, w, h) for z in zonas_cliente)
        )
        self._salvar_amostra_balcao(atendentes, clientes)

    def _salvar_amostra_balcao(self, atendentes_presentes: int, clientes_presentes: int) -> None:
        db = self.session_factory()
        try:
            registro = models.AmostraBalcao(
                camera_id=self.camera_id,
                empresa_id=self.empresa_id,
                timestamp=datetime.utcnow(),
                atendentes_presentes=atendentes_presentes,
                clientes_presentes=clientes_presentes,
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
            sessao = self._sessoes_fila.get(track_id) if track_id is not None else None
            if sessao and sessao.confirmado:
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

    # -------------------- fallback seguro (LGPD) para falha de processamento --------------------
    @staticmethod
    def _frame_fallback_seguro(frame: np.ndarray) -> np.ndarray:
        """
        Usado quando `processar_frame` lança uma exceção (ver `_loop_processamento`)
        — em vez de deixar o streaming de saída sem nenhum frame novo (o que, sem
        esse fallback, faz o viewer nunca receber nada e a tela do usuário ficar
        preta indefinidamente), serve uma versão pixelizada do frame INTEIRO.

        Deliberadamente NÃO reaproveita `_anonimizar` (que só borra as caixas que o
        YOLO detectou) — se a própria detecção/desenho de zonas foi o que lançou a
        exceção, não há garantia de que `pessoas`/`boxes` estejam corretos ou
        mesmo definidos nesse ponto. Pixelizar o frame INTEIRO (downscale agressivo
        + upscale sem interpolação) não depende de nenhuma detecção ter funcionado
        — continua 100% conforme LGPD (nenhum pixel reconhecível chega ao viewer)
        mesmo no pior cenário de falha.
        """
        h, w = frame.shape[:2]
        # Downscale bem agressivo (frame vira uma grade de ~20x15 "blocos") — o
        # upscale de volta com INTER_NEAREST (sem suavização) é o que produz o
        # efeito de pixelização, mais barato que um Gaussian blur num frame inteiro.
        pequeno = cv2.resize(frame, (max(1, w // 32), max(1, h // 32)), interpolation=cv2.INTER_LINEAR)
        pixelizado = cv2.resize(pequeno, (w, h), interpolation=cv2.INTER_NEAREST)
        cv2.putText(
            pixelizado, "Processamento indisponivel no momento", (12, h - 16),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA,
        )
        return pixelizado

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
            self._atualizar_amostra_balcao(centros, w, h, agora)
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
    def _verificar_desconexao_prolongada(self, agora: float) -> None:
        """
        Sem NENHUM frame lido da câmera por mais de CAMERA_OFFLINE_RESET_SEGUNDOS:
        descarta as sessões/presenças em memória em vez de deixá-las penduradas.
        Sem isso, um cliente ou atendente que estava confirmado presente quando a
        câmera caiu ficaria com a sessão aberta durante toda a queda — ao
        reconectar, a saída dele seria confirmada com uma duração de horas
        (o tempo da queda), inflando/corrompendo as métricas do Dashboard
        Analytics. Não há como fechar essas sessões corretamente (não sabemos
        quando a pessoa realmente saiu durante a queda), então são descartadas
        sem persistir nenhuma métrica/evento para elas — só reseta uma vez por
        queda (`_estado_resetado_por_desconexao` evita repetir a cada 0.1s de retry).
        """
        if self._estado_resetado_por_desconexao:
            return
        if agora - self._ultima_leitura_ok_em < config.CAMERA_OFFLINE_RESET_SEGUNDOS:
            return

        self._sessoes_fila.clear()
        self._cooldown_clientes.clear()
        self._debounce_atendente.clear()
        self._debounce_cliente.clear()
        self._fila_atendente_ausente_desde = None
        self._fila_pico_registrado = False
        self._estado_resetado_por_desconexao = True
        print(
            f"[vision] câmera {self.camera_id}: sem frames há mais de "
            f"{config.CAMERA_OFFLINE_RESET_SEGUNDOS:.0f}s — sessões/presenças em memória "
            "descartadas (evita durações infladas pela queda de conexão ao reconectar)"
        )

    def _atualizar_status_camera(self, conectado: bool) -> None:
        """
        Mantém `models.Camera.status` refletindo se `CameraStream` está de fato
        entregando frames — só grava no banco em TRANSIÇÕES (mesmo padrão dos
        outros `_persistir_*`/`_salvar_*` deste módulo), não a cada frame. Antes
        disso, a rota `/api/video_feed` marcava a câmera como "online" só por ter
        sido requisitada, mesmo que a captura nunca tivesse conseguido abrir — daí
        o dashboard mostrar "online"/tela preta ao mesmo tempo em produção quando a
        fonte configurada (ex.: webcam local) não existe no servidor.
        """
        if self._ultimo_status_persistido is conectado:
            return
        self._ultimo_status_persistido = conectado
        novo_status = models.StatusCamera.online if conectado else models.StatusCamera.offline

        db = self.session_factory()
        try:
            camera = db.get(models.Camera, self.camera_id)
            if camera is not None:
                camera.status = novo_status
                db.commit()
        finally:
            db.close()
        logger.info("[camera %s] status -> %s", self.camera_id, novo_status.value)

    def _loop_processamento(self) -> None:
        """
        Roda em background, uma vez por câmera, independente de quantos viewers HTTP
        existem. É aqui — e não em `generate_mjpeg` — que a inferência de IA acontece,
        então requisições concorrentes da API nunca disputam o modelo desta câmera.
        """
        self._carregar_modelo()  # eager, em paralelo com a conexão da fonte — ver docstring do método
        intervalo = 1.0 / max(1, config.STREAM_TARGET_FPS)
        while self._rodando:
            inicio = time.monotonic()
            self._atualizar_status_camera(self.stream.connected)

            frame = self.stream.read()
            if frame is None:
                self._verificar_desconexao_prolongada(inicio)
                time.sleep(0.1)
                continue

            self._ultima_leitura_ok_em = inicio
            self._estado_resetado_por_desconexao = False

            try:
                processado = self.processar_frame(frame)
            except Exception:
                # Uma falha pontual (ex.: frame corrompido) não pode derrubar a
                # thread de processamento da câmera — loga com stack trace completo
                # (antes era silencioso — uma falha recorrente aqui produzia
                # exatamente o mesmo sintoma de "tela preta sem explicação" que a
                # desconexão da câmera, sem nenhum log pra diferenciar as duas) e
                # tenta servir um frame de fallback SEGURO (pixelizado por inteiro,
                # não depende de nenhuma detecção ter funcionado — ver docstring de
                # `_frame_fallback_seguro`) em vez de deixar o buffer de saída sem
                # nenhum frame novo. Só se ATÉ o fallback falhar (bem improvável,
                # já que ele só faz resize) é que o frame é mesmo descartado.
                logger.exception(
                    "[camera %s] falha ao processar frame — servindo fallback pixelizado (LGPD-safe) neste frame.",
                    self.camera_id,
                )
                try:
                    processado = self._frame_fallback_seguro(frame)
                except Exception:
                    logger.exception("[camera %s] fallback de frame pixelizado TAMBÉM falhou — pulando este frame.", self.camera_id)
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

        Antes do PRIMEIRO frame, desiste depois de
        CAMERA_PRIMEIRO_FRAME_TIMEOUT_SEGUNDOS: sem isso, uma câmera cuja fonte
        nunca conecta (webcam local inexistente no servidor, RTSP incorreto/
        inalcançável) mantinha a resposta HTTP pendurada para sempre — 200 OK,
        corpo vazio — e a <img> no navegador nunca disparava onError, então a
        tela ficava preta sem nenhuma explicação. Encerrando o generator aqui, a
        resposta fecha e o navegador dispara onError (ver CameraCard.jsx), que já
        sabe mostrar "Falha ao conectar à câmera" + botão de retry. Depois do
        primeiro frame, o timeout deixa de valer — reconexões subsequentes usam a
        resiliência normal do CameraStream.
        """
        intervalo = 1.0 / max(1, config.STREAM_TARGET_FPS)
        inicio_espera = time.monotonic()
        teve_frame = False
        while True:
            with self._frame_lock:
                jpeg = self._ultimo_jpeg
            if jpeg is None:
                if not teve_frame and (time.monotonic() - inicio_espera) > config.CAMERA_PRIMEIRO_FRAME_TIMEOUT_SEGUNDOS:
                    logger.warning(
                        "[camera %s] nenhum frame em %.0fs — encerrando o streaming deste viewer.",
                        self.camera_id, config.CAMERA_PRIMEIRO_FRAME_TIMEOUT_SEGUNDOS,
                    )
                    return
                time.sleep(0.1)
                continue

            if not teve_frame:
                logger.info(
                    "[camera %s] primeiro frame entregue a um viewer após %.1fs de espera.",
                    self.camera_id, time.monotonic() - inicio_espera,
                )
            teve_frame = True
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
