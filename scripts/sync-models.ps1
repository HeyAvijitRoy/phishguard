$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

$sourceDir = Join-Path $repoRoot "ml\export\onnx"
$targetDir = Join-Path $repoRoot "addin\public\models"

$files = @(
  "vocab.txt",
  "labels.json",
  "phish_intent.onnx",
  "phish_binary.onnx",
  "phish_binary_labels.json"
)

if (-not (Test-Path $sourceDir)) {
  throw "Source directory not found: $sourceDir"
}

if (-not (Test-Path $targetDir)) {
  throw "Target directory not found: $targetDir"
}

foreach ($name in $files) {
  $src = Join-Path $sourceDir $name
  $dst = Join-Path $targetDir $name

  if (-not (Test-Path $src)) {
    throw "Missing required export artifact: $src"
  }

  Copy-Item $src $dst -Force
}

Write-Host "Synced ONNX artifacts to addin/public/models"
