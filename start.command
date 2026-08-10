#!/bin/bash
# MoneyMate 本地启动（数据保存在电脑里，不会丢失）
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "首次运行：创建虚拟环境并安装依赖（约 1 分钟）..."
  python3 -m venv .venv
  .venv/bin/pip install -r backend/requirements.txt
fi

if curl -s -o /dev/null http://127.0.0.1:8000; then
  echo "服务已在运行，打开浏览器..."
  open http://127.0.0.1:8000
  exit 0
fi

echo "正在启动 MoneyMate..."
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
PID=$!
cd ..
sleep 4
open http://127.0.0.1:8000
echo "服务已启动：http://127.0.0.1:8000"
echo "关闭本窗口即停止服务（数据已保存在本地，不会丢失）"
wait $PID
