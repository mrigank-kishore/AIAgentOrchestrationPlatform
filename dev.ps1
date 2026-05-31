param(
    [ValidateSet("start", "stop", "status", "build")]
    [string]$Action = "start"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidsPath = Join-Path $root ".dev-server-pids.json"

function Get-PidInfo {
    if (Test-Path $pidsPath) {
        try {
            return Get-Content $pidsPath -Raw | ConvertFrom-Json
        } catch {
            return @{}
        }
    }
    return @{}
}

function Save-PidInfo($info) {
    $info | ConvertTo-Json | Set-Content $pidsPath
}

function Remove-PidFile {
    if (Test-Path $pidsPath) {
        Remove-Item $pidsPath -Force
    }
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

function Ensure-FrontendDependencies {
    $frontendDir = Join-Path $root 'frontend'
    Write-Host "Installing frontend dependencies with 'npm install'..."
    $npmInstallProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm install' -WorkingDirectory $frontendDir -NoNewWindow -Wait -PassThru
    if ($npmInstallProcess.ExitCode -ne 0) {
        throw "npm install failed with exit code $($npmInstallProcess.ExitCode)."
    }
    Write-Host "Frontend dependencies installed successfully."
}

function Ensure-BackendDependencies {
    $backendDir = Join-Path $root 'backend'
    $backendPython = Join-Path $backendDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $backendPython)) {
        throw "Backend Python executable not found at '$backendPython'. Ensure the virtual environment exists."
    }

    Write-Host "Installing backend dependencies with 'pip install -r requirements.txt'..."
    $pipInstallProcess = Start-Process -FilePath $backendPython -ArgumentList '-m', 'pip', 'install', '-r', 'requirements.txt' -WorkingDirectory $backendDir -NoNewWindow -Wait -PassThru
    if ($pipInstallProcess.ExitCode -ne 0) {
        throw "Backend dependency install failed with exit code $($pipInstallProcess.ExitCode)."
    }
    Write-Host "Backend dependencies installed successfully."
}

switch ($Action) {
    'start' {
        if (Test-Path $pidsPath) {
            $existing = Get-PidInfo
            if ($existing.backendPid -or $existing.frontendPid) {
                Write-Host "A dev server is already running or the pid file exists. Use './dev.ps1 -Action stop' first."
                return
            }
        }

        $backendPython = Join-Path $root "backend\.venv\Scripts\python.exe"
        if (-not (Test-Path $backendPython)) {
            throw "Backend Python executable not found at '$backendPython'. Ensure the virtual environment exists."
        }

        Ensure-BackendDependencies

        $backendProcess = Start-Process -FilePath $backendPython -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload' -WorkingDirectory (Join-Path $root 'backend') -PassThru
        Write-Host "Started backend (uvicorn) with PID $($backendProcess.Id)."

        Ensure-FrontendDependencies
        Write-Host "Building frontend with 'npm run build'..."
        $frontendBuildProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run build' -WorkingDirectory (Join-Path $root 'frontend') -NoNewWindow -Wait -PassThru
        if ($frontendBuildProcess.ExitCode -ne 0) {
            throw "Frontend build failed with exit code $($frontendBuildProcess.ExitCode)."
        }
        Write-Host "Frontend build completed successfully."

        $frontendProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run dev' -WorkingDirectory (Join-Path $root 'frontend') -PassThru
        Write-Host "Started frontend (npm run dev) with PID $($frontendProcess.Id)."

        $pidInfo = [ordered]@{
            backendPid = $backendProcess.Id
            frontendPid = $frontendProcess.Id
            backendCommand = "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
            frontendCommand = "npm run dev"
        }
        Save-PidInfo $pidInfo
        Write-Host "Dev servers started. PID file created at $pidsPath."
    }
    'build' {
        Ensure-BackendDependencies
        Ensure-FrontendDependencies

        Write-Host "Building frontend with 'npm run build'..."
        $frontendBuildProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run build' -WorkingDirectory (Join-Path $root 'frontend') -NoNewWindow -Wait -PassThru
        if ($frontendBuildProcess.ExitCode -ne 0) {
            throw "Frontend build failed with exit code $($frontendBuildProcess.ExitCode)."
        }
        Write-Host "Frontend build completed successfully."
    }
    'stop' {
        $pidInfo = Get-PidInfo
        if (-not $pidInfo) {
            Write-Host "No running dev servers found. PID file is missing or empty."
            return
        }

        $stoppedAny = $false
        if ($pidInfo.backendPid) {
            $stoppedAny = Stop-ServerProcess $pidInfo.backendPid 'backend' -or $stoppedAny
        }
        if ($pidInfo.frontendPid) {
            $stoppedAny = Stop-ServerProcess $pidInfo.frontendPid 'frontend' -or $stoppedAny
        }

        Remove-PidFile
        if ($stoppedAny) {
            Write-Host "Stopped dev servers and removed PID file."
        } else {
            Write-Host "No dev server processes were running, but PID file was removed."
        }
    }
    'status' {
        $pidInfo = Get-PidInfo
        if (-not $pidInfo) {
            Write-Host "No dev server PID file found. Run './dev.ps1 -Action start' to launch backend and frontend."
            return
        }

        Write-Host "Dev server PID file found at $pidsPath"
        foreach ($key in @('backendPid','frontendPid')) {
            $pid = $pidInfo.$key
            if ($pid) {
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Host "$key is running: PID $pid, Name $($process.ProcessName)"
                } else {
                    Write-Host "$key is not running: PID $pid"
                }
            }
        }
    }
    default {
        throw "Unknown action '$Action'. Use 'start', 'stop', or 'status'."
    }
}
