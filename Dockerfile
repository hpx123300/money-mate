# 根目录 Dockerfile：供 Zeabur 等部署平台自动识别
# （内容与 backend/Dockerfile 一致，两者保持同步）

# ===== 阶段一：构建前端 =====
FROM node:22-alpine AS frontend

WORKDIR /web
ENV CI=true
RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# ===== 阶段二：Python 后端（同时托管前端产物）=====
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./backend/app
COPY --from=frontend /web/dist ./backend/app/static

EXPOSE 8000

# Zeabur 默认 8000；Hugging Face Spaces 会注入 PORT=7860，两种平台通用
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir backend"
