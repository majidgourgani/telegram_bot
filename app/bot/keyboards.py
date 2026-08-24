"""Inline and reply keyboards, built from live settings/content."""

from __future__ import annotations

from typing import Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def share_phone_keyboard(button_text: str) -> ReplyKeyboardMarkup:
    """A one-tap reply keyboard that asks the user to share their own number."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(button_text, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_keyboard(support_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("شروع تست / انجام دوباره تست", callback_data="start_test")],
            [
                InlineKeyboardButton("عضویت کانال", callback_data="join_channel"),
                InlineKeyboardButton("ارتباط با پشتیبانی", url=support_link),
            ],
        ]
    )


def join_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("عضویت در کانال", url=channel_link)],
            [InlineKeyboardButton("عضو شدم؛ بررسی مجدد", callback_data="check_membership")],
            [InlineKeyboardButton("بازگشت به منو", callback_data="main_menu")],
        ]
    )


def question_keyboard(options: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(option["label"], callback_data=f"answer:{option['score']}")
        for option in options
    ]
    return InlineKeyboardMarkup([buttons])
