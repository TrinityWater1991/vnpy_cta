#!/usr/bin/env bash
# backup.sh — 备份 vnpy CTA 数据库和配置
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="vnpy_cta_backup_$TIMESTAMP"

echo "备份 vnpy CTA 数据..."

mkdir -p "$BACKUP_DIR"

# 备份数据库
if [ -f "$PROJECT_DIR/.vntrader/database.db" ]; then
    cp "$PROJECT_DIR/.vntrader/database.db" "$BACKUP_DIR/${BACKUP_NAME}.db"
    echo "  数据库已备份: ${BACKUP_NAME}.db"
fi

# 打包配置文件
tar -czf "$BACKUP_DIR/${BACKUP_NAME}_configs.tar.gz" \
    -C "$PROJECT_DIR/configs" \
    cta_strategy_setting.json vt_setting.json 2>/dev/null || true
echo "  配置已备份: ${BACKUP_NAME}_configs.tar.gz"

# 保留最近 30 天
find "$BACKUP_DIR" -name "vnpy_cta_backup_*" -mtime +30 -delete 2>/dev/null || true

echo "备份完成: $BACKUP_DIR/${BACKUP_NAME}*"
