from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from diet.models import UserGoal


def meal_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🌅 Breakfast", callback_data="meal_type:breakfast"),
            InlineKeyboardButton("☀️ Lunch", callback_data="meal_type:lunch"),
        ],
        [
            InlineKeyboardButton("🌙 Dinner", callback_data="meal_type:dinner"),
            InlineKeyboardButton("🍎 Snack", callback_data="meal_type:snack"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def goal_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("⬇️ Lose weight", callback_data=f"goal:{UserGoal.WEIGHT_LOSS}")],
        [InlineKeyboardButton("⬆️ Gain weight", callback_data=f"goal:{UserGoal.WEIGHT_GAIN}")],
        [InlineKeyboardButton("💪 Build muscle", callback_data=f"goal:{UserGoal.MUSCLE_BUILDING}")],
        [InlineKeyboardButton("⚖️ Maintain", callback_data=f"goal:{UserGoal.MAINTENANCE}")],
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(confirm_data: str, cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes", callback_data=confirm_data),
                InlineKeyboardButton("❌ No", callback_data=cancel_data),
            ]
        ]
    )


def skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Skip", callback_data="skip")]])
