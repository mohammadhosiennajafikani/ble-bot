import os
import json
from io import BytesIO

import requests
from telegram.ext import (
    Application, MessageHandler, CommandHandler, filters
)
from PIL import Image, ImageOps

# ─── تنظیمات بله ────────────────────────────────
TOKEN = "451053587:JFrlO7J-1jwlJtvy9n5jffSG1ApRQ6tzSf8"
BASE_URL = "https://tapi.bale.ai/bot"
FILE_URL = "https://tapi.bale.ai/file/bot"

FRAMES_DIR = "frames"
STATE_FILE = "state.json"
JPEG_QUALITY = 95


# ─── مدیریت state ───────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ─── ابزار لیست قالب‌ها / واترمارک‌ها ───────────────
def list_frames():
    if not os.path.exists(FRAMES_DIR):
        return []
    return sorted(
        f for f in os.listdir(FRAMES_DIR)
        if f.lower().endswith(".png")
    )


def frame_name(filename):
    return os.path.splitext(filename)[0]


# ─── اعمال تمام‌صفحه واترمارک روی هر سایز عکس ─────────────
def apply_fullscreen_watermark(img, watermark_path):
    """
    واترمارک را به طور دقیق هم‌اندازه کل سطح عکس تغییر سایز می‌دهد
    و به صورت تمام‌صفحه روی هر عکسی با هر اندازه و نسبتی اعمال می‌کند.
    بدون بوم ۴:۳، بدون حاشیه مشکی، و با حفظ ۱۰۰٪ اندازه اصلی عکس.
    """
    # تصحیح جهت عکس‌های گرفته‌شده با گوشی موبایل بر اساس متادیتای EXIF
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    img = img.convert("RGBA")
    W, H = img.size

    # باز کردن فایل واترمارک با شفافیت
    watermark = Image.open(watermark_path).convert("RGBA")

    # تغییر اندازه واترمارک به طول و عرض کامل عکس با بهترین فیلتر کیفیت (LANCZOS)
    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    watermark_resized = watermark.resize((W, H), resample_filter)

    # ترکیب لایه شفاف واترمارک روی کل سطح عکس به صورت تمام‌صفحه
    return Image.alpha_composite(img, watermark_resized)


# ─── دانلود و ارسال فایل با requests (مخصوص بله) ────
def bale_get_file_path(file_id):
    """مسیر فایل را از API بله می‌گیرد."""
    url = f"{BASE_URL}{TOKEN}/getFile"
    resp = requests.post(url, json={"file_id": file_id}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"getFile failed: {data}")
    return data["result"]["file_path"]


def bale_download_file(file_path):
    """فایل را از سرور بله دانلود می‌کند."""
    url = f"{FILE_URL}{TOKEN}/{file_path}"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def bale_send_photo(chat_id, image_bytes, caption=""):
    """عکس نهایی را از طریق API بله می‌فرستد."""
    url = f"{BASE_URL}{TOKEN}/sendPhoto"
    files = {"photo": ("result.jpg", image_bytes, "image/jpeg")}
    payload = {"chat_id": chat_id}
    if caption:
        payload["caption"] = caption
    resp = requests.post(url, data=payload, files=files, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"sendPhoto failed: {data}")
    return data


# ─── دستورها ────────────────────────────────
async def cmd_start(update, context):
    frames = list_frames()
    if not frames:
        await update.message.reply_text(
            "هیچ فایل واترمارکی در پوشه frames پیدا نشد.\n"
            "لطفاً فایل PNG واترمارک را در پوشه frames بگذارید و دوباره اجرا کنید."
        )
        return

    state = load_state()
    current = state.get("active_frame")

    text = "سلام 👋\n\nواترمارک‌های موجود:\n"
    for f in frames:
        name = frame_name(f)
        marker = " ✅" if current == f else ""
        text += f"• /{name}{marker}\n"

    text += "\nهر واترمارکی را بزنید فعال می‌شود. از این پس هر عکسی با هر ابعادی بفرستید، واترمارک به صورت تمام‌صفحه روی کل عکس قرار می‌گیرد."
    text += "\n\n/current → نمایش واترمارک فعال"
    await update.message.reply_text(text)


async def cmd_current(update, context):
    state = load_state()
    current = state.get("active_frame")
    if not current:
        await update.message.reply_text("هیچ واترمارکی فعال نیست. /start را بزنید.")
        return
    await update.message.reply_text(f"واترمارک فعال: {frame_name(current)}")


async def cmd_set_frame(update, context):
    """وقتی کاربر /اسم‌واترمارک رو می‌زنه، فعالش می‌کنه."""
    command = update.message.text.split()[0].lstrip("/").lower()
    frames = list_frames()

    matched = None
    for f in frames:
        if frame_name(f).lower() == command:
            matched = f
            break

    if not matched:
        await update.message.reply_text(
            "چنین واترمارکی وجود ندارد. /start را بزنید تا لیست را ببینید."
        )
        return

    state = load_state()
    state["active_frame"] = matched
    save_state(state)

    await update.message.reply_text(
        f"✅ واترمارک «{frame_name(matched)}» فعال شد.\n"
        f"از این لحظه هر عکسی بفرستید این واترمارک روی کل عکس (تمام‌صفحه) قرار می‌گیرد."
    )


# ─── پردازش عکس دریافتی ─────────────────────────────
async def handle_photo(update, context):
    state = load_state()
    active = state.get("active_frame")

    if not active:
        available = list_frames()
        if available:
            active = available[0]
            state["active_frame"] = active
            save_state(state)
        else:
            await update.message.reply_text("اول یک واترمارک انتخاب کنید. /start را بزنید.")
            return

    frame_path = os.path.join(FRAMES_DIR, active)
    if not os.path.exists(frame_path):
        await update.message.reply_text("فایل واترمارک فعال پیدا نشد. یک قالب دیگر انتخاب کنید.")
        return

    msg = await update.message.reply_text("⏳ در حال پردازش واترمارک تمام‌صفحه...")

    try:
        # ۱. گرفتن بزرگ‌ترین کیفیت عکس ارسالی
        photo = update.message.photo[-1]

        # ۲. گرفتن مسیر فایل از API بله
        file_path = bale_get_file_path(photo.file_id)

        # ۳. دانلود فایل از سرور بله
        img_bytes = bale_download_file(file_path)
        img = Image.open(BytesIO(img_bytes))

        # ۴. اعمال واترمارک به صورت تمام‌صفحه روی کل ابعاد واقعی عکس
        result = apply_fullscreen_watermark(img, frame_path)

        # ۵. ذخیره خروجی با بالاترین کیفیت
        output = BytesIO()
        result.convert("RGB").save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        output.seek(0)

        # ۶. ارسال تصویر خروجی به کاربر در بله
        orig_w, orig_h = img.size
        bale_send_photo(
            chat_id=update.effective_chat.id,
            image_bytes=output.read(),
            caption=f"واترمارک: {frame_name(active)} ({orig_w}×{orig_h})"
        )

    except Exception as e:
        await update.message.reply_text(f"خطا در پردازش تصویر:\n{type(e).__name__}: {e}")
    finally:
        try:
            await msg.delete()
        except Exception:
            pass


# ─── راه‌اندازی ربات ──────────────────────────────
def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .base_url(BASE_URL)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("current", cmd_current))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^/[^/\s]+"),
        cmd_set_frame
    ))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("ربات واترمارک تمام‌صفحه بله روشن شد. برای خروج Ctrl+C بزنید.")
    app.run_polling()


if __name__ == "__main__":
    main()