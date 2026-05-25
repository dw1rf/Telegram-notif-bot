from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SqlEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [item.value for item in enum_class]


class RepeatType(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SharedReminderStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class SharedReminderMemberRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"


class SharedReminderMemberStatus(str, Enum):
    ACTIVE = "active"
    MUTED = "muted"
    LEFT = "left"
    REMOVED = "removed"


class ReminderDeliveryStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)

    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    owned_shared_reminders: Mapped[list["SharedReminder"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    shared_memberships: Mapped[list["SharedReminderMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Reminder(TimestampMixin, Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    repeat_type: Mapped[RepeatType] = mapped_column(
        SqlEnum(RepeatType, name="repeat_type", values_callable=enum_values),
        default=RepeatType.NONE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    user: Mapped[User] = relationship(back_populates="reminders")


class SharedReminder(TimestampMixin, Base):
    __tablename__ = "shared_reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    repeat_rule: Mapped[RepeatType | None] = mapped_column(
        SqlEnum(RepeatType, name="shared_repeat_rule", values_callable=enum_values)
    )
    status: Mapped[SharedReminderStatus] = mapped_column(
        SqlEnum(SharedReminderStatus, name="shared_reminder_status", values_callable=enum_values),
        default=SharedReminderStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    invite_token_preview: Mapped[str | None] = mapped_column(String(32))
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(back_populates="owned_shared_reminders")
    members: Mapped[list["SharedReminderMember"]] = relationship(
        back_populates="reminder",
        cascade="all, delete-orphan",
    )
    delivery_logs: Mapped[list["ReminderDeliveryLog"]] = relationship(
        back_populates="reminder",
        cascade="all, delete-orphan",
    )


class SharedReminderMember(Base):
    __tablename__ = "shared_reminder_members"
    __table_args__ = (
        UniqueConstraint("reminder_id", "user_id", name="uq_shared_reminder_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("shared_reminders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[SharedReminderMemberRole] = mapped_column(
        SqlEnum(SharedReminderMemberRole, name="shared_reminder_member_role", values_callable=enum_values),
        default=SharedReminderMemberRole.MEMBER,
        nullable=False,
    )
    status: Mapped[SharedReminderMemberStatus] = mapped_column(
        SqlEnum(SharedReminderMemberStatus, name="shared_reminder_member_status", values_callable=enum_values),
        default=SharedReminderMemberStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reminder: Mapped[SharedReminder] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="shared_memberships")


class ReminderDeliveryLog(Base):
    __tablename__ = "reminder_delivery_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("shared_reminders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[ReminderDeliveryStatus] = mapped_column(
        SqlEnum(ReminderDeliveryStatus, name="reminder_delivery_status", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    reminder: Mapped[SharedReminder] = relationship(back_populates="delivery_logs")
