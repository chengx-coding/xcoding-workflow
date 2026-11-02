# Compact helpers around `xcoding runtime` for work order
# 20261102-1145-open-sandbox-xc-044. Process file: workbench tmp only.
$script:Tree = '.xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml'
$script:Agent = 'session-9d0786d6-9a56-472b-a45c-c034f4125ccc'

function Invoke-Rt {
  param([string[]]$CliArgs)
  $json = & xcoding runtime @CliArgs 2>&1 | Out-String
  try { return ($json | ConvertFrom-Json) } catch { return [pscustomobject]@{ ok = $false; raw = $json } }
}

function RtNext {
  $r = Invoke-Rt (@('next', '--tree', $script:Tree))
  if (-not $r.ok) { $r | ConvertTo-Json -Depth 4; return }
  Write-Host ("status={0} revision={1}" -f $r.status, $r.revision)
  foreach ($n in $r.ready) { Write-Host ("READY {0}  [{1}]" -f $n.id, $n.role) }
  foreach ($g in $r.awaiting_dynamic_groups) { Write-Host ("AWAITING {0}" -f $g.id) }
}

function RtSet {
  param([string[]]$Pairs)
  $a = @('set', '--tree', $script:Tree)
  foreach ($p in $Pairs) { $a += @('--set', $p) }
  $r = Invoke-Rt $a
  if ($r.ok) { Write-Host "set ok revision=$($r.revision)" } else { $r | ConvertTo-Json -Depth 6 }
}

function RtStart {
  param([string]$Node)
  $r = Invoke-Rt (@('start', '--tree', $script:Tree, '--node', $Node, '--agent', $script:Agent))
  if ($r.ok) { Write-Host "started $Node revision=$($r.revision)" } else { $r | ConvertTo-Json -Depth 6 }
}

function RtComplete {
  param([string]$Node, [string]$Summary, [string]$Validation, [string[]]$Artifacts = @(), [string[]]$CheckJson = @())
  $a = @('complete', '--tree', $script:Tree, '--node', $Node)
  if ($Summary) { $a += @('--summary', $Summary) }
  if ($Validation) { $a += @('--validation', $Validation) }
  foreach ($p in $Artifacts) { $a += @('--artifact', $p) }
  $i = 0
  foreach ($c in $CheckJson) {
    $i += 1
    $file = Join-Path $PSScriptRoot ("check-result-$i.json")
    [System.IO.File]::WriteAllText($file, $c, [System.Text.UTF8Encoding]::new($false))
    $a += @('--check-result-file', $file)
  }
  $r = Invoke-Rt $a
  if ($r.ok) {
    Write-Host "completed $Node status=$($r.node.status) revision=$($r.revision)"
  } else {
    Write-Host "COMPLETE FAILED for $Node"
    $r | ConvertTo-Json -Depth 8
  }
}

function RtFail {
  param([string]$Node, [string]$Reason, [string[]]$Artifacts = @())
  $a = @('fail', '--tree', $script:Tree, '--node', $Node, '--reason', $Reason)
  foreach ($p in $Artifacts) { $a += @('--artifact', $p) }
  $r = Invoke-Rt $a
  if ($r.ok) { Write-Host "failed $Node" } else { $r | ConvertTo-Json -Depth 6 }
}

function RtBlock {
  param([string]$Node, [string]$Reason, [string[]]$Artifacts = @())
  $a = @('block', '--tree', $script:Tree, '--node', $Node, '--reason', $Reason)
  foreach ($p in $Artifacts) { $a += @('--artifact', $p) }
  $r = Invoke-Rt $a
  if ($r.ok) { Write-Host "blocked $Node" } else { $r | ConvertTo-Json -Depth 6 }
}

function RtEmbed {
  param([string]$Parent, [string]$Template, [string]$InstanceId)
  $a = @('embed-subtree', '--tree', $script:Tree, '--parent', $Parent, '--template', $Template)
  if ($InstanceId) { $a += @('--instance-id', $InstanceId) }
  $r = Invoke-Rt $a
  if ($r.ok) { Write-Host "embedded $Template as $InstanceId under $Parent revision=$($r.revision)" } else { $r | ConvertTo-Json -Depth 6 }
}

function RtCloseGroup {
  param([string]$Group)
  $r = Invoke-Rt (@('close-group', '--tree', $script:Tree, '--group', $Group))
  if ($r.ok) { Write-Host "closed $Group revision=$($r.revision)" } else { $r | ConvertTo-Json -Depth 6 }
}

function RtReceipt {
  # Runs xc-document validation and returns the compact receipt JSON plus a summary line.
  param([string]$Document, [string]$Kind, [string]$Audience = '')
  $json = python "$env:USERPROFILE\.agents\skills\xc-document\scripts\validate_document.py" --document $Document --expected-kind $Kind 2>&1 | Out-String
  $obj = $json | ConvertFrom-Json
  if (-not $obj.ok) {
    Write-Host "DOCUMENT INVALID: $Document"
    $obj | ConvertTo-Json -Depth 8
    return $null
  }
  $receipt = [pscustomobject]@{
    schema_version = 1
    check          = $obj.receipt.check
    ok             = $obj.receipt.ok
    subject        = $obj.receipt.subject
    facts          = [pscustomobject]@{
      document_kind    = $obj.receipt.facts.document_kind
      content_language = $obj.receipt.facts.content_language
      audience         = $obj.receipt.facts.audience
    }
  }
  $compact = $receipt | ConvertTo-Json -Compress -Depth 5
  Write-Host "receipt ok for $Document (audience='$($receipt.facts.audience)')"
  return $compact
}
