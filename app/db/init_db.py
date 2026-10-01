from sqlalchemy.orm import Session
import os

from ..models import Base
from ..db.session import engine

def init_db():
    """初始化数据库"""
    # 读取并执行 SQL 文件
    sql_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                           'migrations', '001_init_database.sql')
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()
        # 分割 SQL 语句
        statements = sql.split(';')
        for statement in statements:
            if statement.strip():
                try:
                    engine.execute(statement)
                except Exception as e:
                    print(f"Error executing SQL: {e}")
                    print(f"Statement: {statement}")

if __name__ == "__main__":
    init_db()