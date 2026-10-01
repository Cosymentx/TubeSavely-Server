"""Initialize missing ORM tables in a new database; never drop existing tables."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect
from app.db.base import Base
from app.models.credit_amount import CreditAmount
from app.db.session import engine

if __name__ == '__main__':
    Base.metadata.create_all(bind=engine)
    print(f"Database schema ready: {len(inspect(engine).get_table_names())} tables")
