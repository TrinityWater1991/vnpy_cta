#!/usr/bin/env bash
# deploy_vps.sh — 一键部署 vnpy CTA 到 VPS
# 用法: ./scripts/deploy_vps.sh
set -euo pipefail

VPS_IP="47.237.121.19"
VPS_USER="root"
VPS_PASS="Telegram123."
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/opt/vnpy_cta"

echo "========================================="
echo "  vnpy CTA VPS 一键部署"
echo "  目标: $VPS_USER@$VPS_IP"
echo "========================================="

# ── Step 1: 检查 VPS 环境 ──────────────────────────────
echo ""
echo "[1/6] 检查 VPS 环境..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" << 'EOF'
echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo "Kernel: $(uname -r)"
python3 --version 2>/dev/null || echo "WARNING: python3 not found"
df -h / | tail -1
free -h | head -2
EOF

# ── Step 2: 安装 Python 3.13 ────────────────────────────
echo ""
echo "[2/6] 安装 Python 3.13..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" '
if ! command -v python3.13 &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq python3.13 python3.13-venv python3.13-dev
    echo "Python 3.13 installed"
else
    echo "Python 3.13 already installed: $(python3.13 --version)"
fi
'

# ── Step 3: 上传项目文件 ────────────────────────────────
echo ""
echo "[3/6] 上传项目文件..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" "mkdir -p $REMOTE_DIR"
sshpass -p "$VPS_PASS" rsync -avz --delete \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '.vntrader' \
    --exclude 'logs' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'backups' \
    -e "ssh -o StrictHostKeyChecking=no" \
    "$PROJECT_DIR/" "$VPS_USER@$VPS_IP:$REMOTE_DIR/"
echo "Files uploaded to $REMOTE_DIR"

# ── Step 4: 创建虚拟环境并安装依赖 ──────────────────────
echo ""
echo "[4/6] 创建虚拟环境并安装依赖..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" << EOF
cd $REMOTE_DIR
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements_freezed.txt -q
echo "Dependencies installed"
EOF

# ── Step 5: 配置 systemd 服务 ────────────────────────────
echo ""
echo "[5/6] 配置 systemd 服务..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no "$VPS_USER@$VPS_IP" << EOF
cp $REMOTE_DIR/scripts/vnpy-cta.service /etc/systemd/system/
# 修正路径
sed -i "s|/home/admin/Desktop/vnpy_cta|$REMOTE_DIR|g" /etc/systemd/system/vnpy-cta.service
sed -i "s|User=admin|User=root|g" /etc/systemd/system/vnpy-cta.service
systemctl daemon-reload
echo "systemd service installed"
EOF

# ── Step 6: 提示后续步骤 ────────────────────────────────
echo ""
echo "========================================="
echo "  部署完成！"
echo "========================================="
echo ""
echo "后续步骤:"
echo "  1. 编辑 VPS 上的 CTP 配置:"
echo "     ssh root@$VPS_IP 'vi $REMOTE_DIR/configs/vt_setting.json'"
echo ""
echo "  2. 检查策略配置:"
echo "     ssh root@$VPS_IP 'cat $REMOTE_DIR/configs/cta_strategy_setting.json'"
echo ""
echo "  3. 启动交易系统:"
echo "     ssh root@$VPS_IP 'systemctl start vnpy-cta'"
echo ""
echo "  4. 查看日志:"
echo "     ssh root@$VPS_IP 'journalctl -u vnpy-cta -f'"
echo ""
