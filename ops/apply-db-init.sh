#!/usr/bin/env bash
set -euo pipefail

DATABASE="school_db2"
USERNAME="postgres"
HOST="127.0.0.1"
PORT="5432"
SQL_FILE="../db-init/full_db_dump.sql"

while getopts ":d:U:h:p:f:" opt; do
  case "$opt" in
    d) DATABASE="$OPTARG" ;;
    U) USERNAME="$OPTARG" ;;
    h) HOST="$OPTARG" ;;
    p) PORT="$OPTARG" ;;
    f) SQL_FILE="$OPTARG" ;;
    *)
      echo "Usage: $0 [-d database] [-U username] [-h host] [-p port] [-f sql_file]"
      exit 1
      ;;
  esac
done

if ! command -v psql >/dev/null 2>&1; then
  echo "psql command not found in PATH"
  exit 1
fi

if [ ! -f "$SQL_FILE" ]; then
  echo "SQL file not found: $SQL_FILE"
  exit 1
fi

echo "Applying SQL file: $SQL_FILE"
echo "Target DB: $DATABASE on $HOST:$PORT as $USERNAME"

psql -v ON_ERROR_STOP=1 -h "$HOST" -p "$PORT" -U "$USERNAME" -d "$DATABASE" -f "$SQL_FILE"

echo "DB init migration completed successfully."
