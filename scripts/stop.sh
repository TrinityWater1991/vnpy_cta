#!/usr/bin/env bash
# stop.sh — 停止 vnpy CTA 交易系统（优雅退出）
set -euo pipefail

echo "停止 vnpy CTA 交易系统..."

# 优先使用 systemd
if systemctl is-active --quiet vnpy-cta 2>/dev/null; then
    sudo systemctl stop vnpy-cta
    echo "已通过 systemd 停止"
    exit 0
fi

# 回退：直接发信号
PID=$(pgrep -f "run_headless.py" || true)
if [ -n "$PID" ]; then
    echo "发送 SIGTERM 到 PID: $PID"
    kill -TERM $PID
    # 等待最多 30 秒
    for i in $(seq 1 30); do
        if ! kill -0 $PID 2>/dev/null; then
            echo "系统已退出"
            exit 0
        fi
        sleep 1
    done
    echo "超时，强制终止..."
    kill -9 $PID 2>/dev/null || true
else
    echo "未找到运行中的进程"
fi
