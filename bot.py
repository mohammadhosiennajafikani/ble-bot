import os
import json
from io import BytesIO

import requests
from telegram.ext import (
    Application, MessageHandler, CommandHandler, filters
)
from PIL import Image, ImageOps

# ─── تنظیمات ربات بله ────────────────────────────────
TOKEN = "451053587:JFrlO7J-1jwlJtvy9n5jffSG1ApRQ6tzSf8"
BASE_URL = "https://tapi.bale.ai/bot"
FILE_URL = "https://tapi.bale.ai/file/bot"

FRAMES_DIR = "frames"
STATE_FILE = "state.json"
JPEG_QUALITY = 95

# تنظیمات اندازه و موقعیت نشان/لوگو روی عکس
# درصد اندازه لوگو نسبت به کوچک‌ترین ضلع عکس (مثلاً ۰.۱۸ یعنی ۱۸ درصد)
LOGO_SCALE_RATIO = 0.18
# فاصله لوگو از لبه‌های تصویر (۳ درصد)
LOGO_MARGIN_RATIO = 0.03
# موقعیت پیش‌فرض: "bottom-right" (پایین-راست), "bottom-left", "top-right", "top-left", "center"
DEFAULT_POSITION = "bottom-right"


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


# ─── ابزار لیست قالب‌ها ─────────────────────────────
def list_frames():
    if not os.path.exists(FRAMES_DIR):
        return []
    return sorted(
        f for f in os.listdir(FRAMES_DIR)
        if f.lower().endswith(".png")
    )


def frame_name(filename):
    return os.path.splitext(filename)[0]


# ─── پردازش هوشمند تصویر برای هر اندازه ─────────────────────────
def apply_logo_or_frame(img, overlay_path, position=DEFAULT_POSITION, scale_ratio=LOGO_SCALE_RATIO):
    """
    این تابع روی هر عکسی با هر اندازه و نسبتی (عمودی، مربعی، افقی، پانوراما) کار می‌کند.
    لوگو یا نشان را بدون دفرمه شدن و متناسب با ابعاد عکس در موقعیت مناسب قرار می‌دهد.
    """
    # جهت تصویر را بر اساس متادیتای دوربین گوشی اصلاح می‌کند تا عکس نچرخد
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    img = img.convert("RGBA")
    W, H = img.size

    overlay = Image.open(overlay_path).convert("RGBA")
    OW, OH = overlay.size

    # تشخیص هوشمند: آیا فایل یک قاب تمام‌صفحه است یا یک لوگو/نشان کوچک؟
    # اگر قالب از قبل هم‌اندازه یا بزرگ‌تر از ۹۰٪ عکس باشد، به صورت قاب کامل اعمال می‌شود
    # در غیر این صورت به عنوان لوگو و واترمارک گوشه عکس تنظیم می‌شود.
    is_full_frame = (OW == W and OH == H)

    resample_filter = getattr(Image, "Resampling", Image).LANCZOS

    if is_full_frame:
        # حالت قاب کامل
        overlay_resized = overlay.resize((W, H), resample_filter)
        return Image.alpha_composite(img, overlay_resized)
    else:
        # حالت لوگو / نشان / واترمارک متناسب با هر سایز عکس
        base_dim = min(W, H)
        target_w = max(35, int(base_dim * (scale_ratio * 1.35)))
        target_h = int(target_w * (OH / OW))

        # جلوگیری از اشغال بیش از حد ارتفاع در عکس‌های عمودی
        max_h = int(H * 0.35)
        if target_h > max_h:
            target_h = max_h
            target_w = int(target_h * (OW / OH))

        overlay_resized = overlay.resize((target_w, target_h), resample_filter)
        margin = max(10, int(base_dim * LOGO_MARGIN_RATIO))

        # تعیین مختصات قرارگیری
        pos = str(position).lower().replace("_", "-")
        if pos in ("bottom-right", "br"):
            x = W - target_w - margin
            y = H - target_h - margin
        elif pos in ("bottom-left", "bl"):
            x = margin
            y = H - target_h - margin
        elif pos in ("top-right", "tr"):
            x = W - target_w - margin
            y = margin
        elif pos in ("top-left", "tl"):
            x = margin
            y = margin
        elif pos in ("center", "c"):
            x = (W - target_w) // 2
            y = (H - target_h) // 2
        else:  # پیش‌فرض: پایین راست
            x = W - target_w - margin
            y = H - target_h - margin

        x = max(0, min(x, W - target_w))
        y = max(0, min(y, H - target_h))

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste(overlay_resized, (x, y), overlay_resized)
        return Image.alpha_composite(img, layer)


# ─── دانلود و ارسال فایل با requests (مخصوص بله) ────
def bale_get_file_path(file_id):
    """مسیر فایل را از API بله دریافت می‌کند."""
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
    """عکس نهایی را از طریق API بله برای کاربر ارسال می‌کند."""
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
            "هیچ قالب یا لوگویی توی پوشه frames پیدا نشد.\n"
            "یک فایل PNG با پس‌زمینه شفاف در پوشه frames قرار دهید و ربات را اجرا کنید."
        )
        return

    state = load_state()
    current = state.get("active_frame")

    text = "سلام 👋\n\nقالب‌ها و لوگوهای موجود:\n"
    for f in frames:
        name = frame_name(f)
        marker = " ✅" if current == f else ""
        text += f"• /{name}{marker}\n"

    text += "\nهر قالبی را لمس کنید فعال می‌شود. بعد از آن هر عکسی با هر اندازه‌ای بفرستید در ابعاد واقعی خودش نشان روی آن قرار می‌گیرد."
    text += "\n\n/current → نمایش قالب فعال"
    await update.message.reply_text(text)


async def cmd_current(update, context):
    state = load_state()
    current = state.get("active_frame")
    if not current:
        await update.message.reply_text("هیچ قالبی فعال نیست. /start را بزنید.")
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
            "چنین قالبی وجود ندارد. /start را بزنید تا لیست را ببینید."
        )
        return

    state = load_state()
    state["active_frame"] = matched
    save_state(state)

    await update.message.reply_text(
        f"✅ قالب «{frame_name(matched)}» فعال شد.\n"
        f"از حالا هر عکسی با هر اندازه‌ای بفرستید با این نشان آماده و ارسال می‌شود."
    )


# ─── پردازش عکس دریافتی ─────────────────────────────
async def handle_photo(update, context):
    state = load_state()
    active = state.get("active_frame")

    if not active:
        # در صورت نبود قالب فعال، اولین قالب پوشه انتخاب می‌شود
        available = list_frames()
        if available:
            active = available[0]
            state["active_frame"] = active
            save_state(state)
        else:
            await update.message.reply_text("ابتدا یک قالب انتخاب کنید. /start را بزنید.")
            return

    frame_path = os.path.join(FRAMES_DIR, active)
    if not os.path.exists(frame_path):
        await update.message.reply_text("فایل قالب فعال پیدا نشد. یک قالب دیگر انتخاب کنید.")
        return

    msg = await update.message.reply_text("⏳ در حال پردازش تصویر در ابعاد اصلی...")

    try:
        # ۱. گرفتن شناسه فایل بزرگ‌ترین سایز ارسالی
        photo = update.message.photo[-1]

        # ۲. گرفتن مسیر فایل از API بله
        file_path = bale_get_file_path(photo.file_id)

        # ۳. دانلود عکس از سرور بله
        img_bytes = bale_download_file(file_path)
        img = Image.open(BytesIO(img_bytes))

        # ۴. اعمال متناسب نشان روی ابعاد اصلی عکس (بدون بوم ۴:۳ و بدون حاشیه مشکی)
        result = apply_logo_or_frame(img, frame_path)

        # ۵. آماده‌سازی خروجی با بالاترین کیفیت
        output = BytesIO()
        result.convert("RGB").save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        output.seek(0)

        # ۶. ارسال به کاربر در بله
        orig_w, orig_h = img.size
        bale_send_photo(
            chat_id=update.effective_chat.id,
            image_bytes=output.read(),
            caption=f"قالب: {frame_name(active)} ({orig_w}×{orig_h})"
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

    print("ربات بله با پشتیبانی از تمام اندازه‌های تصویر روشن شد. برای خروج Ctrl+C بزنید.")
    app.run_polling()


if __name__ == "__main__":
    main()