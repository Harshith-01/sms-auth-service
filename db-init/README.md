# Auth Service DB Init Folder


Expected default filename:
- `full_db_dump.sql`

You can use a different filename by passing it to the helper scripts in `../ops/`.

## Apply migration from this folder

PowerShell:

```powershell
..\ops\apply-db-init.ps1 -Database school_db2 -Username postgres -SqlFile ..\db-init\full_db_dump.sql
```

Bash:

```bash
../ops/apply-db-init.sh -d school_db2 -U postgres -f ../db-init/full_db_dump.sql
```

## Safety notes

- Run on a backup or staging DB first.
- Use `ON_ERROR_STOP=1` flow (enabled in scripts) so migration aborts immediately on first SQL error.
- Keep dump files out of git if they contain sensitive data.
