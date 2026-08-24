"""Conversation handlers for the financial-scan test.

All user-facing text and behaviour toggles are read from the database via the
``content`` service, so the dashboard can change them live.

Flow: MENU → (membership check) → ASK_NAME → ASK_PHONE → QUESTION… → results.
The welcome/start message is never deleted once the flow begins — each step
sends a new message instead.
"""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import ReplyKeyboardRemove, Update
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
from app.bot.utils import normalize_phone_number, round_half_up, to_persian_digits
from app.config import BASE_DIR
from app.services import content
from app.services.files import list_completion_files
from app.services.responses import log_event, save_response

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 150
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
CAPTION_LIMIT = 1024  # Telegram photo caption max length


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _reply(update: Update, text: str, **kwargs):
    """Send a new message, whether the update is a message or a callback."""
    if update.message:
        return await update.message.reply_text(text, **kwargs)
    if update.callback_query and update.callback_query.message:
        return await update.callback_query.message.reply_text(text, **kwargs)
    return None


def _cfg() -> dict:
    return content.get_settings_dict()


async def _edit_own_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None):
    """Edit the message behind a callback in place (used for non-welcome
    messages such as the join prompt and questions).

    Never deletes; if the message can't be edited (e.g. it carries media) a new
    message is sent instead so nothing is lost.
    """
    query = update.callback_query
    message = query.message if query else None
    is_media = bool(
        message and (message.photo or message.document or message.video or message.animation)
    )
    if not is_media:
        try:
            return await query.edit_message_text(text, reply_markup=reply_markup)
        except TelegramError:
            pass
    return await context.bot.send_message(
        chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup
    )


def _resolve_path(raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


async def _membership_status(update: Update, context: ContextTypes.DEFAULT_TYPE, cfg: dict):
    """True = member, False = not a member, None = could not determine."""
    if not cfg.get("require_membership", True):
        return True

    user = update.effective_user
    if user is None:
        return None

    channel_id = cfg.get("channel_id") or 0
    if not channel_id:
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


async def _send_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE, cfg: dict) -> None:
    """Show the welcome/menu, as a photo when a start image is configured.

    Nothing is deleted — the welcome message stays in the chat.
    """
    chat_id = update.effective_chat.id
    markup = keyboards.main_menu_keyboard(cfg.get("support_link", ""))
    text = cfg.get("welcome_text", "")

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
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
            return
        except TelegramError:
            logger.exception("Could not send start image")

    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def _send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    snapshot = context.user_data["quiz"]
    index = context.user_data["question_index"]
    question = snapshot["questions"][index]
    total = len(snapshot["questions"])

    counter = f"سؤال {to_persian_digits(index + 1)} از {to_persian_digits(total)}"
    text = f"{counter}\n\n{question['text']}"
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
        # New message — leaves the welcome/start message intact.
        return await _begin_registration(update, context, cfg)

    if status is False:
        await _reply(
            update,
            "برای شروع تست، ابتدا باید عضو کانال شوید.",
            reply_markup=keyboards.join_keyboard(cfg.get("channel_link", "")),
        )
        return State.CHECK_MEMBERSHIP

    await _reply(
        update,
        "در حال حاضر امکان بررسی عضویت شما وجود ندارد. لطفاً کمی بعد دوباره تلاش کنید.",
        reply_markup=keyboards.main_menu_keyboard(cfg.get("support_link", "")),
    )
    return State.MENU


async def join_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cfg = _cfg()
    await _reply(
        update,
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
        return await _begin_registration(update, context, cfg)

    if status is False:
        await _edit_own_message(
            update,
            context,
            "هنوز عضویت شما تأیید نشده است. لطفاً ابتدا عضو کانال شوید.",
            reply_markup=keyboards.join_keyboard(cfg.get("channel_link", "")),
        )
        return State.CHECK_MEMBERSHIP

    await _edit_own_message(
        update,
        context,
        "بررسی عضویت با خطا مواجه شد. لطفاً دوباره تلاش کنید.",
        reply_markup=keyboards.join_keyboard(cfg.get("channel_link", "")),
    )
    return State.CHECK_MEMBERSHIP


# --------------------------------------------------------------------------- #
# Registration (single name field, then phone)
# --------------------------------------------------------------------------- #
async def _begin_registration(update, context, cfg) -> int:
    await _reply(update, cfg.get("ask_name_text", "لطفاً نام و نام خانوادگی خود را وارد کنید."))
    return State.ASK_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = " ".join(update.message.text.split()).strip()

    if not full_name or len(full_name) > MAX_NAME_LENGTH:
        await update.message.reply_text(
            "لطفاً نام و نام خانوادگی معتبری وارد کنید (حداکثر ۱۵۰ کاراکتر)."
        )
        return State.ASK_NAME

    # Split into first / last so the dashboard columns stay meaningful.
    parts = full_name.split(" ", 1)
    context.user_data["first_name"] = parts[0]
    context.user_data["last_name"] = parts[1] if len(parts) > 1 else ""

    await _ask_phone(update, _cfg())
    return State.ASK_PHONE


async def _ask_phone(update: Update, cfg: dict) -> None:
    """Prompt for the phone number, offering a share-contact button if enabled."""
    text = cfg.get("ask_phone_text", "")
    if cfg.get("phone_via_contact", True):
        button = cfg.get("share_phone_button_text") or "📱 اشتراک‌گذاری شماره‌ی من"
        await _reply(update, text, reply_markup=keyboards.share_phone_keyboard(button))
    else:
        await _reply(update, text)


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle a manually typed phone number."""
    return await _finalize_phone(update, context, update.message.text.strip())


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle a number shared via the 'share my phone' button."""
    contact = update.message.contact
    return await _finalize_phone(update, context, contact.phone_number if contact else "")


async def _finalize_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str) -> int:
    cfg = _cfg()
    phone_number = normalize_phone_number(raw or "")
    if not phone_number:
        await _reply(
            update,
            "شماره تلفن معتبر نیست. لطفاً شماره‌ای بین ۷ تا ۱۵ رقم وارد کنید یا از دکمه استفاده کنید.\n\n"
            "مثال:\n+491234567890",
            reply_markup=(
                keyboards.share_phone_keyboard(
                    cfg.get("share_phone_button_text") or "📱 اشتراک‌گذاری شماره‌ی من"
                )
                if cfg.get("phone_via_contact", True)
                else None
            ),
        )
        return State.ASK_PHONE

    context.user_data["phone_number"] = phone_number

    # Snapshot the quiz so mid-test edits can't corrupt this run.
    snapshot = content.build_quiz_snapshot()
    if not snapshot["questions"] or not snapshot["options"]:
        await _reply(
            update,
            "در حال حاضر سؤالی برای این تست تعریف نشده است. لطفاً بعداً تلاش کنید.",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        return State.MENU

    context.user_data["quiz"] = snapshot
    context.user_data["answers"] = {}
    context.user_data["question_index"] = 0

    # Clear the custom reply keyboard before showing the (inline) questions.
    await _reply(update, "شماره‌ی شما ثبت شد ✅", reply_markup=ReplyKeyboardRemove())
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

    await _send_completion_files(update, context, cfg)

    await query.message.reply_text(
        "از منوی زیر می‌توانید دوباره تست را انجام دهید.",
        reply_markup=keyboards.main_menu_keyboard(cfg.get("support_link", "")),
    )
    return State.MENU


def _build_result_text(cfg: dict, scores: list[dict]) -> str:
    lines = [cfg.get("result_intro", ""), ""]
    for area in scores:
        value = to_persian_digits(round_half_up(area["score"]))
        lines.append(f"{area['name']}: {value} از ۱۰")
    lines += ["", cfg.get("result_disclaimer", "")]
    return "\n".join(lines)


async def _send_completion_files(update, context, cfg) -> None:
    """Send every active completion item after the results.

    Two kinds of item:
    * uploaded file → sent as a photo (images) or document (≤50 MB);
    * channel message → copied or forwarded from the configured channel, which
      has no upload-size limit (so large videos/voice work).
    """
    query = update.callback_query
    chat_id = update.effective_chat.id
    if not cfg.get("send_completion_file", True):
        return

    channel_id = cfg.get("channel_id") or 0
    items = list_completion_files(active_only=True)
    sent_any = False

    for entry in items:
        try:
            if entry.get("is_channel"):
                if not channel_id:
                    logger.warning("Channel completion item but channel_id is not set.")
                    continue
                message_id = entry["source_message_id"]
                caption = entry.get("caption") or None
                if entry.get("send_mode") == "forward":
                    await context.bot.forward_message(
                        chat_id=chat_id, from_chat_id=channel_id, message_id=message_id
                    )
                else:
                    await context.bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=channel_id,
                        message_id=message_id,
                        caption=caption,
                    )
                sent_any = True
                continue

            path = _resolve_path(entry["path"])
            if not path or not path.exists():
                logger.warning("Completion file missing: %s", entry["path"])
                continue
            caption = entry.get("caption") or None
            with path.open("rb") as handle:
                if path.suffix.lower() in IMAGE_SUFFIXES:
                    await query.message.reply_photo(photo=handle, caption=caption)
                else:
                    await query.message.reply_document(
                        document=handle, filename=path.name, caption=caption
                    )
            sent_any = True
        except TelegramError:
            logger.exception("Could not send completion item: %s", entry)

    if items and not sent_any:
        await query.message.reply_text("فایل‌های شما به‌زودی ارسال می‌شود.")


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
            State.ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name),
            ],
            State.ASK_PHONE: [
                MessageHandler(filters.CONTACT, receive_contact),
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
