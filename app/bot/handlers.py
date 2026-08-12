"""Conversation handlers for the financial-scan test.

All user-facing text and behaviour toggles are read from the database via the
``content`` service, so the dashboard can change them live.
"""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot import keyboards
from app.bot.states import State
from app.bot.utils import normalize_phone_number
from app.config import BASE_DIR
from app.services import content
from app.services.responses import log_event, save_response

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 100


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _reply(update: Update, text: str, **kwargs):
    """Reply regardless of whether the update is a message or a callback."""
    if update.message:
        return await update.message.reply_text(text, **kwargs)
    if update.callback_query and update.callback_query.message:
        return await update.callback_query.message.reply_text(text, **kwargs)
    return None


def _cfg() -> dict:
    return content.get_settings_dict()


async def _membership_status(update: Update, context: ContextTypes.DEFAULT_TYPE, cfg: dict):
    """True = member, False = not a member, None = could not determine."""
    if not cfg.get("require_membership", True):
        return True

    user = update.effective_user
    if user is None:
        return None

    channel_id = cfg.get("channel_id") or 0
    if not channel_id:
        # Membership required but no channel configured — don't block users.
        logger.warning("require_membership is on but channel_id is not set.")
        return True

    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user.id)
        if member.status in {"creator", "administrator", "member"}:
            return True
        if member.status == "restricted" and getattr(member, "is_member", False):
            return True
        return False
    except TelegramError as error:
        logger.exception("Could not check channel membership: %s", error)
        return None


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
CAPTION_LIMIT = 1024  # Telegram photo caption max length


async def _send_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE, cfg: dict) -> None:
    """Show the welcome/menu, as a photo when a start image is configured.

    When triggered from a button, the previous message is deleted first so the
    photo posts cleanly (a text message can't be edited into a photo).
    """
    chat_id = update.effective_chat.id
    markup = keyboards.main_menu_keyboard(cfg.get("support_link", ""))
    text = cfg.get("welcome_text", "")

    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.message.delete()
        except TelegramError:
            pass

    image = _resolve_path(cfg.get("start_image_path", ""))
    if cfg.get("send_start_image", True) and image and image.exists():
        caption = text if len(text) <= CAPTION_LIMIT else ""
        try:
            with image.open("rb") as photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    reply_markup=markup if caption else None,
                )
            if caption:
                return
            # Text too long for a caption — send it as a follow-up message.
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
            return
        except TelegramError:
            logger.exception("Could not send start image")

    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None):
    """Update the message behind a callback, robust to media messages.

    A photo/document message can't be edited into text, so in that case (or if
    the edit otherwise fails) the message is deleted and a fresh one is sent.
    """
    query = update.callback_query
    message = query.message if query else None
    is_media = bool(
        message
        and (message.photo or message.document or message.video or message.animation)
    )
    if not is_media:
        try:
            return await query.edit_message_text(text, reply_markup=reply_markup)
        except TelegramError:
            pass
    if message:
        try:
            await message.delete()
        except TelegramError:
            pass
    return await context.bot.send_message(
        chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup
    )


async def _show_consent(update: Update, cfg: dict) -> None:
    text = cfg.get("consent_text", "").format(
        data_use_purpose=cfg.get("data_use_purpose", ""),
        channel_link=cfg.get("channel_link", ""),
    )
    await _reply(update, text, reply_markup=keyboards.consent_keyboard())


async def _send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    snapshot = context.user_data["quiz"]
    index = context.user_data["question_index"]
    question = snapshot["questions"][index]
    total = len(snapshot["questions"])

    text = f"سؤال {index + 1} از {total}\n\n{question['text']}"
    markup = keyboards.question_keyboard(snapshot["options"])

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await _reply(update, text, reply_markup=markup)


# --------------------------------------------------------------------------- #
# Entry / menu
# --------------------------------------------------------------------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await _send_welcome(update, context, _cfg())
    return State.MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await _send_welcome(update, context, _cfg())
    return State.MENU


async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()

    cfg = _cfg()
    log_event("start_test", update.effective_user.id if update.effective_user else None)

    status = await _membership_status(update, context, cfg)

    if status is True:
        if cfg.get("require_consent", True):
            await _edit_or_send(update, context, "عضویت شما تأیید شد.")
            await _show_consent(update, cfg)
            return State.ASK_CONSENT
        return await _begin_registration(update, context, cfg, via_edit=True)

    if status is False:
        await _edit_or_send(
            update,
            context,
            "برای شروع تست، ابتدا باید عضو کانال شوید.",
            reply_markup=keyboards.join_keyboard(cfg.get("channel_link", "")),
        )
        return State.CHECK_MEMBERSHIP

    await _edit_or_send(
        update,
        context,
        "در حال حاضر امکان بررسی عضویت شما وجود ندارد. لطفاً کمی بعد دوباره تلاش کنید.",
        reply_markup=keyboards.main_menu_keyboard(cfg.get("support_link", "")),
    )
    return State.MENU


async def join_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cfg = _cfg()
    await _edit_or_send(
        update,
        context,
        "برای عضویت، روی دکمه زیر بزنید.\n\nبعد از عضویت، گزینه بررسی مجدد را انتخاب کنید.",
        reply_markup=keyboards.join_keyboard(cfg.get("channel_link", "")),
    )
    return State.CHECK_MEMBERSHIP


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cfg = _cfg()
    status = await _membership_status(update, context, cfg)

    if status is True:
        if cfg.get("require_consent", True):
            await _edit_or_send(update, context, "عضویت شما تأیید شد.")
            await _show_consent(update, cfg)
            return State.ASK_CONSENT
        return await _begin_registration(update, context, cfg, via_edit=True)

    if status is False:
        await _edit_or_send(
            update,
            context,
            "هنوز عضویت شما تأیید نشده است. لطفاً ابتدا عضو کانال شوید.",
            reply_markup=keyboards.join_keyboard(cfg.get("channel_link", "")),
        )
        return State.CHECK_MEMBERSHIP

    await _edit_or_send(
        update,
        context,
        "بررسی عضویت با خطا مواجه شد. لطفاً دوباره تلاش کنید.",
        reply_markup=keyboards.join_keyboard(cfg.get("channel_link", "")),
    )
    return State.CHECK_MEMBERSHIP


# --------------------------------------------------------------------------- #
# Consent + registration
# --------------------------------------------------------------------------- #
async def _begin_registration(update, context, cfg, via_edit=False) -> int:
    log_event("consent", update.effective_user.id if update.effective_user else None)
    message = "ممنون. لطفاً اطلاعات خود را وارد کنید."
    if via_edit and update.callback_query:
        await _edit_or_send(update, context, message)
    else:
        await _reply(update, message)
    await _reply(update, cfg.get("ask_first_name_text", ""))
    return State.ASK_FIRST_NAME


async def give_consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cfg = _cfg()

    status = await _membership_status(update, context, cfg)
    if status is not True:
        await _edit_or_send(
            update,
            context,
            "برای ادامه باید عضو کانال باشید.",
            reply_markup=keyboards.join_keyboard(cfg.get("channel_link", "")),
        )
        return State.CHECK_MEMBERSHIP

    return await _begin_registration(update, context, cfg, via_edit=True)


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("لغو شد. هیچ اطلاعاتی ذخیره نشد.")
    context.user_data.clear()
    await _send_welcome(update, context, _cfg())
    return State.MENU


async def receive_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    first_name = update.message.text.strip()
    if not first_name or len(first_name) > MAX_NAME_LENGTH:
        await update.message.reply_text(
            "لطفاً یک نام معتبر، حداکثر تا ۱۰۰ کاراکتر، وارد کنید."
        )
        return State.ASK_FIRST_NAME

    context.user_data["first_name"] = first_name
    await _reply(update, _cfg().get("ask_last_name_text", ""))
    return State.ASK_LAST_NAME


async def receive_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    last_name = update.message.text.strip()
    if not last_name or len(last_name) > MAX_NAME_LENGTH:
        await update.message.reply_text(
            "لطفاً یک نام خانوادگی معتبر وارد کنید. اگر نام خانوادگی ندارید، - وارد کنید."
        )
        return State.ASK_LAST_NAME

    context.user_data["last_name"] = last_name
    await _reply(update, _cfg().get("ask_phone_text", ""))
    return State.ASK_PHONE


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = normalize_phone_number(update.message.text.strip())
    if not phone_number:
        await update.message.reply_text(
            "شماره تلفن معتبر نیست. لطفاً شماره‌ای بین ۷ تا ۱۵ رقم وارد کنید.\n\n"
            "مثال:\n+491234567890"
        )
        return State.ASK_PHONE

    context.user_data["phone_number"] = phone_number

    # Snapshot the quiz so mid-test edits can't corrupt this run.
    snapshot = content.build_quiz_snapshot()
    if not snapshot["questions"] or not snapshot["options"]:
        await update.message.reply_text(
            "در حال حاضر سؤالی برای این تست تعریف نشده است. لطفاً بعداً تلاش کنید."
        )
        context.user_data.clear()
        return State.MENU

    context.user_data["quiz"] = snapshot
    context.user_data["answers"] = {}
    context.user_data["question_index"] = 0

    await _send_question(update, context, edit=False)
    return State.QUESTION


# --------------------------------------------------------------------------- #
# Questions
# --------------------------------------------------------------------------- #
async def receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    snapshot = context.user_data.get("quiz")
    if snapshot is None:
        await query.answer("جلسه شما منقضی شده است. لطفاً دوباره شروع کنید.", show_alert=True)
        return State.MENU

    valid_scores = {option["score"] for option in snapshot["options"]}

    try:
        _, score_text = query.data.split(":")
        score = int(score_text)
    except (ValueError, AttributeError):
        await query.answer("پاسخ نامعتبر است.", show_alert=True)
        return State.QUESTION

    if score not in valid_scores:
        await query.answer("پاسخ نامعتبر است.", show_alert=True)
        return State.QUESTION

    selected = next(o for o in snapshot["options"] if o["score"] == score)
    await query.answer()

    index = context.user_data["question_index"]
    context.user_data["answers"][index] = {"label": selected["label"], "score": score}

    next_index = index + 1
    if next_index < len(snapshot["questions"]):
        context.user_data["question_index"] = next_index
        await _send_question(update, context, edit=True)
        return State.QUESTION

    return await _finish_test(update, context)


async def _finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    cfg = _cfg()
    user = update.effective_user

    scores = save_response(
        first_name=context.user_data["first_name"],
        last_name=context.user_data["last_name"],
        phone_number=context.user_data["phone_number"],
        telegram_user_id=user.id if user else None,
        telegram_username=user.username if user else None,
        answers=context.user_data["answers"],
        snapshot=context.user_data["quiz"],
    )
    log_event("complete", user.id if user else None)

    result_text = _build_result_text(cfg, scores)
    context.user_data.clear()

    await query.edit_message_text("پاسخ‌های شما ثبت شد.")
    await query.message.reply_text(result_text)

    await _send_completion_file(update, context, cfg)

    await query.message.reply_text(
        "از منوی زیر می‌توانید دوباره تست را انجام دهید.",
        reply_markup=keyboards.main_menu_keyboard(cfg.get("support_link", "")),
    )
    return State.MENU


def _build_result_text(cfg: dict, scores: list[dict]) -> str:
    lines = [cfg.get("result_intro", ""), ""]
    for area in scores:
        lines.append(f"{area['name']}: {area['score']:.2f} از ۱۰")
    lines += ["", cfg.get("result_disclaimer", "")]
    return "\n".join(lines)


async def _send_completion_file(update, context, cfg) -> None:
    """Send the configured completion file — as a photo if it's an image,
    otherwise as a document."""
    query = update.callback_query
    if not cfg.get("send_completion_file", True):
        return

    file_path = _resolve_path(cfg.get("completion_file_path", ""))
    caption = cfg.get("completion_caption", "")

    if file_path and file_path.exists():
        try:
            with file_path.open("rb") as handle:
                if file_path.suffix.lower() in IMAGE_SUFFIXES:
                    await query.message.reply_photo(photo=handle, caption=caption)
                else:
                    await query.message.reply_document(
                        document=handle,
                        filename=file_path.name,
                        caption=caption,
                    )
            return
        except TelegramError:
            logger.exception("Could not send completion file")

    logger.warning("Completion file missing or unset: %s", file_path)
    await query.message.reply_text("مینی‌دوره آزمایشی به‌زودی برای شما ارسال می‌شود.")


def _resolve_path(raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    cfg = _cfg()
    await update.message.reply_text(
        "لغو شد. هیچ اطلاعاتی ذخیره نشد.",
        reply_markup=keyboards.main_menu_keyboard(cfg.get("support_link", "")),
    )
    return State.MENU


# --------------------------------------------------------------------------- #
# Wiring
# --------------------------------------------------------------------------- #
def build_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_test, pattern="^start_test$"),
            CallbackQueryHandler(join_channel, pattern="^join_channel$"),
        ],
        states={
            State.MENU: [
                CallbackQueryHandler(start_test, pattern="^start_test$"),
                CallbackQueryHandler(join_channel, pattern="^join_channel$"),
            ],
            State.CHECK_MEMBERSHIP: [
                CallbackQueryHandler(check_membership, pattern="^check_membership$"),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            State.ASK_CONSENT: [
                CallbackQueryHandler(give_consent, pattern="^give_consent$"),
                CallbackQueryHandler(cancel_registration, pattern="^cancel_registration$"),
            ],
            State.ASK_FIRST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_first_name),
            ],
            State.ASK_LAST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_last_name),
            ],
            State.ASK_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone),
            ],
            State.QUESTION: [
                CallbackQueryHandler(receive_answer, pattern=r"^answer:-?\d+$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel_command),
            CallbackQueryHandler(main_menu, pattern="^main_menu$"),
        ],
    )
