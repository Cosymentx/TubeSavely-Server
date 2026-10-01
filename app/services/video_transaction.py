from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.models.video import Video
from app.models.credit import Credit
from app.models.user import User
from app.schemas.video import VideoBase

def complete_video_transaction(
    db: Session,
    user: User,
    video_data: VideoBase,
    credits_cost: int = 3
):
    """
    处理视频解析成功后的数据更新
    包括：
    1. 创建视频记录
    2. 创建用户-视频关联
    3. 扣除用户积分
    4. 记录积分变动
    所有操作在一个事务中完成
    """
    try:
        # 创建视频记录
        video = Video(
            original_url=video_data.url,
            title=video_data.title,
            description=video_data.description,
            thumbnail=video_data.thumbnail,
            duration=video_data.duration,
            video_id=video_data.video_id,
            platform=video_data.platform,
            author=video_data.author,
            formats=[f.dict() for f in video_data.formats],
            credits_cost=credits_cost  # 设置所需积分
        )
        db.add(video)
        db.flush()  # 刷新会话以获取video.id
        
        # 创建用户-视频关联
        video.users.append(user)
        
        # 扣除用户积分
        user.credits -= credits_cost
        
        # 记录积分消费
        credit_record = Credit(
            user_id=user.id,
            credits=-credits_cost,
            action='Consume',  # 添加积分变动类型
            type=2,
            description=f'extraction video ：{video_data.title}'
        )
        db.add(credit_record)
        
        # 提交事务
        db.commit()
        db.refresh(video)
        
    except Exception as e:
        db.rollback()
        raise e