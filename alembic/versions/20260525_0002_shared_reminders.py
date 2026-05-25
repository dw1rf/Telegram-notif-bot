"""Add shared reminders."""

from alembic import op
import sqlalchemy as sa


revision = "20260525_0002"
down_revision = "20260525_0001"
branch_labels = None
depends_on = None


repeat_rule = sa.Enum("none", "daily", "weekly", "monthly", name="shared_repeat_rule")
shared_status = sa.Enum("active", "cancelled", "completed", name="shared_reminder_status")
member_role = sa.Enum("owner", "member", name="shared_reminder_member_role")
member_status = sa.Enum("active", "muted", "left", "removed", name="shared_reminder_member_status")
delivery_status = sa.Enum("sent", "failed", name="reminder_delivery_status")


def upgrade() -> None:
    bind = op.get_bind()
    repeat_rule.create(bind, checkfirst=True)
    shared_status.create(bind, checkfirst=True)
    member_role.create(bind, checkfirst=True)
    member_status.create(bind, checkfirst=True)
    delivery_status.create(bind, checkfirst=True)

    op.create_table(
        "shared_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("repeat_rule", repeat_rule, nullable=True),
        sa.Column("status", shared_status, nullable=False, server_default="active"),
        sa.Column("invite_token_hash", sa.String(length=64), nullable=True),
        sa.Column("invite_token_preview", sa.String(length=32), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_shared_reminders_invite_token_hash"), "shared_reminders", ["invite_token_hash"], unique=True)
    op.create_index(op.f("ix_shared_reminders_owner_user_id"), "shared_reminders", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_shared_reminders_remind_at"), "shared_reminders", ["remind_at"], unique=False)
    op.create_index(op.f("ix_shared_reminders_status"), "shared_reminders", ["status"], unique=False)

    op.create_table(
        "shared_reminder_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("shared_reminders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("role", member_role, nullable=False, server_default="member"),
        sa.Column("status", member_status, nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("reminder_id", "user_id", name="uq_shared_reminder_member"),
    )
    op.create_index(op.f("ix_shared_reminder_members_reminder_id"), "shared_reminder_members", ["reminder_id"], unique=False)
    op.create_index(op.f("ix_shared_reminder_members_status"), "shared_reminder_members", ["status"], unique=False)
    op.create_index(op.f("ix_shared_reminder_members_user_id"), "shared_reminder_members", ["user_id"], unique=False)

    op.create_table(
        "reminder_delivery_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("shared_reminders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", delivery_status, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_reminder_delivery_log_reminder_id"), "reminder_delivery_log", ["reminder_id"], unique=False)
    op.create_index(op.f("ix_reminder_delivery_log_status"), "reminder_delivery_log", ["status"], unique=False)
    op.create_index(op.f("ix_reminder_delivery_log_user_id"), "reminder_delivery_log", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reminder_delivery_log_user_id"), table_name="reminder_delivery_log")
    op.drop_index(op.f("ix_reminder_delivery_log_status"), table_name="reminder_delivery_log")
    op.drop_index(op.f("ix_reminder_delivery_log_reminder_id"), table_name="reminder_delivery_log")
    op.drop_table("reminder_delivery_log")

    op.drop_index(op.f("ix_shared_reminder_members_user_id"), table_name="shared_reminder_members")
    op.drop_index(op.f("ix_shared_reminder_members_status"), table_name="shared_reminder_members")
    op.drop_index(op.f("ix_shared_reminder_members_reminder_id"), table_name="shared_reminder_members")
    op.drop_table("shared_reminder_members")

    op.drop_index(op.f("ix_shared_reminders_status"), table_name="shared_reminders")
    op.drop_index(op.f("ix_shared_reminders_remind_at"), table_name="shared_reminders")
    op.drop_index(op.f("ix_shared_reminders_owner_user_id"), table_name="shared_reminders")
    op.drop_index(op.f("ix_shared_reminders_invite_token_hash"), table_name="shared_reminders")
    op.drop_table("shared_reminders")

    bind = op.get_bind()
    delivery_status.drop(bind, checkfirst=True)
    member_status.drop(bind, checkfirst=True)
    member_role.drop(bind, checkfirst=True)
    shared_status.drop(bind, checkfirst=True)
    repeat_rule.drop(bind, checkfirst=True)
