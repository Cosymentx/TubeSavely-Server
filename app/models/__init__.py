# 首先导入基础模型
from .user import User
from .video import Video

# 然后导入依赖基础模型的模型
from .credit import Credit
from .payment import Payment
from .feedback import Feedback
from .task import Task

# 确保所有模型都被导入
__all__ = [
    "Base",
    "User",
    "Video",
    "Credit",
    "Payment",
    "Feedback",
    "Task"
]
