param(
    [string]$ComposeFile = ".\docker-compose.yml",
    [string]$OutputRoot = ".\backups",
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

function Assert-RunningService {
    param(
        [string]$ServiceName
    )

    $runningServices = @(Invoke-Compose ps --services --status running)
    if ($runningServices -notcontains $ServiceName) {
        throw "Required service '$ServiceName' is not running."
    }
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$backupRootPath = [System.IO.Path]::GetFullPath($OutputRoot)
$backupPath = Join-Path $backupRootPath $timestamp
$dbDumpContainerPath = "/tmp/postgres-$timestamp.dump"
$dbDumpHostPath = Join-Path $backupPath "postgres.dump"
$minioDataHostPath = Join-Path $backupPath "minio-data"
$manifestPath = Join-Path $backupPath "backup-manifest.json"

[System.IO.Directory]::CreateDirectory($backupRootPath) | Out-Null
[System.IO.Directory]::CreateDirectory($backupPath) | Out-Null
[System.IO.Directory]::CreateDirectory($minioDataHostPath) | Out-Null

Assert-RunningService -ServiceName $DbService
Assert-RunningService -ServiceName $MinioService

Invoke-Compose exec -T $DbService pg_dump -U $DbUser -d $DbName -Fc --no-owner --no-privileges -f $dbDumpContainerPath
Invoke-Compose cp "${DbService}:$dbDumpContainerPath" $dbDumpHostPath
Invoke-Compose exec -T $DbService rm -f $dbDumpContainerPath
Invoke-Compose cp "${MinioService}:/data/." $minioDataHostPath

$alembicVersion = (Invoke-Compose exec -T $DbService psql -U $DbUser -d $DbName -t -A -c "SELECT version_num FROM alembic_version LIMIT 1;").Trim()

$manifest = [ordered]@{
    backup_created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    compose_file = $ComposeFile
    db_service = $DbService
    db_name = $DbName
    db_user = $DbUser
    db_dump_file = "postgres.dump"
    minio_service = $MinioService
    minio_data_dir = "minio-data"
    alembic_version = $alembicVersion
    restore_order = @(
        "Start db and minio services",
        "Stop api service",
        "Restore postgres.dump into PostgreSQL",
        "Replace MinIO /data with minio-data contents",
        "Start api service"
    )
}

$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding utf8

Write-Host "Backup created at $backupPath"
