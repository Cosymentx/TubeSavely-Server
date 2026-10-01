<div align="center">

<img src="https://raw.githubusercontent.com/Cosymentx/TubeSavely/master/assets/images/ic_logo.png" width="96" height="96" alt="TubeSavely Logo"/>

# TubeSavely-Server

**TubeSavely 官方后端服务 — 基于 Python 3 + FastAPI + yt-dlp 构建的高性能音视频解析、任务调度与支付积分 API 引擎**

[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.08.19-red?logo=youtube)](https://github.com/yt-dlp/yt-dlp)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1?logo=mysql)](https://mysql.com/)
[![Redis](https://img.shields.io/badge/Redis-6.x%2B-DC382D?logo=redis)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?logo=docker)](https://docker.com/)
[![API Docs](https://img.shields.io/badge/Docs-Swagger-black?logo=swagger)](https://tube-savely-server.vercel.app/docs)
[![Stars](https://img.shields.io/github/stars/Cosymentx/TubeSavely-Server?style=social)](https://github.com/Cosymentx/TubeSavely-Server)

</div>

---

> ⚠️ **合规提示**：请仅下载您拥有版权、获得正规授权或属于公有领域的音视频内容，并严格遵守各主流平台的服务条款与当地法律法规。

---

## 🌐 TubeSavely 系列项目生态

TubeSavely 是一套完整的跨平台音视频解析与下载解决方案，由三个独立且深度联动的核心项目协同构成：

| 项目 / 客户端 | 技术栈 | 职责与定位 | 仓库地址 | 在线体验 / 交付物 |
| :--- | :--- | :--- | :--- | :--- |
| **TubeSavely** | Flutter 3 + Dart | iOS / Android / Windows / macOS / Linux 客户端，提供原生交互与桌面端视频转换/压缩 | [![GitHub](https://img.shields.io/badge/GitHub-TubeSavely-02569B?logo=flutter)](https://github.com/Cosymentx/TubeSavely) | [Releases 下载](https://github.com/Cosymentx/TubeSavely/releases) |
| **TubeSavely-Vue** | Vue 3 + TypeScript + Vite | 现代化响应式 Web 端，无须安装即开即用，支持在线解析、格式筛选与下载 | [![GitHub](https://img.shields.io/badge/GitHub-TubeSavely--Vue-4FC08D?logo=vuedotjs)](https://github.com/Cosymentx/TubeSavely-Vue) | [访问 Web 演示站](https://tube-savely-vue.vercel.app) |
| **TubeSavely-Server** (当前仓库) | Python 3 + FastAPI + yt-dlp | 核心音视频解析引擎、任务队列、多平台提取、支付积分与下载分发 API | [![GitHub](https://img.shields.io/badge/GitHub-TubeSavely--Server-3776AB?logo=python)](https://github.com/Cosymentx/TubeSavely-Server) | [Swagger API 文档](https://tube-savely-server.vercel.app/docs) |

---

## ✨ 功能特性

- ⚡ **高性能视频解析**：基于深度定制的 yt-dlp 内置引擎与 Deno JavaScript 运行时，支持 YouTube、B站、TikTok 等 1800+ 站点解析。
- 🛡️ **账号与权限认证**：集成 OAuth2 (Google, GitHub, WeChat, Facebook) 社交登录及安全 JWT Token 鉴权。
- 💳 **全渠道支付集成**：支持支付宝 (Alipay)、微信支付 (WeChat Pay)、PayPal、Stripe (信用卡) 以及 Airwallex。
- 💎 **积分账本与计费闭环**：原子化积分消耗、充值入账与历史账单审计。
- 🔄 **任务编排与格式转换**：支持后台音视频下载、FFmpeg 转码、压缩与分发。
- 🚦 **多层级限流防护**：基于 Redis 与 fastapi-limiter 的分布式速率限制（未认证/认证/下载分级限制）。

---

## 🛠️ 技术栈

- **主编程语言**：Python 3.13
- **Web 核心框架**：FastAPI 0.115.8 + Starlette + Pydantic v2
- **ORM 与数据层**：SQLAlchemy 2.0.38 + Alembic (数据库迁移) + PyMySQL
- **数据库与缓存**：MySQL 8.0+ / Redis (aioredis)
- **核心解析引擎**：yt-dlp 2026.08.19 (内置 Vendor 源码)
- **JS 挑战挑战与运行时**：Deno 2.9.5 + yt-dlp-ejs 0.8.0
- **多媒体处理**：FFmpeg / ffprobe
- **安全与认证**：python-jose (JWT) + Passlib (Argon2 / Bcrypt)
- **多渠道支付 SDK**：PayPal, Stripe, Alipay, WeChat Pay, Airwallex
- **容器与部署**：Docker + Docker Compose

---

## 📦 yt-dlp 内核与扩展维护

项目在 `app/vendor/yt_dlp` 中采用独立集成的内置源码，当前内核版本为 **2026.08.19**。

> ⚠️ 注意：执行 `pip install -U yt-dlp` **不会**更新本服务实际调用的解析器。

- **EJS 与 Deno 支持**：YouTube 解析需要 `yt-dlp-ejs==0.8.0` 和 Deno（固定为 `2.9.5`），两者随 `requirements.txt` 安装。Deno 必须位于服务进程的 `PATH` 中。
- **自定义解析器维护**：更新内置源码时，务必保留 `extractor/extend/` 下的自定义解析器及项目特定扩展，并将上游模块导入调整为相对导入。
- **Cookies 与代理配置**：
  - 若 YouTube 触发 `Sign in to confirm you're not a bot`，请将 Netscape 格式 Cookies 挂载至 `cookies/youtube.txt`（同时支持 `cookies/tiktok.txt` 和 `cookies/douyin.txt`）。
  - 在 `app/services/video.py` 的 `ydl_opts` 中配置外网解析代理。

#### 环境依赖与内核校验
```bash
# 检查内置版本与依赖环境
python -c "from app.vendor.yt_dlp.version import __version__; print(__version__)"
deno --version
ffmpeg -version

# 执行 yt-dlp 内核回归测试
python -m unittest tests.test_yt_dlp_vendor -v
```

---

## 🚀 快速开始

### 🛠️ 前置条件
- Python 3.11+ (推荐 3.13)
- MySQL 8.0+
- Redis 6.0+
- FFmpeg 与 ffprobe 已加入系统 `PATH`
- Deno 2.9.5+

### 💻 本地运行

```bash
# 1. 克隆代码仓库
git clone https://github.com/Cosymentx/TubeSavely-Server.git
cd TubeSavely-Server

# 2. 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖项
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env

# 5. 执行数据库迁移
alembic upgrade head

# 6. 启动后端开发服务
python -m uvicorn app.main:app --host 127.0.0.1 --port 9527 --reload
```

服务就绪后可访问：
- 健康检查：`http://localhost:9527/api/v1/health`
- Swagger UI 交互式文档：`http://localhost:9527/docs`
- ReDoc 规范文档：`http://localhost:9527/redoc`

---

## ⚙️ 环境变量配置

在根目录下创建 `.env`（生产环境为 `.env.production`）：

```ini
# 核心服务配置
DATABASE_URL=mysql+pymysql://user:password@localhost/tubesavely?charset=utf8mb4
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-at-least-32-chars
API_V1_STR=/api/v1
ACCESS_TOKEN_EXPIRE_MINUTES=43200

# OAuth2 社交登录
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
WECHAT_APP_ID=your-wechat-app-id
WECHAT_APP_SECRET=your-wechat-app-secret

# 支付通道配置
ALIPAY_APP_ID=your-alipay-app-id
ALIPAY_PRIVATE_KEY=your-alipay-private-key
ALIPAY_PUBLIC_KEY=your-alipay-public-key
WECHAT_PAY_APP_ID=your-wechat-pay-app-id
WECHAT_PAY_MCH_ID=your-wechat-pay-mch-id
WECHAT_PAY_KEY=your-wechat-pay-key
PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_CLIENT_SECRET=your-paypal-client-secret
STRIPE_PUBLIC_KEY=your-stripe-public-key
STRIPE_SECRET_KEY=your-stripe-secret-key
AIRWALLEX_CLIENT_ID=your-airwallex-client-id
AIRWALLEX_API_KEY=your-airwallex-api-key

# 对象存储 (可选)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=tubesavely
```

---

## 🐳 Docker 部署

```bash
# 1. 容器构建与后台启动
docker compose up -d --build api

# 2. 容器内执行数据库结构迁移
docker compose exec api alembic upgrade head

# 3. 验证运行状态与日志
docker compose ps
docker compose logs -f api
```

---

## 📡 核心 API 端点

| 模块 | 方法 | 端点 | 描述 |
| :--- | :--- | :--- | :--- |
| **认证** | `POST` | `/api/v1/auth/register` | 用户账号注册 |
| | `POST` | `/api/v1/auth/login` | JWT 密码登录 |
| | `POST` | `/api/v1/auth/oauth/{provider}` | Google / GitHub / WeChat 社交登录 |
| **用户** | `GET` | `/api/v1/users/profile` | 获取当前用户信息 |
| | `PUT` | `/api/v1/users/profile` | 更新用户信息与资料 |
| **视频** | `GET` | `/api/v1/videos/parse` | 提交链接解析视频格式与清晰度 |
| | `POST` | `/api/v1/videos` | 创建视频下载任务 |
| | `GET` | `/api/v1/videos/history` | 查询下载历史列表 |
| **支付** | `POST` | `/api/v1/payments/create` | 发起积分购买订单 |
| | `POST` | `/api/v1/payments/webhook/{provider}`| 第三方支付结果异步回调 |
| | `GET` | `/api/v1/payments/orders` | 查询充值交易流水 |
| **积分** | `GET` | `/api/v1/credits` | 查询账户积分余额 |
| | `GET` | `/api/v1/credits/history` | 查询积分消耗与充值流水 |
| **任务** | `POST` | `/api/v1/tasks/convert` | 提交视频转码与格式转换任务 |
| | `GET` | `/api/v1/tasks/{task_id}` | 查询后台异步任务进度 |

---

## 📁 项目结构

```text
backend/
├── app/
│   ├── api/v1/              # API 路由与接口控制器
│   ├── core/                # 核心配置、中间件、安全鉴权与限流
│   ├── db/                  # 数据库连接会话管理
│   ├── models/              # SQLAlchemy ORM 实体数据模型
│   ├── schemas/             # Pydantic 数据验证与序列化契约
│   ├── services/            # 核心业务逻辑 (视频/支付/积分/转码)
│   └── vendor/              # 内置 yt-dlp 内核源码及自定义解析扩展
├── alembic/                 # Alembic 数据库版本演进迁移脚本
├── cookies/                 # 第三方视频站点 Cookies 挂载目录
├── downloads/               # 视频文件下载与分发暂存目录
├── logs/                    # 运行、访问及异常审计日志
└── tests/                   # 单元测试与端到端接口测试用例
```

---

## 🧪 测试与质量验证

```bash
# 运行全部单元测试
pytest

# 生成测试覆盖率报告
pytest --cov=app tests/

# 仅验证 yt-dlp 解析引擎回归测试
python -m unittest tests.test_yt_dlp_vendor -v
```

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 授权许可。
