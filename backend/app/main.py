"""FastAPI 入口：组装路由 + 静态文件 + 健康检查。"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import auth, budget, categories, stats, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(f"[MoneyMate] 启动完成 | 环境: {settings.app_env}")
    yield


app = FastAPI(
    title="MoneyMate API",
    description="记账本：收支管理 + 分类 + 预算 + 统计报表",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(budget.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "env": settings.app_env}


# 前端构建产物存在时，由后端一并托管（单容器部署）
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
