<#
Resets the password of the local PostgreSQL 16 superuser "postgres" when it has been forgotten.

Run from an *Administrator* PowerShell:
    powershell -ExecutionPolicy Bypass -File scripts\reset_postgres_password.ps1

What it does:
  1. Backs up pg_hba.conf and temporarily allows passwordless login for "postgres" from localhost only.
  2. Restarts the postgresql-x64-16 service, sets the new password you type (hidden input).
  3. Always restores the original pg_hba.conf and restarts the service again, even on error.
The new password is sent to psql over stdin; it is never printed, logged or written to disk.
#>
$ErrorActionPreference = "Stop"

$serviceName = "postgresql-x64-16"
$pgBin = "C:\Program Files\PostgreSQL\16\bin"
$dataDir = "C:\Program Files\PostgreSQL\16\data"
$hba = Join-Path $dataDir "pg_hba.conf"
$backup = Join-Path $dataDir "pg_hba.conf.brightloop-backup"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Please run this from an Administrator PowerShell (right-click PowerShell > Run as administrator)." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $hba)) { throw "pg_hba.conf not found at $hba" }
if (Test-Path $backup) { throw "A previous backup exists at $backup. Restore or delete it manually before re-running." }

function Read-Secret([string]$prompt) {
    $secure = Read-Host $prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

$newPassword = Read-Secret "New password for PostgreSQL user 'postgres'"
$confirm = Read-Secret "Type it again"
if ($newPassword -ne $confirm) { Write-Host "Passwords do not match." -ForegroundColor Red; exit 1 }
if ($newPassword.Length -lt 8) { Write-Host "Use at least 8 characters." -ForegroundColor Red; exit 1 }

Copy-Item $hba $backup
try {
    $trust = "# TEMPORARY (reset_postgres_password.ps1)`r`nhost all postgres 127.0.0.1/32 trust`r`nhost all postgres ::1/128 trust`r`n"
    Set-Content -Path $hba -Value ($trust + (Get-Content $hba -Raw)) -Encoding ASCII -NoNewline
    Write-Host "Restarting $serviceName ..."
    Restart-Service $serviceName

    $escaped = $newPassword.Replace("'", "''")
    "ALTER USER postgres WITH PASSWORD '$escaped';" | & "$pgBin\psql.exe" -w -h 127.0.0.1 -p 5432 -U postgres -d postgres -q -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw "psql failed with exit code $LASTEXITCODE" }
    Write-Host "Password for 'postgres' changed." -ForegroundColor Green
}
finally {
    Copy-Item $backup $hba -Force
    Remove-Item $backup
    Write-Host "Restored original pg_hba.conf; restarting $serviceName ..."
    Restart-Service $serviceName
}

Write-Host ""
Write-Host "Next, run (normal PowerShell is fine) and enter the new password when asked:" -ForegroundColor Cyan
Write-Host "    powershell -ExecutionPolicy Bypass -File scripts\create_database.ps1"
