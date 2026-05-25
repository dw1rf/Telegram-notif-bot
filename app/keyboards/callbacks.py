from aiogram.filters.callback_data import CallbackData


class MainMenuCallback(CallbackData, prefix="menu"):
    action: str


class ReminderPageCallback(CallbackData, prefix="rpage"):
    scope: str
    page: int


class ReminderActionCallback(CallbackData, prefix="ract"):
    action: str
    reminder_id: int
    scope: str = "all"
    page: int = 1


class QuickTimeCallback(CallbackData, prefix="qtime"):
    value: str


class RepeatChoiceCallback(CallbackData, prefix="repeat"):
    value: str


class ConfirmReminderCallback(CallbackData, prefix="confirm"):
    action: str


class SettingsCallback(CallbackData, prefix="settings"):
    action: str

