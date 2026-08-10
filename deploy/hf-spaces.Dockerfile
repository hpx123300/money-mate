# Hugging Face Spaces 部署专用 Dockerfile（监听 7860 端口）
# 用法：把仓库内容推送到 HF Space 后，把本文件复制为根目录 Dockerfile

# ===== 阶段一：构建前端 =====
FROM node:22-alpine AS frontend

WORKDIR /web
ENV CI=true
RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# ===== 阶段二：Python 后端 =====
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./backend/app
COPY --from=frontend /web/dist ./backend/app/static

EXPOSE 7860

# HF Spaces 要求监听 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--app-dir", "backend"]

