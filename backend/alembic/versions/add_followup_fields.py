"""Add follow-up configuration fields to leads table.

Revision ID: add_followup_fields
Revises: 05b279f3899e
Create Date: 2026-01-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_followup_fields'
down_revision = '05b279f3899e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to leads table
    op.add_column('leads', sa.Column('num_followups', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('leads', sa.Column('followup_delay_days', sa.Integer(), nullable=False, server_default='3'))


def downgrade() -> None:
    # Remove columns from leads table
    op.drop_column('leads', 'followup_delay_days')
    op.drop_column('leads', 'num_followups')
