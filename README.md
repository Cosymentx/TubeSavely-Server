# TubeSavely Backend

基于 FastAPI 构建的视频下载和管理系统后端服务。

仓库：[Cosymentx/TubeSavely-Server](https://github.com/Cosymentx/TubeSavely-Server)。

## 技术栈

- Python 3.13（Docker 使用此版本）
- FastAPI 0.115.8
- SQLAlchemy 2.0.38
- MySQL 8.0+
- Redis（redis 5.3.0 / fastapi-limiter 0.1.6）
- JWT Authentication (python-jose 3.4.0)
- OAuth2 (Google, GitHub)
- Rate Limiting (fastapi-limiter 0.1.6)
- Web Scraping (parsel 1.10.0)
- yt-dlp 2026.08.19：内置视频解析下载源码
- yt-dlp-ejs 0.8.0 / Deno 2.9.5：YouTube JavaScript 挑战解析
- FFmpeg: 视频处理
- PayPal SDK: PayPal 支付集成
- Stripe SDK: 信用卡支付集成
- Alipay SDK: 支付宝集成
- WeChat Pay SDK: 微信支付集成
- MinIO: 对象存储服务

## yt-dlp 维护

项目使用 `app/vendor/yt_dlp` 中的内置源码，当前版本为 **2026.08.19**。
`pip install -U yt-dlp` 不会更新项目实际使用的解析器。

YouTube 解析需要 `yt-dlp-ejs==0.8.0` 和 Deno（固定为 `2.9.5`），
两者通过 `pip install -r requirements.txt` 安装。Deno 需位于服务进程的 `PATH` 中。
Docker 构建还会安装 FFmpeg / ffprobe，用于音视频合并和后处理。

更新内置源码时，保留 `extractor/extend/` 下的自定义解析器及项目额外资源，
将上游的 `from yt_dlp...` 导入改为对应的相对导入，并保持 YouTube 导出类的
`__module__` 使用当前包名。不要复制包含上游绝对模块路径的 `lazy_extractors.py`。
同时按照目标版本的官方依赖声明更新 EJS 和 Deno，并验证 YouTube、TikTok、
Facebook 等平台的解析及自定义扩展导入。

版本来源：[官方 2026.08.19 发布页](https://github.com/yt-dlp/yt-dlp/releases/tag/2026.08.19)。
EJS 安装要求见[官方配置指南](https://github.com/yt-dlp/yt-dlp/wiki/EJS)。

安装依赖并激活虚拟环境后，可检查实际加载版本和运行依赖：

```bash
python -c "from app.vendor.yt_dlp.version import __version__; print(__version__)"
deno --version
ffmpeg -version
python -m unittest tests.test_yt_dlp_vendor -v
```

这些回归测试验证内置模块路径、平台匹配、自定义扩展导入，以及 Deno 执行和本地 EJS
脚本加载，不依赖数据库或在线平台响应。实际视频解析还受网络、登录状态和平台限制影响。

若 YouTube 返回 `Sign in to confirm you're not a bot`，需检查服务出口网络和有效的
Netscape 格式 `cookies/youtube.txt`；项目也支持 `cookies/tiktok.txt` 和
`cookies/douyin.txt`。当前解析代理在 `app/services/video.py` 的 `ydl_opts` 中配置，
部署前需确认该代理在运行环境可用。

部署更新需重新构建镜像并重启服务：`docker compose up -d --build api`。

## Vercel 完整版部署

本仓库现在包含用户认证、用户资料、OAuth 登录、视频、积分、支付、任务和反馈接口。
根目录 `main.py` 导出 `app.main:app`，接口统一使用 `/api/v1` 前缀。

- 后端：`https://tube-savely-server.vercel.app`
- 前端：`https://tube-savely-vue.vercel.app`
- 文档：`https://tube-savely-server.vercel.app/docs`
- OpenAPI：`https://tube-savely-server.vercel.app/api/v1/openapi.json`
- 健康检查：`https://tube-savely-server.vercel.app/api/v1/health`

Vercel Root Directory 使用仓库根目录，Python 版本通过 `.python-version` 固定为 3.13。
生产配置从 Vercel Environment Variables 读取，不读取仓库中的 `.env` 文件。
运行依赖仅保留服务所需包，测试和开发工具不进入部署依赖。

### 数据库和 Redis

支持 MySQL（`mysql+pymysql://...`）和 PostgreSQL
（`postgresql+psycopg://...?...`）。Vercel Marketplace 可连接 Neon PostgreSQL
和 Upstash Redis。它们需要先在 Vercel 页面完成服务条款接受，再选择免费方案。
Upstash 免费方案需关闭自动升级，避免自动切换到付费套餐。

生产环境中的 `DATABASE_URL` 使用 SQLAlchemy 对应驱动的连接串，
`REDIS_URL` 使用 Upstash 的 TCP/TLS Redis 连接串（`rediss://...`），
不能使用 Redis HTTP REST URL。

新数据库首次部署前执行以下命令创建缺失表，不删除现有表：

```bash
python scripts/init_database.py
```

旧库的数据需要单独迁移。创建新库不会自动恢复旧用户、积分或订单。
数据库连接与建表不在 Vercel 应用导入期间执行；日志写入标准输出。
健康接口会报告数据库或 Redis 不可用，文档和 OpenAPI 可独立加载。

### Google 登录

在 Vercel 设置 `GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`，
并在 Google Cloud OAuth 客户端配置以下地址：

- 已授权 JavaScript 来源：`https://tube-savely-vue.vercel.app`
- 已授权重定向 URI：`https://tube-savely-vue.vercel.app/auth/oauth/google/callback`

前端先调用 `GET /api/v1/auth/oauth/google/url` 获取授权地址，
Google 回跳前端后，由前端把 `code` 和 `state` 提交给
`GET /api/v1/auth/oauth/google/callback` 换取应用登录凭证。
Google 客户端密钥只保存于后端环境变量。

### 前端调用

`BACKEND_CORS_ORIGINS` 是 JSON 数组，生产配置包括
`https://tube-savely-vue.vercel.app`。登录接口接收 JSON：

```javascript
const API = "https://tube-savely-server.vercel.app/api/v1";
const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
}).then(r => r.json());
if (login.code !== 200) throw new Error(login.msg);
const profile = await fetch(`${API}/users/profile`, {
  headers: { Authorization: `Bearer ${login.data.access_token}` },
}).then(r => r.json());
```

支付返回地址由 `FRONTEND_URL` 控制，支付通知地址由 `API_URL` 控制。
各支付平台还需配置对应密钥及回调 URL。积分购买档位通过
`/api/v1/credit_amount` 配置，并填写实际支付产品 ID；新库没有旧购买档位。

### 验证部署

```bash
python -m unittest discover -s tests -v
vercel deploy --prod --scope cosyment-s-team
```

测试使用临时 SQLite 数据库及模拟 Redis，覆盖注册、登录、用户资料、
订单查询、接口文档、跨域、支付客户端初始化和 yt-dlp 依赖。
测试不向真实支付平台发起扣款，也不修改生产数据库。

## 项目结构

```
backend/
├── app/                         # 主应用目录
│   ├── api/                     # API 路由
│   │   └── v1/                  # API v1 版本
│   ├── core/                    # 核心配置
│   │   ├── config.py            # 配置文件
│   │   ├── auth.py              # 鉴权
│   │   ├── oauth.py             # 三方鉴权
│   │   ├── deps.py              # 数据库实例
│   │   ├── exception.py         # 异常处理
│   │   ├── logger.py            # 日志
│   │   ├── middleware.py        # 中间件
│   │   └── security.py          # 安全相关
│   ├── db/                      # 数据库相关
│   ├── models/                  # 数据库模型
│   ├── schemas/                 # Pydantic 模型
│   ├── services/                # 业务逻辑
│   │   ├── video.py             # 视频服务
│   │   ├── payment.py           # 支付服务
│   │   ├── payments/            # 支付渠道服务
│   │   │   ├── alipay.py        # 支付宝服务
│   │   │   ├── wechat.py        # 微信支付服务
│   │   │   ├── paypal.py        # PayPal服务
│   │   │   ├── stripe.py        # Stripe服务
│   │   │   └── airwallex.py     # Airwallex服务
│   │   ├── video_transaction.py # 视频交易服务
│   │   └── task.py              # 任务服务
│   └─── vendor                  # 第三方解析服务
├── alembic/                     # 数据库迁移
├── downloads/                   # 下载文件存储
├── logs/                        # 日志文件
├── tests/                       # 测试用例
├── supportedsites.md            # 支持的视频网站列表
└── urls.md                      # API 文档
```

## 主要功能模块

1. 用户管理
   - 用户注册和登录
   - OAuth2 社交账号登录 (Google, GitHub, WeChat, Facebook)
   - 用户资料管理
   - JWT 认证和授权

2. 视频管理
   - 视频链接解析
   - 视频下载
   - 下载历史记录
   - 格式转换

3. 支付系统
   - 多渠道支付集成
     - 支付宝 (AliPay)
     - 微信支付 (WeChat Pay)
     - PayPal
     - Stripe (信用卡)
     - Airwallex
   - 积分充值管理
   - 支付订单处理
   - 支付回调处理

4. 任务系统
   - 视频格式转换
   - AI 视频生成
   - 任务队列管理
   - 进度追踪

5. 反馈系统
   - 用户反馈提交
   - 反馈记录管理

6. 积分系统
   - 用户积分管理
   - 积分历史记录

## API 端点

1. 认证相关
   ```
   POST /api/v1/auth/register         # 用户注册
   POST /api/v1/auth/login            # 用户登录
   POST /api/v1/auth/oauth/google     # Google OAuth 登录
   POST /api/v1/auth/oauth/github     # GitHub OAuth 登录
   POST /api/v1/auth/oauth/facebook   # Facebook OAuth 登录
   POST /api/v1/auth/oauth/wechat     # 微信 OAuth 登录
   ```

2. 用户相关
   ```
   GET  /api/v1/users/profile         # 获取用户资料
   PUT  /api/v1/users/profile         # 更新用户资料
   GET  /api/v1/users                 # 获取用户列表
   POST /api/v1/users                 # 创建新用户
   POST /api/v1/users/avatar          # 上传头像
   ```

3. 视频相关
   ```
   GET  /api/v1/videos/parse          # 解析视频链接
   POST /api/v1/videos                # 创建视频记录
   GET  /api/v1/videos/history        # 获取下载历史
   DELETE /api/v1/videos/{id}         # 删除视频
   ```

4. 支付相关
   ```
   POST /api/v1/payments/create             # 购买积分
   POST /api/v1/payments/webhook/{provider} # 支付回调
   GET  /api/v1/payments/orders             # 获取支付订单列表
   GET  /api/v1/payments/status/{order_id}  # 获取订单状态
   ```

5. 任务相关
   ```
   POST /api/v1/tasks/convert              # 创建转换任务
   POST /api/v1/tasks/generate             # 创建生成任务
   GET  /api/v1/tasks/list                 # 获取任务列表
   GET  /api/v1/tasks/{task_id}            # 获取任务详情
   DELETE /api/v1/tasks/{task_id}          # 取消任务
   ```

6. 积分相关
   ```
   GET  /api/v1/credits                     # 获取积分余额
   GET  /api/v1/credits/history             # 获取积分历史
   POST /api/v1/credits/add                 # 增加积分
   POST /api/v1/credits/deduct              # 扣除积分
   ```

## 环境配置

### 0. 获取代码

```bash
git clone https://github.com/Cosymentx/TubeSavely-Server.git tubesavely-server
cd tubesavely-server
```

### 1. 创建并激活虚拟环境

Windows:
```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux/Mac:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
python -m pip install -r requirements.txt
```

本地运行还需安装 FFmpeg，并确保 `ffmpeg`、`ffprobe` 和 `deno` 可通过 `PATH` 找到。
Deno 随 Python 依赖安装，激活虚拟环境后即可使用；FFmpeg 需通过操作系统包管理器安装。

### 3. 环境变量配置

创建 `.env` 文件并配置以下环境变量：

开发环境读取 `.env`；设置 `PRODUCTION=true` 时读取 `.env.production`。
Docker 构建需要这两个文件存在，并使用 `.env.production` 中的配置。

```
DATABASE_URL=mysql+pymysql://user:password@localhost/tubesavely?charset=utf8mb4
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key
API_V1_STR=/api/v1
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OAuth2 配置
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
FACEBOOK_CLIENT_ID=your-facebook-client-id
FACEBOOK_CLIENT_SECRET=your-facebook-client-secret
WECHAT_APP_ID=your-wechat-app-id
WECHAT_APP_SECRET=your-wechat-app-secret

# MinIO配置
MINIO_ENDPOINT=your-minio-endpoint
MINIO_ACCESS_KEY=your-minio-access-key
MINIO_SECRET_KEY=your-minio-secret-key
MINIO_BUCKET_NAME=your-minio-bucket-name
MINIO_SECURE=true

# 支付相关配置
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
CREEM_API_KEY=your-creem-api-key
```

### 4. 数据库配置

1. 确保 MySQL 8.0+ 已安装并运行
2. 创建数据库：
```sql
CREATE DATABASE tubesavely CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
3. 运行数据库迁移：
```bash
alembic upgrade head
```

### 5. Redis 配置

确保 Redis 服务器已安装并运行在默认端口 (6379)。Redis 用于：
- API 速率限制
- 缓存管理
- 任务队列

### 6. 启动项目

确保你已经完成了上述所有配置步骤，然后按照以下步骤启动项目：

1. 激活虚拟环境（如果尚未激活）：
```bash
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate    # Windows
```

2. 启动后端服务：
```bash
# 开发模式（带有自动重载）
python -m uvicorn app.main:app --host 127.0.0.1 --port 9527 --reload

# 生产模式
python -m uvicorn app.main:app --host 127.0.0.1 --port 9527
```

启动后，可以通过以下地址访问：
- 检查：http://localhost:9527/api/v1/health
- API 文档：http://localhost:9527/docs
- ReDoc 文档：http://localhost:9527/redoc
- API 根路径：http://localhost:9527/api/v1

## 部署说明

### Docker 部署

当前 `docker-compose.yml` 只启用 FastAPI 应用服务。MySQL 和 Redis 服务定义已注释，
需提前准备可访问的 MySQL / Redis，并在 `.env.production` 中配置 `DATABASE_URL`
和 `REDIS_URL`。若要启用 Compose 中的数据库服务，需调整服务配置和连接地址。

应用镜像会安装 Deno、EJS、FFmpeg / ffprobe 和用于健康检查的 curl。

#### 前置要求
- Docker 20.10+
- Docker Compose v2.0+

#### 部署步骤

1. 构建并启动服务
```bash
# 在项目根目录下运行
docker compose up -d --build api
```

2. 执行数据库迁移
```bash
docker compose exec api alembic upgrade head
```

3. 验证服务状态
```bash
# 检查容器状态
docker compose ps

# 查看应用日志
docker compose logs -f api

# 检查健康接口
curl -f http://localhost:9527/api/v1/health
```

#### 常用操作

- 停止服务：`docker compose down`
- 重启服务：`docker compose restart api`
- 更新代码或依赖后重新构建：`docker compose up -d --build api`
- 查看日志：`docker compose logs -f api`
- 进入容器：`docker compose exec api bash`

#### 数据持久化
- 下载文件存储在 `./downloads` 目录
- 日志文件存储在 `./logs` 目录
- 平台 Cookies 存储在 `./cookies` 目录，挂载到容器的 `/app/cookies`
- MySQL / Redis 的持久化由实际部署它们的服务负责

## 速率限制配置

API 默认限制：
- 未认证用户：10 请求/分钟
- 已认证用户：60 请求/分钟
- 下载请求：3 请求/分钟

可在 `app/core/config.py` 中调整这些限制。

## 日志配置

日志文件位于 `logs/` 目录：
- `app.log`: 应用程序日志
- `access.log`: 访问日志
- `error.log`: 错误日志

## 下载配置

下载的视频文件将保存在 `downloads/` 目录中，按用户ID和日期组织：
```
downloads/
├── user_1/
│   ├── 2024-03/
│   └── 2024-02/
└── user_2/
    └── 2024-03/
```

## 支持的视频网站

详见 `supportedsites.md` 文件，包括但不限于：
- YouTube
- Bilibili
- Twitter
- TikTok

## 测试

本仓库的部署验证使用 `python -m unittest discover -s tests -v`。

仅验证 yt-dlp 升级（激活虚拟环境后，在项目根目录执行）：

```bash
python -m unittest tests.test_yt_dlp_vendor -v
```


## 贡献

1. Fork 项目
2. 创建特性分支
3. 提交代码
4. 发起 Pull Request

## 许可证

MIT License
