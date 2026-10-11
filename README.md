# 大学生记账助手（MoneyMate）

面向**大学生记账场景**的 Python 全栈 Web 应用。支持多钱包、月度预算、生活费规划、统计报表，以及基于大模型的 AI 一句话记账。

**在线演示**：https://money-mate-8vby.onrender.com （演示账号 `demo` / `demo123456`）
> 部署在 Render 免费套餐上，15 分钟无访问会休眠，首次打开需等待数秒唤醒。

## 功能

- **注册登录**：注册后自动创建 13 个学生场景默认分类，无需手工配置
- **生活费规划**：设置每月生活费金额与到账日，自动计算「已花 / 剩余 / 日均可用 / 还能撑几天」
- **记一笔**：分类、钱包、金额、备注
- **AI 记账小助手**：输入「今天午饭花了 25」自动识别金额 / 分类 / 钱包，确认后入账
- **AI 智能分类与月度分析**：按分类自动归类，按月聚合生成自然语言消费总结
- **多钱包**：微信、支付宝、现金、银行卡分别记账，各自统计余额
- **统计报表**：分类占比、收支趋势、年度账单报告

## 技术栈

- **后端**：FastAPI · SQLModel（SQLAlchemy 2.x + Pydantic）· MySQL · Redis · Uvicorn
- **前端**：Vue3 · TypeScript · Element Plus · ECharts · Pinia · Vite
- **AI**：DeepSeek 大模型（OpenAI 兼容接口），JSON mode 结构化输出 + 流式输出
- **工程化**：pytest（27 项）· GitHub Actions CI · Docker 多阶段构建 · Render 部署

## 架构

```mermaid
flowchart LR
    V[Vue3 前端] -->|REST / JWT| A[FastAPI]
    A --> S[SQLModel / MySQL]
    A --> R[(Redis 缓存 + 限流)]
    A --> L[DeepSeek LLM]
    L --> P[一句话记账解析<br/>智能分类<br/>月度总结]
```

## 快速开始

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # 填入 LLM_API_KEY 可开启 AI 功能（不配也能记账）
./start.command
```

Docker：

```bash
docker build -t moneymate .
docker run -p 8000:8000 moneymate
```

## 核心设计

### 1. AI 一句话记账（LLM + Prompt 工程）

设计系统提示词约束 JSON 输出格式，通过 **JSON mode** 让模型把「奶茶 15 元」这类口语化输入解析为 `{金额, 分类, 备注}`，再经 **Pydantic 二次校验**后入库。未配置 API Key 或解析失败时返回 503，前端优雅降级——**AI 功能异常不影响记账主流程**。

### 2. 金额精度

所有金额使用 `Decimal` 而非 `float`，避免浮点误差在累加统计中放大。

### 3. 鉴权与限流

JWT 无状态鉴权 + Argon2 密码哈希；Redis 实现固定窗口限流与热点数据缓存。

## 测试

```bash
pytest tests/ -q      # 27 项接口测试
```

CI 配置见 `.github/workflows/ci.yml`。

## 部署

仓库根目录的 `render.yaml` 已配好 Render Blueprint（Docker、免费套餐、健康检查）。部署步骤见 [说明文档.md](说明文档.md)。

## 目录结构

```
backend/app/
  main.py         应用入口与路由挂载
  models.py       SQLModel 数据模型
  schemas.py      Pydantic 请求/响应模型
  database.py     引擎与会话
  security.py     JWT + Argon2
  cache.py        Redis 缓存
  rate_limit.py   固定窗口限流
  llm.py          DeepSeek 调用封装
  seed_demo.py    演示数据生成
  routers/        auth / wallets / transactions / categories / budget / allowances / stats / ai
frontend/src/
  views/          登录 / 仪表盘 / 流水 / 预算 / 分类 / 年度报告
  stores/         Pinia 状态（登录态持久化）
  components/     布局与图表组件
tests/            27 项接口测试
```

## License

MIT
