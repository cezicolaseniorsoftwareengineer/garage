# ============================================================================
# run_full_suite.ps1 — 404 Garage: Suite de Testes Completa
# Bio Code Technology Ltda · CeziCola Agent
#
# Executa TODOS os testes do jogo:
#   1. Testes unitários e de integração Python (pytest)
#   2. Validador de desafios de código Java (Node.js)
#   3. Relatório final consolidado
# ============================================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$Garage = $PSScriptRoot
Set-Location $Garage

$SEPARATOR = "=" * 70
$FAIL_COUNT = 0
$PASS_COUNT = 0

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host $SEPARATOR -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host $SEPARATOR -ForegroundColor Cyan
}

function Write-Pass { param([string]$Msg) Write-Host "[PASS] $Msg" -ForegroundColor Green; $script:PASS_COUNT++ }
function Write-Fail { param([string]$Msg) Write-Host "[FAIL] $Msg" -ForegroundColor Red;  $script:FAIL_COUNT++ }

# ============================================================================
# 1. Verificações de pré-requisitos
# ============================================================================
Write-Section "PRE-REQUISITOS"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Fail "Python nao encontrado no PATH"
    exit 1
}
Write-Pass "Python: $(python --version 2>&1)"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[SKIP] Node.js nao encontrado — testes JS serao ignorados" -ForegroundColor Yellow
    $NODE_AVAILABLE = $false
} else {
    Write-Pass "Node.js: $(node --version 2>&1)"
    $NODE_AVAILABLE = $true
}

$JAVAC_AVAILABLE = $false
if (Get-Command javac -ErrorAction SilentlyContinue) {
    # javac exits 1 with no args but it IS available
    $javacVersion = & java -version 2>&1 | Select-Object -First 1
    Write-Pass "Java: $javacVersion"
    $JAVAC_AVAILABLE = $true
} else {
    Write-Host "[SKIP] javac nao encontrado — TestJavacCompilation sera ignorado" -ForegroundColor Yellow
}

# ============================================================================
# 2. Suite principal Python (pytest)
# ============================================================================
Write-Section "PYTEST — SUITE PRINCIPAL"

$PY_ARGS = @(
    "-v",
    "--tb=short",
    "-p", "no:warnings",
    "--color=yes",
    "tests/"
)

# Pass environment flags so Java/Node tests can skip gracefully
$env:JAVAC_AVAILABLE = if ($JAVAC_AVAILABLE) { "1" } else { "0" }
$env:NODE_AVAILABLE  = if ($NODE_AVAILABLE)  { "1" } else { "0" }

python -m pytest @PY_ARGS
$PYTEST_EXIT = $LASTEXITCODE

if ($PYTEST_EXIT -eq 0) {
    Write-Pass "pytest concluiu sem falhas"
} else {
    Write-Fail "pytest reportou falhas (exit code $PYTEST_EXIT)"
}

# ============================================================================
# 3. Validador de desafios JavaScript (Node.js)
# ============================================================================
Write-Section "NODE.JS — VALIDADOR DE DESAFIOS JAVA"

if ($NODE_AVAILABLE -and (Test-Path "$Garage\test_all_challenges.js")) {
    node "$Garage\test_all_challenges.js"
    $NODE_EXIT = $LASTEXITCODE
    if ($NODE_EXIT -eq 0) {
        Write-Pass "test_all_challenges.js concluiu sem falhas"
    } else {
        Write-Fail "test_all_challenges.js reportou falhas (exit code $NODE_EXIT)"
    }
} else {
    Write-Host "[SKIP] test_all_challenges.js ignorado" -ForegroundColor Yellow
}

# ============================================================================
# 4. Validação final de arquivos de dados
# ============================================================================
Write-Section "VALIDACAO DE DADOS"

$ChallengesFile = "$Garage\app\data\challenges.json"
if (Test-Path $ChallengesFile) {
    $json = Get-Content $ChallengesFile -Raw | ConvertFrom-Json
    $total = $json.Count
    if ($total -eq 75) {
        Write-Pass "challenges.json: $total desafios (esperado 75)"
    } else {
        Write-Fail "challenges.json: $total desafios (esperado 75!)"
    }
} else {
    Write-Fail "challenges.json nao encontrado em $ChallengesFile"
}

$StaticDir = "$Garage\app\static"
foreach ($f in @("index.html", "style.css", "game.js")) {
    $fp = "$StaticDir\$f"
    if (Test-Path $fp) {
        $size = (Get-Item $fp).Length
        if ($size -gt 1000) {
            Write-Pass "static/$f ($size bytes)"
        } else {
            Write-Fail "static/$f muito pequeno ($size bytes)"
        }
    } else {
        Write-Fail "static/$f nao encontrado"
    }
}

# ============================================================================
# 5. Relatório final
# ============================================================================
Write-Host ""
Write-Host $SEPARATOR -ForegroundColor White
Write-Host "  RELATORIO FINAL" -ForegroundColor White
Write-Host $SEPARATOR -ForegroundColor White
Write-Host ("  PASSOU : {0,4}" -f $PASS_COUNT) -ForegroundColor Green
Write-Host ("  FALHOU : {0,4}" -f $FAIL_COUNT) -ForegroundColor $(if ($FAIL_COUNT -gt 0) { "Red" } else { "Green" })
Write-Host $SEPARATOR -ForegroundColor White

if ($FAIL_COUNT -gt 0) {
    Write-Host ""
    Write-Host "  *** SUITE COM FALHAS — corrija antes do deploy! ***" -ForegroundColor Red
    exit 1
} else {
    Write-Host ""
    Write-Host "  SUITE 100% OK — seguro para deploy!" -ForegroundColor Green
    exit 0
}
