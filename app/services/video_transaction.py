from sqlalchemy.orm import Session

from app.models.video import Video
from app.models.credit import Credit
from app.models.user import User
from app.schemas.video import VideoBase
from app.services.credit import InsufficientCreditsError


def complete_video_transaction(
    db: Session,
    user: User,
    video_data: VideoBase,
    credits_cost: int = 3
):
    """Persist a successful extraction and charge the user atomically."""
    if credits_cost <= 0:
        raise ValueError("credits_cost must be greater than zero")

    try:
        locked_user = (
            db.query(User)
            .filter(User.id == user.id)
            .populate_existing()
            .with_for_update()
            .one()
        )
        if locked_user.credits < credits_cost:
            raise InsufficientCreditsError("Insufficient credits for this operation")

        video = Video(
            original_url=video_data.url,
            title=video_data.title,
            description=video_data.description,
            thumbnail=video_data.thumbnail,
            duration=video_data.duration,
            video_id=video_data.video_id,
            platform=video_data.platform,
            author=video_data.author,
            formats=[{**f.model_dump(), 'download_headers': f.download_headers,
                      'direct_download': f.direct_download} for f in video_data.formats],
            credits_cost=credits_cost,
        )
        db.add(video)
        db.flush()

        video.users.append(locked_user)
        locked_user.credits -= credits_cost

        db.add(Credit(
            user_id=locked_user.id,
            credits=-credits_cost,
            action="Consume",
            type=2,
            description=f"Video extraction: {video_data.title}",
        ))

        db.commit()
        db.refresh(video)
        db.refresh(locked_user)
        return video
    except Exception:
        db.rollback()
        raise
