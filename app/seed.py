"""Seed the database with the original bot's content on first run.

Runs are idempotent: each block only inserts when its table is empty, so
editing content from the dashboard is never overwritten on restart.
"""

from __future__ import annotations

from app.config import BASE_DIR, settings
from app.database import SessionLocal
from app.models import AnswerOption, Area, Question, Setting


def _bundled_start_image() -> str:
    """Return a project-root start image filename if one ships with the repo."""
    for name in ("start.jpeg", "start.jpg", "start.JPEG", "start.JPG", "start.png"):
        if (BASE_DIR / name).exists():
            return name
    return ""

# --- Areas (slug -> display name) -------------------------------------------
AREAS = [
    ("control", "کنترل مالی"),
    ("security", "امنیت مالی"),
    ("growth", "رشد مالی"),
]

# --- Questions: (area_slug, text) -------------------------------------------
QUESTIONS = [
    ("control", "هرچقدر بیشتر کار می‌کنم، وضعیت مالی‌ام تغییر خاصی نمی‌کند."),
    ("control", "درآمدم نسبت به قبل بیشتر شده، اما هزینه‌هایم هم تقریباً به همان اندازه بیشتر شده است."),
    ("control", "اغلب چیزهایی می‌خرم که از قبل قصد خریدشان را نداشتم و بعد از خرید پشیمان می‌شوم."),
    ("control", "وقتی پولی پیش‌بینی‌نشده به دستم می‌رسد، بدون برنامه و تصمیم مشخص خرج می‌شود."),
    ("security", "اگر از امروز درآمدم قطع شود، نمی‌توانم حداقل ۳ ماه بدون فشار مالی جدی زندگی کنم."),
    ("security", "دائماً نگران هزینه‌های ناگهانی و غیرمنتظره هستم و می‌ترسم نتوانم آن‌ها را مدیریت کنم."),
    ("security", "بیشتر از اینکه در حال ساختن آینده مالی‌ام باشم، در حال پرداخت هزینه‌ها و تصمیمات مالی گذشته هستم."),
    ("security", "دوست دارم پس‌انداز کنم، اما دائماً منتظر شرایط و وضعیت بهتری هستم."),
    ("growth", "با وجود مهارت‌ها و توانایی‌هایی که دارم، درآمد مناسبی از هیچ‌کدام از آن‌ها ندارم."),
    ("growth", "معمولاً به‌خاطر ترس از اشتباه یا پشیمانی، تصمیم‌های مالی را به تعویق می‌اندازم."),
    ("growth", "می‌خواهم درآمدم را در کار فعلی‌ام بیشتر کنم، اما نمی‌دانم از چه طریقی."),
    ("growth", "برای سرمایه‌گذاری منتظر تصمیم و نظر دیگران می‌مانم، چون خودم درباره سرمایه‌گذاری قدرت تشخیص کافی ندارم."),
]

# --- Answer options: (label, score) -----------------------------------------
ANSWER_OPTIONS = [
    ("موافقم", 1),
    ("تا حدودی", 5),
    ("مخالفم", 10),
]

# --- Settings: key -> (value, type, label, group, description) --------------
# Values are seeded from env where it makes sense (token/channel).
def _default_settings() -> dict[str, tuple[str, str, str, str, str]]:
    return {
        # Telegram
        "bot_token": (
            settings.bot_token, "secret", "Bot token", "telegram",
            "Token from @BotFather. Changing it requires a bot restart.",
        ),
        "channel_id": (
            str(settings.channel_id), "int", "Channel ID", "telegram",
            "Numeric id of the private channel (e.g. -1001234567890).",
        ),
        "channel_link": (
            settings.channel_link, "text", "Channel invite link", "telegram",
            "Public invite link shown on the join button.",
        ),
        "support_username": (
            "@Majid_grki", "text", "Support username", "telegram", "",
        ),
        "support_link": (
            "https://t.me/Majid_grki", "text", "Support link", "telegram", "",
        ),
        # Feature toggles
        "require_membership": (
            "true", "bool", "Require channel membership", "features",
            "If on, users must join the channel before taking the test.",
        ),
        "send_completion_file": (
            "true", "bool", "Send files on completion", "features",
            "Send the uploaded completion files (images/documents) after the test.",
        ),
        "phone_via_contact": (
            "true", "bool", "Ask users to share phone via button", "features",
            "Show a one-tap “share my number” button instead of asking users to "
            "type it. Manual typing still works as a fallback.",
        ),
        "send_start_image": (
            "true", "bool", "Show image on welcome", "features",
            "Show the uploaded start image with the welcome message.",
        ),
        # Texts
        "welcome_text": (
            "سلام، من فاطمه شریفی‌ام؛ مربی رشد مالی و مهارت‌های فردی.\n\n"
            "اینجا قراره متوجه بشی که چرا با وجود تلاش و درآمد، "
            "هنوز به رشد مالی‌ای که می‌خوای نرسیدی؟!\n\n"
            "برای همین یک هدیه برات آماده کردم: "
            "اسکن مالی + مینی‌دوره رایگان سواد پولی 🎁\n\n"
            "🔹 اول با تست اسکن مالی، وضعیت و گلوگاه مالیت رو پیدا می‌کنیم\n"
            "🔹 بعد نتیجه رو تحلیل می‌کنیم\n"
            "🔹 سپس متوجه میشی چه چیزی جلوی رشد مالیت رو گرفته\n"
            "🔹 در نهایت یاد میگیری چطور مسیر رشد مالی ساخته میشه\n\n"
            "اگر آماده‌ای، اسکن مالی‌ات رو شروع کنیم 👇🏻",
            "text", "Welcome message", "content", "",
        ),
        "join_text": (
            "برای شروع تست، ابتدا باید عضو کانال شوید:\n\n{channel_link}\n\n"
            "بعد از عضویت، روی گزینه «عضو شدم؛ بررسی مجدد» بزنید.",
            "text", "Join prompt", "content",
            "Use {channel_link} as a placeholder for the invite link.",
        ),
        "ask_name_text": (
            "لطفاً نام و نام خانوادگی خود را وارد کنید.",
            "text", "Ask full name", "content", "",
        ),
        "ask_phone_text": (
            "برای دریافت نتیجه‌ی تست، لطفاً شماره‌ی تلفن خود را با دکمه‌ی زیر به اشتراک بگذارید 👇🏼\n\n"
            "یا می‌توانید شماره را دستی وارد کنید. مثال:\n+491234567890",
            "text", "Ask phone", "content", "",
        ),
        "share_phone_button_text": (
            "📱 اشتراک‌گذاری شماره‌ی من",
            "text", "Share-phone button label", "content", "",
        ),
        "result_intro": (
            "نتیجه ارزیابی شما آماده است.",
            "text", "Result intro", "content", "",
        ),
        "result_disclaimer": (
            "این ارزیابی یک ابزار اولیه است و جایگزین مشاوره تخصصی مالی نیست.",
            "text", "Result disclaimer", "content", "",
        ),
        "start_image_path": (
            _bundled_start_image(), "text", "Start image", "content",
            "Set automatically when you upload a start image on the Settings page.",
        ),
    }


# Deprecated settings keys -> their replacement, for in-place migration.
_RENAMED_SETTINGS = {
    "send_completion_image": "send_completion_file",
}

# Deprecated settings keys to drop entirely (consent + old name/file fields).
_REMOVED_SETTINGS = {
    "require_consent",
    "consent_text",
    "data_use_purpose",
    "ask_first_name_text",
    "ask_last_name_text",
    "completion_caption",
    "completion_file_path",
    "completion_image_path",
}


def _migrate_completion_file(session, rows) -> None:
    """Move a legacy single completion file setting into the new table."""
    from app.models import CompletionFile

    if session.query(CompletionFile).count() > 0:
        return
    legacy = rows.get("completion_file_path") or rows.get("completion_image_path")
    path = legacy.value.strip() if legacy is not None else ""
    if not path:
        return
    caption_row = rows.get("completion_caption")
    caption = caption_row.value if caption_row is not None else ""
    session.add(
        CompletionFile(
            path=path,
            original_name=path.rsplit("/", 1)[-1],
            caption=caption,
            order=1,
            is_active=True,
        )
    )


def seed_defaults() -> None:
    with SessionLocal() as session:
        # Areas
        if session.query(Area).count() == 0:
            for order, (slug, name) in enumerate(AREAS):
                session.add(Area(slug=slug, name=name, order=order))
            session.flush()

        # Questions
        if session.query(Question).count() == 0:
            areas = {a.slug: a for a in session.query(Area).all()}
            for order, (area_slug, text) in enumerate(QUESTIONS):
                session.add(
                    Question(
                        area_id=areas[area_slug].id,
                        text=text,
                        order=order,
                        is_active=True,
                    )
                )

        # Answer options
        if session.query(AnswerOption).count() == 0:
            for order, (label, score) in enumerate(ANSWER_OPTIONS):
                session.add(
                    AnswerOption(label=label, score=score, order=order, is_active=True)
                )

        # Settings
        defaults = _default_settings()
        rows = {s.key: s for s in session.query(Setting).all()}

        # 1) Migrate the legacy single completion file into the new table.
        _migrate_completion_file(session, rows)

        # 2) Rename any deprecated keys to their replacement, preserving values.
        for old_key, new_key in _RENAMED_SETTINGS.items():
            old_row = rows.get(old_key)
            if old_row is None:
                continue
            if new_key not in rows and new_key in defaults:
                value, vtype, label, group, desc = defaults[new_key]
                migrated = Setting(
                    key=new_key,
                    value=old_row.value,  # keep the previously configured value
                    value_type=vtype,
                    label=label,
                    group=group,
                    description=desc,
                )
                session.add(migrated)
                rows[new_key] = migrated
            session.delete(old_row)
            rows.pop(old_key, None)

        # 3) Drop deprecated keys that no longer exist.
        for dead_key in _REMOVED_SETTINGS:
            dead_row = rows.pop(dead_key, None)
            if dead_row is not None:
                session.delete(dead_row)

        # 4) Insert any missing keys, keeping existing values untouched.
        for key, (value, vtype, label, group, desc) in defaults.items():
            if key not in rows:
                session.add(
                    Setting(
                        key=key,
                        value=value,
                        value_type=vtype,
                        label=label,
                        group=group,
                        description=desc,
                    )
                )

        session.commit()

    # Make historical users reachable for broadcasts (idempotent).
    from app.services.broadcast import backfill_bot_users

    backfill_bot_users()
