<#
Creates the local PostgreSQL role and databases for Brightloop and writes backend settings to .env.

  powershell -ExecutionPolicy Bypass -File scripts\create_database.ps1

- Prompts for the `postgres` superuser password (never stored or printed).
- Creates/updates role `brightloop_app` with a freshly generated random password.
- Creates databases `brightloop_sms` and `brightloop_sms_test` owned by that role (if missing).
- Writes .env from .env.example with the generated DB password and a random JWT secret.
  An existing .env is left untouched unless -Force is given (then it is backed up to .env.bak).
#>
param(
    [string]$PgBin = "C:\Program Files\PostgreSQL\16\bin",
    [int]$Port = 5432,
    [switch]$Force
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
$exampleFile = Join-Path $root ".env.example"
$psql = Join-Path $PgBin "psql.exe"

if (-not (Test-Path $psql)) { throw "psql.exe not found at $psql. Pass -PgBin <path to PostgreSQL bin>." }
if ((Test-Path $envFile) -and -not $Force) {
    throw ".env already exists. Re-run with -Force to regenerate it (the old file is saved as .env.bak)."
}

function New-RandomString([int]$Length) {
    $chars = [char[]]"abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    $bytes = New-Object byte[] $Length
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

function Invoke-Psql([string]$Sql) {
    $out = & $psql -h localhost -p $Port -U postgres -d postgres -v ON_ERROR_STOP=1 -tAc $Sql
    if ($LASTEXITCODE -ne 0) { throw "psql command failed." }
    return ($out | Out-String).Trim()
}

$secure = Read-Host "Password for PostgreSQL superuser 'postgres'" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $appPassword = New-RandomString 32
    $jwtSecret = New-RandomString 64

    if ((Invoke-Psql "SELECT 1 FROM pg_roles WHERE rolname = 'brightloop_app'") -eq "1") {
        Invoke-Psql "ALTER ROLE brightloop_app WITH LOGIN PASSWORD '$appPassword'" | Out-Null
        Write-Host "Updated role brightloop_app."
    } else {
        Invoke-Psql "CREATE ROLE brightloop_app LOGIN PASSWORD '$appPassword'" | Out-Null
        Write-Host "Created role brightloop_app."
    }
    foreach ($db in @("brightloop_sms", "brightloop_sms_test")) {
        if ((Invoke-Psql "SELECT 1 FROM pg_database WHERE datname = '$db'") -ne "1") {
            Invoke-Psql "CREATE DATABASE $db OWNER brightloop_app" | Out-Null
            Write-Host "Created database $db."
        } else {
            Write-Host "Database $db already exists."
        }
    }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if (Test-Path $envFile) { Copy-Item $envFile "$envFile.bak" -Force }
$content = Get-Content $exampleFile -Raw
$content = $content.Replace("brightloop_app:CHANGE_ME@", "brightloop_app:$appPassword@")
$content = $content.Replace("JWT_SECRET_KEY=CHANGE_ME", "JWT_SECRET_KEY=$jwtSecret")
[IO.File]::WriteAllText($envFile, $content, (New-Object Text.UTF8Encoding($false)))
Write-Host "Wrote $envFile (not committed; listed in .gitignore). Done."
