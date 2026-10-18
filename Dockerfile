# 有数 单镜像构建：先构建前端，再由 Python 后端一并托管。
#
# 这是项目里唯一的 Dockerfile，构建上下文是仓库根目录：
#     docker build -t youshu .
# render.yaml（Render Blueprint）与 docker-compose.yml 都指向本文件。
# 之前 backend/ 下还有一份内容相同、需要人工保持同步的副本，已删除。

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

# 保持与本地相同的目录结构（backend/app），这样 config.py 里
# 计算的项目根目录在容器内也是 /app，数据库才能写进挂载的 /app/data
COPY backend/app ./backend/app

# 迁移文件与配置：启动前先 alembic upgrade head，避免容器里的库结构落后于代码
COPY alembic.ini ./
COPY migrations ./migrations
COPY --from=frontend /web/dist ./backend/app/static

EXPOSE 8000

# 默认 8000（本地 / Docker Compose）；平台注入 PORT 时自动切换
# （Render、Zeabur 默认 8000，Hugging Face Spaces 注入 7860）
CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir backend"
