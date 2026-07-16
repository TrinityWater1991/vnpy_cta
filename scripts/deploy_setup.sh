#!/usr/bin/env bash
# deploy_setup.sh — 首次部署：在 VPS 上初始化 vnpy CTA 运行环境
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="/usr/bin/python3.13"
VENV_DIR="$PROJECT_DIR/.venv"

echo "=== vnpy CTA 实盘部署脚本 ==="
echo "项目目录: $PROJECT_DIR"

# 1. 创建虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/5] 创建 Python 3.13 虚拟环境..."
    $PYTHON_BIN -m venv "$VENV_DIR"
else
    echo "[1/5] 虚拟环境已存在，跳过"
fi

# 2. 安装依赖
echo "[2/5] 安装依赖包..."
source "$VENV_DIR/bin/activate"
pip install -r "$PROJECT_DIR/requirements_freezed.txt" --quiet

# 3. 创建运行时目录
echo "[3/5] 创建运行时目录..."
mkdir -p "$PROJECT_DIR/.vntrader"
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/logs"

# 4. 配置 vt_setting.json
echo "[4/5] 配置 CTP 连接..."
if [ ! -f "$PROJECT_DIR/configs/vt_setting.json" ]; then
    if [ -f "$PROJECT_DIR/configs/vt_setting.json.template" ]; then
        echo "  请编辑 configs/vt_setting.json 填入 CTP 账户信息"
        echo "  模板文件: configs/vt_setting.json.template"
    fi
else
    echo "  vt_setting.json 已存在，跳过"
fi

# 5. 安装 systemd 服务
echo "[5/5] 安装 systemd 服务..."
SERVICE_FILE="/etc/systemd/system/vnpy-cta.service"
if [ ! -f "$SERVICE_FILE" ]; then
    sudo cp "$PROJECT_DIR/scripts/vnpy-cta.service" "$SERVICE_FILE"
    sudo systemctl daemon-reload
    echo "  服务已安装: sudo systemctl start vnpy-cta"
else
    echo "  服务已存在，跳过"
fi

echo ""
echo "=== 部署完成 ==="
echo "后续步骤:"
echo "  1. 编辑 configs/vt_setting.json 填入 CTP 账户"
echo "  2. 检查 configs/cta_strategy_setting.json 策略配置"
echo "  3. sudo systemctl start vnpy-cta  启动交易系统"
echo "  4. sudo systemctl status vnpy-cta 查看状态"
echo "  5. journalctl -u vnpy-cta -f      查看日志"
