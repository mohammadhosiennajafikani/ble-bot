"""
ربات پردازش تصویر بله / تلگرام با پشتیبانی از تمام ابعاد و نسبت‌های تصویر
سازگار با هر اندازه عکس (بدون تغییر نسبت یا ایجاد حاشیه‌های ناخواسته)
قابلیت قرار دادن لوگو، واترمارک و قاب روی هر نوع عکس با ابعاد دلخواه
"""

import os
import json
from io import BytesIO

import requests
from telegram.ext import (
    Application, MessageHandler, CommandHandler, filters
)
from PIL import Image, ImageOps

# ─── تنظیمات پایه ────────────────────────────────
TOKEN = "451053587:JFrlO7J-1jwlJtvy9n5jffSG1ApRQ6tzSf8"
BASE_URL = "https://tapi.bale.ai/bot"
FILE_URL = "https://tapi.bale.ai/file/bot"

FRAMES_DIR = "frames"
STATE_FILE = "state.json"
JPEG_QUALITY = 95

# تنظیمات پیش‌فرض برای نشان / لوگو
DEFAULT_MODE = "logo"             # "logo" برای نشان و واترمارک، "frame" برای قاب تمام‌صفحه
DEFAULT_POSITION = "bottom-right"  # "bottom-right", "bottom-left", "top-right", "top-left", "center", "bottom-center"
DEFAULT_SCALE = 0.18               # درصد اندازه لوگو نسبت به اندازه عکس (۱۸ درصد)
DEFAULT_MARGIN = 0.03              # فاصله لوگو از لبه تصویر (۳ درصد)

# ─── مدیریت State ───────────────────────────
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
def apply_logo_mark(img, logo_path, position="bottom-right", scale_ratio=0.18, margin_ratio=0.03):
    """
    لوگو یا واترمارک رو بدون تغییر نسبت (تناسب کامل) و متناسب با ابعاد عکس
    در گوشه یا مرکز هر عکسی با هر اندازه قرار می‌ده.
    """
    img = img.convert("RGBA")
    W, H = img.size

    logo = Image.open(logo_path).convert("RGBA")
    LW, LH = logo.size

    # محاسبه ابعاد متناسب با عکس (هرگز دفرمه یا کشیده نمی‌شه)
    base_dim = min(W, H)
    target_w = max(30, int(base_dim * (scale_ratio * 1.4)))
    target_h = int(target_w * (LH / LW))

    # محدودسازی ارتفاع اگر لوگو خیلی عمودی بود
    max_h = int(H * 0.35)
    if target_h > max_h:
        target_h = max_h
        target_w = int(target_h * (LW / LH))

    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    logo_resized = logo.resize((target_w, target_h), resample_filter)

    # محاسبه حاشیه از لبه
    margin = max(10, int(base_dim * margin_ratio))

    pos_lower = str(position).lower().replace("_", "-")
    if pos_lower in ("bottom-right", "br", "پایین-راست"):
        x = W - target_w - margin
        y = H - target_h - margin
    elif pos_lower in ("bottom-left", "bl", "پایین-چپ"):
        x = margin
        y = H - target_h - margin
    elif pos_lower in ("top-right", "tr", "بالا-راست"):
        x = W - target_w - margin
        y = margin
    elif pos_lower in ("top-left", "tl", "بالا-چپ"):
        x = margin
        y = margin
    elif pos_lower in ("center", "c", "مرکز"):
        x = (W - target_w) // 2
        y = (H - target_h) // 2
    elif pos_lower in ("bottom-center", "bc", "پایین-وسط"):
        x = (W - target_w) // 2
        y = H - target_h - margin
    elif pos_lower in ("top-center", "tc", "بالا-وسط"):
        x = (W - target_w) // 2
        y = margin
    else:  # پیش‌فرض پایین راست
        x = W - target_w - margin
        y = H - target_h - margin

    # اطمینان از قرار گرفتن کامل داخل کادر عکس
    x = max(0, min(x, W - target_w))
    y = max(0, min(y, H - target_h))

    # چسباندن لایه شفاف روی عکس
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlay.paste(logo_resized, (x, y), logo_resized)
    return Image.alpha_composite(img, overlay)


def apply_full_frame(img, frame_path):
    """
    قالب تمام‌صفحه یا کادر دور تصویر رو روی عکس با هر اندازه‌ای بدون بوم سیاه قرار می‌ده.
    """
    img = img.convert("RGBA")
    frame = Image.open(frame_path).convert("RGBA")
    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    if frame.size != img.size:
        frame = frame.resize(img.size, resample_filter)
    return Image.alpha_composite(img, frame)


def process_image(img, frame_path, mode="logo", position="bottom-right", scale=0.18):
    """
    پردازش هوشمند و خودکار عکس:
    ۱. تصحیح چرخش دوربین گوشی بر اساس متادیتا EXIF
    ۲. اعمال لوگو در گوشه با اندازه متناسب یا اعمال قاب سراسری
    """
    # چرخش خودکار بر اساس جهت واقعی عکس دوربین
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if mode == "frame":
        return apply_full_frame(img, frame_path)
    else:
        return apply_logo_mark(img, frame_path, position=position, scale_ratio=scale)


# ─── دانلود و ارسال فایل در بله ────────────────────
def bale_get_file_path(file_id):
    """مسیر فایل را از سرور بله دریافت می‌کند."""
    url = f"{BASE_URL}{TOKEN}/getFile"
    resp = requests.post(url, json={"file_id": file_id}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"getFile failed: {data}")
    return data["result"]["file_path"]


def bale_download_file(file_path):
    """دانلود محتوای تصویر از سرور بله."""
    url = f"{FILE_URL}{TOKEN}/{file_path}"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def bale_send_photo(chat_id, image_bytes, caption=""):
    """ارسال تصویر خروجی به کاربر با بالاترین کیفیت."""
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


# ─── دستورات ربات ────────────────────────────────
async def cmd_start(update, context):
    frames = list_frames()
    state = load_state()
    current = state.get("active_frame")
    mode = state.get("mode", DEFAULT_MODE)
    pos = state.get("position", DEFAULT_POSITION)

    if not frames:
        await update.message.reply_text(
            "⚠️ هیچ قالب یا لوگویی در پوشه frames یافت نشد.\n\n"
            "لطفاً فایل PNG لوگو یا قالب خود را درون پوشه frames قرار دهید."
        )
        return

    text = "سلام! 👋 خوش آمدید.\n\n"
    text += "✨ این ربات با **هر اندازه و نسبتی از عکس** (مربعی، استوری عمودی، افقی، پانوراما) به خوبی کار می‌کند و دیگر نیازی به نسبت ثابت ۴:۳ نیست!\n\n"
    text += "📁 **قالب‌ها و لوگوهای موجود:**\n"
    for f in frames:
        name = frame_name(f)
        marker = " ✅" if current == f else ""
        text += f"• /{name}{marker}\n"

    text += "\n⚙️ **دستورات تنظیمی:**\n"
    text += "• `/current` → مشاهده قالب و وضعیت فعلی\n"
    text += "• `/mode logo` → حالت قرارگیری لوگو/واترمارک در گوشه عکس\n"
    text += "• `/mode frame` → حالت قاب دور تا دور تصویر\n"
    text += "• `/pos br` (پایین-راست) | `/pos bl` (پایین-چپ) | `/pos tr` (بالا-راست) | `/pos tl` (بالا-چپ) | `/pos center` (مرکز)\n"
    text += "• `/scale 20` → تنظیم اندازه لوگو به درصد (مثلا ۱۵ یا ۲۰ یا ۲۵ درصد)\n\n"
    text += f"📌 وضعیت فعلی: قالب [{frame_name(current) if current else 'انتخاب نشده'}] | حالت: {mode} | موقعیت: {pos}\n"
    text += "🖼 حالا کافیست یک عکس ارسال کنید!"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_current(update, context):
    state = load_state()
    current = state.get("active_frame")
    mode = state.get("mode", DEFAULT_MODE)
    pos = state.get("position", DEFAULT_POSITION)
    scale = int(state.get("scale", DEFAULT_SCALE) * 100)

    if not current:
        await update.message.reply_text("هیچ قالبی فعال نیست. با دستور /start یک قالب انتخاب کنید.")
        return

    text = (
        f"🎨 **اطلاعات فعلی:**\n"
        f"• قالب/لوگو فعال: `{frame_name(current)}`\n"
        f"• حالت پردازش: `{mode}` (logo = نشان گوشه / frame = قاب کامل)\n"
        f"• موقعیت نشان: `{pos}`\n"
        f"• مقیاس اندازه: `{scale}%`\n\n"
        f"هر عکسی بفرستید در ابعاد واقعی خودش پردازش می‌شود."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_mode(update, context):
    """تغییر حالت بین لوگو و قاب"""
    args = context.args
    state = load_state()
    if not args or args[0].lower() not in ("logo", "frame"):
        await update.message.reply_text("فرمت صحیح: `/mode logo` یا `/mode frame`", parse_mode="Markdown")
        return
    chosen_mode = args[0].lower()
    state["mode"] = chosen_mode
    save_state(state)
    name = "نشان / لوگو متناسب" if chosen_mode == "logo" else "قاب کامل دور تصویر"
    await update.message.reply_text(f"✅ حالت پردازش به «{name}» تغییر یافت.")


async def cmd_position(update, context):
    """تغییر موقعیت لوگو روی عکس"""
    args = context.args
    pos_map = {
        "br": "bottom-right",
        "bl": "bottom-left",
        "tr": "top-right",
        "tl": "top-left",
        "center": "center",
        "c": "center",
        "bottom-right": "bottom-right",
        "bottom-left": "bottom-left",
        "top-right": "top-right",
        "top-left": "top-left",
    }
    if not args or args[0].lower() not in pos_map:
        await update.message.reply_text(
            "موقعیت‌های مجاز:\n"
            "• `/pos br` (پایین-راست)\n"
            "• `/pos bl` (پایین-چپ)\n"
            "• `/pos tr` (بالا-راست)\n"
            "• `/pos tl` (بالا-چپ)\n"
            "• `/pos center` (مرکز تصویر)",
            parse_mode="Markdown"
        )
        return
    chosen = pos_map[args[0].lower()]
    state = load_state()
    state["position"] = chosen
    save_state(state)
    await update.message.reply_text(f"✅ موقعیت لوگو به `{chosen}` تغییر یافت.", parse_mode="Markdown")


async def cmd_scale(update, context):
    """تنظیم مقیاس لوگو بر اساس درصد"""
    args = context.args
    if not args:
        await update.message.reply_text("لطفاً یک عدد بین ۵ تا ۵۰ وارد کنید. مثال: `/scale 20`", parse_mode="Markdown")
        return
    try:
        val = int(args[0])
        if val < 5 or val > 60:
            raise ValueError()
        state = load_state()
        state["scale"] = val / 100.0
        save_state(state)
        await update.message.reply_text(f"✅ اندازه نشان به {val}% اندازه تصویر تغییر یافت.")
    except Exception:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر بین ۵ تا ۵۰ درصد وارد کنید.")


async def cmd_set_frame(update, context):
    """فعال‌سازی قالب با زدن دستور نام آن"""
    cmd = update.message.text.split()[0].lstrip("/").lower()

    # نادیده گرفتن دستورات سیستمی
    if cmd in ("start", "current", "mode", "pos", "scale"):
        return

    frames = list_frames()
    matched = None
    for f in frames:
        if frame_name(f).lower() == cmd:
            matched = f
            break

    if not matched:
        await update.message.reply_text("چنین قالبی وجود ندارد. دستور /start را بزنید تا لیست را ببینید.")
        return

    state = load_state()
    state["active_frame"] = matched
    save_state(state)
    await update.message.reply_text(
        f"✅ قالب «{frame_name(matched)}» فعال شد.\n"
        f"هر عکسی با هر سایزی ارسال کنید، این قالب روی آن قرار می‌گیرد."
    )


# ─── پردازش عکس دریافتی ─────────────────────────────
async def handle_photo(update, context):
    state = load_state()
    active = state.get("active_frame")

    if not active:
        # اگر قالبی فعال نبود ولی در پوشه frames قالبی بود، اولی را خودکار فعال کن
        available = list_frames()
        if available:
            active = available[0]
            state["active_frame"] = active
            save_state(state)
        else:
            await update.message.reply_text("اول یک قالب انتخاب کنید یا در پوشه frames فایل PNG قرار دهید. /start را بزنید.")
            return

    frame_path = os.path.join(FRAMES_DIR, active)
    if not os.path.exists(frame_path):
        await update.message.reply_text("فایل قالب فعال پیدا نشد. لطفاً قالب دیگری را انتخاب کنید.")
        return

    msg = await update.message.reply_text("⏳ در حال پردازش تصویر در ابعاد اصلی...")

    try:
        # ۱. گرفتن بالاترین کیفیت عکس ارسالی
        photo = update.message.photo[-1]

        # ۲. گرفتن مسیر فایل از بله
        file_path = bale_get_file_path(photo.file_id)

        # ۳. دانلود فایل عکس
        img_bytes = bale_download_file(file_path)
        img = Image.open(BytesIO(img_bytes))

        # ۴. پردازش هوشمند در ابعاد واقعی عکس بدون بوم سیاه
        mode = state.get("mode", DEFAULT_MODE)
        position = state.get("position", DEFAULT_POSITION)
        scale = state.get("scale", DEFAULT_SCALE)

        result = process_image(img, frame_path, mode=mode, position=position, scale=scale)

        # ۵. آماده‌سازی خروجی با کیفیت بالا
        output = BytesIO()
        result.convert("RGB").save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        output.seek(0)

        # ۶. ارسال به کاربر
        orig_w, orig_h = img.size
        caption_info = f"🖼 {frame_name(active)} ({orig_w}×{orig_h})"
        bale_send_photo(
            chat_id=update.effective_chat.id,
            image_bytes=output.read(),
            caption=caption_info
        )

    except Exception as e:
        await update.message.reply_text(f"❌ خطا در پردازش تصویر:\n{type(e).__name__}: {e}")
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
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("pos", cmd_position))
    app.add_handler(CommandHandler("scale", cmd_scale))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^/[^/\s]+"),
        cmd_set_frame
    ))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("ربات با پشتیبانی از هر سایز تصویر روشن شد. برای خروج Ctrl+C بزنید.")
    app.run_polling()


if __name__ == "__main__":
    main()
