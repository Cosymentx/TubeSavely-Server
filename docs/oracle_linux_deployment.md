# Oracle Linux 部署指南

此方式在 Oracle Linux 上运行完整后端，监听 9527 端口。需要先安装 Git、Docker Engine 与 Docker Compose 插件。数据库和 Redis 使用已有服务；仓库的 Compose 文件只启动 API，不会创建 MySQL 或 Redis。

## 配置

```bash
git clone https://github.com/Cosymentx/TubeSavely-Server.git tubesavely-server
cd tubesavely-server
cp .env.example .env.production
chmod 600 .env.production
mkdir -p downloads logs cookies
```

编辑 `.env.production`，至少填写：

- `PRODUCTION=true`。
- `SECRET_KEY`：随机生成的登录签名密钥。
- `DATABASE_URL`：可访问的 MySQL 或 PostgreSQL 连接串。
- `REDIS_URL`：可访问的 Redis 连接串。
- `API_URL`、`FRONTEND_URL`、`BACKEND_CORS_ORIGINS`：真实后端地址、前端地址及 JSON 格式跨域白名单。
- 所需支付渠道和 OAuth 登录的环境变量，配置项见 `.env.example`。

容器内的 `localhost` 指 API 容器自身，不能用它访问宿主机或另一个容器中的数据库。数据库账号应具有应用迁移所需权限。

视频平台 Cookie 可以挂载到 `cookies/youtube.txt`、`cookies/douyin.txt`、`cookies/tiktok.txt`，或使用 README 中的 Base64 环境变量。Cookie、环境文件和数据库备份不应提交到 Git，也不会打包进 Docker 镜像。

## 构建与启动

```bash
docker compose build
docker compose run --rm api alembic upgrade head
docker compose up -d
docker compose ps
docker compose logs --tail=100 api
```

访问：

- 健康检查：`http://服务器地址:9527/api/v1/health`
- Swagger：`http://服务器地址:9527/docs`
- ReDoc：`http://服务器地址:9527/redoc`

对公网使用时，在 API 前配置 HTTPS 反向代理，并按实际需要开放防火墙端口。Compose 已设置 `restart: unless-stopped`；主机需要启用 Docker 服务自动启动。

## 更新

先备份数据库，再执行：

```bash
git pull --ff-only
docker compose build
docker compose run --rm api alembic upgrade head
docker compose up -d
docker compose logs --tail=100 api
```

修改 `.env.production` 后，使用 `docker compose up -d --force-recreate api` 重新创建容器，使配置生效。排查连接问题时检查健康接口和日志；不要将包含密钥的完整环境变量输出公开。
