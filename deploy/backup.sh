#!/usr/bin/env bash
# 数据库每日备份（建议加进 crontab）
#   crontab -e
#   10 4 * * * /www/wwwroot/shiji-api/deploy/backup.sh >> /www/wwwlogs/shiji-backup.log 2>&1
set -euo pipefail

DB_PATH="${SHIJI_DB_PATH:-/www/wwwroot/shiji-api/server/data/shiji.db}"
BACKUP_DIR="${BACKUP_DIR:-/www/backup/shiji}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

if command -v sqlite3 >/dev/null 2>&1; then
  # .backup 是 SQLite 官方的在线备份方式，写入过程中也安全
  sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/shiji-$STAMP.db'"
else
  echo "没装 sqlite3 命令，退回直接拷贝；建议 apt install sqlite3 / yum install sqlite"
  cp "$DB_PATH" "$BACKUP_DIR/shiji-$STAMP.db"
fi

find "$BACKUP_DIR" -name 'shiji-*.db' -mtime +"$KEEP_DAYS" -delete
echo "备份完成：$BACKUP_DIR/shiji-$STAMP.db"
