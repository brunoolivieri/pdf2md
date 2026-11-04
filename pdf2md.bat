@echo off
rem Executa o pdf2md no Windows.
rem
rem   pdf2md.bat                                -> converte samples\ para output\ (duplo clique)
rem   pdf2md.bat convert C:\docs\arquivo.pdf    -> repassa os argumentos para o pdf2md
rem   pdf2md.bat convert samples -s pymupdf --force
rem   pdf2md.bat --help
rem
rem O ambiente do Windows fica em .venv-win (o .venv e do Linux/WSL: um venv nao serve aos dois
rem sistemas). Na primeira execucao ele e criado com o uv ou, sem uv, com python -m venv + pip.

setlocal
cd /d "%~dp0"

rem acentos e barras de progresso corretos no console
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set "VENV=.venv-win"
set "ARGS=%*"
set "PAUSE_AT_END="
set "ERR="
if "%~1"=="" (
    set "ARGS=convert samples -o output"
    set "PAUSE_AT_END=1"
)

if not exist "%VENV%\Scripts\pdf2md.exe" call :setup
if not exist "%VENV%\Scripts\pdf2md.exe" (
    set "ERR=1"
    goto :done
)

"%VENV%\Scripts\pdf2md.exe" %ARGS%
set "ERR=%ERRORLEVEL%"
goto :done


:setup
echo Preparando o ambiente em %VENV% (so na primeira vez; baixa ~1 GB com o docling)...
call :find_python
if not defined PYEXE (
    echo Erro: Python 3.11 ou mais novo nao encontrado.
    echo Instale de https://www.python.org/downloads/ e rode de novo.
    exit /b 1
)
echo Usando %PYEXE%
set "UV="
where uv >nul 2>nul && set "UV=uv"
if not defined UV if exist "%APPDATA%\Python\Python312\Scripts\uv.exe" set "UV=%APPDATA%\Python\Python312\Scripts\uv.exe"
if defined UV (
    set "UV_PROJECT_ENVIRONMENT=%VENV%"
    set "UV_PYTHON_PREFERENCE=only-system"
    "%UV%" sync --python "%PYEXE%" --extra dev --extra docling
    exit /b
)
"%PYEXE%" -m venv "%VENV%" || exit /b 1
rem torch so CPU: pelo PyPI viria a versao com CUDA (~3 GB)
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
"%VENV%\Scripts\python.exe" -m pip install -e ".[dev,docling]"
exit /b


:find_python
rem Procura um Python 3.11+: primeiro pelo lancador "py" (acha python.org e Anaconda), depois no PATH.
set "PYEXE="
for %%V in (3.13 3.12 3.11 3.14) do (
    if not defined PYEXE (
        rem so aceita a linha marcada: sem a versao, o "py" imprime a lista de instalados
        for /f "tokens=1,* delims==" %%A in ('py -%%V -c "import sys; print('PYEXE=' + sys.executable)" 2^>nul') do (
            if "%%A"=="PYEXE" set "PYEXE=%%B"
        )
    )
)
if defined PYEXE exit /b
for /f "tokens=1,* delims==" %%A in ('python -c "import sys; assert sys.version_info >= (3, 11); print('PYEXE=' + sys.executable)" 2^>nul') do (
    if "%%A"=="PYEXE" set "PYEXE=%%B"
)
exit /b


:done
if defined PAUSE_AT_END pause
exit /b %ERR%
