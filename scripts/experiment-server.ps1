#Requires -Version 5.1
<#
.SYNOPSIS
  Turn this Windows PC into the PF-3311 experiment server (Docker + Ollama) for Mac/lab clients.

.DESCRIPTION
  Start:  firewall, prevent sleep, docker compose up, warm models, print Mac env vars.
  Stop:   restore sleep settings, remove firewall rules, docker compose stop.
  Status: health checks and connection info.

.EXAMPLE
  .\scripts\experiment-server.ps1 -Action Start
  .\scripts\experiment-server.ps1 -Action Stop
  .\scripts\experiment-server.ps1 -Status
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("Start", "Stop", "Status", "start", "stop", "status")]
    [string]$Action = "Start",

    [string]$ConfigPath = "",

    [switch]$SkipFirewall,
    [switch]$SkipWarmup,
    [switch]$PullModels,
    [switch]$ForceDocker,
    [switch]$ForceNative
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $PSScriptRoot "experiment-server.config.json"
}
$StateDir = Join-Path $RepoRoot ".experiment-server"
$StateFile = Join-Path $StateDir "state.json"

$Action = (Get-Culture).TextInfo.ToTitleCase($Action.ToLower())
$Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

function Write-Banner([string]$Text) {
    Write-Host ""
    Write-Host "=== $Text ===" -ForegroundColor Cyan
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-LanIPv4 {
    $skipIfaces = @(
        "vEthernet", "WSL", "Hyper-V", "VirtualBox", "VMware", "Loopback", "Teredo", "isatap"
    )
    $preferIfaces = @("Wi-Fi", "Ethernet", "WLAN", "en0", "eth0")

    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            $_.PrefixOrigin -ne "WellKnown"
        } |
        ForEach-Object {
            $addr = $_
            $adapter = Get-NetAdapter -InterfaceIndex $addr.InterfaceIndex -ErrorAction SilentlyContinue
            $alias = if ($adapter) { $adapter.Name } else { $addr.InterfaceAlias }
            $skip = $false
            foreach ($s in $skipIfaces) {
                if ($alias -like "*$s*") { $skip = $true; break }
            }
            if ($skip) { return }
            $prefer = 0
            foreach ($p in $preferIfaces) {
                if ($alias -like "*$p*") { $prefer = 1; break }
            }
            $metric = 999
            if ($adapter) {
                $metricProp = $adapter.PSObject.Properties['InterfaceMetric']
                if ($null -ne $metricProp) {
                    $metric = [int]$metricProp.Value
                }
            }
            [PSCustomObject]@{
                IP = $addr.IPAddress
                Alias = $alias
                Prefer = $prefer
                Metric = $metric
            }
        }

    if (-not $candidates) {
        return "127.0.0.1"
    }
    $best = $candidates | Sort-Object -Property @{ Expression = "Prefer"; Descending = $true }, Metric | Select-Object -First 1
    return $best.IP
}

function Save-State([hashtable]$Data) {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    ($Data | ConvertTo-Json -Depth 6) | Set-Content -Path $StateFile -Encoding UTF8
}

function Load-State {
    if (-not (Test-Path $StateFile)) {
        return $null
    }
    return Get-Content $StateFile -Raw | ConvertFrom-Json
}

function Get-PowerTimeouts {
    $schemeLine = (powercfg /getactivescheme) -join " "
    $guid = if ($schemeLine -match "([0-9a-f\-]{36})") { $Matches[1] } else { $null }
    function Read-Setting([string]$name) {
        $out = powercfg /q SCHEME_CURRENT SUB_SLEEP $name 2>$null
        foreach ($line in $out) {
            if ($line -match "Current AC Power Setting Index:\s+0x([0-9a-f]+)") {
                return [Convert]::ToInt32($Matches[1], 16)
            }
        }
        return $null
    }
  return @{
        scheme_guid = $guid
        standby_ac = Read-Setting "STANDBYIDLE"
        monitor_ac = (powercfg /q SCHEME_CURRENT SUB_VIDEO VIDEOIDLE 2>$null | ForEach-Object {
            if ($_ -match "Current AC Power Setting Index:\s+0x([0-9a-f]+)") { [Convert]::ToInt32($Matches[1], 16) }
        } | Select-Object -First 1)
    }
}

function Invoke-PowerCfg([string[]]$Args) {
    try {
        & powercfg @Args 2>$null | Out-Null
    } catch {
        # Some SKUs omit hybrid-sleep or other knobs; ignore.
    }
}

function Disable-SystemSleep {
    Write-Host "Disabling sleep while server mode is active (AC power)..."
    Invoke-PowerCfg @("/change", "standby-timeout-ac", "0")
    Invoke-PowerCfg @("/change", "monitor-timeout-ac", "0")
    Invoke-PowerCfg @("/change", "hibernate-timeout-ac", "0")
    Invoke-PowerCfg @("/change", "hybrid-sleep-timeout-ac", "0")
}

function Restore-SystemSleep([object]$State) {
    if ($null -eq $State) {
        Write-Host "No saved power settings; restoring common defaults (30 min standby, 15 min display)."
        powercfg /change standby-timeout-ac 30 | Out-Null
        powercfg /change monitor-timeout-ac 15 | Out-Null
        return
    }
    if ($null -ne $State.standby_ac) {
        powercfg /change standby-timeout-ac ([int]$State.standby_ac) | Out-Null
    }
    if ($null -ne $State.monitor_ac) {
        powercfg /change monitor-timeout-ac ([int]$State.monitor_ac) | Out-Null
    }
    Write-Host "Power timeouts restored."
}

function Enable-FirewallRules([int]$BackendPort, [int]$OllamaPort, [string]$BackendRule, [string]$OllamaRule) {
    if ($SkipFirewall) {
        Write-Warning "Skipping firewall rules (-SkipFirewall)."
        return
    }
    if (-not (Test-IsAdmin)) {
        $ports = if ($OllamaPort -gt 0) { "$BackendPort and $OllamaPort" } else { "$BackendPort" }
        Write-Warning "Not running as Administrator - firewall rules were NOT added. Re-run Start as admin or open port(s) $ports manually."
        return
    }
    $rules = @(
        @{ Name = $BackendRule; Port = $BackendPort; Desc = "PF-3311 FastAPI backend" }
    )
    if ($OllamaPort -gt 0) {
        $rules += @{ Name = $OllamaRule; Port = $OllamaPort; Desc = "PF-3311 Ollama API" }
    }
    foreach ($pair in $rules) {
        $existing = Get-NetFirewallRule -DisplayName $pair.Name -ErrorAction SilentlyContinue
        if ($existing) {
            Enable-NetFirewallRule -DisplayName $pair.Name | Out-Null
        } else {
            New-NetFirewallRule `
                -DisplayName $pair.Name `
                -Description $pair.Desc `
                -Direction Inbound `
                -Action Allow `
                -Protocol TCP `
                -LocalPort $pair.Port `
                -Profile Any | Out-Null
        }
        Write-Host "Firewall: inbound TCP $($pair.Port) ($($pair.Name))"
    }
}

function Disable-FirewallRules([string]$BackendRule, [string]$OllamaRule) {
    foreach ($name in @($BackendRule, $OllamaRule)) {
        $rule = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
        if ($rule) {
            Remove-NetFirewallRule -DisplayName $name
            Write-Host "Removed firewall rule: $name"
        }
    }
}

function Test-DockerReady {
    try {
        & docker info 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Test-PortListening([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $conn
}

function Test-OllamaReady([string]$BaseUrl) {
    try {
        Invoke-RestMethod -Uri "$BaseUrl/api/tags" -TimeoutSec 5 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Resolve-ServerMode {
    if ($ForceDocker) { return "docker" }
    if ($ForceNative) { return "native" }

    $ollamaUrl = "http://127.0.0.1:$($Config.ollama_port)"
    if ((Test-PortListening ([int]$Config.ollama_port)) -and (Test-OllamaReady $ollamaUrl)) {
        Write-Host "Host Ollama detected; using native mode (backend on 0.0.0.0, Ollama stays local)."
        return "native"
    }
    if (Test-DockerReady) {
        return "docker"
    }
    throw "Neither Docker nor host Ollama is available. Start Docker Desktop or the Ollama app, then retry."
}

function Invoke-OllamaPull([string]$Model, [string]$Mode) {
    Write-Host "Pulling $Model..."
    if ($Mode -eq "docker") {
        & docker exec pf3311-ollama ollama pull $Model
    } else {
        & ollama pull $Model
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to pull model: $Model"
    }
}

function Start-NativeBackend([int]$Port, [string]$KeepAlive) {
    $backendDir = Join-Path $RepoRoot "src\backend"
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $logFile = Join-Path $StateDir "backend.log"

    $env:OLLAMA_KEEP_ALIVE = $KeepAlive
    $env:LLM_MODEL = [string]$Config.chat_model
    $env:OLLAMA_MODEL = [string]$Config.chat_model
    $env:OLLAMA_BASE_URL = "http://127.0.0.1:$($Config.ollama_port)"
    $env:LLM_BASE_URL = $env:OLLAMA_BASE_URL

    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) {
        throw "Native mode requires 'uv' on PATH (install from https://docs.astral.sh/uv/)."
    }

    $proc = Start-Process `
        -FilePath $uv.Source `
        -ArgumentList @("run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$Port") `
        -WorkingDirectory $backendDir `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError (Join-Path $StateDir "backend.err.log")

    return [int]$proc.Id
}

function Stop-NativeBackend([object]$State) {
    if ($null -eq $State) { return }
    $pidProp = $State.PSObject.Properties['backend_pid']
    if ($null -eq $pidProp) { return }
    $pid = [int]$pidProp.Value
    if ($pid -le 0) { return }
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $pid -Force
        Write-Host "Stopped native backend (PID $pid)."
    }
}

function Invoke-DockerCompose([string[]]$ComposeArgs) {
    Push-Location $RepoRoot
    try {
        $files = @()
        foreach ($f in $Config.compose_files) {
            $files += "-f"
            $files += (Join-Path $RepoRoot $f)
        }
        & docker compose @files @ComposeArgs
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose failed (exit $LASTEXITCODE): $($ComposeArgs -join ' ')"
        }
    } finally {
        Pop-Location
    }
}

function Wait-BackendHealth([string]$Url, [int]$Seconds = 120) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-RestMethod -Uri $Url -TimeoutSec 5
            if ($r.status -eq "ok" -or $r.ok -eq $true) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

function Invoke-OllamaWarm([string]$OllamaUrl, [string]$ChatModel, [string]$EmbedModel, [string]$KeepAlive) {
    Write-Host "Warming chat model: $ChatModel (keep_alive=$KeepAlive)..."
    $genBody = @{
        model      = $ChatModel
        prompt     = "Responde solo: OK"
        stream     = $false
        keep_alive = $KeepAlive
        options    = @{ num_predict = 8 }
    } | ConvertTo-Json -Depth 5
    Invoke-RestMethod -Uri "$OllamaUrl/api/generate" -Method Post -Body $genBody -ContentType "application/json" -TimeoutSec 600 | Out-Null

    Write-Host "Warming embed model: $EmbedModel..."
    $embedBody = @{
        model  = $EmbedModel
        prompt = "hola"
        keep_alive = $KeepAlive
    } | ConvertTo-Json -Depth 4
    try {
        Invoke-RestMethod -Uri "$OllamaUrl/api/embeddings" -Method Post -Body $embedBody -ContentType "application/json" -TimeoutSec 120 | Out-Null
    } catch {
        Write-Warning "Embedding warm-up failed (optional): $_"
    }
}

function Show-MacInstructions([string]$LanIp, [int]$BackendPort) {
    Write-Banner "Mac / remote client"
    $lines = @(
        ""
        "On the Mac (Godot or exported client), set before launching:"
        ""
        "  export FAMILIAR_BACKEND_HTTP=http://${LanIp}:${BackendPort}"
        "  export FAMILIAR_BACKEND_WS=ws://${LanIp}:${BackendPort}/ws/session"
        ""
        "Or in Godot: Project -> Run -> Environment variables (same names)."
        ""
        "Test from Mac terminal:"
        "  curl http://${LanIp}:${BackendPort}/healthz"
        ""
        "Research dashboard (any browser on LAN):"
        "  http://${LanIp}:${BackendPort}/research/dashboard"
        ""
    )
    Write-Host ($lines -join "`n") -ForegroundColor Green
}

function Start-ExperimentServer {
    if (Test-Path $StateFile) {
        Write-Warning "State file already exists. If a previous Start was interrupted, run -Action Stop first."
    }

    $lanIp = Get-LanIPv4
    $backendPort = [int]$Config.backend_port
    $ollamaPort = [int]$Config.ollama_port
    $keepAlive = [string]$Config.keep_alive
    $mode = Resolve-ServerMode

    Write-Banner "Starting experiment server"
    Write-Host "Repo:        $RepoRoot"
    Write-Host "Mode:        $mode"
    Write-Host "LAN IP:      $lanIp"
    Write-Host "Chat model:  $($Config.chat_model)"
    Write-Host "Embed model: $($Config.embed_model)"

    $powerBefore = Get-PowerTimeouts
    Disable-SystemSleep
    if ($mode -eq "native") {
        Enable-FirewallRules $backendPort 0 $Config.firewall_rule_backend $Config.firewall_rule_ollama
    } else {
        Enable-FirewallRules $backendPort $ollamaPort $Config.firewall_rule_backend $Config.firewall_rule_ollama
    }

    $backendPid = 0
    if ($PullModels) {
        if ($mode -eq "docker") {
            Invoke-DockerCompose @("up", "-d", "ollama")
        }
        Invoke-OllamaPull $Config.chat_model $mode
        Invoke-OllamaPull $Config.embed_model $mode
    }

    if ($mode -eq "native") {
        if (Test-PortListening $backendPort) {
            throw "Port $backendPort is already in use. Stop the other service or run -Action Stop."
        }
        Write-Host "Starting native backend (uvicorn on 0.0.0.0:$backendPort)..."
        $backendPid = Start-NativeBackend $backendPort $keepAlive
    } else {
        Write-Host "Starting Docker stack..."
        Invoke-DockerCompose @("up", "-d")
    }

    $healthUrl = "http://127.0.0.1:${backendPort}/healthz"
    if (-not (Wait-BackendHealth $healthUrl 180)) {
        if ($mode -eq "native") {
            $logFile = Join-Path $StateDir "backend.log"
            throw "Backend did not become healthy at $healthUrl - see $logFile"
        }
        throw "Backend did not become healthy at $healthUrl - check: docker compose logs backend"
    }
    Write-Host "Backend healthy: $healthUrl" -ForegroundColor Green

    if (-not $SkipWarmup) {
        $ollamaUrl = if ($mode -eq "docker") { "http://127.0.0.1:${ollamaPort}" } else { "http://127.0.0.1:${ollamaPort}" }
        Invoke-OllamaWarm $ollamaUrl $Config.chat_model $Config.embed_model $keepAlive
        Write-Host "Models warmed (keep_alive=$keepAlive)." -ForegroundColor Green
    }

    Save-State @{
        started_at    = (Get-Date).ToString("o")
        mode          = $mode
        lan_ip        = $lanIp
        backend_port  = $backendPort
        backend_pid   = $backendPid
        ollama_port   = $ollamaPort
        chat_model    = $Config.chat_model
        embed_model   = $Config.embed_model
        keep_alive    = $keepAlive
        power_before  = $powerBefore
        skip_firewall = [bool]$SkipFirewall
    }

    Show-MacInstructions $lanIp $backendPort
    Write-Host "Server mode ON ($mode). Leave this PC plugged in. Use -Action Stop when finished." -ForegroundColor Yellow
}

function Stop-ExperimentServer {
    Write-Banner "Stopping experiment server"
    $state = Load-State
    $mode = "docker"
    if ($null -ne $state -and $state.PSObject.Properties['mode']) {
        $mode = [string]$state.mode
    }

    if ($mode -eq "native") {
        Stop-NativeBackend $state
    } else {
        if (Test-DockerReady) {
            Invoke-DockerCompose @("stop")
            Write-Host "Docker services stopped (volumes preserved)."
        } else {
            Write-Warning "Docker not running; skipped docker compose stop."
        }
    }

    Disable-FirewallRules $Config.firewall_rule_backend $Config.firewall_rule_ollama
    if ($null -ne $state -and $state.PSObject.Properties['power_before']) {
        Restore-SystemSleep ($state.power_before)
    } else {
        Restore-SystemSleep $null
    }

    if (Test-Path $StateFile) {
        Remove-Item $StateFile -Force
    }
    Write-Host "Server mode OFF." -ForegroundColor Green
}

function Show-ExperimentStatus {
    $state = Load-State
    $lanIp = Get-LanIPv4
    if ($null -ne $state -and $state.PSObject.Properties['lan_ip']) {
        $lanIp = [string]$state.lan_ip
    }
    $backendPort = [int]$Config.backend_port
    $ollamaPort = [int]$Config.ollama_port

    Write-Banner "Experiment server status"
    if ($null -ne $state) {
        Write-Host "Server mode: ACTIVE since $($state.started_at)"
        if ($state.PSObject.Properties['mode']) {
            Write-Host "Stack mode:  $($state.mode)"
        }
    } else {
        Write-Host "Server mode: not active (no state file)"
    }

    Push-Location $RepoRoot
    try {
        docker compose -f docker-compose.yml -f docker-compose.experiment-server.yml ps
    } finally {
        Pop-Location
    }

    foreach ($pair in @(
        @{ Name = "Backend health"; Url = "http://127.0.0.1:${backendPort}/healthz" },
        @{ Name = "Ollama tags"; Url = "http://127.0.0.1:${ollamaPort}/api/tags" }
    )) {
        try {
            $r = Invoke-RestMethod -Uri $pair.Url -TimeoutSec 5
            Write-Host "$($pair.Name): OK" -ForegroundColor Green
        } catch {
            Write-Host "$($pair.Name): FAIL - $_" -ForegroundColor Red
        }
    }

    Show-MacInstructions $lanIp $backendPort
}

switch ($Action) {
    "Start" { Start-ExperimentServer }
    "Stop" { Stop-ExperimentServer }
    "Status" { Show-ExperimentStatus }
    default { throw "Unknown action: $Action" }
}
