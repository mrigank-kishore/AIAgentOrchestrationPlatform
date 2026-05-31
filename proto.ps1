param(
    [ValidateSet("start", "stop", "status", "build")]
    [string]$Action = "start"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendVenvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$pidsPath = Join-Path $root ".dev-server-pids.json"
$backendStaticDir = Join-Path $backendDir "static"
$frontendOutDir = Join-Path $frontendDir "out"

function Get-PidInfo {
    if (Test-Path $pidsPath) {
        try {
            return Get-Content $pidsPath -Raw | ConvertFrom-Json
        } catch {
            return $null
        }
    }
    return $null
}

function Remove-PidFile {
    if (Test-Path $pidsPath) {
        Remove-Item $pidsPath -Force
    }
}

function Save-PidInfo($info) {
    $info | ConvertTo-Json | Set-Content $pidsPath
}

function Stop-ServerProcess($pid, $name) {
    $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "Stopping $name process with PID $pid..."
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        return $true
    }
    return $false
}

function Test-ProcessIsRunning($pid) {
    if (-not $pid) {
        return $false
    }
    return [bool](Get-Process -Id $pid -ErrorAction SilentlyContinue)
}

function Ensure-BackendEnv {
    $backendEnv = Join-Path $backendDir ".env"
    $exampleEnv = Join-Path $root ".env.example"
    if (-not (Test-Path $backendEnv)) {
        if (-not (Test-Path $exampleEnv)) {
            throw ".env.example not found. Create backend\.env manually before running."
        }
        Copy-Item $exampleEnv $backendEnv
        Write-Host "Created backend\.env from .env.example."
        Write-Host "Edit backend\.env with real keys for Telegram, Gemini/OpenAI/Anthropic, Langfuse, or Ollama as needed."
    }
}

function Ensure-BackendVenv {
    if (Test-Path $backendVenvPython) {
        return
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python was not found on PATH. Install Python 3.14 or update proto.ps1 to point to your Python executable."
    }

    Write-Host "Creating backend virtual environment..."
    $venvProcess = Start-Process -FilePath $pythonCommand.Source -ArgumentList "-m", "venv", ".venv" -WorkingDirectory $backendDir -NoNewWindow -Wait -PassThru
    if ($venvProcess.ExitCode -ne 0) {
        throw "Failed to create backend virtual environment."
    }
}

function Ensure-BackendDependencies {
    Ensure-BackendVenv
    Write-Host "Installing backend dependencies..."
    $pipProcess = Start-Process -FilePath $backendVenvPython -ArgumentList "-m", "pip", "install", "-r", "requirements.txt" -WorkingDirectory $backendDir -NoNewWindow -Wait -PassThru
    if ($pipProcess.ExitCode -ne 0) {
        throw "Backend dependency install failed with exit code $($pipProcess.ExitCode)."
    }
}

function Ensure-FrontendDependencies {
    Write-Host "Installing frontend dependencies..."
    if (Test-Path (Join-Path $frontendDir "package-lock.json")) {
        $npmArgs = "/c npm ci"
    } else {
        $npmArgs = "/c npm install"
    }
    $npmProcess = Start-Process -FilePath "cmd.exe" -ArgumentList $npmArgs -WorkingDirectory $frontendDir -NoNewWindow -Wait -PassThru
    if ($npmProcess.ExitCode -ne 0) {
        throw "Frontend dependency install failed with exit code $($npmProcess.ExitCode)."
    }
}

function Build-FrontendStatic {
    Ensure-FrontendDependencies
    Write-Host "Building frontend static assets..."
    $buildProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run build" -WorkingDirectory $frontendDir -NoNewWindow -Wait -PassThru
    if ($buildProcess.ExitCode -ne 0) {
        throw "Frontend build failed with exit code $($buildProcess.ExitCode)."
    }

    if (-not (Test-Path $frontendOutDir)) {
        throw "Frontend build completed, but frontend\out was not created."
    }

    if (Test-Path $backendStaticDir) {
        Remove-Item $backendStaticDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force $backendStaticDir | Out-Null
    Copy-Item -Recurse -Force (Join-Path $frontendOutDir "*") $backendStaticDir
    Write-Host "Copied frontend build to backend\static."
}

function Build-App {
    Ensure-BackendEnv
    Ensure-BackendDependencies
    Build-FrontendStatic
}

switch ($Action) {
    "start" {
        $existing = Get-PidInfo
        if ($existing -and (Test-ProcessIsRunning $existing.backendPid)) {
            Write-Host "App is already running at http://127.0.0.1:8000"
            Write-Host "Use '.\proto.ps1 -Action stop' before starting again."
            return
        }
        Remove-PidFile

        Build-App

        Write-Host "Starting AIAgentOrchestrationPlatform at http://127.0.0.1:8000 ..."
        $backendProcess = Start-Process -FilePath $backendVenvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru

        Save-PidInfo ([ordered]@{
            backendPid = $backendProcess.Id
            backendCommand = "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
            url = "http://127.0.0.1:8000"
        })

        Write-Host "Started backend with PID $($backendProcess.Id)."
        Write-Host "Open http://127.0.0.1:8000"
    }
    "build" {
        Build-App
        Write-Host "Build completed. Run '.\proto.ps1 -Action start' to launch the app."
    }
    "stop" {
        $pidInfo = Get-PidInfo
        if (-not $pidInfo) {
            Write-Host "No app PID file found."
            return
        }

        $stopped = Stop-ServerProcess $pidInfo.backendPid "backend"
        Remove-PidFile
        if ($stopped) {
            Write-Host "Stopped AIAgentOrchestrationPlatform."
        } else {
            Write-Host "No running process found, but PID file was removed."
        }
    }
    "status" {
        $pidInfo = Get-PidInfo
        if (-not $pidInfo) {
            Write-Host "No app PID file found. Run '.\proto.ps1' to start."
            return
        }

        if (Test-ProcessIsRunning $pidInfo.backendPid) {
            Write-Host "Running at $($pidInfo.url) with PID $($pidInfo.backendPid)."
        } else {
            Write-Host "PID file exists, but the backend process is not running."
        }
    }
}
