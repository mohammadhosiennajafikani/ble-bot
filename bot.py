import os
import json
from io import BytesIO

import requests
from telegram.ext import (
    Application, MessageHandler, CommandHandler, filters
)
from PIL import Image

# ─── تنظیمات ────────────────────────────────
TOKEN = "451053587:JFrlO7J-1jwlJtvy9n5jffSG1ApRQ6tzSf8"
BASE_URL = "https://tapi.bale.ai/bot"
FILE_URL = "https://tapi.bale.ai/file/bot"

CANVAS_RATIO = 4 / 3          # نسبت بوم ثابت
BG_COLOR = (18, 18, 18)       # رنگ پس‌زمینه فضای خالی
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


# ─── ابزار قالب ─────────────────────────────
def list_frames():
    if not os.path.exists(FRAMES_DIR):
        return []
    return sorted(
        f for f in os.listdir(FRAMES_DIR)
        if f.lower().endswith(".png")
    )


def frame_name(filename):
    return os.path.splitext(filename)[0]


# ─── پردازش تصویر ───────────────────────────
def normalize_to_canvas(img, canvas_ratio=4/3, bg_color=(18, 18, 18)):
    """عکس رو داخل بوم با نسبت ثابت قرار می‌ده."""
    img = img.convert("RGBA")
    W, H = img.size
    img_ratio = W / H

    if img_ratio > canvas_ratio:
        canvas_w = W
        canvas_h = int(round(W / canvas_ratio))
    else:
        canvas_h = H
        canvas_w = int(round(H * canvas_ratio))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), bg_color + (255,))
    x = (canvas_w - W) // 2
    y = (canvas_h - H) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def apply_frame(canvas, frame_path):
    """قالب رو هم‌اندازه بوم می‌کنه و روش می‌ذاره."""
    frame = Image.open(frame_path).convert("RGBA")
    if frame.size != canvas.size:
        frame = frame.resize(canvas.size, Image.LANCZOS)
    return Image.alpha_composite(canvas, frame)


# ─── دانلود و ارسال فایل با requests (مخصوص بله) ────
def bale_get_file_path(file_id):
    """مسیر فایل رو از API بله می‌گیره."""
    url = f"{BASE_URL}{TOKEN}/getFile"
    resp = requests.post(url, json={"file_id": file_id}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"getFile failed: {data}")
    return data["result"]["file_path"]


def bale_download_file(file_path):
    """فایل رو از سرور بله دانلود می‌کنه."""
    url = f"{FILE_URL}{TOKEN}/{file_path}"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def bale_send_photo(chat_id, image_bytes, caption=""):
    """عکس رو از طریق API بله می‌فرسته."""
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
            "هیچ قالبی توی پوشه frames پیدا نشد.\n"
            "یه فایل PNG بذار توی پوشه frames و ربات رو دوباره اجرا کن."
        )
        return

    state = load_state()
    current = state.get("active_frame")

    text = "سلام 👋\n\nقالب‌های موجود:\n"
    for f in frames:
        name = frame_name(f)
        marker = " ✅" if current == f else ""
        text += f"• /{name}{marker}\n"

    text += "\nهر قالبی رو بزن، فعال می‌شه. بعدش هر عکسی بفرستی با همون قالب برمی‌گرده."
    text += "\n\n/current → نمایش قالب فعال"
    await update.message.reply_text(text)


async def cmd_current(update, context):
    state = load_state()
    current = state.get("active_frame")
    if not current:
        await update.message.reply_text("هیچ قالبی فعال نیست. /start رو بزن.")
        return
    await update.message.reply_text(f"قالب فعال: {frame_name(current)}")


async def cmd_set_frame(update, context):
    """وقتی کاربر /اسم‌قالب رو می‌زنه، فعالش می‌کنه."""
    command = update.message.text.split()[0].lstrip("/").lower()
    frames = list_frames()

    matched = None
    for f in frames:
        if frame_name(f).lower() == command:
            matched = f
            break

    if not matched:
        await update.message.reply_text(
            "چنین قالبی وجود نداره. /start رو بزن تا لیست رو ببینی."
        )
        return

    state = load_state()
    state["active_frame"] = matched
    save_state(state)

    await update.message.reply_text(
        f"✅ قالب «{frame_name(matched)}» فعال شد.\n"
        f"از الان هر عکسی بفرستی با این قالب برمی‌گرده."
    )


# ─── پردازش عکس ─────────────────────────────
async def handle_photo(update, context):
    state = load_state()
    active = state.get("active_frame")

    if not active:
        await update.message.reply_text("اول یه قالب انتخاب کن. /start رو بزن.")
        return

    frame_path = os.path.join(FRAMES_DIR, active)
    if not os.path.exists(frame_path):
        await update.message.reply_text("قالب فعال پیدا نشد. یه قالب دیگه انتخاب کن.")
        return

    msg = await update.message.reply_text("⏳ در حال پردازش...")

    try:
        # ۱. گرفتن file_id بزرگ‌ترین سایز
        photo = update.message.photo[-1]

        # ۲. گرفتن مسیر فایل از API بله
        file_path = bale_get_file_path(photo.file_id)

        # ۳. دانلود فایل از سرور بله
        img_bytes = bale_download_file(file_path)
        img = Image.open(BytesIO(img_bytes))

        # ۴. بوم ثابت + اعمال قالب
        canvas = normalize_to_canvas(img, CANVAS_RATIO, BG_COLOR)
        result = apply_frame(canvas, frame_path)

        # ۵. آماده‌سازی خروجی
        output = BytesIO()
        result.convert("RGB").save(output, format="JPEG", quality=JPEG_QUALITY)
        output.seek(0)

        # ۶. ارسال از طریق API بله
        bale_send_photo(
            chat_id=update.effective_chat.id,
            image_bytes=output.read(),
            caption=f"قالب: {frame_name(active)}"
        )

    except Exception as e:
        await update.message.reply_text(f"خطا: {type(e).__name__}\n{e}")
    finally:
        try:
            await msg.delete()
        except Exception:
            pass


# ─── راه‌اندازی ──────────────────────────────
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

    print("ربات روشن شد. برای خروج Ctrl+C بزن.")
    app.run_polling()


if __name__ == "__main__":
    main()