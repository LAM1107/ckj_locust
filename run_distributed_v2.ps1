param(
    [ValidateSet("local", "master", "worker")]
    [string]$Mode = "local",

    [string]$MasterHost = "localhost",
    [int]$WebPort = 8089,
    [int]$WorkerCount = 0,
    [int]$WorkerIndexOffset = 0,
    [int]$TotalWorkerCount = 0,

    [switch]$Headless,
    [int]$Users = 0,
    [double]$SpawnRate = 0,
    [string]$RunTime = "",
    [switch]$ResetStats,
    [switch]$OnlySummary,
    [string]$CsvPrefix = "",
    [string]$HtmlReport = "",
    [string]$TokenFile = "",
    [string]$ScenarioMode = "",
    [string]$EnablePrometheus = "",
    [string]$EnableMetricsReport = "",
    [string]$EnableOrderPairStore = ""
)

$ScriptPath = $PSScriptRoot
if (-not $ScriptPath) { $ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition }
Set-Location $ScriptPath

$LocustFile = "case/locust_life.py"
$MasterPidFile = "locust_master.pid"
$WorkerPidFile = if ($Mode -eq "worker") {
    "locust_workers_{0}_{1}.pid" -f $WorkerIndexOffset, $WorkerCount
} else {
    "locust_workers.pid"
}
$ManageMaster = $Mode -in "master", "local"
$ManageWorkers = $Mode -in "worker", "local"

function Stop-LocustSafely {
    param(
        [bool]$StopMaster = $true,
        [bool]$StopWorkers = $true
    )

    Write-Host "Stopping Locust processes safely..." -ForegroundColor Yellow
    $stoppedAny = $false

    if ($StopMaster -and (Test-Path $MasterPidFile)) {
        $masterPid = Get-Content $MasterPidFile
        try {
            $process = Get-Process -Id $masterPid -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "Stopping Master process (PID: $masterPid)..." -ForegroundColor Gray
                Stop-Process -Id $masterPid -Force -ErrorAction SilentlyContinue
                $stoppedAny = $true
            }
        } catch {
            Write-Host "Master process (PID: $masterPid) already stopped or not found." -ForegroundColor DarkGray
        }
    }

    if ($StopWorkers -and (Test-Path $WorkerPidFile)) {
        $workerPids = Get-Content $WorkerPidFile
        foreach ($workerPid in $workerPids) {
            if ($workerPid -match '^\d+$') {
                try {
                    $process = Get-Process -Id $workerPid -ErrorAction SilentlyContinue
                    if ($process) {
                        Write-Host "Stopping Worker process (PID: $workerPid)..." -ForegroundColor Gray
                        Stop-Process -Id $workerPid -Force -ErrorAction SilentlyContinue
                        $stoppedAny = $true
                    }
                } catch {
                    Write-Host "Worker process (PID: $workerPid) already stopped or not found." -ForegroundColor DarkGray
                }
            }
        }
    }

    if ($stoppedAny) {
        Write-Host "Locust processes stopped." -ForegroundColor Green
    } else {
        Write-Host "No Locust processes were running." -ForegroundColor Yellow
    }
}

function Set-LocustEnvVar {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    Set-Item -Path "Env:$Name" -Value $Value
    Write-Host "Set $Name=$Value" -ForegroundColor DarkGray
}

function Ensure-ParentDirectory {
    param(
        [string]$PathValue
    )

    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return
    }

    $parent = [System.IO.Path]::GetDirectoryName($PathValue)
    if ([string]::IsNullOrWhiteSpace($parent)) {
        return
    }

    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Write-Host "Created directory: $parent" -ForegroundColor DarkGray
    }
}

function Get-MasterArgumentList {
    param(
        [bool]$StartWebUi
    )

    $args = @("-f", $LocustFile, "--master")
    $expectedWorkers = 0

    if ($StartWebUi) {
        $args += @("--web-port", "$WebPort")
    }

    if ($Headless) {
        $args += "--headless"

        if ($Users -le 0) {
            throw "When -Headless is used, -Users must be greater than 0."
        }
        if ($SpawnRate -le 0) {
            throw "When -Headless is used, -SpawnRate must be greater than 0."
        }

        $args += @("-u", "$Users", "-r", "$SpawnRate")

        if (-not [string]::IsNullOrWhiteSpace($RunTime)) {
            $args += @("-t", $RunTime)
        }
        if ($ResetStats) {
            $args += "--reset-stats"
        }
        if ($OnlySummary) {
            $args += "--only-summary"
        }
        if (-not [string]::IsNullOrWhiteSpace($CsvPrefix)) {
            $args += @("--csv", $CsvPrefix)
        }
        if (-not [string]::IsNullOrWhiteSpace($HtmlReport)) {
            $args += @("--html", $HtmlReport)
        }
        if ($Mode -eq "local" -and $WorkerCount -gt 0) {
            $expectedWorkers = $WorkerCount
        } elseif ($Mode -eq "master") {
            if ($TotalWorkerCount -gt 0) {
                $expectedWorkers = $TotalWorkerCount
            } elseif ($WorkerCount -gt 0) {
                $expectedWorkers = $WorkerCount
            }
        }

        if ($expectedWorkers -gt 0) {
            $args += @("--expect-workers", "$expectedWorkers")
        }
    }

    return $args
}

function Get-WorkerArgumentList {
    $args = @("-f", $LocustFile, "--worker", "--master-host", $MasterHost)

    if ($ResetStats) {
        $args += "--reset-stats"
    }

    return $args
}

Stop-LocustSafely -StopMaster:$ManageMaster -StopWorkers:$ManageWorkers

Write-Host "Cleaning up old PID files..." -ForegroundColor Yellow
if ($ManageMaster -and (Test-Path $MasterPidFile)) { Remove-Item $MasterPidFile -Force }
if ($ManageWorkers -and (Test-Path $WorkerPidFile)) { Remove-Item $WorkerPidFile -Force }

$oldScenarioMode = $env:LOCUST_SCENARIO_MODE
$oldEnablePrometheus = $env:LOCUST_ENABLE_PROMETHEUS
$oldEnableMetricsReport = $env:LOCUST_ENABLE_METRICS_REPORT
$oldEnableOrderPairStore = $env:LOCUST_ENABLE_ORDER_PAIR_STORE
$oldTokenFile = $env:LOCUST_TOKEN_FILE

if (-not [string]::IsNullOrWhiteSpace($ScenarioMode)) {
    Set-LocustEnvVar -Name "LOCUST_SCENARIO_MODE" -Value $ScenarioMode
}
if (-not [string]::IsNullOrWhiteSpace($EnablePrometheus)) {
    Set-LocustEnvVar -Name "LOCUST_ENABLE_PROMETHEUS" -Value $EnablePrometheus
}
if (-not [string]::IsNullOrWhiteSpace($EnableMetricsReport)) {
    Set-LocustEnvVar -Name "LOCUST_ENABLE_METRICS_REPORT" -Value $EnableMetricsReport
}
if (-not [string]::IsNullOrWhiteSpace($EnableOrderPairStore)) {
    Set-LocustEnvVar -Name "LOCUST_ENABLE_ORDER_PAIR_STORE" -Value $EnableOrderPairStore
}
if (-not [string]::IsNullOrWhiteSpace($TokenFile)) {
    Set-LocustEnvVar -Name "LOCUST_TOKEN_FILE" -Value $TokenFile
}

try {
    Ensure-ParentDirectory -PathValue $CsvPrefix
    Ensure-ParentDirectory -PathValue $HtmlReport

    if ($Mode -in "worker", "local") {
        if ($WorkerCount -eq 0) {
            $Cores = [Environment]::ProcessorCount
            $WorkerCount = [Math]::Max(1, $Cores - 2)
        }

        if ($TotalWorkerCount -eq 0) {
            $TotalWorkerCount = $WorkerCount
        }

        if (($WorkerIndexOffset + $WorkerCount) -gt $TotalWorkerCount) {
            throw "WorkerIndexOffset + WorkerCount must be <= TotalWorkerCount"
        }
    }

    if ($Mode -in "master", "local") {
        $startWebUi = -not $Headless
        $masterArgs = Get-MasterArgumentList -StartWebUi:$startWebUi

        Write-Host "Starting Locust Master..." -ForegroundColor Green
        Write-Host ("Master args: " + ($masterArgs -join " ")) -ForegroundColor DarkGray

        $master = Start-Process "locust" `
            -ArgumentList $masterArgs `
            -PassThru `
            -RedirectStandardOutput "master.log" `
            -RedirectStandardError "master_error.log"

        $master.Id | Out-File $MasterPidFile -Encoding UTF8
        Write-Host "Master started with PID: $($master.Id)" -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }

    if ($Mode -in "worker", "local") {
        Write-Host "Starting $WorkerCount Locust Workers..." -ForegroundColor Cyan
        Write-Host "Token shard range: $WorkerIndexOffset..$($WorkerIndexOffset + $WorkerCount - 1) / $TotalWorkerCount" -ForegroundColor Gray

        $oldWorkerIndex = $env:LOCUST_WORKER_INDEX
        $oldWorkerCount = $env:LOCUST_WORKER_COUNT

        try {
            1..$WorkerCount | ForEach-Object {
                $workerNumber = $_
                $workerIndex = $WorkerIndexOffset + $workerNumber - 1
                $env:LOCUST_WORKER_INDEX = "$workerIndex"
                $env:LOCUST_WORKER_COUNT = "$TotalWorkerCount"

                $workerArgs = Get-WorkerArgumentList

                $worker = Start-Process "locust" `
                    -ArgumentList $workerArgs `
                    -PassThru `
                    -RedirectStandardOutput "worker_$workerNumber.log" `
                    -RedirectStandardError "worker_${workerNumber}_error.log"

                $worker.Id | Out-File -Append $WorkerPidFile -Encoding UTF8
                Write-Host "Worker $workerNumber started with PID: $($worker.Id), token shard: $workerIndex/$TotalWorkerCount" -ForegroundColor Gray
            }
        } finally {
            if ($null -eq $oldWorkerIndex) {
                Remove-Item Env:\LOCUST_WORKER_INDEX -ErrorAction SilentlyContinue
            } else {
                $env:LOCUST_WORKER_INDEX = $oldWorkerIndex
            }

            if ($null -eq $oldWorkerCount) {
                Remove-Item Env:\LOCUST_WORKER_COUNT -ErrorAction SilentlyContinue
            } else {
                $env:LOCUST_WORKER_COUNT = $oldWorkerCount
            }
        }
    }

    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host "Locust is running!" -ForegroundColor Green
    if (-not $Headless -and $Mode -in "master", "local") {
        Write-Host "Web UI: http://localhost:$WebPort" -ForegroundColor White
    }
    Write-Host "Mode: $Mode" -ForegroundColor White
    if ($Headless) {
        Write-Host "Headless: true" -ForegroundColor White
        Write-Host "Users: $Users" -ForegroundColor White
        Write-Host "SpawnRate: $SpawnRate" -ForegroundColor White
        if (-not [string]::IsNullOrWhiteSpace($RunTime)) {
            Write-Host "RunTime: $RunTime" -ForegroundColor White
        }
    }
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host ""

    if ($Headless) {
        Write-Host "Headless mode is running. Use Ctrl+C or wait for run-time to finish." -ForegroundColor Yellow
        if (Test-Path $MasterPidFile) {
            $masterPid = Get-Content $MasterPidFile
            try {
                Wait-Process -Id $masterPid
            } catch {
                Write-Host "Master process already exited." -ForegroundColor DarkGray
            }
        }
    } else {
        Write-Host "Press Enter to stop this Locust instance..." -ForegroundColor Yellow
        Read-Host
    }
} finally {
    Stop-LocustSafely -StopMaster:$ManageMaster -StopWorkers:$ManageWorkers

    if ($ManageMaster -and (Test-Path $MasterPidFile)) { Remove-Item $MasterPidFile -Force }
    if ($ManageWorkers -and (Test-Path $WorkerPidFile)) { Remove-Item $WorkerPidFile -Force }

    if ($null -eq $oldScenarioMode) {
        Remove-Item Env:\LOCUST_SCENARIO_MODE -ErrorAction SilentlyContinue
    } else {
        $env:LOCUST_SCENARIO_MODE = $oldScenarioMode
    }

    if ($null -eq $oldEnablePrometheus) {
        Remove-Item Env:\LOCUST_ENABLE_PROMETHEUS -ErrorAction SilentlyContinue
    } else {
        $env:LOCUST_ENABLE_PROMETHEUS = $oldEnablePrometheus
    }

    if ($null -eq $oldEnableMetricsReport) {
        Remove-Item Env:\LOCUST_ENABLE_METRICS_REPORT -ErrorAction SilentlyContinue
    } else {
        $env:LOCUST_ENABLE_METRICS_REPORT = $oldEnableMetricsReport
    }

    if ($null -eq $oldEnableOrderPairStore) {
        Remove-Item Env:\LOCUST_ENABLE_ORDER_PAIR_STORE -ErrorAction SilentlyContinue
    } else {
        $env:LOCUST_ENABLE_ORDER_PAIR_STORE = $oldEnableOrderPairStore
    }

    if ($null -eq $oldTokenFile) {
        Remove-Item Env:\LOCUST_TOKEN_FILE -ErrorAction SilentlyContinue
    } else {
        $env:LOCUST_TOKEN_FILE = $oldTokenFile
    }

    Write-Host "Locust stopped." -ForegroundColor Green
}
