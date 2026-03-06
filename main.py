import os
from pathlib import Path

import yt_dlp
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL")
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing.")

if not REQUIRED_CHANNEL:
    raise ValueError("REQUIRED_CHANNEL is missing.")

if not REQUIRED_CHANNEL_URL:
    raise ValueError("REQUIRED_CHANNEL_URL is missing.")

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


def is_valid_url(text: str) -> bool:
    text = text.strip()
    return text.startswith("http://") or text.startswith("https://")


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("اشترك في القناة", url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton("تحقق من الاشتراك", callback_data="check_subscription")]
    ])


async def is_user_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


async def require_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    subscribed = await is_user_subscribed(user.id, context)
    if subscribed:
        return True

    text = (
        "يجب عليك الاشتراك أولًا في القناة لاستخدام البوت.\n\n"
        "بعد الاشتراك اضغط على زر: تحقق من الاشتراك."
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=subscribe_keyboard())
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=subscribe_keyboard())

    return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed = await require_subscription(update, context)
    if not allowed:
        return

    await update.message.reply_text(
        "أهلًا بك.\n"
        "أرسل رابط فيديو من TikTok أو Instagram أو YouTube وسأحاول تنزيله لك."
    )


async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user:
        return

    subscribed = await is_user_subscribed(user.id, context)

    if subscribed:
        await query.message.reply_text(
            "تم التحقق من الاشتراك بنجاح ✅\n"
            "الآن يمكنك إرسال رابط الفيديو."
        )
    else:
        await query.message.reply_text(
            "ما زلت غير مشترك أو لم يتم التحقق بعد.\n"
            "اشترك أولًا ثم اضغط على زر التحقق.",
            reply_markup=subscribe_keyboard()
        )


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed = await require_subscription(update, context)
    if not allowed:
        return

    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    if not is_valid_url(url):
        await update.message.reply_text("أرسل رابط فيديو صحيح يبدأ بـ http:// أو https://")
        return

    await update.message.reply_text("جارٍ تنزيل الفيديو...")

    output_template = str(DOWNLOAD_DIR / "%(title).80s.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "format": "mp4/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }

    downloaded_file = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            prepared = ydl.prepare_filename(info)

        prepared_path = Path(prepared)
        mp4_path = prepared_path.with_suffix(".mp4")

        if mp4_path.exists():
            downloaded_file = mp4_path
        elif prepared_path.exists():
            downloaded_file = prepared_path
        else:
            files = sorted(DOWNLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                downloaded_file = files[0]

        if not downloaded_file or not downloaded_file.exists():
            await update.message.reply_text("فشل التنزيل: لم يتم العثور على الملف.")
            return

        with downloaded_file.open("rb") as video_file:
            await update.message.reply_video(video=video_file)

    except Exception:
        await update.message.reply_text("فشل تنزيل هذا الرابط.")
    finally:
        try:
            if downloaded_file and downloaded_file.exists():
                downloaded_file.unlink()
        except Exception:
            pass


def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    app.run_polling()


if __name__ == "__main__":

    main()

