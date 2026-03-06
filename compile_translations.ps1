# Compile translation files for CManager.

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "CManager Translation Compiler" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

$fallbackGettextBin = "C:\Program Files\gettext-iconv\bin"
if ((-not (Get-Command msgfmt -ErrorAction SilentlyContinue)) -and (Test-Path $fallbackGettextBin)) {
    $env:Path = "$fallbackGettextBin;$env:Path"
}

if (-not (Get-Command msgfmt -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: msgfmt is not available in PATH." -ForegroundColor Red
    Write-Host "Add to PATH: C:\Program Files\gettext-iconv\bin" -ForegroundColor White
    exit 1
}

$enPoFile = "locale\en\LC_MESSAGES\django.po"
$zhPoFile = "locale\zh_Hans\LC_MESSAGES\django.po"

$hasAnyPo = $false
if (Test-Path $enPoFile) {
    Write-Host "Found: $enPoFile" -ForegroundColor Green
    $hasAnyPo = $true
}
if (Test-Path $zhPoFile) {
    Write-Host "Found: $zhPoFile" -ForegroundColor Green
    $hasAnyPo = $true
}

if (-not $hasAnyPo) {
    Write-Host "ERROR: no .po files found. Run .\\make_translations.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Compiling messages..." -ForegroundColor Yellow
python manage.py compilemessages
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: compilemessages failed. Check .po format." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "OK: translation files compiled successfully." -ForegroundColor Green
Write-Host "Restart Django server to apply changes." -ForegroundColor Yellow
