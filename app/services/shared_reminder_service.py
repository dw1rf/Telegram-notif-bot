from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    ReminderDeliveryLog,
    ReminderDeliveryStatus,
    RepeatType,
    SharedReminder,
    SharedReminderMember,
    SharedReminderMemberRole,
    SharedReminderMemberStatus,
    SharedReminderStatus,
    User,
)
from app.utils.timezone import calculate_next_occurrence, utc_now


TITLE_MAX_LENGTH = 120
DESCRIPTION_MAX_LENGTH = 1000


def generate_invite_token() -> str:
    return secrets.token_urlsafe(16)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_preview(token: str) -> str:
    return f"{token[:6]}..."


class SharedReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_shared_reminder(
        self,
        owner: User,
        title: str,
        description: str | None,
        remind_at: datetime,
        repeat_rule: RepeatType | None,
    ) -> tuple[SharedReminder, str]:
        token = generate_invite_token()
        reminder = SharedReminder(
            owner_user_id=owner.id,
            title=title[:TITLE_MAX_LENGTH],
            description=description[:DESCRIPTION_MAX_LENGTH] if description else None,
            remind_at=remind_at.astimezone(UTC),
            timezone=owner.timezone,
            repeat_rule=repeat_rule,
            status=SharedReminderStatus.ACTIVE,
            invite_token_hash=hash_invite_token(token),
            invite_token_preview=token_preview(token),
        )
        self.session.add(reminder)
        await self.session.flush()

        self.session.add(
            SharedReminderMember(
                reminder_id=reminder.id,
                user_id=owner.id,
                username=owner.username,
                first_name=owner.first_name,
                role=SharedReminderMemberRole.OWNER,
                status=SharedReminderMemberStatus.ACTIVE,
            )
        )
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder, token

    async def get_reminder(self, reminder_id: int) -> SharedReminder | None:
        result = await self.session.execute(
            select(SharedReminder)
            .options(selectinload(SharedReminder.members))
            .where(SharedReminder.id == reminder_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_token(self, token: str) -> SharedReminder | None:
        token_hash = hash_invite_token(token)
        now = utc_now()
        result = await self.session.execute(
            select(SharedReminder)
            .options(selectinload(SharedReminder.members))
            .where(
                SharedReminder.invite_token_hash == token_hash,
                SharedReminder.status == SharedReminderStatus.ACTIVE,
                (SharedReminder.token_expires_at.is_(None) | (SharedReminder.token_expires_at > now)),
            )
        )
        return result.scalar_one_or_none()

    async def get_member(self, reminder_id: int, user_id: int) -> SharedReminderMember | None:
        result = await self.session.execute(
            select(SharedReminderMember).where(
                SharedReminderMember.reminder_id == reminder_id,
                SharedReminderMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def active_member_count(self, reminder_id: int) -> int:
        total = await self.session.scalar(
            select(func.count(SharedReminderMember.id)).where(
                SharedReminderMember.reminder_id == reminder_id,
                SharedReminderMember.status == SharedReminderMemberStatus.ACTIVE,
            )
        )
        return int(total or 0)

    async def join_reminder(self, reminder: SharedReminder, user: User) -> tuple[bool, str]:
        member = await self.get_member(reminder.id, user.id)
        if member is None:
            self.session.add(
                SharedReminderMember(
                    reminder_id=reminder.id,
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    role=SharedReminderMemberRole.MEMBER,
                    status=SharedReminderMemberStatus.ACTIVE,
                )
            )
            await self.session.commit()
            return True, "joined"

        if member.status == SharedReminderMemberStatus.REMOVED:
            return False, "removed"

        member.username = user.username
        member.first_name = user.first_name
        if member.status == SharedReminderMemberStatus.ACTIVE:
            await self.session.commit()
            return False, "already"

        member.status = SharedReminderMemberStatus.ACTIVE
        await self.session.commit()
        return True, "restored"

    async def list_user_reminders(self, user_id: int) -> list[SharedReminderMember]:
        result = await self.session.execute(
            select(SharedReminderMember)
            .options(selectinload(SharedReminderMember.reminder))
            .where(
                SharedReminderMember.user_id == user_id,
                SharedReminderMember.status.in_(
                    [SharedReminderMemberStatus.ACTIVE, SharedReminderMemberStatus.MUTED]
                ),
            )
            .order_by(SharedReminderMember.joined_at.desc())
        )
        return list(result.scalars().all())

    async def list_members(self, reminder_id: int) -> list[SharedReminderMember]:
        result = await self.session.execute(
            select(SharedReminderMember)
            .where(SharedReminderMember.reminder_id == reminder_id)
            .order_by(SharedReminderMember.role.asc(), SharedReminderMember.joined_at.asc())
        )
        return list(result.scalars().all())

    async def ensure_owner(self, reminder_id: int, user_id: int) -> SharedReminder | None:
        result = await self.session.execute(
            select(SharedReminder).where(
                SharedReminder.id == reminder_id,
                SharedReminder.owner_user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_title(self, reminder: SharedReminder, title: str) -> SharedReminder:
        reminder.title = title[:TITLE_MAX_LENGTH]
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def update_description(self, reminder: SharedReminder, description: str | None) -> SharedReminder:
        reminder.description = description[:DESCRIPTION_MAX_LENGTH] if description else None
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def update_time(self, reminder: SharedReminder, remind_at: datetime) -> SharedReminder:
        reminder.remind_at = remind_at.astimezone(UTC)
        if reminder.status == SharedReminderStatus.COMPLETED:
            reminder.status = SharedReminderStatus.ACTIVE
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def cancel(self, reminder: SharedReminder) -> SharedReminder:
        reminder.status = SharedReminderStatus.CANCELLED
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def renew_token(self, reminder: SharedReminder) -> str:
        token = generate_invite_token()
        reminder.invite_token_hash = hash_invite_token(token)
        reminder.invite_token_preview = token_preview(token)
        reminder.token_expires_at = None
        await self.session.commit()
        await self.session.refresh(reminder)
        return token

    async def disable_token(self, reminder: SharedReminder) -> SharedReminder:
        reminder.invite_token_hash = None
        reminder.invite_token_preview = None
        reminder.token_expires_at = utc_now()
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def set_member_status(
        self,
        reminder_id: int,
        user_id: int,
        status: SharedReminderMemberStatus,
    ) -> bool:
        member = await self.get_member(reminder_id, user_id)
        if member is None or member.role == SharedReminderMemberRole.OWNER and status == SharedReminderMemberStatus.LEFT:
            return False

        member.status = status
        await self.session.commit()
        return True

    async def get_due_reminders(self, now: datetime | None = None) -> list[SharedReminder]:
        now = now or utc_now()
        result = await self.session.execute(
            select(SharedReminder)
            .options(
                selectinload(SharedReminder.members).selectinload(SharedReminderMember.user)
            )
            .where(
                SharedReminder.status == SharedReminderStatus.ACTIVE,
                SharedReminder.remind_at <= now,
            )
            .order_by(SharedReminder.remind_at.asc())
        )
        return list(result.scalars().all())

    async def log_delivery(
        self,
        reminder_id: int,
        user_id: int,
        status: ReminderDeliveryStatus,
        error: str | None = None,
    ) -> None:
        self.session.add(
            ReminderDeliveryLog(
                reminder_id=reminder_id,
                user_id=user_id,
                status=status,
                error=error[:1000] if error else None,
            )
        )

    async def advance_after_delivery(self, reminder: SharedReminder) -> None:
        if reminder.repeat_rule is None or reminder.repeat_rule == RepeatType.NONE:
            reminder.status = SharedReminderStatus.COMPLETED
            await self.session.commit()
            return

        reminder.remind_at = calculate_next_occurrence(
            reminder.remind_at,
            reminder.repeat_rule,
            reminder.timezone,
        )
        await self.session.commit()
