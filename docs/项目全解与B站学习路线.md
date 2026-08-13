# 大学生记账助手（MoneyMate）项目全解 & B 站自学路线

> 这份文档解决两件事：
> 1. **把项目讲清楚**——每个目录、每个文件是干什么的，面试官问哪都能答；
> 2. **把知识补完整**——从零开始按什么顺序在 B 站自学，学完刚好能和这个项目一一对应。

---

## 一、项目是什么

**一句话**：面向大学生的收支记账 + 生活费规划 + 月度报表 + AI 记账助手的全栈 Web 应用。

**核心功能**：

| 模块 | 功能 |
|---|---|
| 记账 | 收入 / 支出流水，多钱包（微信、支付宝、现金）、分类、备注、日期 |
| 生活费规划 | 设置每月生活费与到账日，自动算"还剩多少、还能撑几天、日均可用" |
| 预算 | 按月度设置预算，实时对比当月支出 |
| 统计报表 | 仪表盘、趋势图、月度汇总、年度报告（ECharts） |
| 导入导出 | CSV 账单批量导入（自动去重）+ 导出 |
| AI 助手 | 一句话记账（智能解析金额/分类）、AI 分类推荐、月度消费总结（DeepSeek） |
| 账号体系 | 注册 / 登录，JWT 无状态认证 |

---

## 二、技术栈总览

| 层 | 技术 | 在项目里的角色 |
|---|---|---|
| 后端框架 | FastAPI + Uvicorn | 提供 REST API（8 组路由） |
| ORM | SQLModel（基于 SQLAlchemy） | 数据模型即代码，表结构 = 类定义 |
| 数据库 | SQLite（本地）/ MySQL、PostgreSQL（可切换） | 数据持久化，金额用 `Numeric(10,2)` |
| 认证安全 | PyJWT（HS256）+ Argon2（pwdlib） | 无状态登录 + 密码单向哈希 |
| 缓存 | Redis（未配置自动降级内存） | 统计接口缓存、限流计数 |
| 限流 | 固定窗口计数 | 保护 AI 接口防滥用 |
| AI | DeepSeek（OpenAI 兼容协议） | 记账解析、分类推荐、月度总结（JSON mode + 流式） |
| 前端框架 | Vue 3 + TypeScript + Vite | SPA 应用 |
| UI 组件 | Element Plus | 表格、表单、对话框等 |
| 状态管理 | Pinia | 登录状态全局管理 |
| 路由 | Vue Router | 页面路由 + 登录守卫 |
| 图表 | ECharts | 仪表盘、趋势、年度报告 |
| HTTP | Axios | 请求封装、令牌注入、401 跳登录 |
| 测试 | pytest | 27 项接口测试 + 线上冒烟脚本 |
| 工程化 | Docker（多阶段构建）、GitHub Actions CI、docker-compose、render.yaml | 构建、测试、部署 |

---

## 三、完整目录结构与文件详解

### 3.1 根目录

```
money-mate/
├── README.md                  # 项目主页：功能介绍、截图、怎么跑
├── start.command              # macOS 一键启动脚本（自动建虚拟环境 + 装依赖 + 起服务 + 开浏览器）
├── Dockerfile                 # 全栈多阶段构建：Node 构建前端 → Python 运行后端并托管前端
├── docker-compose.yml         # 本地一键编排（后端 + MySQL 示例）
├── render.yaml                # Render 云平台部署配置
├── .github/workflows/ci.yml   # GitHub Actions CI：后端测试 + 前端构建
├── .env                       # 本地环境变量（密钥，已被 gitignore，不上传）
├── .env.example               # 环境变量示例（上传到仓库，别人照着配）
├── .gitignore                 # 忽略规则：node_modules/.venv/数据库/构建产物
├── LICENSE                    # MIT 开源协议
```

### 3.2 后端 `backend/`

```
backend/
├── Dockerfile                 # 后端镜像（生产用，也可单独跑）
├── requirements.txt           # Python 依赖清单（FastAPI/SQLModel/Redis/JWT/argon2/pytest…）
└── app/
    ├── __init__.py            # 包标记
    ├── main.py                # FastAPI 入口：组装路由、CORS、生命周期（建表+演示数据）、托管前端静态文件
    ├── config.py              # 配置中心：所有密钥/地址从环境变量读，不硬编码
    ├── database.py            # 数据库引擎：SQLite/MySQL 切换、建表、跨线程兼容、迁移辅助
    ├── models.py              # 数据模型：User / Wallet / Category / Transaction / Budget / Allowance
    ├── schemas.py             # Pydantic 请求/响应模型：参数校验、返回结构
    ├── security.py            # 安全：Argon2 密码哈希 + JWT 签发/校验（HS256）
    ├── deps.py                # FastAPI 依赖：OAuth2 取令牌 → 解析 → 返回当前用户
    ├── cache.py               # 缓存模块：Redis 优先、内存兜底，支持 JSON 序列化与 TTL
    ├── rate_limit.py          # 固定窗口限流：60 秒内最多 N 次，超限返回 429
    ├── llm.py                 # LLM 客户端：调 DeepSeek /chat/completions（JSON mode、流式、错误兜底）
    ├── seed_demo.py           # 演示数据：首次启动注入 demo 账号和示例流水
    ├── static/                # 前端构建产物（FastAPI 直接托管，单端口跑全栈）
    └── routers/               # 8 组业务路由（见下表）
```

**`routers/` 每个文件的作用**：

| 文件 | 前缀 | 作用 |
|---|---|---|
| `auth.py` | `/api/auth` | 注册、登录（OAuth2 密码模式）、获取当前用户 |
| `wallets.py` | `/api/wallets` | 钱包/账户增删改查，余额随流水自动累计 |
| `categories.py` | `/api/categories` | 收支分类管理（餐饮/交通/宿舍水电…） |
| `transactions.py` | `/api/transactions` | 流水核心：增删改查、分页、关键词搜索、CSV 导入（去重）/导出/模板 |
| `budget.py` | `/api/budget` | 月度预算设置与当月支出对比 |
| `allowances.py` | `/api/allowance` | 生活费规划：到账日倒计时、剩余天数、日均可用 |
| `stats.py` | `/api/stats` | 汇总/趋势/月度统计/年度报告（给 ECharts 供数） |
| `ai.py` | `/api/ai` | AI 记账解析、AI 分类推荐、月度总结（带限流） |

### 3.3 前端 `frontend/`

```
frontend/
├── package.json              # 依赖与脚本（dev/build/typecheck）
├── pnpm-lock.yaml            # 依赖锁定文件（pnpm 用）
├── pnpm-workspace.yaml       # pnpm workspace 配置
├── index.html                # HTML 入口
├── vite.config.ts            # Vite 构建配置（代理 /api → 后端）
├── tsconfig.json / tsconfig.node.json  # TypeScript 编译配置
└── src/
    ├── main.ts               # 应用入口：挂载 Vue、Pinia、路由
    ├── App.vue               # 根组件
    ├── api.ts                # Axios 封装：baseURL、自动带令牌、401 自动跳登录
    ├── types.ts              # 与后端对应的 TS 类型（User/Category/Wallet/Transaction…）
    ├── utils.ts              # 工具函数（金额格式化等）
    ├── styles.css            # 全局样式
    ├── router.ts             # 路由表 + 登录守卫（没登录不能进业务页）
    ├── stores/auth.ts        # Pinia 登录状态：token 持久化到 localStorage
    ├── components/
    │   ├── AppLayout.vue     # 后台布局：侧边导航 + 顶栏 + 内容区
    │   └── EChart.vue        # ECharts 封装组件（传 option 即出图）
    └── views/
        ├── LoginView.vue     # 登录/注册页
        ├── DashboardView.vue # 仪表盘：本月收支、钱包、生活费倒计时、趋势图
        ├── TransactionsView.vue # 流水页：增删改、分页搜索、CSV 导入导出
        ├── BudgetView.vue    # 预算页：设置月度预算、进度展示
        ├── CategoriesView.vue# 分类管理页
        └── AnnualReportView.vue # 年度报告页
```

### 3.4 测试、脚本、部署、文档

```
tests/
├── test_api.py               # 27 项接口测试（pytest + TestClient，覆盖全业务）
└── test_live.py              # 线上冒烟脚本：对运行中的服务跑完整流程（可配 MONEYMATE_URL）

scripts/
├── dev.sh                    # 一键启动后端（自动建虚拟环境）
└── build-frontend.sh         # 构建前端并拷贝到 backend/app/static

docs/
├── 开发记录.md                # 踩坑记录：每次关键决策的来龙去脉
├── 简历写法.md                # 简历条目怎么写、量化指标怎么放
├── 部署指南.md                # 本地/Docker/Render 部署步骤
├── 面试追问补充.md            # 面试官可能追问的深度问题与答案
└── screenshots/              # 页面截图（README 用）

data/
└── moneymate.db              # 运行数据库（SQLite，gitignore 不提交）
```

---

## 四、核心设计深挖（面试问答素材）

### 4.1 数据模型（`models.py`）

- `User` → 用户；`Wallet` → 钱包；`Category` → 分类；`Transaction` → 流水；`Budget` → 月度预算；`Allowance` → 生活费设置
- 关系：流水挂在用户 + 分类 + 钱包下；预算按"用户 + 月份"唯一
- 金额一律 `Decimal` + `Numeric(10,2)`，**绝不用 float**（浮点误差会导致账算不平）

### 4.2 认证链路（`security.py` + `deps.py` + `stores/auth.ts`）

注册 → Argon2 哈希密码入库 → 登录成功签发 JWT（HS256，含用户 id 与过期时间）→ 前端存 localStorage → 每次请求 Axios 自动带 `Authorization: Bearer <token>` → 后端 `get_current_user` 校验签名并返回用户 → 过期/无效返回 401 → 前端拦截器跳登录页。

### 4.3 缓存（`cache.py`）

统计接口每次全表聚合很慢 → 结果缓存 60 秒；记账/改账时主动清掉该用户缓存（写时失效），保证一致性。Redis 可用时用 Redis，本地无 Redis 自动降级内存——**零依赖也能跑**。

### 4.4 限流（`rate_limit.py`）

固定窗口计数：`ratelimit:{key}:{user}:{窗口}`，60 秒内超限返回 429。用来保护 AI 接口，防止有人刷接口烧光你的 API 额度。

### 4.5 AI 集成（`llm.py` + `routers/ai.py`）

- 用 OpenAI 兼容协议调 DeepSeek，**不依赖 SDK**，标准库 urllib 就能发请求（换供应商只改环境变量）
- 记账解析用 `response_format={"type":"json_object"}` 强制返回 JSON，再严格校验字段
- 月度总结用流式输出，前端打字机效果；没配 key 时返回 503，前端优雅降级

### 4.6 前端架构

- Pinia 管登录态，token 持久化到 localStorage，刷新不丢
- Vue Router 路由守卫：没 token 一律弹回登录页
- Axios 拦截器统一注入令牌 + 401 统一处理（一处写、到处生效）
- ECharts 封装成 `<EChart :option="...">` 组件，图表页面零重复代码

### 4.7 部署与 CI

- Docker 多阶段：第一阶段 Node 构建前端 → 第二阶段 Python 运行时，`COPY --from=frontend` 把产物并进后端静态目录，单端口跑全栈
- GitHub Actions：每次 push 自动跑后端测试 + 前端构建，挂了会红
- Render 配置齐全，改环境变量即可上线（免费档偶尔休眠，重新访问会等几秒）

---

## 五、B 站自学路线（从零到能面试，完整顺序）

> 原则：**先学什么就立刻去项目里找对应文件看一遍**，知识永远挂在项目上，才不会学完就忘。
> 所有课程都给了直达链接（BV 号），「必看章节」列的是最值得看的部分，不用从头到尾硬啃。

### 阶段 0：开发环境与工具（1 周）

| 学什么 | B 站课程（点击直达） | 必看章节 | 对应项目文件 | 过关标准 |
|---|---|---|---|---|
| 安装 Python 3.12、VS Code | [黑马 Python 600 集（BV1ex411x7Em）](https://www.bilibili.com/video/BV1ex411x7Em) | 开头环境篇：Python 下载安装、环境变量 | `start.command` | 能跑 `python -V` |
| Git 与 GitHub | [尚硅谷 Git 入门到精通（BV1vy4y1s7k6）](https://www.bilibili.com/video/BV1vy4y1s7k6)（新版 3 小时速通 [BV1wm4y1z7Dg](https://www.bilibili.com/video/BV1wm4y1z7Dg)） | 常用命令（add/commit/log）→ 分支 → 远程仓库/GitHub | `.git`、`README.md` | 会 add/commit/push/clone |
| 终端命令 | [黑马 Linux 快速入门（BV1n84y1i7td）开头的命令章节](https://www.bilibili.com/video/BV1n84y1i7td)（Mac 终端命令基本通用；或搜「Mac 终端入门」） | 常用命令：cd/ls/mkdir/rm、PATH | `scripts/dev.sh` | 会用 cd/ls 看日志 |

### 阶段 1：Python 语言基础（2 周）

| 学什么 | B 站课程（点击直达） | 必看章节 | 对应项目文件 | 过关标准 |
|---|---|---|---|---|
| 语法：变量/类型/运算符/条件/循环 | [黑马 Python 600 集（BV1ex411x7Em）](https://www.bilibili.com/video/BV1ex411x7Em) | 基础语法章节：变量、数据类型、流程控制 | `routers/*.py` | 能读懂接口代码 |
| 数据结构：列表/字典/集合/元组 | 同上 | 数据结构章节：列表/字典/切片/推导式 | `models.py`、`cache.py` | 会增删改查 |
| 函数与作用域 | 同上 | 函数章节：参数、默认值、作用域 | `llm.py` | 会写函数 + 默认参数 |
| 类与面向对象 | 同上 | 面向对象章节：class/`__init__`/继承/魔术方法 | `models.py` 的 `class User` | 知道 `__init__`、属性、方法 |
| 异常处理 | 同上 | 异常处理章节：try/except/raise/自定义异常 | `llm.py` 的 `LLMError` | 会 try/except/raise |
| 装饰器与生成器 | 同上（若没讲透，另搜「Python 装饰器 生成器」） | 装饰器/生成器章节（面试高频，必看） | `deps.py`（`Depends`）、`main.py` | 知道是什么、在哪见过 |

### 阶段 2：数据库与 SQL（2 周）

| 学什么 | B 站课程（点击直达） | 必看章节 | 对应项目文件 | 过关标准 |
|---|---|---|---|---|
| MySQL 安装与基本操作 | [黑马 MySQL 入门到精通（BV1Kr4y1i7ru）](https://www.bilibili.com/video/BV1Kr4y1i7ru) | 基础篇：安装、DDL/DML/DQL | `database.py` | 会建库建表 |
| 建表与字段类型 | 同上 | 基础篇：数据类型、字段约束 | `models.py` | 能解释每个字段 |
| 主键/外键/唯一约束 | 同上 | 基础篇：约束章节（主键/外键/UNIQUE） | `User.username unique` | 知道为什么唯一 |
| 范式与表设计 | 同上 | 基础篇：多表关系与设计（一对多/多对多） | 表关系设计 | 能说出"为什么拆表" |
| 索引 | 同上 | 进阶篇：索引原理（B+树、聚簇/非聚簇） | `Field(index=True)` | 知道索引为什么快 |
| 事务 ACID | 同上 | 基础篇：事务章节（ACID、隔离级别） | `transactions.py` 写库处 | 知道原子性 |
| ORM 概念 | [2026 FastAPI 从入门到实战（BV1ufgY6MEHJ）ORM/SQLModel 章节](https://www.bilibili.com/video/BV1ufgY6MEHJ)（或搜「SQLAlchemy 入门」） | 模型映射、会话 Session、增删改查 | `database.py`、`models.py` | 知道 ORM 是什么 |

### 阶段 3：后端 Web 开发（3 周）——本项目核心

| 学什么 | B 站课程（点击直达） | 必看章节 | 对应项目文件 | 过关标准 |
|---|---|---|---|---|
| HTTP 协议（方法/状态码） | [王道考研 计算机网络（BV19E411D78Q）HTTP 章节](https://www.bilibili.com/video/BV19E411D78Q)（或搜「HTTP 协议 计算机网络」） | 请求方法、状态码、HTTP/HTTPS | 任意接口 | 说得清 GET/POST/401/429 |
| REST 设计规范 | 搜「RESTful API 设计」 | 资源路径、动词、状态码语义 | `routers/*` | 会设计资源路径 |
| FastAPI 路由与参数 | [2026 FastAPI 从入门到实战（BV1ufgY6MEHJ）](https://www.bilibili.com/video/BV1ufgY6MEHJ) | 路由与路径/查询参数、请求体 | `routers/transactions.py` | 会写增删改查接口 |
| Pydantic 校验 | 同上 | Pydantic 模型与校验章节 | `schemas.py` | 知道请求/响应模型 |
| 依赖注入 | 同上 | 依赖注入（Depends）章节 | `deps.py` | 能解释 `Depends` |
| CORS 与中间件 | 同上 | 中间件与 CORS 章节 | `main.py` | 知道为什么开发要开 CORS |
| JWT 认证 | [编程不良人 JWT 认证原理（BV1i54y1m7cP）](https://www.bilibili.com/video/BV1i54y1m7cP)（或搜「JWT 前后端分离」） | 签发/校验/过期，登录流程图 | `security.py`、`deps.py` | 能画出登录流程图 |
| 密码哈希 | 搜「密码加密 Argon2」 | Argon2 原理、为什么不用明文 | `security.py` | 能说清为什么不能存明文 |
| 缓存 | [黑马 Redis 入门到精通（BV1CJ411m7Gc）](https://www.bilibili.com/video/BV1CJ411m7Gc) | Redis 入门：数据类型、TTL、缓存应用 | `cache.py` | 知道 TTL 与一致性 |
| 限流 | 搜「接口限流 固定窗口」 | 固定窗口/滑动窗口算法 | `rate_limit.py` | 能讲出算法思路 |
| 接口测试 | [pytest 测试框架入门（BV18K411m7FH）](https://www.bilibili.com/video/BV18K411m7FH) | fixture、断言、TestClient | `tests/test_api.py` | 会写用例并跑通 |

### 阶段 4：前端开发（3-4 周）

| 学什么 | B 站课程（点击直达） | 必看章节 | 对应项目文件 | 过关标准 |
|---|---|---|---|---|
| HTML/CSS 基础 | [黑马 Pink 老师 HTML5+CSS3 前端入门（BV14J4114768）](https://www.bilibili.com/video/BV14J4114768) | 盒模型、选择器、flex 布局 | `frontend/index.html` | 看得懂结构 |
| JS 基础 | [尚硅谷 JS 高级（BV14s411E7qf）](https://www.bilibili.com/video/BV14s411E7qf) | 作用域/闭包 → 原型链 → 事件循环（这部分也可放到阶段 6 一起补） | `frontend/src/*.ts` | 能解释闭包和事件循环 |
| Vue3 组合式 API | [尚硅谷 Vue2+Vue3 全套（BV1Zy4y1K7SH）](https://www.bilibili.com/video/BV1Zy4y1K7SH) | **直接跳 Vue3 部分**：setup/ref/reactive/computed/生命周期 | `views/*.vue` | 会写 `ref`/`computed`/`onMounted` |
| 组件与通信 | 同上 | 组件章节：props/emit/插槽 | `components/AppLayout.vue` | 会 props/emit |
| TypeScript | [尚硅谷 TypeScript（BV1Xy4y1v7S2）](https://www.bilibili.com/video/BV1Xy4y1v7S2) | 基础类型 → 接口 → 泛型 → 类型守卫 | `types.ts`、`api.ts` | 会写接口类型 |
| Pinia 状态管理 | [Pinia 状态管理课程讲解 2024（BV1wx421S7xb）](https://www.bilibili.com/video/BV1wx421S7xb)（或搜「10分钟学会 Pinia」） | store/state/getters/actions | `stores/auth.ts` | 能解释为什么用它 |
| Vue Router | [尚硅谷 Vue 教程内的 Router 章节（BV1Zy4y1K7SH）](https://www.bilibili.com/video/BV1Zy4y1K7SH)（或搜「Vue Router 教程」） | 路由配置、导航守卫 | `router.ts` | 会写路由守卫 |
| Element Plus | [2025 Element Plus 从入门到精通（BV1q4hwzhEJp）](https://www.bilibili.com/video/BV1q4hwzhEJp) | 常用组件：表单/表格/消息提示 | 各页面表单/表格 | 会用组件 |
| ECharts | [ECharts 大屏可视化入门（BV1v7411R7mp）](https://www.bilibili.com/video/BV1v7411R7mp) | 基础图表：option、柱状图/饼图 | `components/EChart.vue` | 会配 option |
| Axios 封装 | [尚硅谷 axios 入门与源码解析（BV1wr4y1K7tq）](https://www.bilibili.com/video/BV1wr4y1K7tq) | 请求/响应拦截器、token 注入 | `api.ts` | 会统一注入令牌 |
| Vite 构建 | [Vite.js 快速入门到精通（BV13arYYxEGF）](https://www.bilibili.com/video/BV13arYYxEGF) | dev/build 区别、开发代理 | `vite.config.ts` | 知道 dev/build 区别 |

### 阶段 5：工程化与部署（2 周）

| 学什么 | B 站课程（点击直达） | 必看章节 | 对应项目文件 | 过关标准 |
|---|---|---|---|---|
| Docker 基础 | [狂神说 Docker 超详细版（BV1og4y1q7M4）](https://www.bilibili.com/video/BV1og4y1q7M4) | 核心概念（镜像/容器/仓库）→ 常用命令 → 数据卷 | `Dockerfile` | 会写基础 Dockerfile |
| 多阶段构建 | [狂神说 Docker 超详细版（BV1og4y1q7M4）Dockerfile 章节](https://www.bilibili.com/video/BV1og4y1q7M4)（或搜「Docker 多阶段构建」） | 多阶段原理（FROM ... AS build → 复制产物） | `Dockerfile` | 能解释为什么分两段 |
| docker-compose | [狂神说 Docker 进阶篇（BV1kv411q7Qc）](https://www.bilibili.com/video/BV1kv411q7Qc) | Compose 文件编写、服务编排 | `docker-compose.yml` | 会起 MySQL + 后端 |
| Linux 基础 | [黑马 Linux 快速入门（BV1n84y1i7td）](https://www.bilibili.com/video/BV1n84y1i7td) | 常用命令、文件权限、进程 | `deploy/` | 会用基本命令 |
| CI/CD | [GitHub Actions 从入门到专业人士（BV1dMCsBKEyk）](https://www.bilibili.com/video/BV1dMCsBKEyk) | workflow 基本语法：job/step/on | `.github/workflows/ci.yml` | 看懂 workflow |
| 云部署 | [Render 部署](https://render.com/docs) 官方文档 + 回看阶段 5 Docker/Linux（或搜「Render 部署」） | 环境变量、启动命令、健康检查 | `render.yaml`、`deploy/` | 能部署出公网链接 |

### 阶段 6：面试理论补强（长期，投简历前 2 周集中）

| 学什么 | B 站课程（点击直达） | 面试会问什么 |
|---|---|---|
| 计算机网络 | [王道考研 计算机网络（BV19E411D78Q）](https://www.bilibili.com/video/BV19E411D78Q) | TCP 三次握手、HTTP/HTTPS、状态码 |
| MySQL 原理 | [黑马 MySQL（BV1Kr4y1i7ru）进阶篇](https://www.bilibili.com/video/BV1Kr4y1i7ru) | 索引 B+树、执行计划/慢查询、事务隔离级别 |
| Redis 原理 | [黑马 Redis（BV1CJ411m7Gc）](https://www.bilibili.com/video/BV1CJ411m7Gc) | 缓存穿透/击穿/雪崩、过期策略 |
| 操作系统 | [王道考研 操作系统（BV1YE411D7nH）](https://www.bilibili.com/video/BV1YE411D7nH) | 进程线程、死锁、内存 |
| 数据结构与算法 | [王道考研 数据结构（BV1b7411N798）](https://www.bilibili.com/video/BV1b7411N798) + LeetCode 简单题 | 链表/栈/队列/哈希/树/排序/二分 |
| Vue 原理 | [尚硅谷 Vue（BV1Zy4y1K7SH）原理部分](https://www.bilibili.com/video/BV1Zy4y1K7SH) | 响应式、虚拟 DOM、diff |
| JS 基础 | [尚硅谷 JS 高级（BV14s411E7qf）](https://www.bilibili.com/video/BV14s411E7qf) | 事件循环、闭包、原型链 |

---

## 六、整体时间规划

| 周次 | 阶段 | 产出 |
|---|---|---|
| 第 1 周 | 阶段 0 + 阶段 1 前半 | 环境就绪，能读懂 Python 接口代码 |
| 第 2-3 周 | 阶段 1 后半 + 阶段 2 | 能画数据模型、写 SQL |
| 第 4-6 周 | 阶段 3 | 能独立讲清并复现后端每个接口 |
| 第 7-10 周 | 阶段 4 | 能讲清前端每个页面和状态流 |
| 第 11-12 周 | 阶段 5 | 能用 Docker 把项目部署起来 |
| 第 13 周起 | 阶段 6 | 刷题 + 背八股 + 模拟面试 |

---

## 七、面试要点速查（技术点 → 一句话答案）

| 技术点 | 一句话回答 |
|---|---|
| JWT 为什么无状态 | 令牌自带用户信息与签名，服务端不用存 session，靠密钥验签 |
| 为什么用 Argon2 | 抗 GPU 暴力破解的现代密码哈希（BCrypt 的升级替代） |
| 金额为什么不用 float | 浮点有精度误差，账会算不平；用 `Decimal(10,2)` 精确到分 |
| 缓存一致性怎么处理 | 短 TTL（60s）+ 写操作主动清缓存（cache invalidation） |
| 为什么用 Redis 还支持内存 | 本地开发零依赖，生产有 Redis 自动切换，代码零改动 |
| 限流怎么做的 | 固定窗口：`key:用户:当前窗口` 计数，超限 429；简单可靠 |
| AI 解析怎么保证格式 | 用 JSON mode 强制返回 JSON + Pydantic 校验，解析失败兜底 |
| 前端 401 怎么处理 | Axios 响应拦截器统一拦截，清 token 跳登录页，一处配置全站生效 |
| 为什么拆成多张表 | 减少冗余、避免数据不一致（范式化），用外键关联 |
| CORS 是什么 | 浏览器跨域限制，后端配置允许来源白名单即可 |
| Docker 为什么分两阶段 | 构建阶段要 Node 环境，运行阶段只要 Python，镜像更小更安全 |
| CI 有什么用 | push 自动跑测试和构建，坏代码到不了线上 |

---

## 八、学习方法建议

1. **每学完一个知识点，打开项目对应文件看一遍**，用"注释里写了什么"检验自己懂没懂——本项目几乎所有核心文件都写了设计说明
2. **先跑起来再深入**：用 `start.command` 启动，边用边看代码，功能 → 代码 → 原理
3. **面试准备**：对着"面试要点速查"表，每个点口述一遍，讲不出来就回阶段对应视频重看
4. **进阶**：项目里标了"下一步计划"（AA 分账等），做完任何一个都能当加分项写进简历
