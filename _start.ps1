# Inicializa e executa o Classificador Contábil (Windows / PowerShell).
#   .\_start.ps1            -> sobe a aplicação
#   .\_start.ps1 -Test      -> roda a suíte de testes
#   .\_start.ps1 -Lint      -> roda o ruff
#   .\_start.ps1 -Port 8600 -> usa outra porta

param(
    [switch]$Test,
    [switch]$Lint,
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# --- Ambiente virtual ------------------------------------------------------
if (-not (Test-Path $venvPython)) {
    # Localiza o Python: py launcher primeiro, depois python.
    $pyCmd = $null
    foreach ($candidate in @(@("py", "-3"), @("python"))) {
        try {
            $exe = $candidate[0]; $pre = @($candidate | Select-Object -Skip 1)
            & $exe @pre --version *> $null
            if ($LASTEXITCODE -eq 0) { $pyCmd = $candidate; break }
        } catch { }
    }
    if (-not $pyCmd) {
        Write-Host "[ERRO] Python nao encontrado. Instale o Python 3.13 em" -ForegroundColor Red
        Write-Host "       https://www.python.org/downloads/windows/ marcando 'Add python.exe to PATH'." -ForegroundColor Red
        exit 1
    }
    $exe = $pyCmd[0]; $pre = @($pyCmd | Select-Object -Skip 1)
    & $exe @pre -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] E preciso Python 3.11 ou superior." -ForegroundColor Red
        exit 1
    }
    Write-Host "[setup] Criando ambiente virtual..." -ForegroundColor Cyan
    & $exe @pre -m venv .venv
    & $venvPython -m pip install --upgrade pip --quiet
    Write-Host "[setup] Instalando dependencias..." -ForegroundColor Cyan
    & $venvPython -m pip install -r requirements.txt
} else {
    Write-Host "[setup] Ambiente virtual encontrado." -ForegroundColor DarkGray
}

# --- Configuração ----------------------------------------------------------
if (-not (Test-Path ".env")) {
    Write-Host "[setup] .env ausente. Copiando de .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[setup] Abra o arquivo .env e cole sua chave em GEMINI_API_KEY=" -ForegroundColor Yellow
}

# Obrigatório: as paginas usam imports absolutos (core.*, db.*, app.*).
$env:PYTHONPATH = $PSScriptRoot

foreach ($dir in @("logs", "data", "data\exports")) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
}

# --- Modos alternativos ----------------------------------------------------
if ($Lint) {
    Write-Host "[lint] Executando ruff..." -ForegroundColor Cyan
    & $venvPython -m ruff check .
    exit $LASTEXITCODE
}

if ($Test) {
    Write-Host "[test] Executando pytest..." -ForegroundColor Cyan
    & $venvPython -m pytest -v
    exit $LASTEXITCODE
}

# --- Aplicação -------------------------------------------------------------
Write-Host ""
Write-Host "  Classificador Contabil" -ForegroundColor Green
Write-Host "  http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "  Ctrl+C para encerrar." -ForegroundColor DarkGray
Write-Host ""

& $venvPython -m streamlit run app/main.py --server.port $Port --server.address 127.0.0.1
