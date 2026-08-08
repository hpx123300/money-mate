# ===== 阶段一：构建前端 =====
FROM node:22-alpine AS frontend

WORKDIR /web
# pnpm 在无终端环境（Docker/CI）下需要确认清理模块目录，这里声明为 CI 环境跳过确认
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

COPY backend/app ./app
COPY --from=frontend /web/dist ./app/static

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
