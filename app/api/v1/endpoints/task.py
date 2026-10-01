from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.schemas.task import Task, TaskCreate
from app.schemas.response import ApiResponse
from app.core import deps
from app.services import task as task_service
from app.models.user import User

router = APIRouter()

@router.post("/convert", response_model=ApiResponse[Task])
def create_convert_task(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    task_in: TaskCreate,
    background_tasks: BackgroundTasks
):
    """创建视频转换任务
    
    将现有视频转换为不同格式或进行处理，例如：
    - 视频格式转换（MP4, AVI, MOV等）
    - 视频压缩和优化
    - 视频剪辑和编辑
    - 添加水印或特效
    - 提取音频
    """
    try:
        # 检查用户积分是否足够
        if current_user.credits < task_in.credits_cost:
            return ApiResponse(
                code=400,
                msg="Insufficient credits balance",
                data=None
            )
        
        # 创建转换任务
        task = task_service.create_convert_task(
            db=db,
            user_id=current_user.id,
            task_in=task_in
        )
        
        # 在后台开始处理任务
        background_tasks.add_task(
            task_service.process_convert_task,
            db=db,
            task_id=task.id
        )
        
        return ApiResponse(data=task)
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to create convert task: {str(e)}",
            data=None
        )

@router.post("/generate", response_model=ApiResponse[Task])
def create_generate_task(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    task_in: TaskCreate,
    background_tasks: BackgroundTasks
):
    """创建视频生成任务
    
    使用 AI 或模板生成全新的视频内容，例如：
    - AI 视频生成
    - 模板视频制作
    - 图片/PPT转视频
    - 文字转视频
    - 自动剪辑生成
    """
    try:
        # 检查用户积分是否足够
        if current_user.credits < task_in.credits_cost:
            return ApiResponse(
                code=400,
                msg="Insufficient credits balance",
                data=None
            )
        
        # 创建生成任务
        task = task_service.create_generate_task(
            db=db,
            user_id=current_user.id,
            task_in=task_in
        )
        
        # 在后台开始处理任务
        background_tasks.add_task(
            task_service.process_generate_task,
            db=db,
            task_id=task.id
        )
        
        return ApiResponse(data=task)
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to create generate task: {str(e)}",
            data=None
        )

@router.get("/list", response_model=ApiResponse[List[Task]])
def list_tasks(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    skip: int = 0,
    limit: int = 10,
    task_type: str = None
):
    """获取用户的任务列表
    
    Args:
        task_type: 任务类型，可选值：
            - convert: 视频转换任务（格式转换、压缩、剪辑等）
            - generate: 视频生成任务（AI生成、模板制作等）
            - None: 所有任务
    """
    try:
        tasks = task_service.get_user_tasks(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            task_type=task_type
        )
        return ApiResponse(data=tasks)
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to fetch tasks: {str(e)}",
            data=None
        )

@router.get("/{task_id}", response_model=ApiResponse[Task])
def get_task_detail(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    task_id: int
):
    """获取任务详情
    
    返回任务的详细信息，包括：
    - 任务状态
    - 进度信息
    - 输入参数
    - 输出结果
    - 错误信息（如果有）
    """
    try:
        task = task_service.get_task(db, task_id)
        if not task:
            return ApiResponse(
                code=404,
                msg="Task not found",
                data=None
            )
        if task.user_id != current_user.id:
            return ApiResponse(
                code=403,
                msg="Not enough permissions",
                data=None
            )
        return ApiResponse(data=task)
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to fetch task details: {str(e)}",
            data=None
        )

@router.delete("/{task_id}", response_model=ApiResponse[dict])
def cancel_task(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    task_id: int
):
    """取消任务
    
    可以取消的任务状态：
    - pending: 等待处理
    - processing: 处理中
    
    已完成或失败的任务无法取消
    """
    try:
        task = task_service.get_task(db, task_id)
        if not task:
            return ApiResponse(
                code=404,
                msg="Task not found",
                data=None
            )
        if task.user_id != current_user.id:
            return ApiResponse(
                code=403,
                msg="Not enough permissions",
                data=None
            )
        
        if task_service.cancel_task(db, task_id):
            return ApiResponse(data={"status": "success"})
        else:
            return ApiResponse(
                code=400,
                msg="Cannot cancel completed or failed task",
                data=None
            )
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to cancel task: {str(e)}",
            data=None
        )