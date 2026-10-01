# 使用Python 3.13作为基础镜像
FROM python:3.13

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRODUCTION=true

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件--复制配置文件和应用代码--复制数据库迁移配置、应用代码、数据库迁移脚本和第三方库--复制环境变量配置
COPY alembic.ini .
COPY app/ app/
COPY alembic/ alembic/

# 根据环境变量复制对应的配置文件
COPY .env.production .env.production
COPY .env .env
RUN if [ "$PRODUCTION" = "true" ] ; then cp .env.production .env ; fi

# 创建必要的目录
RUN mkdir -p downloads logs

# 暴露端口
EXPOSE 9527

# 健康检查配置
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9527/api/v1/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9527"]
