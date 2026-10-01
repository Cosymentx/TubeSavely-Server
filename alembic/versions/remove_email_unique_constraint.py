"""remove email unique constraint

Revision ID: remove_email_unique_constraint
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_email_unique_constraint'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 移除 email 字段的唯一约束
    op.drop_constraint('uq_users_email', 'users', type_='unique')

def downgrade():
    # 恢复 email 字段的唯一约束
    op.create_unique_constraint('uq_users_email', 'users', ['email'])