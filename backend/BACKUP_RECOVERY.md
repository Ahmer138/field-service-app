# Backup and Recovery

This document describes the current backup and recovery posture for the Field Service App backend.

## Scope

The backend stores operational state in two places:

- PostgreSQL for application data and Alembic version state
- MinIO object storage for job update photo objects

The current posture uses:

- logical PostgreSQL backups with `pg_dump`
- full MinIO data directory copies
- a manifest file per backup set
- a documented restore workflow for Docker Compose environments

## Backup Artifacts

Each backup set contains:

- `postgres.dump`
- `minio-data/`
- `backup-manifest.json`

The manifest captures:

- backup timestamp
- compose file used
- database service and database name
- MinIO service name
- Alembic version captured at backup time
- expected restore order

## Create a Backup

From the backend directory:

```powershell
.\scripts\backup-compose.ps1
```

Optional parameters:

```powershell
.\scripts\backup-compose.ps1 `
  -ComposeFile .\docker-compose.yml `
  -OutputRoot .\backups `
  -DbService db `
  -MinioService minio `
  -DbName fsa_db `
  -DbUser fsa
```

This creates a timestamped backup directory under `backups/`.

## Restore a Backup

From the backend directory:

```powershell
.\scripts\restore-compose.ps1 -BackupPath .\backups\20260418T120000Z
```

Optional parameters:

```powershell
.\scripts\restore-compose.ps1 `
  -BackupPath .\backups\20260418T120000Z `
  -ComposeFile .\docker-compose.yml `
  -ApiService api `
  -DbService db `
  -MinioService minio `
  -DbName fsa_db `
  -DbUser fsa
```

Restore behavior:

- starts `db` and `minio`
- stops `api`
- recreates the target PostgreSQL database from `postgres.dump`
- replaces the MinIO `/data` contents from the backup copy
- starts `api` again

## Recommended Operating Practice

- run backups on a fixed schedule, at least daily for beta/production environments
- copy backup artifacts off the Docker host to external durable storage
- encrypt backups at rest in the storage platform you use
- test restore regularly in a separate environment
- keep multiple recovery points instead of only the latest snapshot

## Minimum Recovery Drill

At least once per release cycle:

1. Create a fresh backup set.
2. Restore it into a separate Docker Compose environment or host.
3. Run `alembic current` and confirm the restored database version matches the manifest.
4. Verify:
   - login works
   - core job reads work
   - photo download objects are present
   - `/health/db` returns healthy
   - `/health/storage` returns healthy

## Current Limitations

- the provided scripts target the current Docker Compose deployment shape
- point-in-time recovery is not implemented
- offsite replication is not automated by the backend repo itself
- encryption and retention enforcement depend on the destination backup platform
