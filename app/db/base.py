# Import all the models, so that Base has them before being
# imported by Alembic
from .base_class import Base  # noqa
from ..models.user import User  # noqa
from ..models.video import Video  # noqa
from ..models.payment import Payment  # noqa
from ..models.payment_event import PaymentEvent  # noqa
from ..models.feedback import Feedback  # noqa
from ..models.task import Task  # noqa
from ..models.credit import Credit  # noqa
from ..models.video_user_relation import VideoUserRelation  # noqa

# Make sure all models are imported before initializing Base
# This is required for relationships to work properly
__all__ = ["Base", "User", "Video", "Payment", "PaymentEvent", "Feedback", "Task", "Credit", "VideoUserRelation"]