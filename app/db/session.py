from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    **({'connect_args': {'connect_timeout': 5, 'read_timeout': 10, 'write_timeout': 10}}
       if settings.DATABASE_URL.startswith('mysql+pymysql:') else {}),
    **({'connect_args': {'connect_timeout': 5}}
       if settings.DATABASE_URL.startswith('postgresql') else {}),
    **({'poolclass': NullPool} if os.environ.get('VERCEL') else {}),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
