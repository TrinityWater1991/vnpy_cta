#!/usr/bin/env bash
# start.sh — 启动 vnpy CTA 交易系统
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo "启动 vnpy CTA 交易系统..."

# 检查是否已运行
if systemctl is-active --quiet vnpy-cta 2>/dev/null; then
    echo "系统已在运行中 (systemd)"
    exit 0
fi

if pgrep -f "run_headless.py" > /dev/null; then
    echo "系统已在运行中 (进程)"
    exit 0
fi

# 通过 systemd 启动
if [ -f "/etc/systemd/system/vnpy-cta.service" ]; then
    sudo systemctl start vnpy-cta
    echo "已通过 systemd 启动，查看状态: sudo systemctl status vnpy-cta"
else
    # 直接启动（开发/测试用）
    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"
    nohup python3.13 run_headless.py > logs/cta.log 2>&1 &
    echo "已通过 nohup 启动，PID: $!"
fi
