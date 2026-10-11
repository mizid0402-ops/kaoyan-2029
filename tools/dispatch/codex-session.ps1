[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string]$PromptFile,

    [Parameter(Mandatory = $true)]
    [string]$ArtifactPath,

    [string]$WorkingDirectory = (Get-Location).Path,
    [string]$Model,
    [switch]$NewSession,
    # Live web search for tasks that must find public material (e.g. a syllabus); off by default.
    [switch]$WebSearch,
    [switch]$DangerouslyBypassApprovalsAndSandbox
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = $utf8NoBom

function Resolve-FullPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$BaseDirectory
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $Path))
}

function Resolve-CliApplication {
    param([Parameter(Mandatory = $true)][string]$BaseName)

    $cmdShim = Get-Command "$BaseName.cmd" -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $cmdShim) {
        return $cmdShim.Source
    }

    $application = Get-Command $BaseName -All -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandType -eq 'Application' } |
        Select-Object -First 1
    if ($null -eq $application) {
        throw "找不到 $BaseName CLI。请先安装并确保其 .cmd 或可执行文件在 PATH 中。"
    }
    return $application.Source
}

function Quote-PowerShellLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-ArtifactState {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject]@{ Exists = $false; Length = 0L; Hash = $null; LastWriteUtcTicks = 0L }
    }

    $item = Get-Item -LiteralPath $Path
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    return [pscustomobject]@{
        Exists = $true
        Length = [long]$item.Length
        Hash = $hash
        LastWriteUtcTicks = $item.LastWriteTimeUtc.Ticks
    }
}

function Get-CodexThreadId {
    param([Parameter(Mandatory = $true)][string]$RawLogPath)

    foreach ($line in [System.IO.File]::ReadLines($RawLogPath, [System.Text.Encoding]::UTF8)) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try {
            $event = $line | ConvertFrom-Json -ErrorAction Stop
            if ($event.type -eq 'thread.started' -and $event.thread_id) {
                return [string]$event.thread_id
            }
        }
        catch {
            # Native diagnostics can be mixed with JSONL; keep them in the log.
        }
    }
    return $null
}

$workingRoot = Resolve-FullPath -Path $WorkingDirectory -BaseDirectory (Get-Location).Path
if (-not (Test-Path -LiteralPath $workingRoot -PathType Container)) {
    throw "工作目录不存在：$workingRoot"
}

$promptPath = Resolve-FullPath -Path $PromptFile -BaseDirectory $workingRoot
if (-not (Test-Path -LiteralPath $promptPath -PathType Leaf)) {
    throw "提示词文件不存在：$promptPath"
}

$artifactFullPath = Resolve-FullPath -Path $ArtifactPath -BaseDirectory $workingRoot
$repoRoot = Resolve-FullPath -Path (Join-Path $PSScriptRoot '..\..') -BaseDirectory $PSScriptRoot
$dispatchLogDirectory = Join-Path $repoRoot 'logs\dispatch'
[System.IO.Directory]::CreateDirectory($dispatchLogDirectory) | Out-Null

$sessionFile = Join-Path $dispatchLogDirectory "codex-$Name.session"
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$logPath = Join-Path $dispatchLogDirectory "$Name-codex-$timestamp.log"
$rawLogPath = Join-Path $dispatchLogDirectory "$Name-codex-$timestamp.raw.log"
$promptText = [System.IO.File]::ReadAllText($promptPath, [System.Text.Encoding]::UTF8)
if ([string]::IsNullOrWhiteSpace($promptText)) {
    throw "提示词文件为空：$promptPath"
}

$mode = 'new'
$storedSessionId = $null
if (-not $NewSession) {
    if (-not (Test-Path -LiteralPath $sessionFile -PathType Leaf)) {
        $mode = 'new'
    }
    else {
        $mode = 'resume'
        $storedSessionId = [System.IO.File]::ReadAllText($sessionFile, [System.Text.Encoding]::UTF8).Trim()
        $parsedId = [guid]::Empty
        if (-not [guid]::TryParse($storedSessionId, [ref]$parsedId)) {
            throw "会话文件中的 Codex session id 无效：$sessionFile。请修复该文件或使用 -NewSession。"
        }
    }
}

$codexPath = Resolve-CliApplication -BaseName 'codex'
$cliArguments = [System.Collections.Generic.List[string]]::new()
$cliArguments.Add('exec')
if ($mode -eq 'resume') {
    $cliArguments.Add('resume')
}
$cliArguments.Add('--json')
if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $cliArguments.Add('--model')
    $cliArguments.Add($Model)
}
if ($WebSearch) {
    $cliArguments.Add('-c')
    $cliArguments.Add('web_search="live"')
}
if ($DangerouslyBypassApprovalsAndSandbox) {
    $cliArguments.Add('--dangerously-bypass-approvals-and-sandbox')
}
if ($mode -eq 'resume') {
    $cliArguments.Add($storedSessionId)
}
$cliArguments.Add('-')

$readExpression = "[System.IO.File]::ReadAllText($(Quote-PowerShellLiteral $promptPath), [System.Text.Encoding]::UTF8)"
$quotedArgs = @($cliArguments | ForEach-Object { Quote-PowerShellLiteral $_ }) -join ' '
$copyableCommand = "$readExpression | & $(Quote-PowerShellLiteral $codexPath) $quotedArgs *> $(Quote-PowerShellLiteral $rawLogPath)"
$headLength = [Math]::Min(40, $promptText.Length)
$tailLength = [Math]::Min(40, $promptText.Length)
$promptHead = $promptText.Substring(0, $headLength).Replace("`r", '\r').Replace("`n", '\n')
$promptTail = $promptText.Substring($promptText.Length - $tailLength, $tailLength).Replace("`r", '\r').Replace("`n", '\n')
$beforeArtifact = Get-ArtifactState -Path $artifactFullPath

Push-Location -LiteralPath $workingRoot
$previousErrorActionPreference = $ErrorActionPreference
try {
    # Windows PowerShell 5.1 wraps native stderr as non-terminating ErrorRecord
    # objects. Keep them in *> output instead of letting Stop bypass artifact checks.
    $ErrorActionPreference = 'Continue'
    $promptText | & $codexPath @cliArguments *> $rawLogPath
    $cliExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Pop-Location
}

$observedSessionId = Get-CodexThreadId -RawLogPath $rawLogPath
$afterArtifact = Get-ArtifactState -Path $artifactFullPath
$artifactChanged = $afterArtifact.Exists -and $afterArtifact.Length -gt 0 -and (
    (-not $beforeArtifact.Exists) -or
    $beforeArtifact.Hash -ne $afterArtifact.Hash -or
    $beforeArtifact.LastWriteUtcTicks -ne $afterArtifact.LastWriteUtcTicks
)
$sessionMatches = $mode -eq 'new' -or (
    -not [string]::IsNullOrWhiteSpace($observedSessionId) -and
    $observedSessionId -eq $storedSessionId
)

$metadata = @(
    '=== dispatch metadata ==='
    "wrapper=codex-session.ps1"
    "mode=$mode"
    "name=$Name"
    "working_directory=$workingRoot"
    "prompt_file=$promptPath"
    "prompt_characters=$($promptText.Length)"
    "prompt_head=$promptHead"
    "prompt_tail=$promptTail"
    "artifact=$artifactFullPath"
    "artifact_changed=$artifactChanged"
    "stored_session_id=$storedSessionId"
    "observed_session_id=$observedSessionId"
    "cli_exit_code=$cliExitCode"
    "copyable_command=$copyableCommand"
    '=== raw cli output ==='
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText($logPath, $metadata + [Environment]::NewLine, $utf8NoBom)
[System.IO.File]::AppendAllText($logPath, [System.IO.File]::ReadAllText($rawLogPath, [System.Text.Encoding]::UTF8), $utf8NoBom)

if (-not $artifactChanged) {
    if ($mode -eq 'resume') {
        throw "Codex 续会话失败或未更新产物：$artifactFullPath。没有静默新开会话；请查看 $logPath，确认旧会话状态后使用 -NewSession。"
    }
    throw "Codex 新会话未创建或更新非空产物：$artifactFullPath。请查看 $logPath。"
}
if ([string]::IsNullOrWhiteSpace($observedSessionId)) {
    throw "产物已更新，但无法从 Codex JSONL 提取 session id；为避免丢失续会话状态，本次判定失败。请查看 $logPath。"
}
if (-not $sessionMatches) {
    throw "Codex 返回的 session id 与记录值不一致；没有静默切换会话。请查看 $logPath，并在确认后使用 -NewSession。"
}

$sessionTempFile = "$sessionFile.$PID.tmp"
[System.IO.File]::WriteAllText($sessionTempFile, $observedSessionId + [Environment]::NewLine, $utf8NoBom)
Move-Item -LiteralPath $sessionTempFile -Destination $sessionFile -Force

[pscustomobject]@{
    Cli = 'codex'
    Mode = $mode
    SessionId = $observedSessionId
    PromptCharacters = $promptText.Length
    Artifact = $artifactFullPath
    Log = $logPath
    CliExitCode = $cliExitCode
    SuccessBasis = 'artifact-created-or-updated'
}
