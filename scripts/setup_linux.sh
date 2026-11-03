#!/usr/bin/env bash
# Cria .venv e instala o pdf2md no Linux (Debian/Ubuntu ou similar).
#
# Uso:  ./scripts/setup_linux.sh            # pymupdf + docling (torch só CPU)
#       WITH_DOCLING=0 ./scripts/setup_linux.sh  # só pymupdf (leve, sem torch)
#       TORCH_INDEX=https://download.pytorch.org/whl/cu124 ./scripts/setup_linux.sh  # GPU NVIDIA
#       PYTHON=python3.12 ./scripts/setup_linux.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
WITH_DOCLING="${WITH_DOCLING:-1}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cpu}"

if ! "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    echo "Erro: é preciso Python >= 3.11 (encontrado: $("$PYTHON" --version 2>&1))." >&2
    exit 1
fi
if ! "$PYTHON" -c 'import venv' 2>/dev/null; then
    echo "Erro: módulo venv ausente. No Ubuntu/Debian: sudo apt install python3-venv" >&2
    exit 1
fi

if "$PYTHON" -c 'import ensurepip' 2>/dev/null; then
    "$PYTHON" -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    # Ubuntu/Debian sem o pacote python3-venv: cria o venv sem pip e instala o pip pelo
    # bootstrap oficial da PyPA. Alternativa com sudo: apt install python3-venv
    echo "Aviso: ensurepip ausente; instalando pip via https://bootstrap.pypa.io/get-pip.py"
    "$PYTHON" -m venv --without-pip .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    if command -v curl >/dev/null; then
        curl -fsSL https://bootstrap.pypa.io/get-pip.py | python -
    else
        wget -qO- https://bootstrap.pypa.io/get-pip.py | python -
    fi
fi
python -m pip install --upgrade pip

if [ "$WITH_DOCLING" = "1" ]; then
    # torch antes do docling: pelo PyPI o pip baixaria a versão CUDA (~3 GB) mesmo sem GPU
    python -m pip install torch torchvision --index-url "$TORCH_INDEX"
    python -m pip install -e ".[dev,docling]"
else
    python -m pip install -e ".[dev]"
fi

echo
echo "Pronto. Ative o ambiente com:  source .venv/bin/activate"
echo "Teste com:                     pdf2md --help"
