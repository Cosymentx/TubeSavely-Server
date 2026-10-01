from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.task import Task
from app.schemas.task import TaskCreate

def create_convert_task(
    db: Session,
    user_id: int,
    task_in: TaskCreate
) -> Task:
    """创建视频转换任务"""
    task = Task(
        title=task_in.title,
        description=task_in.description,
        input_url=task_in.input_url,
        output_format=task_in.output_format,
        task_type="convert",
        status="pending",
        user_id=user_id,
        credit_cost=task_in.credit_cost
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def create_generate_task(
    db: Session,
    user_id: int,
    task_in: TaskCreate
) -> Task:
    """创建视频生成任务"""
    task = Task(
        title=task_in.title,
        description=task_in.description,
        input_params=task_in.input_params,
        task_type="generate",
        status="pending",
        user_id=user_id,
        credit_cost=task_in.credit_cost
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def get_task(
    db: Session,
    task_id: int
) -> Optional[Task]:
    """获取任务详情"""
    return db.query(Task).filter(Task.id == task_id).first()

def get_user_tasks(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 10,
    task_type: str = None
) -> List[Task]:
    """获取用户的任务列表"""
    query = db.query(Task).filter(Task.user_id == user_id)
    if task_type:
        query = query.filter(Task.task_type == task_type)
    return query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

def cancel_task(
    db: Session,
    task_id: int
) -> bool:
    """取消任务"""
    task = get_task(db, task_id)
    if not task:
        return False
    
    if task.status not in ["pending", "processing"]:
        return False
    
    task.status = "cancelled"
    db.commit()
    return True

async def process_convert_task(
    db: Session,
    task_id: int
):
    """处理视频转换任务"""
    task = get_task(db, task_id)
    if not task:
        return
    
    try:
        task.status = "processing"
        db.commit()
        
        # TODO: 实现视频转换逻辑
        # 1. 下载源视频
        # 2. 转换格式
        # 3. 上传结果
        
        task.status = "completed"
        db.commit()
    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        db.commit()

async def process_generate_task(
    db: Session,
    task_id: int
):
    """处理视频生成任务"""
    task = get_task(db, task_id)
    if not task:
        return
    
    try:
        task.status = "processing"
        db.commit()
        
        # TODO: 实现视频生成逻辑
        # 1. 解析输入参数
        # 2. 调用 AI 或模板生成视频
        # 3. 上传结果
        
        task.status = "completed"
        db.commit()
    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        db.commit()