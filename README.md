# TubeSavely Server

基于 FastAPI 和内置 yt-dlp 的视频信息解析 API。
仓库：https://github.com/Cosymentx/TubeSavely-Server

此仓库是精简版服务，入口为根目录 `main.py`，不包含用户登录、支付或 MySQL。
接口没有 `/api/v1` 前缀，也不需要 JWT Token。

## 本地运行

使用 Python 3.12 或 3.13，在仓库根目录执行：

```bash
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 9527 --reload
```

依赖文件包含 FastAPI、uvicorn、Redis 客户端、限流库及自定义解析器所需依赖。
部署时不需要运行 Jupyter 或安装 notebook 开发工具。

## Vercel 部署

1. 导入本仓库，选择 `master` 或包含修复的分支，Root Directory 设为仓库根目录。
2. 使用 Vercel 的 FastAPI 自动检测；应用入口为 `main.py` 中的 `app`。
3. 在 Settings → Environment Variables 配置下表中的变量。
4. 部署后检查 `/docs`、`/openapi.json` 和 `/health`。
5. 修改依赖或环境变量后重新部署；排查依赖问题时关闭使用旧 Build Cache 的选项。

| 环境变量 | 用途 | 示例 |
| --- | --- | --- |
| `BACKEND_CORS_ORIGINS` | 允许浏览器调用接口的前端 Origin，JSON 数组 | `["https://your-frontend.vercel.app","http://localhost:5173"]` |
| `REDIS_URL` | 可选，启用 Redis 限流；必须使用 Vercel 可访问的 Redis | `rediss://:PASSWORD@HOST:PORT/0` |

未配置 `REDIS_URL` 时，服务不连接 Redis，且不启用请求限流。
配置后按客户端 IP 和接口限制每 5 秒 1 次请求，超限返回 HTTP 429。
若已配置的 Redis 无法初始化，文档仍可打开，`/health` 报告异常，
`/test` 和 `/parse` 返回 HTTP 503，避免绕过已配置的限流。
Vercel 环境没有项目专用的本地 Redis，不能使用 `127.0.0.1:6379`。

前端应使用可公开访问的生产域名。如果返回 Vercel 登录页，检查项目的
Deployment Protection 设置。当前生产地址为：

```text
https://tube-savely-server.vercel.app
```

## API

| 方法 | 路径 | 参数 | 说明 |
| --- | --- | --- | --- |
| GET | `/docs` | 无 | Swagger 文档 |
| GET | `/openapi.json` | 无 | OpenAPI 定义 |
| GET | `/health` | 无 | 服务与 Redis 状态 |
| GET | `/test` | `params` | 连通性测试 |
| GET | `/parse` | `url` | 视频信息解析 |

```bash
curl 'https://tube-savely-server.vercel.app/test?params=hello'
curl --get 'https://tube-savely-server.vercel.app/parse' \
  --data-urlencode 'url=https://www.youtube.com/watch?v=jNQXAC9IVRw'
```

解析响应采用 `{ "code": 200, "msg": "success", "data": ... }` 格式，
前端需要同时检查 HTTP 状态、业务 `code` 以及 `data` 是否为空。

```javascript
const api = "https://tube-savely-server.vercel.app";
const response = await fetch(`${api}/parse?${new URLSearchParams({ url: videoUrl })}`);
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const result = await response.json();
if (result.code !== 200 || !result.data) throw new Error(result.msg || "解析失败");
console.log(result.data);
```

## 验证与排错

```bash
python -m pip install httpx==0.28.1
python -m unittest discover -s tests -v
```

测试覆盖无需 uvicorn 的应用导入、无 Redis 时的文档访问、跨域预检、
Redis 故障时的 HTTP 503，以及正常 Redis 配置下的限流调用。
测试中的 Redis 为模拟对象，不访问真实数据库或在线平台。

- `ModuleNotFoundError: No module named 'uvicorn'`：确认部署包含最新的
  `requirements.txt`，Vercel Root Directory 为仓库根目录，再重新构建部署。
  本版将 uvicorn 导入放在本地启动函数中，Vercel 导入 ASGI 应用时不需要它。
- `/docs` 可访问但浏览器调用被拒绝：检查 `BACKEND_CORS_ORIGINS`，
  Origin 包含协议和端口，不包含路径或末尾 `/`。
- `/test` 返回 503：检查 `REDIS_URL`、Redis TLS 设置和网络连通性。
- 在线平台解析失败：检查 yt-dlp 版本、平台登录要求、网络和 Vercel 执行时限。

当前远程仓库内置 yt-dlp 为 `2024.07.09`，本次部署修复未更新这份源码。
另一个本地项目 `tubesavely-server/app/vendor/yt_dlp` 的升级不会自动同步到此仓库。
本项目禁用 yt-dlp 文件缓存以适配函数运行环境。视频解析返回链接，
长时间下载、FFmpeg 合并和持久化文件需要另外设计执行和存储方式。

官方参考：[FastAPI 部署](https://vercel.com/docs/frameworks/backend/fastapi)、
[Python 运行时](https://vercel.com/docs/functions/runtimes/python)。
