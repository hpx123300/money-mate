# MoneyMate · 记账本

一个完整的 Python 全栈记账系统：**收支记录 + 分类管理 + 月度预算 + 统计报表 + CSV 导出**。

## 🛠️ 技术栈

- **后端**：Python 3.12 · FastAPI · SQLModel · JWT 认证（Argon2 密码哈希）
- **数据库**：SQLite（零配置启动，生产可换 MySQL）
- **前端**：Vue 3 · Vite · TypeScript · Element Plus · ECharts（开发中）
- **工程**：Docker · pytest

## ✨ 功能

| 模块 | 说明 |
|---|---|
| 账号 | 注册 / 登录 / JWT 鉴权 |
| 分类 | 预置收支分类，支持自定义 |
| 流水 | 记一笔、修改、删除、按月/类型筛选 |
| 预算 | 月度预算设置，自动计算当月已支出 |
| 统计 | 月度汇总、分类占比饼图、近 6 月趋势折线图 |
| 导出 | 一键导出 CSV，方便自己二次分析 |

## 🚀 本地启动

```bash
cd money-mate
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn app.main:app --port 8000 --app-dir backend
```

打开 http://127.0.0.1:8000/docs 查看接口文档。

## 🧪 测试

```bash
.venv/bin/python tests/test_api.py
```

