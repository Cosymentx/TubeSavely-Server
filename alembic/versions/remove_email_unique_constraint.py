"""remove legacy users.email unique constraint when present

Revision ID: remove_email_unique_constraint
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "remove_email_unique_constraint"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    constraints = {item.get("name") for item in inspector.get_unique_constraints("users")}
    if "uq_users_email" in constraints:
        op.drop_constraint("uq_users_email", "users", type_="unique")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    constraints = {item.get("name") for item in inspector.get_unique_constraints("users")}
    if "uq_users_email" not in constraints:
        op.create_unique_constraint("uq_users_email", "users", ["email"])
