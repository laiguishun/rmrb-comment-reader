$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = "python"
if (Test-Path "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe") {
    $Python = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}

& $Python collector.py --limit 2 --output-dir public/data --content-mode full

Write-Host ""
Write-Host "采集完成。打开 http://localhost:8765/ 可预览阅读器。"
