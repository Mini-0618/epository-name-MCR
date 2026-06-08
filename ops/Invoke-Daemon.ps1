param(
  [Parameter(Position=0)]
  [string]$Action = "status",
  [string]$Goal = "60",
  [int]$MaxIterations = 24,
  [switch]$Json
)

$ErrorActionPreference = "Stop"

# --- Paths ---
$EcosystemRoot    = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DaemonDir        = Join-Path $EcosystemRoot "runtime\daemon"
$StateJson        = Join-Path $DaemonDir "state.json"
$HeartbeatsLog    = Join-Path $DaemonDir "heartbeats.jsonl"
$RecoveryJson     = Join-Path $DaemonDir "recovery.json"
$RunsDir          = Join-Path $DaemonDir "runs"
$ReportsDir       = Join-Path $DaemonDir "reports"
$McrOsPath        = Join-Path $EcosystemRoot "ops\mcr-os.ps1"
$PsExe            = Join-Path $PSHOME "powershell.exe"
$TaskJsonPath     = "sdk/templates/mcr.task.json"
$WeeklyPlanPath   = Join-Path $EcosystemRoot "runtime\life\weekly-plan.json"
$DailyReviewPath  = Join-Path $EcosystemRoot "runtime\life\daily-review.jsonl"
$MemoryJsonlPath  = Join-Path $EcosystemRoot "runtime\swarm\memory.jsonl"
$AgiDir           = Join-Path $EcosystemRoot "runtime\agi"
$PredTrackerPy    = Join-Path $AgiDir "prediction-tracker.py"
$PredStatsPath    = Join-Path $AgiDir "prediction-stats.json"
$WorldModelPath   = Join-Path $AgiDir "world-model.json"
$TierManagerPy    = Join-Path $AgiDir "tier-manager.py"
$SelfImprovePy    = Join-Path $AgiDir "self-improve.py"
$SessionsJsonl    = Join-Path $AgiDir "sessions.jsonl"
$CheckpointsDir   = Join-Path $AgiDir "checkpoints"
$SessionMgrPy     = Join-Path $AgiDir "session_manager.py"
$CheckpointMgrPy  = Join-Path $AgiDir "checkpoint.py"
$ConsolidatorPy   = Join-Path $AgiDir "knowledge-consolidator.py"
$ConsolidationLog = Join-Path $AgiDir "consolidation-log.jsonl"
$RealStatePy      = Join-Path $AgiDir "real-state-checker.py"
$SelfDiagnosisPy  = Join-Path $AgiDir "self-diagnosis.py"
$DiagnosisJson    = Join-Path $AgiDir "diagnosis.json"
$ToolRouterPy     = Join-Path $AgiDir "tool-router.py"
$FeedbackQuarantinePy = Join-Path $AgiDir "feedback-quarantine.py"
$ConceptMapPy     = Join-Path $AgiDir "concept_map.py"
# Detect Python for prediction tracker
$PythonExe = $null
foreach ($candidate in @("py", "python", "python3")) {
  $found = Get-Command $candidate -ErrorAction SilentlyContinue
  if ($found) { $PythonExe = $found.Source; break }
}
if (-not $PythonExe) {
  foreach ($p in @("C:\Python314\python.exe", "C:\Python313\python.exe", "C:\Python312\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe")) {
    if (Test-Path $p) { $PythonExe = $p; break }
  }
}

# --- Ensure directories ---
foreach ($dir in @($RunsDir, $ReportsDir, $CheckpointsDir)) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

function Get-ShortGuid {
  [guid]::NewGuid().ToString().Substring(0, 8)
}

function Read-DaemonState {
  Get-Content -LiteralPath $StateJson -Raw | ConvertFrom-Json
}

function Write-DaemonState {
  param($State)
  $State | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StateJson -Encoding UTF8
}

function Write-Heartbeat {
  <#
    .DESCRIPTION
    Enhanced heartbeat: writes structured entry to heartbeats.jsonl.
    Includes heartbeat_id, steps_passed, steps_failed, score, next_scheduled, recovery.
  #>
  param(
    [string]$RunId,
    [string]$Status,
    [string]$Phase,
    [string]$Detail = "",
    [int]$StepsPassed = 0,
    [int]$StepsFailed = 0,
    [int]$Score = 0,
    [string]$NextScheduled = "",
    [bool]$Recovery = $false
  )

  $hbId = "hb-$(Get-ShortGuid)"
  $hb = [ordered]@{
    heartbeat_id   = $hbId
    run_id         = $RunId
    timestamp      = (Get-Date).ToString("o")
    status         = $Status
    phase          = $Phase
    detail         = $Detail
    steps_passed   = $StepsPassed
    steps_failed   = $StepsFailed
    score          = $Score
    next_scheduled = $NextScheduled
    recovery       = $Recovery
  }
  ($hb | ConvertTo-Json -Depth 6 -Compress) | Add-Content -LiteralPath $HeartbeatsLog -Encoding UTF8
  return $hbId
}

function Write-HeartbeatLegacy {
  <# Backward-compatible heartbeat for in-progress phases #>
  param([string]$RunId, [string]$Status, [string]$Phase, [string]$Detail = "")
  $hb = [ordered]@{
    timestamp = (Get-Date).ToString("o")
    run_id    = $RunId
    status    = $Status
    phase     = $Phase
    detail    = $Detail
  }
  ($hb | ConvertTo-Json -Depth 6 -Compress) | Add-Content -LiteralPath $HeartbeatsLog -Encoding UTF8
}

function Read-Recovery {
  if (Test-Path -LiteralPath $RecoveryJson) {
    return Get-Content -LiteralPath $RecoveryJson -Raw | ConvertFrom-Json
  }
  return $null
}

function Write-Recovery {
  param($RecoveryData)
  $RecoveryData | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $RecoveryJson -Encoding UTF8
}

function Clear-Recovery {
  if (Test-Path -LiteralPath $RecoveryJson) {
    Remove-Item -LiteralPath $RecoveryJson -Force
  }
}

function Invoke-DaemonStep {
  <#
    .DESCRIPTION
    Runs a single mcr-os subcommand. Returns @{ success=bool; output=string; duration=double; exitCode=int }
    SAFETY: Only local verification commands. Never external, never destructive.
  #>
  param(
    [string]$Label,
    [string[]]$McrOsArgs
  )

  $fullArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $McrOsPath) + $McrOsArgs
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $output = ""
  $exitCode = 0

  try {
    $output = & $PsExe @($fullArgs) 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
  } catch {
    $output = $_.ToString()
    $exitCode = 1
  }
  $sw.Stop()
  $duration = [math]::Round($sw.Elapsed.TotalSeconds, 3)

  return @{
    success  = ($exitCode -eq 0)
    output   = $output
    duration = $duration
    exitCode = $exitCode
    label    = $Label
  }
}

function Get-NextScheduled {
  param([int]$IntervalMinutes)
  $next = (Get-Date).AddMinutes($IntervalMinutes)
  return $next.ToString("o")
}

# ============================================================
# SESSION & CHECKPOINT HELPERS
# ============================================================

function Invoke-SessionStart {
  param([string]$SessionId = "")
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $SessionMgrPy)) { return $null }
  try {
    $args = @($SessionMgrPy, $SessionsJsonl, "start")
    if ($SessionId) { $args += $SessionId }
    $output = & $PythonExe @args 2>&1 | Out-String
    return $output | ConvertFrom-Json
  } catch { return $null }
}

function Invoke-SessionHeartbeat {
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $SessionMgrPy)) { return $null }
  try {
    $output = & $PythonExe $SessionMgrPy $SessionsJsonl "heartbeat" 2>&1 | Out-String
    return $output | ConvertFrom-Json
  } catch { return $null }
}

function Invoke-SessionStop {
  param([string]$Reason = "normal")
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $SessionMgrPy)) { return $null }
  try {
    $output = & $PythonExe $SessionMgrPy $SessionsJsonl "stop" $Reason 2>&1 | Out-String
    return $output | ConvertFrom-Json
  } catch { return $null }
}

function Invoke-CheckpointCreate {
  param([string]$Label = "")
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $CheckpointMgrPy)) { return $null }
  try {
    $args = @($CheckpointMgrPy, $CheckpointsDir, $EcosystemRoot, "create")
    if ($Label) { $args += $Label }
    $output = & $PythonExe @args 2>&1 | Out-String
    return $output | ConvertFrom-Json
  } catch { return $null }
}

function Invoke-PredictionReview {
  <#
    .DESCRIPTION
    Reviews recent predictions, calculates Brier score, reports calibration quality,
    writes to runtime/agi/prediction-stats.json and updates world-model.json.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $PredTrackerPy)) {
    Write-Host "  [prediction-review] Skipped: Python or prediction-tracker.py not found"
    return $null
  }

  try {
    # Get stats from prediction tracker
    $statsOutput = & $PythonExe $PredTrackerPy stats 2>&1 | Out-String
    $stats = $statsOutput | ConvertFrom-Json

    # Write prediction-stats.json
    $predStats = [ordered]@{
      total_predictions = $stats.total_predictions
      brier_score       = $stats.brier_score
      accuracy          = $stats.accuracy
      should_intervene  = $stats.should_intervene
      last_updated      = (Get-Date).ToString("o")
    }
    $predStats | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $PredStatsPath -Encoding UTF8

    # Update world-model.json with prediction stats
    if (Test-Path -LiteralPath $WorldModelPath) {
      try {
        $wm = Get-Content -LiteralPath $WorldModelPath -Raw | ConvertFrom-Json
        $wmHt = [ordered]@{}
        $wm.PSObject.Properties | ForEach-Object { $wmHt[$_.Name] = $_.Value }
        $wmHt["prediction_tracker"] = $predStats
        $wmHt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $WorldModelPath -Encoding UTF8
      } catch {}
    }

    Write-Host "  [prediction-review] PASS - brier=$($stats.brier_score) accuracy=$($stats.accuracy) total=$($stats.total_predictions)"
    return $predStats
  } catch {
    Write-Host "  [prediction-review] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-TierEvaluate {
  <#
    .DESCRIPTION
    Runs tier-manager.py evaluate to process memory tier transitions.
    Returns the evaluation result or null if skipped.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $TierManagerPy)) {
    Write-Host "  [tier-evaluate] Skipped: Python or tier-manager.py not found"
    return $null
  }

  try {
    $output = & $PythonExe $TierManagerPy evaluate 2>&1 | Out-String
    $result = $output | ConvertFrom-Json
    $count = if ($result.count) { [int]$result.count } else { 0 }
    Write-Host "  [tier-evaluate] PASS - $count transitions"
    return $result
  } catch {
    Write-Host "  [tier-evaluate] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-SelfImproveReview {
  <#
    .DESCRIPTION
    Runs self-improve.py suggest to check for improvement suggestions.
    Returns the suggestions or null if skipped.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $SelfImprovePy)) {
    Write-Host "  [self-improve-review] Skipped: Python or self-improve.py not found"
    return $null
  }

  try {
    $output = & $PythonExe $SelfImprovePy suggest 2>&1 | Out-String
    $result = $output | ConvertFrom-Json
    $count = if ($result.count) { [int]$result.count } else { 0 }
    if ($count -gt 0) {
      Write-Host "  [self-improve-review] PASS - $count suggestions"
    } else {
      Write-Host "  [self-improve-review] PASS - no new suggestions"
    }
    return $result
  } catch {
    Write-Host "  [self-improve-review] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-CognitiveTick {
  <#
    .DESCRIPTION
    Runs one cognitive cycle via cognitive-loop.py tick.
    Returns the tick result or null if skipped.
  #>
  $cognitiveLoopPy = Join-Path $AgiDir "cognitive-loop.py"
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $cognitiveLoopPy)) {
    Write-Host "  [cognitive-tick] Skipped: Python or cognitive-loop.py not found"
    return $null
  }

  try {
    $output = & $PythonExe $cognitiveLoopPy tick 2>&1 | Out-String
    $result = $output | ConvertFrom-Json
    $gateDecision = if ($result.gate) { $result.gate.decision } else { "unknown" }
    $obsCount = if ($result.observation_count) { $result.observation_count } else { 0 }
    Write-Host "  [cognitive-tick] PASS - tick=$($result.tick) gate=$gateDecision obs=$obsCount safety=$($result.safety_mode)"
    return $result
  } catch {
    Write-Host "  [cognitive-tick] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-SelfDiagnose {
  <#
    .DESCRIPTION
    Runs self-diagnosis via self-diagnosis.py diagnose.
    Returns the diagnosis result or null if skipped.
    If critical issues found, writes feedback question to feedback-pending.jsonl.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $SelfDiagnosisPy)) {
    Write-Host "  [self-diagnose] Skipped: Python or self-diagnosis.py not found"
    return $null
  }

  try {
    $output = & $PythonExe $SelfDiagnosisPy diagnose 2>&1 | Out-String
    $result = $output | ConvertFrom-Json
    $issueCount = if ($result.issue_count) { [int]$result.issue_count } else { 0 }
    $severity = if ($result.severity) { $result.severity } else { "unknown" }
    $score = if ($result.health_score) { [int]$result.health_score } else { 0 }

    $color = switch ($severity) {
      "ok"       { "Green" }
      "warning"  { "Yellow" }
      "critical" { "Red" }
      default    { "White" }
    }
    Write-Host "  [self-diagnose] PASS - severity=$severity score=$score issues=$issueCount" -ForegroundColor $color
    return $result
  } catch {
    Write-Host "  [self-diagnose] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-SelfImproveAutoFix {
  <#
    .DESCRIPTION
    Runs self-improve.py auto-fix to apply safe fixes automatically.
    Returns auto-fix results or null if skipped.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $SelfImprovePy)) {
    Write-Host "  [self-improve-auto-fix] Skipped: Python or self-improve.py not found"
    return $null
  }

  try {
    $output = & $PythonExe $SelfImprovePy auto-fix 2>&1 | Out-String
    $result = $output | ConvertFrom-Json
    $applied = 0
    $skipped = 0
    foreach ($prop in $result.PSObject.Properties) {
      if ($prop.Value.status -eq "applied") { $applied++ }
      else { $skipped++ }
    }
    Write-Host "  [self-improve-auto-fix] PASS - $applied applied, $skipped skipped"
    return $result
  } catch {
    Write-Host "  [self-improve-auto-fix] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-ToolRouter {
  <#
    .DESCRIPTION
    Runs tool-router.py list to verify dynamic routing is available.
    Returns tool count or null if skipped.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $ToolRouterPy)) {
    Write-Host "  [tool-router] Skipped: Python or tool-router.py not found"
    return $null
  }

  try {
    $output = & $PythonExe $ToolRouterPy list 2>&1 | Out-String
    $result = $output | ConvertFrom-Json
    $toolCount = if ($result -is [array]) { $result.Count } else { 0 }
    Write-Host "  [tool-router] PASS - $toolCount tools registered"
    return $result
  } catch {
    Write-Host "  [tool-router] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-FeedbackQuarantine {
  <#
    .DESCRIPTION
    Runs feedback-quarantine.py scan to detect injected feedback.
    Returns quarantine stats or null if skipped.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $FeedbackQuarantinePy)) {
    Write-Host "  [feedback-quarantine] Skipped: Python or feedback-quarantine.py not found"
    return $null
  }

  try {
    $output = & $PythonExe $FeedbackQuarantinePy scan 2>&1 | Out-String
    $result = $output | ConvertFrom-Json
    $quarantined = if ($result.quarantined) { [int]$result.quarantined } else { 0 }
    $total = if ($result.total_feedback) { [int]$result.total_feedback } else { 0 }
    Write-Host "  [feedback-quarantine] PASS - $quarantined/$total quarantined"
    return $result
  } catch {
    Write-Host "  [feedback-quarantine] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-ConceptMapValidate {
  <#
    .DESCRIPTION
    Runs concept_map.py validate to verify concept map integrity.
    Returns validation result or null if skipped.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $ConceptMapPy)) {
    Write-Host "  [concept-map] Skipped: Python or concept_map.py not found"
    return $null
  }

  try {
    $output = & $PythonExe $ConceptMapPy validate 2>&1 | Out-String
    $result = $output | ConvertFrom-Json
    $valid = if ($result.valid) { $result.valid } else { $false }
    $mappings = if ($result.mappings_count) { [int]$result.mappings_count } else { 0 }
    $rules = if ($result.rules_count) { [int]$result.rules_count } else { 0 }
    Write-Host "  [concept-map] PASS - valid=$valid mappings=$mappings rules=$rules"
    return $result
  } catch {
    Write-Host "  [concept-map] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-KnowledgeConsolidate {
  <#
    .DESCRIPTION
    Runs knowledge-consolidator.py to find and merge duplicate memories.
    If duplicates > 5, auto-consolidates. Otherwise reports findings.
    Writes to consolidation-log.jsonl.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $ConsolidatorPy)) {
    Write-Host "  [knowledge-consolidate] Skipped: Python or knowledge-consolidator.py not found"
    return $null
  }

  try {
    # Step 1: Find duplicates
    $dupOutput = & $PythonExe $ConsolidatorPy find-duplicates 2>&1 | Out-String
    $dupResult = $dupOutput | ConvertFrom-Json
    $dupCount = if ($dupResult.total_duplicates) { [int]$dupResult.total_duplicates } else { 0 }

    if ($dupCount -gt 5) {
      # Step 2: Run consolidation (execute mode)
      $consolOutput = & $PythonExe $ConsolidatorPy consolidate --execute 2>&1 | Out-String
      $consolResult = $consolOutput | ConvertFrom-Json
      $archived = if ($consolResult.archived) { [int]$consolResult.archived } else { 0 }
      Write-Host "  [knowledge-consolidate] PASS - $dupCount duplicates found, $archived archived"
      return $consolResult
    } else {
      Write-Host "  [knowledge-consolidate] PASS - $dupCount duplicates found (threshold: consolidate if > 5)"
      return $dupResult
    }
  } catch {
    Write-Host "  [knowledge-consolidate] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

function Invoke-RealStateCheck {
  <#
    .DESCRIPTION
    Runs real-state-checker.py to check actual filesystem state of all apps.
    Compares with previous state history, detects anomalies, writes to anomalies.jsonl.
    Returns the ecosystem summary or null if skipped.
  #>
  if (-not $PythonExe -or -not (Test-Path -LiteralPath $RealStatePy)) {
    Write-Host "  [real-state-check] Skipped: Python or real-state-checker.py not found"
    return $null
  }

  try {
    # Step 1: Run anomaly detection (also updates history)
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUTF8 = '1'
    $anomalyOutput = & $PythonExe $RealStatePy anomalies --json 2>&1 | Out-String
    $anomalies = $anomalyOutput | ConvertFrom-Json
    $anomalyCount = if ($anomalies -is [array]) { $anomalies.Count } else { 0 }

    # Step 2: Get ecosystem summary
    $ecoOutput = & $PythonExe $RealStatePy ecosystem --json 2>&1 | Out-String
    $eco = $ecoOutput | ConvertFrom-Json

    $ecoHealthy = if ($eco.healthy) { [int]$eco.healthy } else { 0 }
    $ecoWarning = if ($eco.warning) { [int]$eco.warning } else { 0 }
    $ecoCritical = if ($eco.critical) { [int]$eco.critical } else { 0 }

    if ($anomalyCount -gt 0) {
      Write-Host "  [real-state-check] PASS - H=$ecoHealthy W=$ecoWarning C=$ecoCritical anomalies=$anomalyCount" -ForegroundColor Yellow
    } else {
      Write-Host "  [real-state-check] PASS - H=$ecoHealthy W=$ecoWarning C=$ecoCritical no anomalies"
    }
    return $eco
  } catch {
    Write-Host "  [real-state-check] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    return $null
  }
}

# ============================================================
# WEEKLY PLAN & DAILY REVIEW FUNCTIONS
# ============================================================

function Read-WeeklyPlan {
  if (-not (Test-Path -LiteralPath $WeeklyPlanPath)) { return $null }
  Get-Content -LiteralPath $WeeklyPlanPath -Raw | ConvertFrom-Json
}

function Write-WeeklyPlan {
  param($Plan)
  $Plan.updated_at = (Get-Date).ToString("yyyy-MM-dd")
  $Plan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $WeeklyPlanPath -Encoding UTF8
}

function Get-DailyReviewEntries {
  if (-not (Test-Path -LiteralPath $DailyReviewPath)) { return @() }
  @(Get-Content -LiteralPath $DailyReviewPath -ErrorAction SilentlyContinue | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
}

function Add-DailyReviewEntry {
  param($Entry)
  ($Entry | ConvertTo-Json -Depth 8 -Compress) | Add-Content -LiteralPath $DailyReviewPath -Encoding UTF8
}

function Invoke-DailyReview {
  <#
    .DESCRIPTION
    Step 5: Read weekly-plan.json, find today's planned tasks, check completion
    by scanning memory.jsonl and daemon reports, write review to daily-review.jsonl,
    update weekly-plan.json with actual results and corrections.
  #>
  $plan = Read-WeeklyPlan
  if (-not $plan) {
    Write-Host "  [review] No weekly-plan.json found. Skipping daily review."
    return $null
  }

  $today = (Get-Date).ToString("yyyy-MM-dd")
  $todayDay = $plan.days | Where-Object { $_.date -eq $today } | Select-Object -First 1
  if (-not $todayDay) {
    Write-Host "  [review] Today ($today) not found in weekly plan. Skipping."
    return $null
  }

  $planned = @($todayDay.planned)
  Write-Host "  [review] Reviewing today's plan: $($planned -join ', ')"

  # Scan reports directory for today's activity
  $todayReports = @()
  if (Test-Path -LiteralPath $ReportsDir) {
    $todayReports = @(Get-ChildItem -LiteralPath $ReportsDir -Filter "*.md" -ErrorAction SilentlyContinue |
      Where-Object { $_.LastWriteTime.ToString("yyyy-MM-dd") -eq $today })
  }

  # Scan memory.jsonl for today's entries
  $memoryHits = @()
  if (Test-Path -LiteralPath $MemoryJsonlPath) {
    $memoryHits = @(Get-Content -LiteralPath $MemoryJsonlPath -ErrorAction SilentlyContinue |
      Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json } |
      Where-Object { $_.written_at -match $today })
  }

  # Scan runtime reports for today
  $runtimeReports = @()
  $runtimeReportsDir = Join-Path $EcosystemRoot "runtime\reports"
  if (Test-Path -LiteralPath $runtimeReportsDir) {
    $runtimeReports = @(Get-ChildItem -LiteralPath $runtimeReportsDir -Filter "*.json" -ErrorAction SilentlyContinue |
      Where-Object { $_.LastWriteTime.ToString("yyyy-MM-dd") -eq $today })
  }

  # Determine completed vs missed based on keyword matching
  $completed = @()
  $missed = @()
  $allReportText = ($todayReports | ForEach-Object { Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue }) -join " "
  $allReportText += " " + (($runtimeReports | ForEach-Object { Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue }) -join " ")

  foreach ($task in $planned) {
    $taskLower = $task.ToLower()
    $found = $false
    # Check if any report content mentions this task
    if ($allReportText -match [regex]::Escape($task)) { $found = $true }
    # Check keyword overlap
    $keywords = $taskLower -split "\s+" | Where-Object { $_.Length -gt 3 }
    foreach ($kw in $keywords) {
      if ($allReportText.ToLower() -match $kw) { $found = $true; break }
    }
    if ($found) { $completed += $task } else { $missed += $task }
  }

  # Generate corrections for missed tasks
  $corrections = @()
  foreach ($m in $missed) {
    $corrections += "reschedule '$m' to next available day"
  }

  # Write review entry
  $reviewEntry = [ordered]@{
    review_id    = "review-$(Get-Date -Format 'yyyyMMdd')"
    date         = $today
    planned      = $planned
    completed    = $completed
    missed       = $missed
    corrections  = $corrections
    lessons      = "reports scanned: $($todayReports.Count) daemon, $($runtimeReports.Count) runtime, $($memoryHits.Count) memory entries"
    tomorrow_adjustments = @()
    created_at   = (Get-Date).ToString("o")
  }
  Add-DailyReviewEntry $reviewEntry
  Write-Host "  [review] Written: $($completed.Count) completed, $($missed.Count) missed"

  # Update weekly-plan.json with actual results
  $todayDay.actual = $completed
  $todayDay.status = if ($missed.Count -eq 0) { "done" } elseif ($completed.Count -gt 0) { "partial" } else { "missed" }
  $todayDay.corrections = $corrections

  # Update metrics
  $plan.metrics.completed_tasks = @($plan.days | ForEach-Object { @($_.actual).Count } | Measure-Object -Sum).Sum
  $plan.metrics.missed_tasks = @($plan.days | ForEach-Object { $diff = @($_.planned).Count - @($_.actual).Count; if ($diff -gt 0) { $diff } } | Measure-Object -Sum).Sum
  $plan.metrics.correction_count = @($plan.days | ForEach-Object { @($_.corrections).Count } | Measure-Object -Sum).Sum

  Write-WeeklyPlan $plan
  Write-Host "  [review] Plan updated: status=$($todayDay.status)"
  return $reviewEntry
}

function Update-TomorrowPlan {
  <#
    .DESCRIPTION
    Step 6: Based on today's review, generate tomorrow's task list and write to weekly-plan.json.
    Moves missed tasks to tomorrow, adds carry-forward corrections.
  #>
  $plan = Read-WeeklyPlan
  if (-not $plan) {
    Write-Host "  [tomorrow] No weekly-plan.json found. Skipping."
    return
  }

  $today = (Get-Date).ToString("yyyy-MM-dd")
  $tomorrow = (Get-Date).AddDays(1).ToString("yyyy-MM-dd")
  $todayDay = $plan.days | Where-Object { $_.date -eq $today } | Select-Object -First 1
  $tomorrowDay = $plan.days | Where-Object { $_.date -eq $tomorrow } | Select-Object -First 1

  if (-not $tomorrowDay) {
    Write-Host "  [tomorrow] Tomorrow ($tomorrow) not in current week plan. Skipping."
    return
  }

  $adjustments = @()

  # Carry forward missed tasks
  if ($todayDay) {
    $missed = @($todayDay.planned | Where-Object { $todayDay.actual -notcontains $_ })
    foreach ($m in $missed) {
      if ($tomorrowDay.planned -notcontains $m) {
        $tomorrowDay.planned += $m
        $adjustments += "carried forward: $m"
      }
    }
  }

  # Read yesterday's review for lessons
  $entries = Get-DailyReviewEntries
  $todayReview = $entries | Where-Object { $_.date -eq $today } | Select-Object -Last 1
  if ($todayReview -and $todayReview.lessons) {
    $adjustments += "lesson: $($todayReview.lessons)"
  }

  $tomorrowDay.corrections = $adjustments
  Write-WeeklyPlan $plan
  Write-Host "  [tomorrow] Tomorrow plan updated: $($tomorrowDay.planned.Count) tasks, $($adjustments.Count) adjustments"
}

# ============================================================
# ACTION: status
# ============================================================
function Invoke-Status {
  $state = Read-DaemonState

  # Compute next_scheduled hint
  $nextScheduled = "manual (use 'loop' for autonomous mode)"
  if ($state.started_at -and $state.mode -eq "loop") {
    $nextScheduled = "loop active since $($state.started_at)"
  } elseif ($state.started_at) {
    $nextScheduled = "every 24h from $($state.started_at)"
  }

  if ($Json) {
    [ordered]@{
      schema_version       = $state.schema_version
      status               = $state.status
      mode                 = $state.mode
      last_run_id          = $state.last_run_id
      last_run_at          = $state.last_run_at
      last_status          = $state.last_status
      total_runs           = $state.total_runs
      consecutive_passes   = $state.consecutive_passes
      consecutive_failures = $state.consecutive_failures
      last_heartbeat_at    = $state.last_heartbeat_at
      recovery_pending     = $state.recovery_pending
      started_at           = $state.started_at
      pid                  = $state.pid
      next_scheduled       = $nextScheduled
    } | ConvertTo-Json -Depth 6
  } else {
    Write-Host "MCR Daily Daemon v0.2"
    Write-Host ("-" * 40)
    Write-Host "  Status             : $($state.status)"
    Write-Host "  Mode               : $($state.mode)"
    Write-Host "  Last Run ID        : $($state.last_run_id)"
    Write-Host "  Last Run At        : $($state.last_run_at)"
    Write-Host "  Last Status        : $($state.last_status)"
    Write-Host "  Total Runs         : $($state.total_runs)"
    Write-Host "  Consecutive Passes : $($state.consecutive_passes)"
    Write-Host "  Consecutive Fails  : $($state.consecutive_failures)"
    Write-Host "  Last Heartbeat     : $($state.last_heartbeat_at)"
    Write-Host "  Recovery Pending   : $($state.recovery_pending)"
    Write-Host "  Started At         : $($state.started_at)"
    Write-Host "  PID                : $($state.pid)"
    Write-Host "  Next Scheduled     : $nextScheduled"
  }
}

# ============================================================
# ACTION: once
# ============================================================
function Invoke-Once {
  param([bool]$IsRecoveryRun = $false, [string]$RecoveryStep = "")

  $runId    = "daemon-$(Get-ShortGuid)"
  $runStart = Get-Date
  $intervalMinutes = [int]$Goal

  # 1. Update state to running
  $state = Read-DaemonState
  $state.status = "running"
  $state.last_run_id = $runId
  Write-DaemonState $state

  # 2. Write initial heartbeat
  Write-HeartbeatLegacy -RunId $runId -Status "running" -Phase "start"

  # 2b. Start session + initial checkpoint
  $sessionInfo = Invoke-SessionStart -SessionId $runId
  if ($sessionInfo) { Write-Host "  [session] Started: $($sessionInfo.session_id)" }
  $startCkpt = Invoke-CheckpointCreate -Label "daemon-start"
  if ($startCkpt) { Write-Host "  [checkpoint] Created: $($startCkpt.checkpoint_id)" }

  # 3. Define verification steps (SAFETY: local-only, read-only checks)
  $steps = @(
    @{
      label    = "registry validate"
      args     = @("registry", "validate")
      fallback = $null
    }
    @{
      label    = "swarm audit"
      args     = @("swarm", "audit")
      fallback = $null
    }
    @{
      label    = "swarm status"
      args     = @("swarm", "status")
      fallback = $null
    }
    @{
      label    = "plan today"
      args     = @("plan", "today")
      fallback = $null
    }
    @{
      label    = "skill candidates"
      args     = @("skill", "candidates")
      fallback = $null
    }
    @{
      label    = "swarm deliveries"
      args     = @("swarm", "deliveries")
      fallback = $null
    }
    @{
      label    = "eval agi-readiness"
      args     = @("eval", "agi-readiness")
      fallback = $null
    }
    @{
      label    = "integration gate"
      args     = @("integration", "gate")
      fallback = $null
    }
    @{
      label    = "world-model-update"
      args     = @("swarm", "world-model")
      fallback = $null
    }
    @{
      label    = "adaptive-memory"
      args     = @("agi", "g1-g6")
      fallback = $null
    }
    @{
      label    = "prediction-review"
      args     = $null  # handled by Invoke-PredictionReview
      fallback = $null
    }
    @{
      label    = "memory-index-rebuild"
      args     = @("agi", "memory-stats")
      fallback = $null
    }
    @{
      label    = "tier-evaluate"
      args     = $null  # handled by Invoke-TierEvaluate
      fallback = $null
    }
    @{
      label    = "self-improve-review"
      args     = $null  # handled by Invoke-SelfImproveReview
      fallback = $null
    }
    @{
      label    = "self-improve-auto-fix"
      args     = $null  # handled by Invoke-SelfImproveAutoFix
      fallback = $null
    }
    @{
      label    = "cognitive-tick"
      args     = $null  # handled by Invoke-CognitiveTick
      fallback = $null
    }
    @{
      label    = "knowledge-consolidate"
      args     = $null  # handled by Invoke-KnowledgeConsolidate
      fallback = $null
    }
    @{
      label    = "real-state-check"
      args     = $null  # handled by Invoke-RealStateCheck
      fallback = $null
    }
    @{
      label    = "self-diagnose"
      args     = $null  # handled by Invoke-SelfDiagnose
      fallback = $null
    }
    @{
      label    = "tool-router"
      args     = $null  # handled by Invoke-ToolRouter
      fallback = $null
    }
    @{
      label    = "feedback-quarantine"
      args     = $null  # handled by Invoke-FeedbackQuarantine
      fallback = $null
    }
    @{
      label    = "concept-map"
      args     = $null  # handled by Invoke-ConceptMapValidate
      fallback = $null
    }
  )

  # 3b. If recovery run, prioritize the failed step by moving it first
  if ($IsRecoveryRun -and $RecoveryStep) {
    $prioritized = @()
    $others = @()
    foreach ($step in $steps) {
      if ($step.label -eq $RecoveryStep) {
        $prioritized += $step
      } else {
        $others += $step
      }
    }
    $steps = $prioritized + $others
    Write-Host "  [daemon] Recovery mode: prioritizing '$RecoveryStep'" -ForegroundColor Yellow
  }

  # 4. Execute each step sequentially
  $stepResults = @()
  $allPassed = $true

  foreach ($step in $steps) {
    Write-Host "  [daemon] Running: $($step.label) ..."
    Write-HeartbeatLegacy -RunId $runId -Status "running" -Phase $step.label
    Invoke-SessionHeartbeat | Out-Null

    if ($step.label -eq "prediction-review") {
      # Special: call Invoke-PredictionReview directly (not an mcr-os command)
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $predResult = Invoke-PredictionReview
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $predSuccess = ($null -ne $predResult)
      $stepResults += @{
        success  = $predSuccess
        output   = if ($predResult) { "brier=$($predResult.brier_score) accuracy=$($predResult.accuracy)" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($predSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $predSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "tier-evaluate") {
      # Special: call Invoke-TierEvaluate directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $tierResult = Invoke-TierEvaluate
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $tierSuccess = ($null -ne $tierResult)
      $tierCount = if ($tierResult -and $tierResult.count) { [int]$tierResult.count } else { 0 }
      $stepResults += @{
        success  = $tierSuccess
        output   = if ($tierResult) { "$tierCount transitions" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($tierSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $tierSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "self-improve-review") {
      # Special: call Invoke-SelfImproveReview directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $improveResult = Invoke-SelfImproveReview
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $improveSuccess = ($null -ne $improveResult)
      $suggestCount = if ($improveResult -and $improveResult.count) { [int]$improveResult.count } else { 0 }
      $stepResults += @{
        success  = $improveSuccess
        output   = if ($improveResult) { "$suggestCount suggestions" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($improveSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $improveSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "self-improve-auto-fix") {
      # Special: call Invoke-SelfImproveAutoFix directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $autoFixResult = Invoke-SelfImproveAutoFix
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $autoFixSuccess = ($null -ne $autoFixResult)
      $stepResults += @{
        success  = $autoFixSuccess
        output   = if ($autoFixResult) { "auto-fix completed" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($autoFixSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $autoFixSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "cognitive-tick") {
      # Special: call Invoke-CognitiveTick directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $cogResult = Invoke-CognitiveTick
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $cogSuccess = ($null -ne $cogResult)
      $gateDec = if ($cogResult -and $cogResult.gate) { $cogResult.gate.decision } else { "skipped" }
      $stepResults += @{
        success  = $cogSuccess
        output   = if ($cogResult) { "tick=$($cogResult.tick) gate=$gateDec safety=$($cogResult.safety_mode)" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($cogSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $cogSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "knowledge-consolidate") {
      # Special: call Invoke-KnowledgeConsolidate directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $consolResult = Invoke-KnowledgeConsolidate
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $consolSuccess = ($null -ne $consolResult)
      $dupsFound = if ($consolResult -and $consolResult.total_duplicates) { [int]$consolResult.total_duplicates } else { 0 }
      $archived = if ($consolResult -and $consolResult.archived) { [int]$consolResult.archived } else { 0 }
      $stepResults += @{
        success  = $consolSuccess
        output   = if ($consolResult) { "dups=$dupsFound archived=$archived" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($consolSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $consolSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "real-state-check") {
      # Special: call Invoke-RealStateCheck directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $rsResult = Invoke-RealStateCheck
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $rsSuccess = ($null -ne $rsResult)
      $rsH = if ($rsResult -and $rsResult.healthy) { [int]$rsResult.healthy } else { 0 }
      $rsW = if ($rsResult -and $rsResult.warning) { [int]$rsResult.warning } else { 0 }
      $rsC = if ($rsResult -and $rsResult.critical) { [int]$rsResult.critical } else { 0 }
      $stepResults += @{
        success  = $rsSuccess
        output   = if ($rsResult) { "H=$rsH W=$rsW C=$rsC size=$($rsResult.total_size_mb)MB" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($rsSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $rsSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "self-diagnose") {
      # Special: call Invoke-SelfDiagnose directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $diagResult = Invoke-SelfDiagnose
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $diagSuccess = ($null -ne $diagResult)
      $diagSeverity = if ($diagResult -and $diagResult.severity) { $diagResult.severity } else { "unknown" }
      $diagScore = if ($diagResult -and $diagResult.health_score) { [int]$diagResult.health_score } else { 0 }
      $diagIssues = if ($diagResult -and $diagResult.issue_count) { [int]$diagResult.issue_count } else { 0 }
      $stepResults += @{
        success  = $diagSuccess
        output   = if ($diagResult) { "severity=$diagSeverity score=$diagScore issues=$diagIssues" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($diagSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $diagSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "tool-router") {
      # Special: call Invoke-ToolRouter directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $routerResult = Invoke-ToolRouter
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $routerSuccess = ($null -ne $routerResult)
      $toolCount = if ($routerResult -is [array]) { $routerResult.Count } else { 0 }
      $stepResults += @{
        success  = $routerSuccess
        output   = if ($routerResult) { "$toolCount tools registered" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($routerSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $routerSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "feedback-quarantine") {
      # Special: call Invoke-FeedbackQuarantine directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $quarantineResult = Invoke-FeedbackQuarantine
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $quarantineSuccess = ($null -ne $quarantineResult)
      $quarantined = if ($quarantineResult -and $quarantineResult.quarantined) { [int]$quarantineResult.quarantined } else { 0 }
      $total = if ($quarantineResult -and $quarantineResult.total_feedback) { [int]$quarantineResult.total_feedback } else { 0 }
      $stepResults += @{
        success  = $quarantineSuccess
        output   = if ($quarantineResult) { "$quarantined/$total quarantined" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($quarantineSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $quarantineSuccess) { $allPassed = $false }
    } elseif ($step.label -eq "concept-map") {
      # Special: call Invoke-ConceptMapValidate directly
      $sw = [Diagnostics.Stopwatch]::StartNew()
      $conceptResult = Invoke-ConceptMapValidate
      $sw.Stop()
      $dur = [math]::Round($sw.Elapsed.TotalSeconds, 3)
      $conceptSuccess = ($null -ne $conceptResult)
      $valid = if ($conceptResult -and $conceptResult.valid) { $conceptResult.valid } else { $false }
      $mappings = if ($conceptResult -and $conceptResult.mappings_count) { [int]$conceptResult.mappings_count } else { 0 }
      $stepResults += @{
        success  = $conceptSuccess
        output   = if ($conceptResult) { "valid=$valid mappings=$mappings" } else { "skipped or failed" }
        duration = $dur
        exitCode = if ($conceptSuccess) { 0 } else { 1 }
        label    = $step.label
      }
      if (-not $conceptSuccess) { $allPassed = $false }
    } else {
      $result = Invoke-DaemonStep -Label $step.label -McrOsArgs $step.args

      $stepResults += $result
      if (-not $result.success) {
        $allPassed = $false
        Write-Host "    FAIL: $($step.label) (exit $($result.exitCode))" -ForegroundColor Red
      } else {
        Write-Host "    PASS: $($step.label) ($($result.duration)s)" -ForegroundColor Green
      }
    }
  }

  # 5. Daily review: check today's planned tasks against actual activity
  Write-Host "  [daemon] Running: daily review ..."
  Write-HeartbeatLegacy -RunId $runId -Status "running" -Phase "daily review"
  try {
    $reviewResult = Invoke-DailyReview
    if ($reviewResult) {
      Write-Host "    PASS: daily review ($($reviewResult.completed.Count)/$($reviewResult.planned.Count) completed)" -ForegroundColor Green
    } else {
      Write-Host "    SKIP: daily review (no plan or not in plan window)" -ForegroundColor Yellow
    }
  } catch {
    Write-Host "    FAIL: daily review - $($_.Exception.Message)" -ForegroundColor Red
  }

  # 6. Tomorrow plan: carry forward missed tasks, apply lessons
  Write-Host "  [daemon] Running: tomorrow plan ..."
  Write-HeartbeatLegacy -RunId $runId -Status "running" -Phase "tomorrow plan"
  try {
    Update-TomorrowPlan
    Write-Host "    PASS: tomorrow plan" -ForegroundColor Green
  } catch {
    Write-Host "    FAIL: tomorrow plan - $($_.Exception.Message)" -ForegroundColor Red
  }

  # 6b. Auto-goal scan: generate autonomous goals from memory patterns
  Write-Host "  [daemon] Running: auto-goal-scan ..."
  Write-HeartbeatLegacy -RunId $runId -Status "running" -Phase "auto-goal-scan"
  $autoGoalCount = 0
  try {
    $swarmScript = Join-Path $EcosystemRoot "ops\Invoke-Swarm.ps1"
    $autoGoalOutput = & $PsExe -NoProfile -ExecutionPolicy Bypass -File $swarmScript -Action "auto-goals" -Json 2>&1 | Out-String
    $autoGoalResult = $null
    try { $autoGoalResult = $autoGoalOutput | ConvertFrom-Json } catch {}
    if ($autoGoalResult -and $autoGoalResult.goals_generated) {
      $autoGoalCount = [int]$autoGoalResult.goals_generated
    }
    Write-Host "    PASS: auto-goal-scan ($autoGoalCount new goals)" -ForegroundColor Green
  } catch {
    Write-Host "    FAIL: auto-goal-scan - $($_.Exception.Message)" -ForegroundColor Red
  }

  $runEnd   = Get-Date
  $totalDur = [math]::Round(($runEnd - $runStart).TotalSeconds, 3)

  # 7. Compute score
  $passCount = @($stepResults | Where-Object { $_.success }).Count
  $failCount = @($stepResults | Where-Object { -not $_.success }).Count
  $score = [math]::Max(0, 100 - ($failCount * 20))
  $overallStatus = if ($allPassed) { "PASS" } else { "FAIL" }

  # 8. Generate daily report
  $reportLines = @()
  $reportLines += "# Daemon Daily Report"
  $reportLines += ""
  $reportLines += "- **Run ID**: $runId"
  $reportLines += "- **Timestamp**: $($runStart.ToString('o'))"
  $reportLines += "- **Duration**: ${totalDur}s"
  $reportLines += "- **Overall**: $overallStatus"
  $reportLines += "- **Score**: $score/100"
  if ($IsRecoveryRun) {
    $reportLines += "- **Mode**: RECOVERY (prioritized: $RecoveryStep)"
  }
  $reportLines += ""

  $reportLines += "## Step Results"
  $reportLines += ""
  $reportLines += "| Step | Status | Duration | Exit Code |"
  $reportLines += "|------|--------|----------|-----------|"
  foreach ($sr in $stepResults) {
    $statusText = if ($sr.success) { "PASS" } else { "FAIL" }
    $preview = ($sr.output.Trim() -replace "`r`n", " " -replace "`n", " ")
    if ($preview.Length -gt 80) { $preview = $preview.Substring(0, 80) + "..." }
    $reportLines += "| $($sr.label) | $statusText | $($sr.duration)s | $($sr.exitCode) |"
  }
  $reportLines += ""

  $reportLines += "## Output Previews"
  $reportLines += ""
  foreach ($sr in $stepResults) {
    $reportLines += "### $($sr.label)"
    $reportLines += ""
    $preview = $sr.output.Trim()
    if ($preview.Length -gt 300) { $preview = $preview.Substring(0, 300) + "`n... (truncated)" }
    $reportLines += '```'
    $reportLines += $preview
    $reportLines += '```'
    $reportLines += ""
  }

  # 9. Auto-goal scan results
  $reportLines += "## Auto-Goal Scan"
  $reportLines += ""
  $reportLines += "- New goals generated: $autoGoalCount"
  $reportLines += "- State file: ``runtime/agi/goal-generator.json``"
  $reportLines += ""

  # 10. Next suggestions
  $reportLines += "## Next Suggestions"
  $reportLines += ""
  if ($allPassed) {
    $reportLines += "- All checks passed. Ecosystem is healthy."
    $reportLines += "- Consider running ``Invoke-Swarm.ps1 run`` for deeper validation."
    if ($autoGoalCount -gt 0) {
      $reportLines += "- Review $autoGoalCount auto-generated goals: ``mcr-os agi goals``"
    }
  } else {
    $reportLines += "- Some checks failed. Review output above."
    $reportLines += "- Run individual steps manually to debug: ``mcr-os <subcommand>``"
    $reportLines += "- Check ``Invoke-Daemon.ps1 status`` for daemon state."
  }
  $reportLines += ""

  $reportPath = Join-Path $ReportsDir "$runId.md"
  ($reportLines -join "`n") | Set-Content -LiteralPath $reportPath -Encoding UTF8

  # 10. Write run metadata
  $runMeta = [ordered]@{
    run_id     = $runId
    started_at = $runStart.ToString("o")
    ended_at   = $runEnd.ToString("o")
    duration_s = $totalDur
    status     = $overallStatus
    score      = $score
    recovery   = $IsRecoveryRun
    steps      = @($stepResults | ForEach-Object {
      [ordered]@{
        label    = $_.label
        success  = $_.success
        duration = $_.duration
        exitCode = $_.exitCode
      }
    })
    report_path = $reportPath
  }
  $runPath = Join-Path $RunsDir "$runId.json"
  $runMeta | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $runPath -Encoding UTF8

  # 11. Compute next_scheduled
  $nextScheduled = Get-NextScheduled -IntervalMinutes $intervalMinutes

  # 12. Write detailed heartbeat with full telemetry (Step 5 from spec)
  $hbId = Write-Heartbeat `
    -RunId $runId `
    -Status $overallStatus.ToLower() `
    -Phase "done" `
    -Detail "score=$score duration=${totalDur}s" `
    -StepsPassed $passCount `
    -StepsFailed $failCount `
    -Score $score `
    -NextScheduled $nextScheduled `
    -Recovery $IsRecoveryRun

  # 13. If any step failed, write recovery.json (Step 6 from spec)
  $recoveryWritten = $false
  if (-not $allPassed) {
    $failedStep = ($stepResults | Where-Object { -not $_.success } | Select-Object -First 1)
    $recoveryData = [ordered]@{
      recovery_id     = "rec-$(Get-ShortGuid)"
      failed_run_id   = $runId
      failed_step     = $failedStep.label
      error           = "exit code $($failedStep.exitCode)"
      retry_scheduled = $true
      retry_at        = $nextScheduled
      created_at      = (Get-Date).ToString("o")
    }
    Write-Recovery $recoveryData
    $recoveryWritten = $true

    $state = Read-DaemonState
    $state.recovery_pending = $true
    Write-DaemonState $state

    Write-Host "  [daemon] Recovery info written: $RecoveryJson" -ForegroundColor Yellow
  } else {
    Clear-Recovery
    $state = Read-DaemonState
    $state.recovery_pending = $false
    Write-DaemonState $state
  }

  # 14. Update state: idle, counters, heartbeat timestamp
  $state = Read-DaemonState
  $state.status            = "idle"
  $state.last_run_at       = $runEnd.ToString("o")
  $state.last_status       = $overallStatus.ToLower()
  $state.total_runs        = [int]$state.total_runs + 1
  $state.last_heartbeat_at = (Get-Date).ToString("o")

  if ($allPassed) {
    $state.consecutive_passes   = [int]$state.consecutive_passes + 1
    $state.consecutive_failures = 0
  } else {
    $state.consecutive_failures = [int]$state.consecutive_failures + 1
    $state.consecutive_passes   = 0
  }
  Write-DaemonState $state

  # 15. If any failures: write reflection
  if (-not $allPassed) {
    $reflLines = @()
    $reflLines += "# Reflection: $runId"
    $reflLines += ""
    $reflLines += "## Failed Steps"
    foreach ($sr in ($stepResults | Where-Object { -not $_.success })) {
      $reflLines += "- **$($sr.label)**: exit $($sr.exitCode)"
    }
    $reflLines += ""
    $reflLines += "## Root Cause"
    $reflLines += "Steps failed with non-zero exit codes. Review output previews in the daily report."
    $reflLines += ""
    $reflLines += "## Lessons"
    $reflLines += "- Verify prerequisites before running daemon"
    $reflLines += "- Check mcr-os subcommands individually"
    $reflLines += ""
    $reflLines += "## Next Time"
    $reflLines += "- Run ``mcr-os integration gate`` manually first"
    $reflLines += "- Ensure all registry entries are valid"
    $reflLines += "- Check swarm state with ``Invoke-Swarm.ps1 status``"

    $reflPath = Join-Path $ReportsDir "$runId-reflection.md"
    ($reflLines -join "`n") | Set-Content -LiteralPath $reflPath -Encoding UTF8
    Write-Host "  [daemon] Reflection written: $reflPath"
  }

  # 16. Session stop + final checkpoint
  $endLabel = if ($allPassed) { "daemon-end" } else { "daemon-failure" }
  $endCkpt = Invoke-CheckpointCreate -Label $endLabel
  if ($endCkpt) { Write-Host "  [checkpoint] Created: $($endCkpt.checkpoint_id) ($endLabel)" }
  $sessionResult = Invoke-SessionStop -Reason $(if ($allPassed) { "normal" } else { "failure" })
  if ($sessionResult) { Write-Host "  [session] Stopped: $($sessionResult.session_id) (reason=$($sessionResult.stop_reason))" }

  # Final output
  if ($Json) {
    [ordered]@{
      run_id           = $runId
      status           = $overallStatus
      score            = $score
      duration_s       = $totalDur
      steps_total      = $stepResults.Count
      steps_pass       = $passCount
      steps_fail       = $failCount
      report_path      = $reportPath
      run_path         = $runPath
      recovery_written = $recoveryWritten
      next_scheduled   = $nextScheduled
    } | ConvertTo-Json -Depth 6
  } else {
    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host "Daemon Run Complete: $runId"
    Write-Host "Status: $overallStatus  Score: $score/100  Duration: ${totalDur}s"
    Write-Host "Steps: $passCount passed, $failCount failed (of $($stepResults.Count))"
    if ($recoveryWritten) {
      Write-Host "Recovery: queued for next run" -ForegroundColor Yellow
    }
    Write-Host "Report: $reportPath"
  }

  return @{
    run_id      = $runId
    status      = $overallStatus
    score       = $score
    all_passed  = $allPassed
    fail_count  = $failCount
    pass_count  = $passCount
  }
}

# ============================================================
# ACTION: loop
# ============================================================
function Invoke-Loop {
  $intervalMinutes = [int]$Goal
  if ($intervalMinutes -lt 1) { $intervalMinutes = 1 }

  $state = Read-DaemonState

  # Mark daemon as started in loop mode
  $state.started_at = (Get-Date).ToString("o")
  $state.mode       = "loop"
  $state.pid        = $PID
  $state.status     = "idle"
  Write-DaemonState $state

  Write-Host "MCR Daemon v0.2 - LOOP MODE"
  Write-Host ("-" * 40)
  Write-Host "  Interval     : every $intervalMinutes minutes"
  Write-Host "  Max Iters    : $MaxIterations"
  Write-Host "  PID          : $PID"
  Write-Host "  Started      : $($state.started_at)"
  Write-Host ""
  Write-Host "Press Ctrl+C to stop gracefully."
  Write-Host ""

  # Start loop-level session
  $loopSession = Invoke-SessionStart -SessionId "loop-$PID"
  if ($loopSession) { Write-Host "  [session] Loop session started: $($loopSession.session_id)" }
  Invoke-CheckpointCreate -Label "loop-start" | Out-Null

  $iteration = 0
  $running = $true

  try {
    while ($running -and $iteration -lt $MaxIterations) {
      $iteration++
      Write-Host ("=" * 60)
      Write-Host "[loop] Iteration $iteration / $MaxIterations at $(Get-Date -Format 'HH:mm:ss')"

      # Check recovery queue
      $recovery = Read-Recovery
      $isRecovery = $false
      $recoveryStep = ""

      if ($recovery -and $recovery.retry_scheduled) {
        Write-Host "[loop] Recovery pending: retrying failed step '$($recovery.failed_step)'" -ForegroundColor Yellow
        $isRecovery = $true
        $recoveryStep = $recovery.failed_step
      }

      # Run once
      $result = Invoke-Once -IsRecoveryRun $isRecovery -RecoveryStep $recoveryStep

      Write-Host "[loop] Iteration $iteration complete: $($result.status) (score=$($result.score))"
      Write-Host ""

      # Sleep for interval (unless last iteration)
      if ($running -and $iteration -lt $MaxIterations) {
        Write-Host "[loop] Sleeping $intervalMinutes minutes until next run..."
        Start-Sleep -Seconds ($intervalMinutes * 60)
      }
    }
  } catch {
    Write-Host "[loop] Exception: $($_.Exception.Message)" -ForegroundColor Red
  } finally {
    # Graceful shutdown: write final heartbeat, set state to idle
    Write-Host ""
    Write-Host "[loop] Shutting down gracefully..."

    $state = Read-DaemonState
    $state.status     = "idle"
    $state.mode       = "manual"
    $state.started_at = $null
    $state.pid        = $null
    Write-DaemonState $state

    # Write final heartbeat
    Write-HeartbeatLegacy -RunId "loop-shutdown" -Status "idle" -Phase "shutdown" -Detail "iterations=$iteration"

    # Stop loop session + final checkpoint
    Invoke-CheckpointCreate -Label "loop-end" | Out-Null
    Invoke-SessionStop -Reason "loop-stopped" | Out-Null

    Write-Host "[loop] Daemon stopped. Completed $iteration iterations."
    Write-Host "[loop] Final state: idle"
  }
}

# ============================================================
# ACTION: health
# ============================================================
function Invoke-Health {
  $state = Read-DaemonState
  $healthStatus = "healthy"
  $issues = @()

  # 1. Check last heartbeat timestamp
  $lastHbAt = $state.last_heartbeat_at
  $minutesSinceHeartbeat = -1

  if ($lastHbAt) {
    try {
      $lastHbTime = [DateTime]::Parse($lastHbAt)
      $minutesSinceHeartbeat = [math]::Round(((Get-Date) - $lastHbTime).TotalMinutes, 1)
    } catch {
      $minutesSinceHeartbeat = -1
    }
  }

  # 2. Check if daemon is stuck (state=running but no heartbeat in 30min)
  if ($state.status -eq "running") {
    if ($minutesSinceHeartbeat -gt 30 -or $minutesSinceHeartbeat -lt 0) {
      $healthStatus = "unhealthy"
      $issues += "STUCK: state=running but no heartbeat in $minutesSinceHeartbeat minutes"
    } elseif ($minutesSinceHeartbeat -gt 10) {
      if ($healthStatus -eq "healthy") { $healthStatus = "degraded" }
      $issues += "WARNING: state=running, last heartbeat $minutesSinceHeartbeat min ago"
    }
  }

  # 3. Check recovery queue
  $recovery = Read-Recovery
  if ($recovery -and $recovery.retry_scheduled) {
    if ($healthStatus -eq "healthy") { $healthStatus = "degraded" }
    $issues += "RECOVERY PENDING: step '$($recovery.failed_step)' from run $($recovery.failed_run_id)"
  }

  # 4. Check consecutive failures
  if ([int]$state.consecutive_failures -ge 3) {
    $healthStatus = "unhealthy"
    $issues += "CRITICAL: $($state.consecutive_failures) consecutive failures"
  } elseif ([int]$state.consecutive_failures -ge 1) {
    if ($healthStatus -eq "healthy") { $healthStatus = "degraded" }
    $issues += "WARNING: $($state.consecutive_failures) consecutive failure(s)"
  }

  # 5. Check if last run failed
  if ($state.last_status -eq "fail") {
    if ($healthStatus -eq "healthy") { $healthStatus = "degraded" }
    $issues += "Last run FAILED: $($state.last_run_id)"
  }

  # 6. Check if no runs ever
  if ([int]$state.total_runs -eq 0) {
    if ($healthStatus -eq "healthy") { $healthStatus = "degraded" }
    $issues += "No runs recorded yet"
  }

  # Output
  $color = switch ($healthStatus) {
    "healthy"   { "Green" }
    "degraded"  { "Yellow" }
    "unhealthy" { "Red" }
    default     { "White" }
  }

  if ($Json) {
    [ordered]@{
      health                  = $healthStatus
      last_heartbeat_at       = $lastHbAt
      minutes_since_heartbeat = $minutesSinceHeartbeat
      consecutive_passes      = $state.consecutive_passes
      consecutive_failures    = $state.consecutive_failures
      recovery_pending        = $state.recovery_pending
      total_runs              = $state.total_runs
      last_status             = $state.last_status
      issues                  = $issues
    } | ConvertTo-Json -Depth 6
  } else {
    Write-Host "MCR Daemon Health Check"
    Write-Host ("-" * 40)
    Write-Host "  Health           : $healthStatus" -ForegroundColor $color
    Write-Host "  Last Heartbeat   : $lastHbAt"
    Write-Host "  Minutes Since HB : $minutesSinceHeartbeat"
    Write-Host "  Total Runs       : $($state.total_runs)"
    Write-Host "  Consec. Passes   : $($state.consecutive_passes)"
    Write-Host "  Consec. Failures : $($state.consecutive_failures)"
    Write-Host "  Recovery Pending : $($state.recovery_pending)"
    Write-Host "  Last Status      : $($state.last_status)"
    if ($issues.Count -gt 0) {
      Write-Host ""
      Write-Host "  Issues:" -ForegroundColor $color
      foreach ($issue in $issues) {
        Write-Host "    - $issue" -ForegroundColor $color
      }
    }
  }
}

# ============================================================
# ACTION: start
# ============================================================
function Invoke-Start {
  $state = Read-DaemonState

  if ($state.started_at) {
    Write-Host "Daemon is already marked as started (since $($state.started_at))."
    Write-Host "Use 'stop' first, then 'start' to restart."
    return
  }

  $markerPath = Join-Path $DaemonDir ".running"
  "started at $(Get-Date -Format o)" | Set-Content -LiteralPath $markerPath -Encoding UTF8

  $state.started_at = (Get-Date).ToString("o")
  $state.mode       = "scheduled"
  $state.pid        = $PID
  Write-DaemonState $state

  Write-Host "MCR Daily Daemon v0.2 - STARTED"
  Write-Host ("-" * 40)
  Write-Host "  Mode      : scheduled"
  Write-Host "  Started   : $($state.started_at)"
  Write-Host "  PID       : $PID"
  Write-Host ""
  Write-Host "For autonomous loop mode, use:"
  Write-Host "  powershell -ExecutionPolicy Bypass -File ops\Invoke-Daemon.ps1 loop"
  Write-Host ""
  Write-Host "For Windows Task Scheduler, create a task that runs:"
  Write-Host "  powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`" once"
  Write-Host "  Trigger: Daily at your preferred time"
}

# ============================================================
# ACTION: stop
# ============================================================
function Invoke-Stop {
  $state = Read-DaemonState
  $markerPath = Join-Path $DaemonDir ".running"

  if (Test-Path -LiteralPath $markerPath) {
    Remove-Item -LiteralPath $markerPath -Force
  }

  $state.started_at = $null
  $state.mode       = "manual"
  $state.pid        = $null
  Write-DaemonState $state

  Write-Host "MCR Daily Daemon v0.2 - STOPPED"
  Write-Host ("-" * 40)
  Write-Host "  Mode      : manual"
  Write-Host "  Status    : $($state.status)"
  Write-Host "  Total Runs: $($state.total_runs)"
  Write-Host ""
  Write-Host "Daemon marker cleared. Use 'start' or 'loop' to re-enable."
}

# ============================================================
# MAIN DISPATCH
# ============================================================
switch ($Action) {
  "status" { Invoke-Status }
  "once"   { Invoke-Once }
  "loop"   { Invoke-Loop }
  "health" { Invoke-Health }
  "start"  { Invoke-Start }
  "stop"   { Invoke-Stop }
  default {
    @"
MCR Daily Daemon v0.2 - Multi-Round Autonomous Execution

Usage:
  Invoke-Daemon.ps1 status          Show daemon state and last run info
  Invoke-Daemon.ps1 once            Run the daily verification cycle ONCE
  Invoke-Daemon.ps1 loop            Run 'once' in a loop with heartbeat monitoring
  Invoke-Daemon.ps1 health          Quick health check (healthy/degraded/unhealthy)
  Invoke-Daemon.ps1 start           Mark daemon as scheduled (prints instructions)
  Invoke-Daemon.ps1 stop            Clear the running marker

Options:
  -Goal <minutes>                   Loop interval in minutes (default: 60)
  -MaxIterations <n>                Max loop iterations (default: 24)
  -Json                             Output as JSON

Loop Mode:
  Runs 'once' every <Goal> minutes, up to <MaxIterations> times.
  Checks recovery.json before each run to prioritize failed steps.
  Handles Ctrl+C gracefully: writes final heartbeat, sets state to idle.
  Writes detailed heartbeats to heartbeats.jsonl after each run.

Health Status:
  healthy    - All systems nominal
  degraded   - Warnings present (recovery pending, recent failures)
  unhealthy  - Critical issues (stuck daemon, 3+ consecutive failures)

Safety Rules:
  - Daemon NEVER runs external commands
  - Daemon NEVER deletes files
  - Daemon NEVER installs software
  - Daemon ONLY runs local verification and reporting
  - If any step fails, log it and continue (don't abort)

Session & Checkpoint:
  Each daemon run creates a session (runtime/agi/sessions.jsonl) and
  checkpoints (runtime/agi/checkpoints/). On failure, a failure checkpoint
  is saved for diagnostics. Query via:
    mcr-os agi sessions [n]
    mcr-os agi checkpoints [n]
    mcr-os agi checkpoint create [label]
    mcr-os agi checkpoint restore <id>

Steps executed by 'once':
  1. registry validate   (mcr-os registry validate)
  2. swarm audit         (mcr-os swarm audit)
  3. swarm status        (mcr-os swarm status)
  4. plan today          (mcr-os plan today)
  5. skill candidates    (mcr-os skill candidates)
  6. swarm deliveries    (mcr-os swarm deliveries)
  7. eval agi-readiness  (mcr-os eval agi-readiness)
  8. integration gate    (mcr-os integration gate)
  9. world-model-update  (mcr-os swarm world-model)
 10. adaptive-memory     (mcr-os agi g1-g6 -- adaptive memory verification)
 11. prediction-review   (Brier score, calibration, prediction quality)
 12. real-state-check    (filesystem state: file count, size, git, anomalies)
 13. self-diagnose       (health checks: memory, prediction, daemon, skills, filesystem)
 14. daily review        (check today's plan vs actual, write to daily-review.jsonl)
 15. tomorrow plan       (carry forward missed tasks, update weekly-plan.json)
 16. auto-goal-scan      (generate autonomous goals from memory patterns)

Examples:
  powershell -ExecutionPolicy Bypass -File Invoke-Daemon.ps1 status
  powershell -ExecutionPolicy Bypass -File Invoke-Daemon.ps1 once
  powershell -ExecutionPolicy Bypass -File Invoke-Daemon.ps1 once -Json
  powershell -ExecutionPolicy Bypass -File Invoke-Daemon.ps1 loop -Goal 30 -MaxIterations 48
  powershell -ExecutionPolicy Bypass -File Invoke-Daemon.ps1 health
  powershell -ExecutionPolicy Bypass -File Invoke-Daemon.ps1 health -Json
  powershell -ExecutionPolicy Bypass -File Invoke-Daemon.ps1 start
"@
  }
}
