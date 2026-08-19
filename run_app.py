#!/usr/bin/env python3
"""
Script único de inicialização do sistema completo em modo de desenvolvimento local.

O que ele faz, em ordem:
  1. Garante o venv do backend (cria se faltar) e instala/atualiza requirements.txt.
  2. Garante node_modules do frontend (roda `npm install` se faltar).
  3. Popula o banco com os dados de teste (seed.py) — idempotente, seguro rodar sempre.
  4. Sobe o backend (Uvicorn/FastAPI) na porta 8000 e espera ele responder.
  5. Sobe o frontend (Vite/React) na porta 3000 e espera ele responder.
  6. Abre o navegador em http://localhost:3000.
  7. Imprime o passo a passo de teste com webcam e fica acompanhando os logs dos
     dois processos (prefixados [backend]/[frontend]) até você apertar Ctrl+C.

Uso:
    python run_app.py
    python run_app.py --no-install      # pula pip install / npm install (mais rápido)
    python run_app.py --no-seed         # não roda o seeder de dados de teste
    python run_app.py --no-browser      # não abre o navegador automaticamente
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# No Windows, stdout/stderr por padrão usam a codepage legada do console (ex.: cp1252),
# que não tem os caracteres Unicode usados no output colorido do Vite/uvicorn (ex.: "➜")
# nem alguns acentos — sem isso, um único print() derruba a thread que repassa os logs.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent
BACKEND_DIR = RAIZ / "backend"
FRONTEND_DIR = RAIZ / "frontend"

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000

_WINDOWS = os.name == "nt"


# ==============================================================================
# Utilidades
# ==============================================================================
def log(prefixo: str, mensagem: str) -> None:
    print(f"[{prefixo}] {mensagem}", flush=True)


def venv_python(backend_dir: Path) -> Path:
    return backend_dir / "venv" / ("Scripts/python.exe" if _WINDOWS else "bin/python")


def rodar(cmd: list[str], cwd: Path, prefixo: str) -> None:
    """Roda um comando e espera terminar, mostrando a saída em tempo real."""
    log(prefixo, "$ " + " ".join(str(c) for c in cmd))
    resultado = subprocess.run(cmd, cwd=cwd)
    if resultado.returncode != 0:
        log(prefixo, f"comando falhou com código {resultado.returncode}")
        sys.exit(resultado.returncode)


# ==============================================================================
# Passo 1: dependências do backend (Python)
# ==============================================================================
def garantir_backend(pular_install: bool) -> Path:
    venv_dir = BACKEND_DIR / "venv"
    python_exe = venv_python(BACKEND_DIR)

    if not python_exe.exists():
        log("setup", "venv do backend não encontrado — criando (isso só acontece uma vez)...")
        rodar([sys.executable, "-m", "venv", str(venv_dir)], cwd=BACKEND_DIR, prefixo="setup")

    if pular_install:
        log("setup", "pulando verificação de dependências Python (--no-install)")
        return python_exe

    log("setup", "verificando/instalando dependências Python (requirements.txt)...")
    rodar([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "--quiet"], cwd=BACKEND_DIR, prefixo="setup")

    # PyTorch é uma dependência pesada (a build com CUDA tem alguns GB) — em máquina
    # sem GPU dedicada, instalar a variante CPU-only primeiro evita esse download.
    torch_ja_instalado = subprocess.run(
        [str(python_exe), "-c", "import torch"], cwd=BACKEND_DIR, capture_output=True
    ).returncode == 0
    if not torch_ja_instalado:
        log("setup", "instalando PyTorch (build CPU-only, mais leve)...")
        rodar(
            [str(python_exe), "-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/cpu", "--quiet"],
            cwd=BACKEND_DIR,
            prefixo="setup",
        )

    rodar(
        [str(python_exe), "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
        cwd=BACKEND_DIR,
        prefixo="setup",
    )
    log("setup", "dependências Python OK")
    return python_exe


# ==============================================================================
# Passo 2: dependências do frontend (Node)
# ==============================================================================
def garantir_frontend(pular_install: bool) -> Path:
    npm = shutil.which("npm")
    if not npm:
        log("setup", "ERRO: npm não encontrado no PATH. Instale o Node.js: https://nodejs.org/")
        sys.exit(1)

    node_modules = FRONTEND_DIR / "node_modules"
    if pular_install:
        log("setup", "pulando verificação de dependências Node (--no-install)")
    elif not node_modules.exists():
        log("setup", "node_modules não encontrado — rodando npm install (pode demorar um pouco)...")
        rodar([npm, "install"], cwd=FRONTEND_DIR, prefixo="setup")
        log("setup", "dependências Node OK")
    else:
        log("setup", "node_modules já existe — pulando npm install (use --no-install de qualquer forma se quiser forçar)")

    return Path(npm)


# ==============================================================================
# Passo 3: dados de teste (seed.py)
# ==============================================================================
def rodar_seed(python_exe: Path) -> None:
    log("seed", "populando banco com dados de teste (idempotente)...")
    resultado = subprocess.run([str(python_exe), "seed.py"], cwd=BACKEND_DIR)
    if resultado.returncode != 0:
        log("seed", f"seed.py falhou com código {resultado.returncode} — continuando mesmo assim")


# ==============================================================================
# Passos 4-5: subir os processos e esperar cada um responder
# ==============================================================================
def _encaminhar_saida(processo: subprocess.Popen, prefixo: str) -> None:
    for linha in processo.stdout:
        try:
            print(f"[{prefixo}] {linha.rstrip()}", flush=True)
        except UnicodeEncodeError:
            # Defesa extra além do reconfigure() de stdout no topo do arquivo —
            # nunca deixa uma linha problemática derrubar o encaminhamento de log.
            print(f"[{prefixo}] {linha.rstrip().encode('ascii', 'replace').decode('ascii')}", flush=True)


def iniciar_processo(cmd: list[str], cwd: Path, prefixo: str) -> subprocess.Popen:
    """
    Sobe `npm run dev`/uvicorn como um processo "raiz" de uma árvore inteira de
    processos-filho (no Windows, npm.CMD → cmd.exe → node → cmd.exe → vite.js).
    Por isso o processo é criado em seu próprio grupo/sessão — necessário para
    conseguir encerrar a árvore inteira depois (ver `encerrar_arvore`), já que
    `Popen.terminate()` sozinho mataria só esse primeiro elo e deixaria os
    processos-neto (o Vite de verdade, por exemplo) órfãos segurando a porta.
    """
    log(prefixo, "$ " + " ".join(str(c) for c in cmd))
    kwargs = {}
    if _WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    processo = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **kwargs,
    )
    threading.Thread(target=_encaminhar_saida, args=(processo, prefixo), daemon=True).start()
    return processo


def encerrar_arvore(processo: subprocess.Popen, prefixo: str) -> None:
    """Mata o processo E toda a árvore de filhos que ele possa ter gerado."""
    if processo.poll() is not None:
        return
    try:
        if _WINDOWS:
            # taskkill /T mata a árvore inteira — Popen.terminate() sozinho não
            # alcançaria os processos-neto (ver docstring de iniciar_processo).
            subprocess.run(
                ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
            )
        else:
            os.killpg(processo.pid, signal.SIGTERM)
    except Exception as exc:  # nunca deixa a limpeza de um processo travar a dos outros
        log(prefixo, f"aviso: falha ao encerrar árvore de processos ({exc})")

    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if not _WINDOWS:
            try:
                os.killpg(processo.pid, signal.SIGKILL)
            except Exception:
                pass
        processo.kill()


def aguardar_http(url: str, prefixo: str, timeout_segundos: int = 60) -> bool:
    log(prefixo, f"aguardando {url} responder...")
    limite = time.monotonic() + timeout_segundos
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    log(prefixo, "no ar!")
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(0.5)
    log(prefixo, f"não respondeu em {timeout_segundos}s — siga acompanhando os logs acima")
    return False


# ==============================================================================
# Passo 7: guia de teste impresso no terminal
# ==============================================================================
def imprimir_guia_teste() -> None:
    print(
        r"""
================================================================
  TESTE PRÁTICO COM A WEBCAM — PASSO A PASSO
================================================================
  1. Faça login como Admin:
       http://localhost:3000/login
       email: admin@sistema.com   senha: admin123

  2. No painel Master Admin, escolha a aba/cliente "Padaria Silva"
     na lista à esquerda.

  3. Vá em "Câmeras & Zonas" e clique em "Zonas" na câmera
     "Balcão Principal (Webcam)". Desenhe (clicando na imagem):
       - Zona ATENDENTE no lado ESQUERDO da tela
       - Zona CLIENTE no lado DIREITO da tela
     Clique em "Finalizar zona" após cada uma (mínimo 3 pontos) e
     depois em "Salvar Zonas".

  4. Fique parado no lado ESQUERDO da webcam (simulando o
     atendente) e peça para outra pessoa (ou você mesmo, alternando)
     ficar no lado DIREITO por mais de 15 segundos (simulando o
     cliente sendo atendido) — depois saia da zona da direita.

  5. Vá na aba "Dashboard" desse mesmo cliente (ou faça login como
     gerente@padaria.com / cliente123 para ver a visão do lojista)
     e veja o contador de "Clientes Atendidos Hoje" incrementar.

  6. Na aba "Relatórios", clique em "Baixar Relatório PDF" para
     testar a exportação com o atendimento que você acabou de gerar.
================================================================
""",
        flush=True,
    )


# ==============================================================================
# Orquestração
# ==============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-install", action="store_true", help="pula pip install / npm install")
    parser.add_argument("--no-seed", action="store_true", help="não roda o seeder de dados de teste")
    parser.add_argument("--no-browser", action="store_true", help="não abre o navegador automaticamente")
    args = parser.parse_args()

    if not BACKEND_DIR.is_dir() or not FRONTEND_DIR.is_dir():
        print("ERRO: rode este script a partir da raiz do projeto (onde ficam backend/ e frontend/).")
        sys.exit(1)

    python_exe = garantir_backend(args.no_install)
    npm_exe = garantir_frontend(args.no_install)

    if not args.no_seed:
        rodar_seed(python_exe)
    else:
        log("seed", "pulando seed de dados de teste (--no-seed)")

    processos: list[subprocess.Popen] = []
    try:
        backend_cmd = [str(python_exe), "-m", "uvicorn", "main:app", "--host", BACKEND_HOST, "--port", str(BACKEND_PORT)]
        processo_backend = iniciar_processo(backend_cmd, cwd=BACKEND_DIR, prefixo="backend")
        processos.append(processo_backend)
        aguardar_http(f"http://{BACKEND_HOST}:{BACKEND_PORT}/", prefixo="backend")

        frontend_cmd = [str(npm_exe), "run", "dev"]
        processo_frontend = iniciar_processo(frontend_cmd, cwd=FRONTEND_DIR, prefixo="frontend")
        processos.append(processo_frontend)
        aguardar_http(f"http://localhost:{FRONTEND_PORT}/", prefixo="frontend")

        url_app = f"http://localhost:{FRONTEND_PORT}"
        if not args.no_browser:
            log("setup", f"abrindo o navegador em {url_app} ...")
            webbrowser.open(url_app)

        imprimir_guia_teste()
        log("setup", "sistema no ar. Pressione Ctrl+C para encerrar backend e frontend.")

        # Mantém o script vivo enquanto os processos filhos rodam; encerra se
        # algum deles morrer sozinho (ex.: erro fatal de configuração).
        while all(p.poll() is None for p in processos):
            time.sleep(1)

        for p in processos:
            if p.poll() is not None:
                log("setup", f"um dos processos encerrou sozinho (código {p.returncode}) — parando tudo")

    except KeyboardInterrupt:
        log("setup", "Ctrl+C recebido — encerrando backend e frontend...")
    finally:
        for p, prefixo in zip(processos, ("backend", "frontend")):
            encerrar_arvore(p, prefixo)
        log("setup", "encerrado.")


if __name__ == "__main__":
    main()
