# 大学生记账助手（MoneyMate）

面向**大学生记账场景**的 Python 全栈 Web 应用。支持多钱包、月度预算、生活费规划、统计报表，以及基于大模型的 AI 一句话记账。

**在线演示**：https://money-mate-8vby.onrender.com （演示账号 `demo` / `demo123456`）
> 部署在 Render 免费套餐上，15 分钟无访问会休眠，首次打开需等待数秒唤醒；免费套餐的文件系统不持久，重新部署后数据会重置（每次会重新种入演示数据）。

## 功能

- **注册登录**：注册后自动创建 13 个学生场景默认分类，无需手工配置
- **生活费规划**：设置每月生活费金额与到账日，自动计算「已花 / 剩余 / 日均可用 / 还能撑几天」
- **记一笔**：分类、钱包、金额、备注
- **AI 记账小助手**：输入「今天午饭花了 25」自动识别金额 / 分类 / 钱包，确认后入账
- **AI 智能分类与月度分析**：按分类自动归类，按月聚合生成自然语言消费总结
- **多钱包**：微信、支付宝、现金、银行卡分别记账，各自统计余额
- **统计报表**：分类占比、收支趋势、年度账单报告

## 技术栈

- **后端**：FastAPI · SQLModel（SQLAlchemy 2.x + Pydantic）· SQLite（配 `DATABASE_URL` 即可切 MySQL）· Redis · Uvicorn
- **前端**：Vue3 · TypeScript · Element Plus · ECharts · Pinia · Vite
- **AI**：DeepSeek 大模型（OpenAI 兼容接口），JSON mode 结构化输出 + 流式输出
- **工程化**：pytest（37 项）· Vitest（14 项）· GitHub Actions CI · Docker 多阶段构建 · Render 部署

## 架构

```mermaid
flowchart LR
    V[Vue3 前端] -->|REST / JWT| A[FastAPI]
    A --> S[SQLModel<br/>SQLite / MySQL]
    A --> R[(Redis 缓存<br/>滑动窗口限流)]
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

JWT 无状态鉴权 + Argon2 密码哈希；Redis 做热点数据缓存与**滑动窗口限流**。

限流用在 AI 这类成本高的接口上。两个细节：

- **滑动窗口而非固定窗口**：固定窗口把时间切成 `[0,60)`、`[60,120)` 这样的桶，在桶边界两侧各打满一次，任意 60 秒内实际会放过 2×limit 次请求。滑动窗口统计的是「当前时刻往前推 60 秒」，区间连续右移，没有边界突变。
- **原子执行**：判断与计数不能分成「先读再写」两步，否则并发下两个请求会读到同一个旧值、各自 +1 写回，计数少于真实请求数。Redis 侧把「清理过期 + 计数 + 写入」放进一段 Lua 脚本，由 Redis 单线程执行；内存兜底路径用线程锁保护。

Redis 不可用时自动退化为进程内限流，限流组件本身不会成为故障点。

## 测试

```bash
# 后端：27 项接口测试 + 10 项限流测试
pytest tests/ -q

# 前端：api 封装、登录 store、金额格式化
cd frontend && pnpm test
```

限流的 Redis 分支用 `fakeredis` 在进程内真实执行那段 Lua 脚本——本地不一定有 Redis 服务，但它是生产路径，不测等于没跑过。

CI 配置见 `.github/workflows/ci.yml`。

## 部署

仓库根目录的 `render.yaml` 已配好 Render Blueprint（Docker、免费套餐、健康检查）。部署步骤见 [说明文档.md](说明文档.md)。

> 关于数据持久化：本地与 Docker Compose 用 SQLite 文件；Render 免费套餐的文件系统不持久，所以线上演示的数据会随重新部署重置。需要长期保存就把 `DATABASE_URL` 指向托管数据库（Postgres / MySQL 均可，代码层只改这一处配置）。

## 目录结构

```
backend/app/
  main.py         应用入口与路由挂载
  config.py       环境变量配置
  constants.py    默认分类等跨模块常量
  models.py       SQLModel 数据模型
  schemas.py      Pydantic 请求/响应模型
  database.py     引擎与会话
  security.py     JWT + Argon2
  cache.py        Redis 缓存（未配置时降级为内存）
  rate_limit.py   滑动窗口限流（Redis 原子执行 + 内存兜底）
  llm.py          DeepSeek 调用封装
  seed_demo.py    演示数据生成
  routers/        auth / wallets / transactions / categories / budget / allowances / stats / ai
frontend/src/
  views/          登录 / 仪表盘 / 流水 / 预算 / 分类 / 年度报告
  stores/         Pinia 状态（登录态持久化）
  components/     布局与图表组件
  *.test.ts       Vitest 单元测试
Dockerfile        唯一的镜像构建文件（render.yaml 与 docker-compose 都指向它）
tests/
  conftest.py     测试环境固定（测试库 / 内存缓存 / 不真调模型）
  test_api.py     27 项接口测试
  test_rate_limit.py  10 项限流测试
  test_live.py    对运行中服务的冒烟脚本
```

## License

MIT
