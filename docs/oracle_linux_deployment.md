# Oracle Linux 部署指南

本文档详细说明如何在Oracle Linux服务器上部署TubeSavely后端服务。

## 1. 系统要求

- Oracle Linux 8.x 或更高版本
- 最小4GB RAM
- 20GB可用磁盘空间

## 2. 安装基础环境

### 2.1 更新系统包
```bash
sudo dnf update -y
```

### 2.2 安装必要工具
```bash
sudo dnf install -y dnf-utils device-mapper-persistent-data lvm2 git curl wget
```

### 2.3 安装Python 3.13
```bash
sudo dnf install -y python3.13 python3.13-devel python3.13-pip

# 设置Python 3.13为默认版本
sudo alternatives --set python /usr/bin/python3.13
```

### 2.4 安装Docker
```bash
# 添加Docker仓库
sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo

# 安装Docker
sudo dnf install -y docker-ce docker-ce-cli containerd.io

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到docker组
sudo usermod -aG docker $USER
```

### 2.5 安装Docker Compose
```bash
# 下载Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# 添加执行权限
sudo chmod +x /usr/local/bin/docker-compose
```

## 3. 部署项目

### 3.1 克隆项目代码
```bash
git clone https://github.com/Cosymentx/TubeSavely-Server.git tubesavely-server
cd tubesavely-server
```

### 3.2 配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量文件
vim .env
```

配置以下必要的环境变量：
```env
PYTHONPATH=/app
DATABASE_URL=mysql+pymysql://user:password@mysql/tubesavely?charset=utf8mb4
SECRET_KEY=your-secret-key
API_V1_STR=/api/v1
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_URL=redis://redis:6379/0

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
```

### 3.3 创建必要目录
```bash
# 创建数据和日志目录
mkdir -p mysql_data redis_data downloads logs

# 设置目录权限
chmod -R 750 downloads logs
```

### 3.4 启动服务
```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps
```

### 3.5 执行数据库迁移
```bash
# 进入API容器
docker-compose exec api bash

# 执行迁移
alembic upgrade head

# 退出容器
exit
```

## 4. 验证部署

### 4.1 检查服务状态
```bash
# 查看所有容器状态
docker-compose ps

# 查看应用日志
docker-compose logs -f api
```

### 4.2 访问API文档
- Swagger UI: http://your-server-ip:8000/docs
- ReDoc: http://your-server-ip:8000/redoc

## 5. 维护操作

### 5.1 更新代码
```bash
# 拉取最新代码
git pull

# 重新构建并启动服务
docker-compose up -d --build
```

### 5.2 查看日志
```bash
# 查看特定服务的日志
docker-compose logs -f [service_name]

# 查看应用日志
tail -f logs/app.log
```

### 5.3 备份数据
```bash
# 备份MySQL数据
docker-compose exec mysql mysqldump -u root -p tubesavely > backup.sql
```

### 5.4 常见问题处理

1. 如果服务无法启动，检查日志：
```bash
docker-compose logs -f
```

2. 如果需要重启服务：
```bash
docker-compose restart
```

3. 如果需要完全重建：
```bash
docker-compose down
docker-compose up -d --build
```

## 6. 安全建议

1. 配置防火墙，只开放必要端口
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

2. 定期更新系统和依赖
```bash
sudo dnf update -y
docker-compose pull
```

3. 配置SSL证书
建议使用Nginx作为反向代理，配置SSL证书实现HTTPS访问。

## 7. 监控建议

1. 使用Docker stats监控容器资源使用
```bash
docker stats
```

2. 设置日志轮转
```bash
# 编辑logrotate配置
sudo vim /etc/logrotate.d/tubesavely
```

添加以下内容：
```
/path/to/tubesavely-server/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
```

## 8. 性能优化

1. 调整Docker容器资源限制
2. 优化MySQL配置
3. 配置Redis持久化
4. 使用CDN加速静态资源

## 9. 故障恢复

1. 服务器重启后自动启动服务
```bash
# 确保Docker服务开机自启
sudo systemctl enable docker

# 配置容器自动重启
docker-compose up -d
# 自动重启策略由 docker-compose.yml 中的 restart 配置控制
```

2. 数据恢复
```bash
# 从备份恢复MySQL数据
docker-compose exec -T mysql mysql -u root -p tubesavely < backup.sql
```

## 10. 联系与支持

如果在部署过程中遇到问题，请：
1. 查看应用日志文件
2. 检查Docker容器状态
3. 提交Issue到项目仓库
4. 联系技术支持团队
