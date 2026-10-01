import logging
from typing import Optional
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile
import uuid
from functools import cached_property

from app.core.config import settings

logger = logging.getLogger(__name__)

class MinioService:
    @cached_property
    def client(self):
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
            client.make_bucket(settings.MINIO_BUCKET_NAME)
        return client
    
    def _ensure_bucket_exists(self):
        """确保存储桶存在"""
        try:
            if not self.client.bucket_exists(settings.MINIO_BUCKET_NAME):
                self.client.make_bucket(settings.MINIO_BUCKET_NAME)
                logger.info(f"Bucket '{settings.MINIO_BUCKET_NAME}' created successfully")
        except S3Error as e:
            logger.error(f"Error checking/creating bucket: {str(e)}")
            raise
    
    async def upload_avatar(self, file: UploadFile, user_id: int) -> Optional[str]:
        """
        上传用户头像
        :param file: 上传的文件
        :param user_id: 用户ID
        :return: 文件的访问URL
        """
        try:
            # 生成唯一的文件名
            file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
            object_name = f"avatars/{user_id}/{str(uuid.uuid4())}.{file_extension}"
            
            # 读取文件内容
            content = await file.read()
            
            # 上传到MinIO
            self.client.put_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name,
                data=file.file,
                length=len(content),
                content_type=file.content_type
            )
            
            # 生成预签名URL（7天有效）
            url = self.client.presigned_get_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name,
                expires=timedelta(days=7)
            )
            
            logger.info(f"Successfully uploaded avatar for user {user_id}")
            return url
            
        except S3Error as e:
            logger.error(f"Error uploading avatar for user {user_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading avatar: {str(e)}")
            return None
    
    def delete_avatar(self, object_name: str) -> bool:
        """
        删除用户头像
        :param object_name: 文件的对象名称
        :return: 是否删除成功
        """
        try:
            self.client.remove_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name
            )
            logger.info(f"Successfully deleted avatar: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting avatar {object_name}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting avatar: {str(e)}")
            return False

# 创建全局MinIO服务实例
minio_service = MinioService() 
