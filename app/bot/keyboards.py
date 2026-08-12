"""Inline keyboards, built from live settings/content."""

from __future__ import annotations

from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("موافقم و ادامه می‌دهم", callback_data="give_consent")],
            [InlineKeyboardButton("لغو", callback_data="cancel_registration")],
        ]
    )


def question_keyboard(options: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(option["label"], callback_data=f"answer:{option['score']}")
        for option in options
    ]
    return InlineKeyboardMarkup([buttons])
