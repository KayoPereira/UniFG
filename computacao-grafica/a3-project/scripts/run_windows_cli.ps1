param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CliArgs
)

$ErrorActionPreference = 'Stop'

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).ProviderPath
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @('py', '-3')
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @('python')
    }

    throw 'Python para Windows nao encontrado. Instale com: winget install -e --id Python.Python.3.11 --scope user'
}

function Ensure-WindowsVenv {
    param(
        [string] $ProjectRoot,
        [string[]] $PythonCommand
    )

    $venvPath = Join-Path $env:LOCALAPPDATA 'a3-project-win-venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'

    if (-not (Test-Path $venvPython)) {
        Write-Host 'Criando ambiente virtual do Windows em' $venvPath
        $pythonExecutable = $PythonCommand[0]
        $pythonArgs = @()
        if ($PythonCommand.Length -gt 1) {
            $pythonArgs += $PythonCommand[1..($PythonCommand.Length - 1)]
        }
        $pythonArgs += @('-m', 'venv', $venvPath)
        & $pythonExecutable @pythonArgs | Out-Host
    }

    Write-Host 'Instalando dependencias do ambiente Windows...'
    & $venvPython -m pip install --upgrade pip | Out-Host
    & $venvPython -m pip install -r (Join-Path $ProjectRoot 'requirements.txt') | Out-Host

    return $venvPython
}

$projectRoot = Get-ProjectRoot
$pythonCommand = Get-PythonCommand
$venvPython = Ensure-WindowsVenv -ProjectRoot $projectRoot -PythonCommand $pythonCommand

$sharedDataDir = Join-Path $env:LOCALAPPDATA 'a3-project-data'
$sharedFacesDir = Join-Path $sharedDataDir 'faces'
New-Item -ItemType Directory -Force -Path $sharedFacesDir | Out-Null

$env:PYTHONPATH = $projectRoot
$env:DATA_DIR = $sharedDataDir
$env:FACES_DIR = $sharedFacesDir
$env:DATABASE_PATH = Join-Path $sharedDataDir 'attendance.db'
Set-Location $projectRoot

if (-not $CliArgs -or $CliArgs.Length -eq 0) {
    throw 'Informe os argumentos do app.cli. Exemplo: enroll --code FUNC001 --name "Kayo Pereira"'
}

& $venvPython -m app.cli @CliArgs

