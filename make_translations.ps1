# Generate translation files for CManager.

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "CManager i18n Translation Generator" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Checking gettext tools..." -ForegroundColor Yellow
$fallbackGettextBin = "C:\Program Files\gettext-iconv\bin"
if ((-not (Get-Command msgfmt -ErrorAction SilentlyContinue)) -and (Test-Path $fallbackGettextBin)) {
    $env:Path = "$fallbackGettextBin;$env:Path"
}

$msgfmtCmd = Get-Command msgfmt -ErrorAction SilentlyContinue
$msguniqCmd = Get-Command msguniq -ErrorAction SilentlyContinue
if ((-not $msgfmtCmd) -or (-not $msguniqCmd)) {
    Write-Host "ERROR: gettext is not available in PATH." -ForegroundColor Red
    Write-Host "Install gettext, then reopen this terminal." -ForegroundColor Yellow
    Write-Host "Windows (Chocolatey): choco install gettext" -ForegroundColor White
    Write-Host "Or add to PATH: C:\Program Files\gettext-iconv\bin" -ForegroundColor White
    exit 1
}
Write-Host "OK: gettext found." -ForegroundColor Green

Write-Host ""
Write-Host "Generating English messages..." -ForegroundColor Yellow
python manage.py makemessages -l en --ignore=venv --ignore=env --ignore=staticfiles
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: failed to generate en messages." -ForegroundColor Red
    exit 1
}
Write-Host "OK: locale/en/LC_MESSAGES/django.po updated." -ForegroundColor Green

Write-Host ""
Write-Host "Generating Simplified Chinese messages..." -ForegroundColor Yellow
python manage.py makemessages -l zh_Hans --ignore=venv --ignore=env --ignore=staticfiles
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: failed to generate zh_Hans messages." -ForegroundColor Red
    exit 1
}
Write-Host "OK: locale/zh_Hans/LC_MESSAGES/django.po updated." -ForegroundColor Green

Write-Host ""
Write-Host "Done. Next steps:" -ForegroundColor Cyan
Write-Host "1. Review locale/en/LC_MESSAGES/django.po" -ForegroundColor White
Write-Host "2. Run .\\compile_translations.ps1" -ForegroundColor White
Write-Host "3. Restart Django server" -ForegroundColor White
