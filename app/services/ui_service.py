from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


logger = logging.getLogger(__name__)


async def answer_ok(callback: CallbackQuery, text: str = "Готово") -> None:
    await callback.answer(text)


async def answer_error(callback: CallbackQuery, text: str) -> None:
    await callback.answer(text, show_alert=True)


async def safe_delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        return


def _is_not_modified(error: TelegramBadRequest) -> bool:
    return "message is not modified" in str(error).lower()


async def safe_edit_message(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    **kwargs: Any,
) -> Message:
    try:
        return await message.edit_text(text, reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest as error:
        if _is_not_modified(error):
            return message
        logger.info("Could not edit message %s: %s", message.message_id, error)
        return await message.answer(text, reply_markup=reply_markup, **kwargs)


async def safe_edit_by_id(
    bot: Bot,
    chat_id: int,
    message_id: int | None,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    **kwargs: Any,
) -> Message | None:
    if message_id is not None:
        try:
            return await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                **kwargs,
            )
        except TelegramBadRequest as error:
            if _is_not_modified(error):
                return None
            logger.info("Could not edit stored UI message %s: %s", message_id, error)

    return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, **kwargs)


async def remember_ui_message(state: FSMContext, message: Message) -> None:
    await state.update_data(ui_message_id=message.message_id)


async def render_callback(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    answer_text: str | None = None,
) -> Message:
    message = await safe_edit_message(callback.message, text, reply_markup=reply_markup)
    await remember_ui_message(state, message)
    await callback.answer(answer_text)
    return message


async def render_state(
    message: Message,
    state: FSMContext,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    data = await state.get_data()
    ui_message_id = data.get("ui_message_id")
    rendered = await safe_edit_by_id(
        bot=message.bot,
        chat_id=message.chat.id,
        message_id=int(ui_message_id) if ui_message_id else None,
        text=text,
        reply_markup=reply_markup,
    )
    if rendered is not None:
        await remember_ui_message(state, rendered)
    return rendered
