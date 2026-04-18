param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$ComposeFile = ".\docker-compose.yml",
    [string]$ApiService = "api",
    [string]$DbService = "db",
    [string]$MinioService = "minio",
    [string]$DbName = "fsa_db",
    [string]$DbUser = "fsa"
)

$ErrorActionPreference = "Stop"

function Invoke-Compose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    & docker compose -f $ComposeFile @Args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($Args -join ' ')"
    }
}

$resolvedBackupPath = [System.IO.Path]::GetFullPath($BackupPath)
$dbDumpHostPath = Join-Path $resolvedBackupPath "postgres.dump"
$minioDataHostPath = Join-Path $resolvedBackupPath "minio-data"
$manifestPath = Join-Path $resolvedBackupPath "backup-manifest.json"
$dbDumpContainerPath = "/tmp/restore.dump"

if (-not (Test-Path -LiteralPath $dbDumpHostPath -PathType Leaf)) {
    throw "Backup file not found: $dbDumpHostPath"
}

if (-not (Test-Path -LiteralPath $minioDataHostPath -PathType Container)) {
    throw "MinIO backup directory not found: $minioDataHostPath"
}

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Backup manifest not found: $manifestPath"
}

Invoke-Compose up -d $DbService $MinioService
Invoke-Compose stop $ApiService

Invoke-Compose cp $dbDumpHostPath "${DbService}:$dbDumpContainerPath"
Invoke-Compose exec -T $DbService dropdb -U $DbUser --if-exists $DbName
Invoke-Compose exec -T $DbService createdb -U $DbUser $DbName
Invoke-Compose exec -T $DbService pg_restore -U $DbUser -d $DbName --clean --if-exists --no-owner --no-privileges $dbDumpContainerPath
Invoke-Compose exec -T $DbService rm -f $dbDumpContainerPath

Invoke-Compose exec -T $MinioService sh -c "find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} +"
Invoke-Compose cp (Join-Path $minioDataHostPath ".") "${MinioService}:/data"

Invoke-Compose up -d $ApiService

$manifest = Get-Content -Path $manifestPath -Raw | ConvertFrom-Json
Write-Host "Restore completed from $resolvedBackupPath"
Write-Host "Backup Alembic version: $($manifest.alembic_version)"
