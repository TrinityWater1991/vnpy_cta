#!/usr/bin/env bash
# install_python313.sh — 在 VPS 上编译安装 Python 3.13.13
set -euo pipefail

echo "=== 安装编译依赖 ==="
dnf install -y gcc make wget openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel 2>&1 | tail -3

echo "=== 下载 Python 3.13.13 ==="
cd /tmp
wget -q https://www.python.org/ftp/python/3.13.13/Python-3.13.13.tgz
tar xzf Python-3.13.13.tgz

echo "=== 编译安装 ==="
cd Python-3.13.13
./configure --enable-optimizations --prefix=/usr/local 2>&1 | tail -3
make -j$(nproc) 2>&1 | tail -5
make altinstall 2>&1 | tail -3

echo "=== 验证 ==="
python3.13 --version
echo "Python 3.13 installed at $(which python3.13)"
