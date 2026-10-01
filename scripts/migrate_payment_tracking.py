"""Add checkout tracking columns without altering existing payment records."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, text
from app.db.session import engine

with engine.begin() as connection:
    columns = {column['name'] for column in inspect(connection).get_columns('payments')}
    changes = {
        'currency': "VARCHAR(3) NOT NULL DEFAULT 'USD'",
        'provider_checkout_id': 'VARCHAR(255)',
        'provider_product_id': 'VARCHAR(255)',
    }
    for name, definition in changes.items():
        if name not in columns:
            connection.execute(text(f'ALTER TABLE payments ADD COLUMN {name} {definition}'))
    if engine.dialect.name == 'postgresql':
        connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_provider_checkout_id ON payments (provider_checkout_id)'))
print('Payment checkout tracking schema ready')
