#!/usr/bin/env bash
# 构建前端并把产物复制到后端静态目录（本地单端口部署用）
set -e

cd "$(dirname "$0")/../frontend"

if [ ! -d "node_modules" ]; then
  echo "请先安装前端依赖：cd frontend && pnpm install"
  exit 1
fi

pnpm build
rm -rf ../backend/app/static
cp -r dist ../backend/app/static
echo "✅ 前端已构建并同步到 backend/app/static"
