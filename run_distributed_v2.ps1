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
try {
    $LocustExecutable = (Get-Command "locust" -ErrorAction Stop).Source
    $PowerShellExecutable = (Get-Command "powershell" -ErrorAction Stop).Source
} catch {
    throw "Unable to resolve required executable: $($_.Exception.Message)"
}

$MasterPidFile = "locust_master.pid"
$WorkerPidFile = if ($Mode -eq "worker") {
    "locust_workers_{0}_{1}.pid" -f $WorkerIndexOffset, $WorkerCount
} else {
    "locust_workers.pid"
}
$ManageMaster = $Mode -in "master", "local"
$ManageWorkers = $Mode -in "worker", "local"

function Get-LocustPidFiles {
    param(
        [bool]$IncludeMaster = $true,
        [bool]$IncludeWorkers = $true
    )

    $files = @()

    if ($IncludeMaster) {
        $files += Get-Item -Path $MasterPidFile -ErrorAction SilentlyContinue
    }

    if ($IncludeWorkers) {
        $files += Get-ChildItem -Path "locust_workers*.pid" -ErrorAction SilentlyContinue
    }

    return $files | Where-Object { $null -ne $_ } | Sort-Object -Property FullName -Unique
}

function Get-ProcessCommandLineMap {
    $map = @{}
    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    foreach ($process in $processes) {
        $map[[int]$process.ProcessId] = $process
    }

    return $map
}

function Stop-ProcessTreeById {
    param(
        [int]$ProcessId,
        [hashtable]$ProcessMap
    )

    if (-not $ProcessMap.ContainsKey($ProcessId)) {
        return $false
    }

    $stoppedAny = $false
    $children = $ProcessMap.Values | Where-Object { [int]$_.ParentProcessId -eq $ProcessId }
    foreach ($child in $children) {
        if (Stop-ProcessTreeById -ProcessId ([int]$child.ProcessId) -ProcessMap $ProcessMap) {
            $stoppedAny = $true
        }
    }

    try {
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Stopping process tree node PID: $ProcessId ($($process.ProcessName))..." -ForegroundColor Gray
            Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
            $stoppedAny = $true
        }
    } catch {
        Write-Host "Process tree node PID: $ProcessId already stopped or not found." -ForegroundColor DarkGray
    }

    return $stoppedAny
}

function Test-CommandLineMatches {
    param(
        [string]$CommandLine,
        [string[]]$RequiredPatterns
    )

    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return $false
    }

    foreach ($pattern in $RequiredPatterns) {
        if ($CommandLine -notlike "*$pattern*") {
            return $false
        }
    }

    return $true
}

function Stop-StaleLocustProcesses {
    param(
        [bool]$StopMaster = $true,
        [bool]$StopWorkers = $true
    )

    $processMap = Get-ProcessCommandLineMap
    if ($processMap.Count -eq 0) {
        return $false
    }

    $stoppedAny = $false
    $locustFilePattern = $LocustFile.Replace("/", "\")
    $targets = @()

    if ($StopMaster) {
        $targets += @{
            Label = "master"
            Patterns = @($locustFilePattern, "--master")
        }
    }

    if ($StopWorkers) {
        $targets += @{
            Label = "worker"
            Patterns = @($locustFilePattern, "--worker")
        }
    }

    foreach ($target in $targets) {
        $matchingProcesses = $processMap.Values |
            Where-Object { Test-CommandLineMatches -CommandLine $_.CommandLine -RequiredPatterns $target.Patterns } |
            Sort-Object -Property ProcessId -Unique

        foreach ($process in $matchingProcesses) {
            $processId = [int]$process.ProcessId
            Write-Host "Found stale Locust $($target.Label) process by command line (PID: $processId)." -ForegroundColor DarkGray
            if (Stop-ProcessTreeById -ProcessId $processId -ProcessMap $processMap) {
                $stoppedAny = $true
            }
        }
    }

    return $stoppedAny
}

function Stop-LocustSafely {
    param(
        [bool]$StopMaster = $true,
        [bool]$StopWorkers = $true
    )

    Write-Host "Stopping Locust processes safely..." -ForegroundColor Yellow
    $stoppedAny = $false

    $processMap = Get-ProcessCommandLineMap
    $pidFiles = Get-LocustPidFiles -IncludeMaster:$StopMaster -IncludeWorkers:$StopWorkers
    foreach ($pidFile in $pidFiles) {
        $pids = Get-Content $pidFile.FullName -ErrorAction SilentlyContinue
        foreach ($processIdText in $pids) {
            if ($processIdText -match '^\d+$') {
                if (Stop-ProcessTreeById -ProcessId ([int]$processIdText) -ProcessMap $processMap) {
                    $stoppedAny = $true
                }
            }
        }
    }

    if (Stop-StaleLocustProcesses -StopMaster:$StopMaster -StopWorkers:$StopWorkers) {
        $stoppedAny = $true
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

function Convert-ToArgumentString {
    param(
        [string[]]$Arguments
    )

    $escaped = foreach ($arg in $Arguments) {
        if ($null -eq $arg) {
            continue
        }

        if ($arg -match '[\s"]') {
            '"' + ($arg -replace '"', '\"') + '"'
        } else {
            $arg
        }
    }

    return ($escaped -join " ")
}

function Escape-SingleQuotedPowerShellString {
    param(
        [string]$Value
    )

    if ($null -eq $Value) {
        return ""
    }

    return $Value.Replace("'", "''")
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

    $masterArgList = @("-f", $LocustFile, "--master")
    $expectedWorkers = 0

    if ($StartWebUi) {
        $masterArgList += @("--web-port", "$WebPort")
    }

    if ($Headless) {
        $masterArgList += "--headless"

        if ($Users -le 0) {
            throw "When -Headless is used, -Users must be greater than 0."
        }
        if ($SpawnRate -le 0) {
            throw "When -Headless is used, -SpawnRate must be greater than 0."
        }

        $masterArgList += @("-u", "$Users", "-r", "$SpawnRate")

        if (-not [string]::IsNullOrWhiteSpace($RunTime)) {
            $masterArgList += @("-t", $RunTime)
        }
        if ($ResetStats) {
            $masterArgList += "--reset-stats"
        }
        if ($OnlySummary) {
            $masterArgList += "--only-summary"
        }
        if (-not [string]::IsNullOrWhiteSpace($CsvPrefix)) {
            $masterArgList += @("--csv", $CsvPrefix)
        }
        if (-not [string]::IsNullOrWhiteSpace($HtmlReport)) {
            $masterArgList += @("--html", $HtmlReport)
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
            $masterArgList += @("--expect-workers", "$expectedWorkers")
        }
    }

    return $masterArgList
}

function Get-WorkerArgumentList {
    $workerArgList = @("-f", $LocustFile, "--worker", "--master-host", $MasterHost)

    if ($ResetStats) {
        $workerArgList += "--reset-stats"
    }

    return $workerArgList
}

function Wait-ManagedProcesses {
    if ($ManageMaster -and (Test-Path $MasterPidFile)) {
        $masterPid = Get-Content $MasterPidFile
        try {
            Wait-Process -Id $masterPid
        } catch {
            Write-Host "Master process already exited." -ForegroundColor DarkGray
        }
        return
    }

    if ($ManageWorkers -and (Test-Path $WorkerPidFile)) {
        $workerPids = Get-Content $WorkerPidFile | Where-Object { $_ -match '^\d+$' }
        if ($workerPids.Count -gt 0) {
            try {
                Wait-Process -Id $workerPids
            } catch {
                Write-Host "One or more worker processes already exited." -ForegroundColor DarkGray
            }
        }
    }
}

Stop-LocustSafely -StopMaster:$ManageMaster -StopWorkers:$ManageWorkers

Write-Host "Cleaning up old PID files..." -ForegroundColor Yellow
Get-LocustPidFiles -IncludeMaster:$ManageMaster -IncludeWorkers:$ManageWorkers | ForEach-Object {
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
}

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

        $master = Start-Process $LocustExecutable `
            -ArgumentList $masterArgs `
            -WorkingDirectory $ScriptPath `
            -PassThru `
            -WindowStyle Hidden `
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

                $workerArgs = Get-WorkerArgumentList
                $workerArgumentString = Convert-ToArgumentString -Arguments $workerArgs
                $escapedScriptPath = Escape-SingleQuotedPowerShellString -Value $ScriptPath
                $escapedLocustExecutable = Escape-SingleQuotedPowerShellString -Value $LocustExecutable
                $workerCommand = @(
                    "`$env:LOCUST_WORKER_INDEX = '$workerIndex'"
                    "`$env:LOCUST_WORKER_COUNT = '$TotalWorkerCount'"
                    "Set-Location '$escapedScriptPath'"
                    "& '$escapedLocustExecutable' $workerArgumentString"
                ) -join "; "

                $worker = Start-Process $PowerShellExecutable `
                    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $workerCommand) `
                    -WorkingDirectory $ScriptPath `
                    -PassThru `
                    -WindowStyle Hidden `
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
        Write-Host "Headless mode is running. 使用 Ctrl+C 或等待 run-time 结束." -ForegroundColor Yellow
        Wait-ManagedProcesses
    } else {
        Write-Host "Press Enter to 结束 Locust 实例..." -ForegroundColor Yellow
        Read-Host
    }
} finally {
    Stop-LocustSafely -StopMaster:$ManageMaster -StopWorkers:$ManageWorkers

    Get-LocustPidFiles -IncludeMaster:$ManageMaster -IncludeWorkers:$ManageWorkers | ForEach-Object {
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }

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
