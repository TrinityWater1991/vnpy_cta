#!/usr/bin/env bash
# check_vps.sh — 检查 VPS 环境
set -euo pipefail

SSHPASS='Telegram123.' sshpass -e ssh -o StrictHostKeyChecking=no root@47.237.121.19 << 'REMOTE_EOF'
echo "=== OS ==="
cat /etc/os-release | head -5

echo ""
echo "=== Python ==="
python3 --version 2>/dev/null || echo "no python3"
python3.13 --version 2>/dev/null || echo "no python3.13"
which python3.13 2>/dev/null || echo "python3.13 not found in PATH"

echo ""
echo "=== System ==="
uname -a
df -h /
free -h

echo ""
echo "=== Existing vnpy ==="
pip3 list 2>/dev/null | grep -i vnpy || echo "no vnpy installed"
ls /opt/vnpy_cta 2>/dev/null || echo "no /opt/vnpy_cta"
REMOTE_EOF
