param(
    [Parameter(Mandatory = $false)] [string]$Database = "school_db2",
    [Parameter(Mandatory = $false)] [string]$Username = "postgres",
    [Parameter(Mandatory = $false)] [string]$Host = "127.0.0.1",
    [Parameter(Mandatory = $false)] [int]$Port = 5432,
    [Parameter(Mandatory = $false)] [string]$SqlFile = "../db-init/full_db_dump.sql",
    [Parameter(Mandatory = $false)] [string]$PsqlPath = "E:/PostgreSQL/17/bin/psql.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PsqlPath)) {
    throw "psql not found at $PsqlPath"
}

if (-not (Test-Path $SqlFile)) {
    throw "SQL file not found: $SqlFile"
}

Write-Host "Applying SQL file: $SqlFile"
Write-Host "Target DB: $Database on $Host`:$Port as $Username"

& $PsqlPath -v ON_ERROR_STOP=1 -h $Host -p $Port -U $Username -d $Database -f $SqlFile

Write-Host "DB init migration completed successfully."
