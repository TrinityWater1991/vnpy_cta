#!/usr/bin/env bash
# health_check.sh — 快速健康检查
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OK="\033[32m✓\033[0m"
FAIL="\033[31m✗\033[0m"
WARN="\033[33m⚠\033[0m"

echo "vnpy CTA 健康检查 $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================="

# 1. 进程
if pgrep -f "run_headless.py" > /dev/null || systemctl is-active --quiet vnpy-cta 2>/dev/null; then
    echo -e "$OK 进程: 运行中"
else
    echo -e "$FAIL 进程: 未运行"
fi

# 2. 数据库
if [ -f "$PROJECT_DIR/.vntrader/database.db" ]; then
    echo -e "$OK 数据库文件存在 ($(du -h "$PROJECT_DIR/.vntrader/database.db" | cut -f1))"
else
    echo -e "$WARN 数据库文件不存在"
fi

# 3. 磁盘
DISK_USAGE=$(df -h "$PROJECT_DIR" | tail -1 | awk '{print $5}')
DISK_PCT=${DISK_USAGE%\%}
if [ "$DISK_PCT" -gt 80 ]; then
    echo -e "$FAIL 磁盘: ${DISK_USAGE} (超过80%)"
elif [ "$DISK_PCT" -gt 60 ]; then
    echo -e "$WARN 磁盘: ${DISK_USAGE}"
else
    echo -e "$OK 磁盘: ${DISK_USAGE}"
fi

# 4. 内存
MEM_AVAIL=$(free -h | awk '/Mem:/ {print $7}')
echo -e "$OK 可用内存: $MEM_AVAIL"

# 5. 最近日志
if [ -f "$PROJECT_DIR/logs/cta.log" ]; then
    LAST_LOG=$(tail -1 "$PROJECT_DIR/logs/cta.log" 2>/dev/null || echo "无")
    echo -e "$OK 最近日志: ${LAST_LOG:0:80}"
else
    echo -e "$WARN 日志文件不存在"
fi

echo "=================================="
