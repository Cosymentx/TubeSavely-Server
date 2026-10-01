<div align="center">

<img src="https://raw.githubusercontent.com/Cosymentx/TubeSavely/master/assets/images/ic_logo.png" width="96" alt="TubeSavely Logo"/>

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

- **EJS 与 Deno 支持**：YouTube 解析需要 `yt-dlp-ejs==0.8.0` 和 Deno（固定为 `2.9.5`），两者随 `requirements.txt` 安装。本地运行可使用 `PATH` 中的 Deno。Vercel 构建通过 `scripts/prepare_runtime.py` 将 Deno 复制到 `app/runtime_bin/` 并纳入函数包，运行时不依赖构建机器的 scripts 目录；二进制文件不提交 Git。
- **自定义解析器维护**：更新内置源码时，务必保留 `extractor/extend/` 下的自定义解析器及项目特定扩展，并将上游模块导入调整为相对导入。
- **Cookies 与代理配置**：
  - 若 YouTube 触发 `Sign in to confirm you're not a bot`，本地或 Docker 可将 Netscape 格式 Cookies 挂载至 `cookies/youtube.txt`。Vercel 使用加密的 Production 环境变量 `YOUTUBE_COOKIES_BASE64`，配置后重新部署。Cookies 导出步骤见 [yt-dlp 官方说明](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)。
  - `YOUTUBE_COOKIES_BASE64` 是 Netscape Cookies 文件的 Base64，程序会写入权限为 600 的临时文件，并在解析完成或失败后删除，不记录 Cookie 内容。TubeSavely 的登录 Token 不会将 YouTube 登录会话传给解析器。
  - 解析代理通过 `VIDEO_PROXY` 环境变量配置；YouTube 代理连接超时会尝试直接连接。接口分别返回登录验证、私有视频及网络错误，不再统一将平台失败提示为 URL 不正确。

在 macOS 上，可以将 Cookie 文件编码后复制到剪贴板，再粘贴进 Vercel 环境变量：

```bash
base64 < youtube.txt | tr -d '\n' | pbcopy
```

#### Douyin / TikTok 专用解析

- 支持粘贴分享文案、抖音 `video/作品ID`、`jingxuan?modal_id=作品ID`、TikTok `@用户名/video/作品ID` 和两平台短链接。短链接最多跟随 5 次跳转，每一步校验平台域名。
- 先读取页面内嵌作品数据，缺失时尝试签名详情接口，最后使用 yt-dlp 兜底。单次专用解析最多 40 秒；一个请求内共用 Cookie、Chrome 131 请求特征和代理。
- 返回真实分辨率、时长、稳定作品 ID、多码率及备用播放地址；未知清晰度保持空值。TikTok 同清晰度优先提供官方播放地址。播放地址可能有时效、地区或请求来源限制，解析成功不代表所有 CDN 地址都可用。
- 本地或 Docker 可以挂载 `cookies/douyin.txt`、`cookies/tiktok.txt`，格式为 Netscape。Vercel 对应配置加密环境变量 `DOUYIN_COOKIES_BASE64`、`TIKTOK_COOKIES_BASE64`，编码方法同 YouTube。配置后重新部署；不要将 Cookie 文件提交到 Git。
- 两平台默认继承 `VIDEO_PROXY`；可用 `DOUYIN_PROXY`、`TIKTOK_PROXY` 分别指定代理。未设置表示继承，显式设置为空字符串表示直连。同一解析会话不会在中途切换出口。
- 抖音可以先尝试匿名会话：本地安装 `playwright` 并执行 `playwright install chromium`，再运行 `python scripts/refresh_douyin_cookies.py`。脚本新建浏览器会话并将 Cookie 保存到被 Git 忽略的 `cookies/douyin.txt`（权限 600），不读取个人浏览器资料。Vercel 需将此文件编码后更新 `DOUYIN_COOKIES_BASE64` 并重新部署。平台若要求人工验证，脚本会失败，需要正常访问平台后手动导出。Playwright 不随生产依赖安装。
- 风控验证、签名拒绝、网络错误、作品不可访问分别返回明确提示。旧 Cookie 可能缺少当前平台必需的会话信息，届时需要重新导出。图集返回业务码 `422`，不作为可下载视频扣除积分；完整图集下载暂未实现。
- 签名模块来自 [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API/tree/d8f874cd5b647b0ca087a57b15a458c3864439fa/src/dtk/signing/native)，版本固定为 `d8f874c`，Apache-2.0 许可证及 NOTICE 保存在 `app/vendor/short_video_signing/`。媒体提取设计参考 [JoeanAmier/TikTokDownloader](https://github.com/JoeanAmier/TikTokDownloader/tree/473c90ff70c663cfb69310fff2b8d5192f200661/src/extract)，未复制其 GPL 代码。

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

### 下载与积分

成功解析扣除 3 积分，余额不足时不会创建解析记录或产生负余额。`POST /api/v1/videos/download` 接收 `{"url":"原始作品链接","format_id":"解析结果中的格式ID"}`，携带 Bearer Token 即可流式下载本人已解析的格式，下载不重复扣分。下载地址由服务端解析记录确定，错误页面不会作为视频返回。

TikTok 作品没有发布文案时，标题使用作者昵称，描述保持为空；作品 ID、秒数时长、分辨率和文件大小按独立字段返回。套餐管理、人工修改积分和用户列表需要管理员权限，普通用户不能通过资料更新修改积分或申请管理员身份。
