#!/usr/bin/env bash
# proxy_tunnel.sh — 建立到 VPS 的代理链路
# 层级: 本地 pproxy (HTTP :1081) → SSH SOCKS5 (:1080) → VPS → Bitget
# 用法: ./scripts/proxy_tunnel.sh [start|stop|status]

VPS="root@47.237.121.19"
SOCKS_PORT=1080
HTTP_PORT=1081
VENV="$(cd "$(dirname "$0")/.." && pwd)/.venv"

case "${1:-start}" in
    start)
        # 1. SSH SOCKS5 隧道
        if ! pgrep -f "ssh.*-D $SOCKS_PORT" > /dev/null 2>&1; then
            echo "启动 SSH SOCKS5 隧道: 127.0.0.1:$SOCKS_PORT → $VPS"
            nohup ssh -o StrictHostKeyChecking=no -N -D $SOCKS_PORT $VPS > /dev/null 2>&1 &
            sleep 1
        else
            echo "SSH SOCKS5 隧道已在运行"
        fi

        # 2. SOCKS5 → HTTP 转换 (pproxy)
        if ! pgrep -f pproxy > /dev/null 2>&1; then
            echo "启动 pproxy HTTP 代理: 127.0.0.1:$HTTP_PORT → socks5://127.0.0.1:$SOCKS_PORT"
            nohup $VENV/bin/pproxy -l http://127.0.0.1:$HTTP_PORT -r socks5://127.0.0.1:$SOCKS_PORT > /dev/null 2>&1 &
            sleep 1
        else
            echo "pproxy 已在运行"
        fi

        # 验证
        if curl -x http://127.0.0.1:$HTTP_PORT -s -o /dev/null -w "%{http_code}" https://api.bitget.com/api/v2/public/time 2>/dev/null | grep -q 200; then
            echo "代理链路正常 (Bitget HTTP 200)"
        else
            echo "代理链路异常，请检查"
        fi
        ;;
    stop)
        pkill -f pproxy 2>/dev/null && echo "pproxy 已停止"
        pkill -f "ssh.*-D $SOCKS_PORT" 2>/dev/null && echo "SSH 隧道已停止"
        ;;
    status)
        echo -n "SSH 隧道: "; pgrep -f "ssh.*-D $SOCKS_PORT" > /dev/null && echo "运行中" || echo "未运行"
        echo -n "pproxy:   "; pgrep -f pproxy > /dev/null && echo "运行中" || echo "未运行"
        ;;
esac
