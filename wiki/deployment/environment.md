---
title: "Python 运行环境与 vnpy 安装"
category: "deployment"
tags: [python, venv, vnpy, dependency, conda]
created: 2026-07-16
updated: 2026-07-16
---

# Python 运行环境与 vnpy 安装

> 本文档说明 vnpy CTA 实盘环境的 Python 版本管理、虚拟环境创建、vnpy 安装及依赖管理流程。

---

## Python 版本管理

### 版本要求

| 组件 | 推荐版本 | 最低版本 | 说明 |
|------|----------|----------|------|
| Python | 3.10.x | 3.9.x | vnpy 官方推荐版本 |
| pip | 24.x | 21.x | Python 包管理器 |
| setuptools | 68.x+ | — | 构建依赖 |

<!-- TODO: 确认当前生产环境实际使用的 Python 版本 -->

### 安装方式

**方式一：apt 安装（Ubuntu）**

```bash
$ sudo apt update
$ sudo apt install python3.10 python3.10-venv python3.10-dev
```

**方式二：pyenv 管理多版本**

```bash
$ curl https://pyenv.run | bash
$ pyenv install 3.10.13
$ pyenv global 3.10.13
```

**方式三：Miniconda（备选）**

```bash
$ wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
$ bash Miniconda3-latest-Linux-x86_64.sh
$ conda create -n vnpy python=3.10
```

<!-- TODO: 记录生产环境使用的 Python 安装方式和具体路径 -->

---

## 虚拟环境创建

### 标准操作流程

```bash
# 创建虚拟环境
$ python3.10 -m venv /opt/vnpy/venv

# 激活环境
$ source /opt/vnpy/venv/bin/activate

# 验证
$ python --version
$ pip --version
```

### 虚拟环境目录结构

```
/opt/vnpy/venv/
├── bin/              # Python 可执行文件与激活脚本
├── lib/              # site-packages 依赖库
├── include/          # C 头文件
└── pyvenv.cfg        # 环境配置文件
```

<!-- TODO: 确认虚拟环境实际部署路径 -->

---

## vnpy 安装

### 安装方式对比

| 方式 | 命令 | 适用场景 | 推荐度 |
|------|------|----------|--------|
| pip 安装 | `pip install vnpy` | 快速部署，标准组件 | ⭐⭐⭐ |
| 源码安装 | `pip install -e .` | 二次开发，自定义组件 | ⭐⭐⭐⭐⭐ |
| Docker | `docker pull vnpy` | 容器化部署，隔离性好 | ⭐⭐（备选） |

### 标准源码安装步骤

```bash
# 克隆 vnpy 仓库
$ git clone https://github.com/vnpy/vnpy.git /opt/vnpy/vnpy
$ cd /opt/vnpy/vnpy

# 激活虚拟环境后安装
$ source /opt/vnpy/venv/bin/activate

# 安装核心库
$ pip install -e .

# 安装 CTP 接口（Linux）
$ pip install vnpy_ctp

# 安装其他常用接口
$ pip install vnpy_ctastrategy        # CTA 策略模块
$ pip install vnpy_ctabacktester       # 回测模块
$ pip install vnpy_spreadtrading       # 价差交易（可选）
$ pip install vnpy_optionmaster        # 期权（可选）
```

<!-- TODO: 确认生产环境 vnpy 的具体版本号 -->
<!-- TODO: 记录使用的 git commit SHA（源码部署时） -->

---

## 依赖管理

### 核心依赖清单

| 包名 | 用途 | 版本约束 | 备注 |
|------|------|----------|------|
| vnpy | 主框架 | >= 3.8.0, < 4.0 | <!-- TODO: 补充 --> |
| vnpy_ctp | CTP 接口 | 最新 | CTP 行情与交易 API |
| numpy | 数值计算 | >= 1.24 | 策略计算依赖 |
| pandas | 数据处理 | >= 2.0 | K 线数据处理 |
| ta-lib | 技术指标 | 最新 | 技术分析库 |
| pymongo | MongoDB 驱动 | >= 4.5 | 数据库连接（可选） |
| redis | Redis 驱动 | >= 5.0 | 缓存（可选） |
| pyzmq | ZeroMQ 通信 | >= 25.0 | 进程间通信 |
| requests | HTTP 请求 | >= 2.31 | 通知推送 / REST API |

### 依赖冻结

```bash
# 生成当前环境依赖清单
$ pip freeze > /opt/vnpy/requirements/requirements-$(date +%Y%m%d).txt

# 从冻结文件重建环境
$ pip install -r requirements-20260716.txt
```

<!-- TODO: 制定依赖更新策略和版本冻结流程 -->

---

## 环境验证

### 验证脚本

```python
# check_env.py
import sys
print(f"Python version: {sys.version}")

try:
    import vnpy
    print(f"vnpy version: {vnpy.__version__}")
except ImportError:
    print("vnpy not installed")

try:
    import vnpy_ctp
    print("vnpy_ctp: OK")
except ImportError:
    print("vnpy_ctp not installed")

try:
    import numpy
    print(f"numpy version: {numpy.__version__}")
except ImportError:
    print("numpy not installed")
```

### 验收标准

| 检查项 | 期望结果 | 实际结果 |
|--------|----------|----------|
| Python 版本 | 3.10.x | <!-- TODO: 补充 --> |
| vnpy 可导入 | 无报错 | <!-- TODO: 补充 --> |
| CTP 接口可加载 | 无报错 | <!-- TODO: 补充 --> |
| 数据库驱动可连接 | 连接成功 | <!-- TODO: 补充 --> |
| ta-lib 计算正确 | 指标计算无误 | <!-- TODO: 补充 --> |

---

## 相关页面

- [[deployment/vps-setup]] — VPS 服务器配置（环境前置条件）
- [[deployment/database]] — 数据库配置与连接
- [[deployment/deploy-workflow]] — 标准部署流程中的环境准备步骤
- [[troubleshooting/common-issues]] — 环境相关的常见错误
- [[reference/vnpy-docs]] — vnpy 官方文档安装章节索引
