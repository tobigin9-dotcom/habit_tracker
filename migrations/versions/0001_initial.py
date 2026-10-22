"""Create users, habits, completions, and reminder delivery tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_table(
        "habits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("goal", sa.String(length=255), nullable=False),
        sa.Column("target_completions", sa.Integer(), nullable=False),
        sa.Column("completion_count", sa.Integer(), nullable=False),
        sa.Column("reminder_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_habits_owner_id", "habits", ["owner_id"])
    op.create_table(
        "habit_completions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "habit_id",
            sa.Integer(),
            sa.ForeignKey("habits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("completion_date", sa.Date(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "habit_id",
            "completion_date",
            name="uq_habit_day",
        ),
    )
    op.create_index(
        "ix_habit_completions_habit_id",
        "habit_completions",
        ["habit_id"],
    )
    op.create_index(
        "ix_habit_completions_completion_date",
        "habit_completions",
        ["completion_date"],
    )
    op.create_table(
        "reminder_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "habit_id",
            sa.Integer(),
            sa.ForeignKey("habits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reminder_date", sa.Date(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "habit_id",
            "reminder_date",
            name="uq_reminder_habit_day",
        ),
    )
    op.create_index(
        "ix_reminder_deliveries_habit_id", "reminder_deliveries", ["habit_id"]
    )
    op.create_index(
        "ix_reminder_deliveries_reminder_date",
        "reminder_deliveries",
        ["reminder_date"],
    )


def downgrade():
    op.drop_index(
        "ix_reminder_deliveries_reminder_date",
        table_name="reminder_deliveries",
    )
    op.drop_index(
        "ix_reminder_deliveries_habit_id",
        table_name="reminder_deliveries",
    )
    op.drop_table("reminder_deliveries")
    op.drop_index(
        "ix_habit_completions_completion_date", table_name="habit_completions"
    )
    op.drop_index(
        "ix_habit_completions_habit_id",
        table_name="habit_completions",
    )
    op.drop_table("habit_completions")
    op.drop_index("ix_habits_owner_id", table_name="habits")
    op.drop_table("habits")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
