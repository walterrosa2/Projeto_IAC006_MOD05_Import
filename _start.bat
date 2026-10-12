@echo off
REM Inicializa e executa o Classificador Contabil (Windows / cmd).
REM   _start.bat         -> prepara o ambiente (se preciso) e sobe a aplicacao
REM   _start.bat setup   -> so prepara o ambiente (venv + dependencias + .env)
REM   _start.bat test    -> roda a suite de testes
REM   _start.bat lint    -> roda o ruff

setlocal
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "PORT=8501"

if exist "%VENV_PY%" (
    echo [setup] Ambiente virtual encontrado.
    goto :config
)

REM --- Localiza o Python (py launcher primeiro, depois python) -------------
set "PY_CMD="
py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1 && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo.
    echo [ERRO] Python nao encontrado neste computador.
    echo        Instale o Python 3.13 em https://www.python.org/downloads/windows/
    echo        marcando a opcao "Add python.exe to PATH" e rode este script de novo.
    exit /b 1
)

%PY_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo.
    echo [ERRO] Versao do Python muito antiga. E preciso Python 3.11 ou superior.
    %PY_CMD% --version
    exit /b 1
)

echo [setup] Criando ambiente virtual com:
%PY_CMD% --version
%PY_CMD% -m venv .venv
if errorlevel 1 goto :erro
"%VENV_PY%" -m pip install --upgrade pip --quiet
echo [setup] Instalando dependencias (pode levar alguns minutos)...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :erro

:config
if not exist ".env" (
    echo [setup] .env ausente. Copiando de .env.example...
    copy /y ".env.example" ".env" >nul
    echo [setup] Abra o arquivo .env e cole sua chave em GEMINI_API_KEY=
)

REM Obrigatorio: as paginas usam imports absolutos (core.*, db.*, app.*).
set "PYTHONPATH=%~dp0"

if not exist "logs" mkdir "logs"
if not exist "data" mkdir "data"
if not exist "data\exports" mkdir "data\exports"

if /i "%~1"=="setup" (
    echo [setup] Ambiente pronto. Para iniciar a aplicacao rode: _start.bat
    goto :fim
)

if /i "%~1"=="lint" (
    echo [lint] Executando ruff...
    "%VENV_PY%" -m ruff check .
    goto :fim
)

if /i "%~1"=="test" (
    echo [test] Executando pytest...
    "%VENV_PY%" -m pytest -v
    goto :fim
)

echo.
echo   Classificador Contabil
echo   http://127.0.0.1:%PORT%
echo   Ctrl+C para encerrar.
echo.

"%VENV_PY%" -m streamlit run app/main.py --server.port %PORT% --server.address 127.0.0.1
goto :fim

:erro
echo [ERRO] Falha na preparacao do ambiente. Apague a pasta .venv e rode de novo.
exit /b 1

:fim
endlocal
