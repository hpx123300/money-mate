#!/usr/bin/env bash
# 一键本地启动后端（含自动建虚拟环境）
set -e

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "创建虚拟环境并安装依赖（首次约 1 分钟）..."
  python3 -m venv .venv
  # 国内镜像加速，失败自动回退官方源
  .venv/bin/pip install -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    || .venv/bin/pip install -r backend/requirements.txt
fi

echo "启动后端：http://127.0.0.1:8000 （接口文档 /docs）"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
