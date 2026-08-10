"""FastAPI 入口：组装路由 + 静态文件 + 健康检查。"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .cache import cache
from .database import init_db
from .routers import ai, allowances, auth, budget, categories, stats, transactions, wallets
from .seed_demo import maybe_seed_demo

logger = logging.getLogger("moneymate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if maybe_seed_demo():
        logger.info("已初始化演示数据（demo / demo123456）")
    logger.info("启动完成 | 环境: %s", settings.app_env)
    logger.info("数据库: %s", settings.database_url)
    yield


app = FastAPI(
    title="MoneyMate API",
    description="记账本：收支管理 + 分类 + 预算 + 统计报表",
    version="1.0.0",
    lifespan=lifespan,
)

# 跨域配置：开发环境允许所有来源，生产环境从 CORS_ORIGINS 读白名单
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(allowances.router)
app.include_router(categories.router)
app.include_router(wallets.router)
app.include_router(transactions.router)
app.include_router(budget.router)
app.include_router(stats.router)
app.include_router(ai.router)


# 兜底异常处理：避免把内部错误堆栈直接暴露给用户
@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.error("未处理异常：%s", exc)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


@app.get("/api/health")
def health():
    return {"status": "ok", "env": settings.app_env, "cache": cache.backend}


# 前端构建产物存在时，由后端一并托管（单容器部署）
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(_static_dir):

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """
        SPA 兜底：前端路由是 history 模式（/dashboard 这种假路径），
        直接刷新时浏览器会请求这个路径，这里统一返回 index.html 交给前端路由处理。
        """
        # API 路径保持正常 404（返回 JSON 而不是 HTML）
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        # 真实存在的静态文件（js/css/图片）正常返回
        file_path = os.path.join(_static_dir, full_path or "index.html")
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_static_dir, "index.html"))
