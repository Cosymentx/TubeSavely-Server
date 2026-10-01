-- 创建数据库
CREATE DATABASE IF NOT EXISTS tubesavely
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE tubesavely;

-- 删除旧表（如果存在）
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS videos;
DROP TABLE IF EXISTS video_user_relations;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS feedbacks;
DROP TABLE IF EXISTS credits;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS credit_amount;


-- 创建用户表
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(50) UNIQUE NOT NULL,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255),
    has_password BOOLEAN DEFAULT FALSE,
    avatar VARCHAR(255),
    credits INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    oauth_provider VARCHAR(20),
    oauth_id VARCHAR(100),
    bio VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email_oauth (email, oauth_provider),
    INDEX idx_user_id (user_id),
    INDEX idx_oauth_id (oauth_id)
);

-- 创建视频表
CREATE TABLE videos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    original_url TEXT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    thumbnail TEXT,
    duration VARCHAR(50),
    platform VARCHAR(50),
    video_id VARCHAR(100),
    author VARCHAR(100),
    author_url TEXT,
    formats JSON,
    credits_cost INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_video_id (video_id)
);

-- 创建用户视频关联表
CREATE TABLE video_user_relations (
    user_id INT NOT NULL,
    video_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, video_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_video_id (video_id)
);

-- 创建积分记录表
CREATE TABLE credits (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    credits INT NOT NULL,
    action VARCHAR(100) NOT NULL,
    type INT NOT NULL,
    description VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
);

-- 创建支付记录表
CREATE TABLE payments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    trade_no VARCHAR(100),
    amount DECIMAL(10,2) NOT NULL,
    credits INT NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_order_id (order_id)
);

-- 创建反馈表
CREATE TABLE feedbacks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    email VARCHAR(255),
    content TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    ip_address VARCHAR(50),
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id)
);

-- 创建任务表
CREATE TABLE tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    input_url VARCHAR(2048),
    input_params JSON,
    output_format VARCHAR(50),
    output_url VARCHAR(2048),
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    progress INT,
    credits_cost INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id)
);

-- 创建积分价格配置表
CREATE TABLE credit_amount (
    id INT PRIMARY KEY AUTO_INCREMENT,
    credits INT NOT NULL,
    amount_cny DECIMAL(10,2) NOT NULL,
    amount_usd DECIMAL(10,2) NOT NULL,   
    creem_product_id VARCHAR(50),
     is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_credits (credits),
    INDEX idx_is_active (is_active)
);

-- 初始化积分价格配置
INSERT INTO credit_amount (credits, amount_cny, amount_usd, creem_product_id, is_active) VALUES
(100, 9.99, 6.99, "prod_51FPgJ7cgMp49sXIWdFqx6", TRUE),
(500, 19.99, 16.99, "prod_51FPgJ7cgMp49sXIWdFqx6", TRUE),
(1000, 39.99, 36.99, "prod_51FPgJ7cgMp49sXIWdFqx6", TRUE),
(2000, 59.99, 56.99, "prod_51FPgJ7cgMp49sXIWdFqx6", TRUE);