import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logging():
    # 创建日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 设置根日志器级别
    logging.getLogger().setLevel(logging.INFO if os.environ.get('VERCEL') else logging.DEBUG)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

    if not os.environ.get('VERCEL'):
        file_handler = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)

    # 设置特定模块的日志级别
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if os.environ.get('VERCEL') else logging.INFO)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.DEBUG) 
