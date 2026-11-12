"""
Watermark Bot - Multi-user, Privacy-First, Future-Proof Architecture

Features:
- Per-user temporary watermarks (no permanent storage for free users)
- Automatic TTL-based cleanup
- User isolation and privacy protection
- Ready for Pro subscription (persistent watermarks)
- Concurrent request handling
- Secure temporary file management
"""

import os
import json
import logging
import asyncio
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from telegram.ext import (
    Application, MessageHandler, CommandHandler, filters, ContextTypes, CallbackQueryHandler
)
from telegram import Update
from PIL import Image, ImageOps

# Local modules
from watermark_providers import (
    WatermarkProviderFactory, TemporaryWatermarkProvider
)
from temp_file_manager import get_temp_file_manager, shutdown_temp_file_manager
from user_manager import (
    get_user_manager, UserState, WatermarkFormat,
    LogoPosition, LogoSize, ProcessingMode
)

# ─── Configuration ─────────────────────────────────────────────
TOKEN = "2036088747:kKVkB0rK9NpI96355WNxjQ05tBUTQFrpap8"
BASE_URL = "https://tapi.bale.ai/bot"
FILE_URL = "https://tapi.bale.ai/file/bot"

# Watermark settings
WATERMARK_TTL_SECONDS = 300        # 5 minutes TTL for watermarks
TEMP_FILE_TTL_SECONDS = 300        # 5 minutes TTL for temp files
CLEANUP_INTERVAL_SECONDS = 60      # Cleanup check every minute
MAX_FILE_SIZE_MB = 20              # Max upload size
JPEG_QUALITY = 95                  # Output JPEG quality

# Logo Mode settings (configurable presets)
LOGO_SIZE_PRESETS = {
    LogoSize.SMALL: 0.08,     # ~8% of image width
    LogoSize.MEDIUM: 0.13,    # ~13% of image width
    LogoSize.LARGE: 0.18,     # ~18% of image width
}
LOGO_MARGIN_RATIO = 0.03       # 3% margin from edges
LOGO_POSITIONS = list(LogoPosition)  # All available positions

# User session settings
SESSION_TIMEOUT_SECONDS = 300      # 5 minutes inactivity timeout

# ─── Logging Setup ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Reduce noise from libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

# ─── Global Components (initialized in main) ───────────────────
provider_factory: Optional[WatermarkProviderFactory] = None
temp_manager = None
user_manager = None


# ─── Bale API Helpers ──────────────────────────────────────────
def bale_get_file_path(file_id: str) -> str:
    """Get file path from Bale API."""
    url = f"{BASE_URL}{TOKEN}/getFile"
    resp = requests.post(url, json={"file_id": file_id}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"getFile failed: {data}")
    return data["result"]["file_path"]


def bale_download_file(file_path: str) -> bytes:
    """Download file from Bale file server."""
    url = f"{FILE_URL}{TOKEN}/{file_path}"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def bale_send_photo(chat_id: int, image_bytes: bytes, caption: str = "") -> dict:
    """Send photo via Bale API."""
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


# ─── Image Processing (Preserved from Original) ─────────────────
def apply_fullscreen_watermark(img: Image.Image, watermark: Image.Image) -> Image.Image:
    """
    Apply watermark as full-screen overlay on image.

    Preserves original algorithm:
    - EXIF orientation correction
    - Watermark resized to exact image dimensions
    - Alpha compositing for transparency support
    - LANCZOS resampling for quality
    """
    # Correct orientation from EXIF data (mobile photos)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    img = img.convert("RGBA")
    W, H = img.size

    # Resize watermark to match image exactly
    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    watermark_resized = watermark.resize((W, H), resample_filter)

    # Alpha composite watermark over entire image
    return Image.alpha_composite(img, watermark_resized)


# ─── Watermark Validation ──────────────────────────────────────
def validate_watermark_image(image_bytes: bytes) -> tuple[Optional[Image.Image], Optional[str]]:
    """
    Validate uploaded watermark image.

    Returns:
        (PIL Image, None) if valid
        (None, error_message) if invalid
    """
    try:
        img = Image.open(BytesIO(image_bytes))

        # Check format
        if img.format != "PNG":
            return None, "فایل باید فرمت PNG باشد. فرمت‌های دیگر پشتیبانی نمی‌شوند."

        # Verify it's a valid image
        img.verify()

        # Reopen for actual use (verify() consumes the stream)
        img = Image.open(BytesIO(image_bytes))
        img.load()  # Force load to catch any corruption

        # Check dimensions (reasonable limits)
        width, height = img.size
        if width < 10 or height < 10:
            return None, "ابعاد واترمارک خیلی کوچک است (حداقل 10×10 پیکسل)."
        if width > 5000 or height > 5000:
            return None, "ابعاد واترمارک خیلی بزرگ است (حداکثر 5000×5000 پیکسل)."

        # Convert to RGBA for compositing
        img = img.convert("RGBA")

        return img, None

    except Exception as e:
        logger.warning(f"Watermark validation failed: {type(e).__name__}: {e}")
        return None, "فایل واترمارک معتبر نیست یا خراب است. لطفاً یک فایل PNG معتبر ارسال کنید."


# ─── Logo Validation ─────────────────────────────────────────────
def validate_logo_image(image_bytes: bytes) -> tuple[Optional[Image.Image], Optional[str]]:
    """
    Validate uploaded logo image (same as watermark validation).

    Returns:
        (PIL Image, None) if valid
        (None, error_message) if invalid
    """
    try:
        img = Image.open(BytesIO(image_bytes))

        # Check format
        if img.format != "PNG":
            return None, "فایل باید فرمت PNG باشد. فرمت‌های دیگر پشتیبانی نمی‌شوند."

        # Verify it's a valid image
        img.verify()

        # Reopen for actual use (verify() consumes the stream)
        img = Image.open(BytesIO(image_bytes))
        img.load()  # Force load to catch any corruption

        # Check dimensions (reasonable limits for logo)
        width, height = img.size
        if width < 10 or height < 10:
            return None, "ابعاد لوگو خیلی کوچک است (حداقل 10×10 پیکسل)."
        if width > 2000 or height > 2000:
            return None, "ابعاد لوگو خیلی بزرگ است (حداکثر 2000×2000 پیکسل)."

        # Convert to RGBA for compositing (preserve transparency)
        img = img.convert("RGBA")

        return img, None

    except Exception as e:
        logger.warning(f"Logo validation failed: {type(e).__name__}: {e}")
        return None, "فایل لوگو معتبر نیست یا خراب است. لطفاً یک فایل PNG معتبر ارسال کنید."


# ─── Logo Overlay Processing ─────────────────────────────────────
def apply_logo_overlay(img: Image.Image, logo: Image.Image,
                       position: LogoPosition, size_preset: LogoSize) -> Image.Image:
    """
    Apply logo as overlay on image with specified position and size.

    - Preserves logo aspect ratio
    - Preserves PNG transparency (alpha channel)
    - Places logo at specified position with proportional margins
    - Scales logo based on image width using configurable presets
    - Ensures logo stays within image boundaries
    """
    # Correct orientation from EXIF data (mobile photos)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    img = img.convert("RGBA")
    img_w, img_h = img.size

    # Calculate logo size based on image width
    scale_ratio = LOGO_SIZE_PRESETS[size_preset]
    target_w = int(img_w * scale_ratio)

    # Maintain aspect ratio
    logo_aspect = logo.width / logo.height
    target_h = int(target_w / logo_aspect)

    # Resize logo with high quality
    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    logo_resized = logo.resize((target_w, target_h), resample_filter)

    # Calculate position with margins
    margin_w = int(img_w * LOGO_MARGIN_RATIO)
    margin_h = int(img_h * LOGO_MARGIN_RATIO)

    logo_w, logo_h = logo_resized.size

    if position == LogoPosition.BOTTOM_LEFT:
        x = margin_w
        y = img_h - logo_h - margin_h
    elif position == LogoPosition.BOTTOM_CENTER:
        x = (img_w - logo_w) // 2
        y = img_h - logo_h - margin_h
    elif position == LogoPosition.BOTTOM_RIGHT:
        x = img_w - logo_w - margin_w
        y = img_h - logo_h - margin_h
    elif position == LogoPosition.TOP_LEFT:
        x = margin_w
        y = margin_h
    elif position == LogoPosition.TOP_CENTER:
        x = (img_w - logo_w) // 2
        y = margin_h
    elif position == LogoPosition.TOP_RIGHT:
        x = img_w - logo_w - margin_w
        y = margin_h
    else:
        # Default to bottom right
        x = img_w - logo_w - margin_w
        y = img_h - logo_h - margin_h

    # Ensure logo stays within boundaries
    x = max(0, min(x, img_w - logo_w))
    y = max(0, min(y, img_h - logo_h))

    # Create a copy to avoid modifying original
    result = img.copy()

    # Alpha composite logo onto image
    result.alpha_composite(logo_resized, (x, y))

    return result


# ─── Command Handlers ──────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show mode selection menu or current status."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Clean up expired session if any
    if user_manager.is_session_expired(user_id):
        user_manager.remove_user(user_id)
        # Also clean up provider and temp files
        provider = provider_factory.get_provider(user_id)
        await provider.remove_watermark(user_id)
        temp_manager.delete_user_files(user_id)

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    # If user has an active session, show status
    if state == UserState.WATERMARK_READY and mode == ProcessingMode.WATERMARK:
        # User has active watermark
        info = user_manager.get_watermark_info(user_id)
        size_str = f"{info['size'][0]}×{info['size'][1]}" if info and info['size'] else "نامشخص"
        await update.message.reply_text(
            f"سلام! 👋\n\n"
            f"✅ حالت: واترمارک\n"
            f"✅ واترمارک فعال دارید: {info['format'].upper()} ({size_str})\n"
            f"تعداد عکس‌های پردازش شده: {user_manager._users[user_id].images_processed}\n\n"
            f"اکنون می‌توانید عکس بفرستید تا واترمارک روی آن اعمال شود.\n\n"
            f"دستورات:\n"
            f"• /change — تغییر واترمارک\n"
            f"• /remove — حذف واترمارک فعلی\n"
            f"• /mode — تغییر حالت (واترمارک/لوگو)\n"
            f"• /status — وضعیت فعلی\n"
            f"• /help — راهنما"
        )
    elif state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY) and mode == ProcessingMode.LOGO:
        # User has active logo
        info = user_manager.get_logo_info(user_id)
        if info:
            size_str = f"{info['size'][0]}×{info['size'][1]}" if info and info['size'] else "نامشخص"
            pos_str = info['position'] or "تنظیم نشده"
            size_preset_str = info['size_preset'] or "تنظیم نشده"
            await update.message.reply_text(
                f"سلام! 👋\n\n"
                f"✅ حالت: لوگو\n"
                f"✅ لوگو فعال دارید: {info['format'].upper()} ({size_str})\n"
                f"📍 موقعیت: {pos_str}\n"
                f"📏 اندازه: {size_preset_str}\n"
                f"تعداد عکس‌های پردازش شده: {user_manager._users[user_id].images_processed}\n\n"
                f"اکنون می‌توانید عکس بفرستید تا لوگو روی آن اعمال شود.\n\n"
                f"دستورات:\n"
                f"• /changelogo — تغییر لوگو\n"
                f"• /changeposition — تغییر موقعیت لوگو\n"
                f"• /changesize — تغییر اندازه لوگو\n"
                f"• /mode — تغییر حالت (واترمارک/لوگو)\n"
                f"• /status — وضعیت فعلی\n"
                f"• /help — راهنما"
            )
        else:
            await show_mode_selection(update, context)
    elif state == UserState.MODE_SELECTION:
        await show_mode_selection(update, context)
    else:
        # New user or reset - show mode selection
        await show_mode_selection(update, context)


async def show_mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show mode selection menu."""
    await update.message.reply_text(
        "سلام! 👋 به ربات پردازش عکس خوش آمدید.\n\n"
        "لطفاً حالت مورد نظر خود را انتخاب کنید:\n\n"
        "🔹 **واترمارک (Watermark Mode)**\n"
        "   واترمارک تمام‌صفحه روی عکس‌های شما اعمال می‌شود.\n"
        "   مناسب برای محافظت از کپی‌رایت عکس‌ها.\n\n"
        "🔹 **لوگو (Logo Mode)**\n"
        "   لوگو کوچک در گوشه یا مرکز عکس قرار می‌گیرد.\n"
        "   مناسب برای برندینگ و واترمارک ظریف.\n\n"
        "📋 برای انتخاب، یکی از دستورات زیر را بزنید:\n"
        "• `/watermark` — ورود به حالت واترمارک\n"
        "• `/logo` — ورود به حالت لوگو\n\n"
        "🔒 حریم خصوصی:\n"
        "• فایل‌ها فقط در حافظه موقت نگهداری می‌شوند\n"
        "• پس از ۵ دقیقه غیرفعالیتی به صورت خودکار حذف می‌شوند\n"
        "• هیچ داده‌ای به صورت دائمی ذخیره نمی‌شود"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "📖 راهنمای ربات پردازش عکس\n\n"
        "🔹 /start — شروع کار و انتخاب حالت\n"
        "🔹 /help — این راهنما\n"
        "🔹 /status — وضعیت فعلی\n"
        "🔹 /watermark — انتخاب حالت واترمارک\n"
        "🔹 /logo — انتخاب حالت لوگو\n"
        "🔹 /mode — تغییر حالت\n\n"
        "📋 **حالت واترمارک:**\n"
        "🔹 /change — تغییر واترمارک (آپلود فایل PNG جدید)\n"
        "🔹 /remove — حذف واترمارک فعلی\n\n"
        "📋 **حالت لوگو:**\n"
        "🔹 /changelogo — تغییر لوگو (آپلود فایل PNG جدید)\n"
        "🔹 /changeposition — تغییر موقعیت لوگو\n"
        "🔹 /changesize — تغییر اندازه لوگو\n\n"
        "📤 نحوه استفاده:\n"
        "1. حالت را انتخاب کنید (/watermark یا /logo)\n"
        "2. فایل PNG خود را ارسال کنید (واترمارک یا لوگو)\n"
        "3. در حالت لوگو: موقعیت و اندازه را انتخاب کنید\n"
        "4. عکس‌های مورد نظر را بفرستید\n"
        "5. عکس‌های پردازش شده را دریافت کنید\n\n"
        "🔒 حریم خصوصی:\n"
        "• فایل‌ها فقط در حافظه موقت نگهداری می‌شوند\n"
        "• پس از ۵ دقیقه غیرفعالیتی به صورت خودکار حذف می‌شوند\n"
        "• هیچ داده‌ای به صورت دائمی ذخیره نمی‌شود\n"
        "• کاربران دسترسی به داده‌های هم ندارند"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show current status based on mode."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)
    stats = user_manager.get_stats(user_id)

    if mode == ProcessingMode.WATERMARK:
        if state == UserState.WATERMARK_READY:
            info = user_manager.get_watermark_info(user_id)
            size_str = f"{info['size'][0]}\u00d7{info['size'][1]}" if info and info['size'] else "\u0646\u0627\u0645\u0634\u062e\u0635"
            await update.message.reply_text(
                f"\U0001f4ca \u0648\u0636\u0639\u06cc\u062a \u0634\u0645\u0627:\n\n"
                f"\U0001f539 \u062d\u0627\u0644\u062a: \u0648\u0627\u062a\u0645\u0631\u0627\u06a9\n"
                f"\u2705 \u0648\u0627\u062a\u0631\u0645\u0627\u0631\u06a9: \u0641\u0639\u0627\u0644 ({info['format'].upper()}, {size_str})\n"
                f"\U0001f5bc \u0639\u06a9\u0633\u0647\u0627\u06cc \u067e\u0631\u062f\u0627\u0632 \u0634\u062f\u0647: {stats['images_processed']}\n"
                f"\u274c \u062e\u0637\u0627\u0647\u0627: {stats['errors_count']}\n"
                f"\u23f1 \u0622\u062e\u0631\u06cc\u0646 \u0641\u0639\u0627\u0644\u06cc\u062a: {int(__import__('time').time() - stats['last_activity'])} \u062b\u0627\u0646\u06cc\u0647 \u067e\u06cc\u0634"
            )
        elif state == UserState.WATERMARK_INVALID:
            await update.message.reply_text(
                "\u26a0\ufe0f \u0648\u0627\u062a\u0631\u0645\u0627\u0631\u06a9 \u0642\u0628\u0644\u06cc \u0645\u0639\u062a\u0628\u0631 \u0645\u0639\u062a\u0628\u0631 \u0646\u0628\u0648\u062f.\n"
                "\u0644\u0637\u0641\u0627\u0646\u0647 \u06cc\u06a9 \u0641\u0627\u06cc\u0644 PNG \u0645\u0639\u062a\u0628\u0631 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
            )
        else:
            await update.message.reply_text(
                "\u2139\ufe0f \u0647\u06cc\u0686 \u0648\u0627\u062a\u0645\u0631\u0627\u06a9\u06cc \u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647.\n"
                "\u0641\u0627\u06cc\u0644 PNG \u0648\u0627\u062a\u0645\u0631\u0627\u06a9 \u062e\u0648\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f \u06cc\u0627 /watermark \u0628\u0632\u0646\u06cc\u062f."
            )
    elif mode == ProcessingMode.LOGO:
        if state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
            info = user_manager.get_logo_info(user_id)
            if info:
                size_str = f"{info['size'][0]}\u00d7{info['size'][1]}" if info and info['size'] else "\u0646\u0627\u0645\u0634\u062e\u0635"
                pos_str = info['position'] or "\u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647"
                size_preset_str = info['size_preset'] or "\u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647"
                await update.message.reply_text(
                    f"\U0001f4ca \u0648\u0636\u0639\u06cc\u062a \u0634\u0645\u0627:\n\n"
                    f"\U0001f539 \u062d\u0627\u0644\u062a: \u0644\u0648\u06af\u0648\n"
                    f"\u2705 \u0644\u0648\u06af\u0648: \u0641\u0639\u0627\u0644 ({info['format'].upper()}, {size_str})\n"
                    f"\U0001f4cd \u0645\u0648\u0642\u0639\u06cc\u062a: {pos_str}\n"
                    f"\U0001f4cf \u0627\u0646\u062f\u0627\u0632\u0647: {size_preset_str}\n"
                    f"\U0001f5bc \u0639\u06a9\u0633\u0647\u0627\u06cc \u067e\u0631\u062f\u0627\u0632 \u0634\u062f\u0647: {stats['images_processed']}\n"
                    f"\u274c \u062e\u0637\u0627\u0647\u0627: {stats['errors_count']}\n"
                    f"\u23f1 \u0622\u062e\u0631\u06cc\u0646 \u0641\u0639\u0627\u0644\u06cc\u062a: {int(__import__('time').time() - stats['last_activity'])} \u062b\u0627\u0646\u06cc\u0647 \u067e\u06cc\u0634"
                )
            else:
                await update.message.reply_text(
                    "\u2139\ufe0f \u0644\u0648\u06af\u0648 \u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647.\n"
                    "\u0641\u0627\u06cc\u0644 PNG \u0644\u0648\u06af\u0648 \u062e\u0648\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062d \u06cc\u0627 /logo \u0628\u0632\u0646\u06cc\u062f."
                )
        elif state == UserState.LOGO_INVALID:
            await update.message.reply_text(
                "\u26a0\ufe0f \u0644\u0648\u06af\u0648 \u0642\u0628\u0644\u06cc \u0645\u0639\u062a\u0628\u0631 \u0645\u0639\u062a\u0628\u0631 \u0646\u0628\u0648\u062f.\n"
                "\u0644\u0637\u0641\u0627\u0646\u0647 \u06cc\u06a9 \u0641\u0627\u06cc\u0644 PNG \u0645\u0639\u062a\u0628\u0631 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
            )
        else:
            await update.message.reply_text(
                "\u2139\ufe0f \u0647\u06cc\u0686 \u0644\u0648\u06af\u0648\u06cc \u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647.\n"
                "\u0641\u0627\u06cc\u0644 PNG \u0644\u0648\u06af\u0648 \u062e\u0648\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f \u06cc\u0627 /logo \u0628\u0632\u0646\u06cc\u062f."
            )
    else:
        await update.message.reply_text(
            "\u2139\ufe0f \u062d\u0627\u0644\u062a \u0627\u0646\u062a\u062e\u0627\u0628 \u0646\u0634\u062f\u0647.\n"
            "/start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f \u062a\u0627 \u062d\u0627\u0644\u062a \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f."
        )



async def cmd_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /change command - prompt for new watermark or logo based on mode."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode == ProcessingMode.WATERMARK:
        if state == UserState.WATERMARK_READY:
            await update.message.reply_text(
                "\U0001f504 \u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0648\u0627\u062a\u0631\u0645\u0627\u0631\u06a9, \u0641\u0627\u06cc\u0644 PNG \u062c\u062f\u06cc\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f.\n"
                "\u0648\u0627\u062a\u0631\u0645\u0627\u0631\u06a9 \u0642\u0628\u0644\u06cc \u062c\u0627\u06cc\u06af\u0632\u06cc\u0646 \u062e\u0648\u0627\u0647\u062f \u062c\u0627\u06cc\u06af\u0632\u06cc\u0646 \u062e\u0648\u0627\u0647\u062f \u0634\u062f."
            )
        else:
            await update.message.reply_text(
                "\u0634\u0645\u0627 \u0648\u0627\u062a\u0631\u0645\u0627\u0631\u06a9 \u0641\u0639\u0627\u0644\u06cc \u0646\u062f\u0627\u0631\u06cc\u062f. \u0641\u0627\u06cc\u0644 PNG \u0648\u0627\u062a\u0631\u0645\u0627\u0631\u06a9 \u062e\u0648\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
            )

        # Set state to expecting watermark
        user_manager.set_state(user_id, UserState.WATERMARK_PENDING)

    elif mode == ProcessingMode.LOGO:
        if state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
            await update.message.reply_text(
                "\U0001f504 \u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0644\u0648\u06af\u0648, \u0641\u0627\u06cc\u0644 PNG \u062c\u062f\u06cc\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f.\n"
                "\u0644\u0648\u06af\u0648 \u0642\u0628\u0644\u06cc \u062c\u0627\u06cc\u06af\u0632\u06cc\u0646 \u062e\u0648\u0627\u0647\u062f \u062c\u0627\u06cc\u06af\u0632\u06cc\u0646 \u062e\u0648\u0627\u0647\u062f \u0634\u062f.\n"
                "\u0628\u0639\u062f \u0627\u0632 \u0627\u0631\u0633\u0627\u0644, \u0645\u0648\u0642\u0639\u06cc\u062a \u0648 \u0627\u0646\u062f\u0627\u0632\u0647 \u0628\u0627\u06cc\u062f \u0628\u0631\u0627\u06cc \u0627\u0646\u062a\u062e\u0627\u0628."
            )
        else:
            await update.message.reply_text(
                "\u0634\u0645\u0627 \u0644\u0648\u06af\u0648 \u0641\u0639\u0627\u0644\u06cc \u0646\u062f\u0627\u0631\u06cc\u062f. \u0641\u0627\u06cc\u0644 PNG \u0644\u0648\u06af\u0648 \u062e\u0648\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
            )

        # Clear old logo and set state to expecting logo
        from user_manager import get_user_manager
        um = get_user_manager()
        um.clear_logo(user_id)
        user_manager.set_state(user_id, UserState.LOGO_PENDING)

    else:
        await update.message.reply_text(
            "\u062d\u0627\u0644\u062a \u0627\u0646\u062a\u062e\u0627\u0628 \u0646\u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f \u062a\u0627 \u062d\u0627\u0644\u062a \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f."
        )

async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove command - remove current watermark."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نشست شما منقضی شده. /start را بزنید.")
        return

    state = user_manager.get_state(user_id)

    if state == UserState.WATERMARK_READY:
        # Remove from provider
        provider = provider_factory.get_provider(user_id)
        await provider.remove_watermark(user_id)

        # Clean up temp files
        temp_manager.delete_user_files(user_id)

        # Clear user state
        user_manager.clear_watermark(user_id)

        await update.message.reply_text(
            "🗑 واترمارک شما حذف شد.\n"
            "برای استفاده مجدد، /start را بزنید و واترمارک جدید آپلود کنید."
        )
    else:
        await update.message.reply_text("هیچ واترمارک فعالی برای حذف وجود ندارد.")


# ─── Mode Selection Commands ─────────────────────────────────────
async def cmd_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /watermark command - switch to watermark mode."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نشست شما منقضی شده. /start را بزنید.")
        return

    # Clean up any existing logo data
    user_manager.clear_logo(user_id)
    temp_manager.delete_user_files(user_id)

    # Set mode to watermark
    user_manager.set_mode(user_id, ProcessingMode.WATERMARK)

    await update.message.reply_text(
        "✅ حالت واترمارک انتخاب شد.\n\n"
        "📋 لطفاً **واترمارک خودتان را به فرمت PNG** ارسال کنید.\n\n"
        "نکات مهم:\n"
        "• واترمارک شما فقط در حافظه موقت سرور نگهداری می‌شود (حداکثر ۵ دقیقه غیرفعالیتی)\n"
        "• هیچ فایلی به صورت دائمی ذخیره نمی‌شود\n"
        "• واترمارک شما فقط برای شما قابل دسترسی است\n"
        "• پس از اتمام کار، فایل‌ها به صورت خودکار حذف می‌شوند\n\n"
        "منتظر فایل PNG واترمارک شما هستم... 📎"
    )


async def cmd_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /logo command - switch to logo mode."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نشست شما منقضی شده. /start را بزنید.")
        return

    # Clean up any existing watermark data
    provider = provider_factory.get_provider(user_id)
    await provider.remove_watermark(user_id)
    temp_manager.delete_user_files(user_id)

    # Set mode to logo
    user_manager.set_mode(user_id, ProcessingMode.LOGO)

    await update.message.reply_text(
        "✅ حالت لوگو انتخاب شد.\n\n"
        "📋 لطفاً **لوگو خودتان را به فرمت PNG** ارسال کنید.\n\n"
        "نکات مهم:\n"
        "• لوگو شما فقط در حافظه موقت سرور نگهداری می‌شود (حداکثر ۵ دقیقه غیرفعالیتی)\n"
        "• هیچ فایلی به صورت دائمی ذخیره نمی‌شود\n"
        "• لوگو شما فقط برای شما قابل دسترسی است\n"
        "• پس از اتمام کار، فایل‌ها به صورت خودکار حذف می‌شوند\n\n"
        "منتظر فایل PNG لوگو شما هستم... 📎"
    )


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mode command - show mode selection."""
    await show_mode_selection(update, context)


# ─── Logo Mode Command Handlers ───────────────────────────────────
async def cmd_changelogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /changelogo command - prompt for new logo."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO:
        await update.message.reply_text(
            "\u0634\u0645\u0627 \u062f\u0631 \u062d\u0627\u0644\u062a \u0648\u0627\u062a\u0645\u0631\u0627\u06a9 \u0647\u0633\u062a\u06cc\u062f. \u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0644\u0648\u06af\u0648, \u0627\u0648\u0644\u06cc\u0646 /logo \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f."
        )
        return

    if state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await update.message.reply_text(
            "\U0001f504 \u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0644\u0648\u06af\u0648, \u0641\u0627\u06cc\u0644 PNG \u062c\u062f\u06cc\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f.\n"
            "\u0644\u0648\u06af\u0648 \u0642\u0628\u0644\u06cc \u062c\u0627\u06cc\u06af\u0632\u06cc\u0646 \u062e\u0648\u0627\u0647\u062f \u062c\u0627\u06cc\u06af\u0632\u06cc\u0646 \u062e\u0648\u0627\u0647\u062f \u0634\u062f.\n"
            "\u0628\u0639\u062f \u0627\u0632 \u0627\u0631\u0633\u0627\u0644, \u0645\u0648\u0642\u0639\u06cc\u062a \u0648 \u0627\u0646\u062f\u0627\u0632\u0647 \u0628\u0627\u06cc\u062f \u0628\u0631\u0627\u06cc \u0627\u0646\u062a\u062e\u0627\u0628."
        )
    else:
        await update.message.reply_text(
            "\u0634\u0645\u0627 \u0644\u0648\u06af\u0648 \u0641\u0639\u0627\u0644\u06cc \u0646\u062f\u0627\u0631\u06cc\u062f. \u0641\u0627\u06cc\u0644 PNG \u0644\u0648\u06af\u0648 \u062e\u0648\u062f \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
        )

    # Clear old logo and set state to expecting logo
    user_manager.clear_logo(user_id)
    user_manager.set_state(user_id, UserState.LOGO_PENDING)


async def cmd_changeposition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /changeposition command - show position selection keyboard."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO:
        await update.message.reply_text(
            "\u0634\u0645\u0627 \u062f\u0631 \u062d\u0627\u0644\u062a \u0648\u0627\u062a\u0645\u0631\u0627\u06a9 \u0647\u0633\u062a\u06cc\u062f. \u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0645\u0648\u0642\u0639\u06cc\u062a \u0644\u0648\u06af\u0648, \u0627\u0648\u0644\u06cc\u0646 /logo \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f."
        )
        return

    if state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await update.message.reply_text(
            "\u0647\u06cc\u0686 \u0644\u0648\u06af\u0648\u06cc \u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0645\u0648\u0642\u0639\u06cc\u062a \u0648\u062c\u0648\u062f \u0646\u062f\u0627\u0631\u062f. \u0644\u0648\u06af\u0648 \u0631\u0627 \u0627\u0648\u0644 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
        )
        return

    # Show inline keyboard for position selection
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("\u067e\u0627\u06cc\u06cc\u0646 \u0686\u067e", callback_data="logo_pos:bottom_left"),
            InlineKeyboardButton("\u067e\u0627\u06cc\u06cc\u0646 \u0648\u0633\u0637", callback_data="logo_pos:bottom_center"),
            InlineKeyboardButton("\u067e\u0627\u06cc\u06cc\u0646 \u0631\u0627\u0633\u062a", callback_data="logo_pos:bottom_right"),
        ],
        [
            InlineKeyboardButton("\u0628\u0627\u0644\u0627 \u0686\u067e", callback_data="logo_pos:top_left"),
            InlineKeyboardButton("\u0628\u0627\u0644\u0627 \u0648\u0633\u0637", callback_data="logo_pos:top_center"),
            InlineKeyboardButton("\u0628\u0627\u0644\u0627 \u0631\u0627\u0633\u062a", callback_data="logo_pos:top_right"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "\U0001f4cd \u0645\u0648\u0642\u0639\u06cc\u062a \u0644\u0648\u06af\u0648 \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:\n\n"
        "\u2022 \u067e\u0627\u06cc\u06cc\u0646 \u0686\u067e (Bottom Left)\n"
        "\u2022 \u067e\u0627\u06cc\u06cc\u0646 \u0648\u0633\u0637 (Bottom Center)\n"
        "\u2022 \u067e\u0627\u06cc\u06cc\u0646 \u0631\u0627\u0633\u062a (Bottom Right)\n"
        "\u2022 \u0628\u0627\u0644\u0627 \u0686\u067e (Top Left)\n"
        "\u2022 \u0628\u0627\u0644\u0627 \u0648\u0633\u0637 (Top Center)\n"
        "\u2022 \u0628\u0627\u0644\u0627 \u0631\u0627\u0633\u062a (Top Right)\n\n"
        "\u06cc\u06a9 \u062f\u06af\u0645\u0647 \u0631\u0627 \u06a9\u0644\u06cc\u06a9 \u06a9\u0646\u06cc\u062f.",
        reply_markup=reply_markup
    )


async def cmd_changesize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /changesize command - show size selection keyboard."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO:
        await update.message.reply_text(
            "\u0634\u0645\u0627 \u062f\u0631 \u062d\u0627\u0644\u062a \u0648\u0627\u062a\u0645\u0631\u0627\u06a9 \u0647\u0633\u062a\u06cc\u062f. \u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0627\u0646\u062f\u0627\u0632\u0647 \u0644\u0648\u06af\u0648, \u0627\u0648\u0644\u06cc\u0646 /logo \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f."
        )
        return

    if state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await update.message.reply_text(
            "\u0647\u06cc\u0686 \u0644\u0648\u06af\u0648\u06cc \u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0627\u0646\u062f\u0627\u0632\u0647 \u0648\u062c\u0648\u062f \u0646\u062f\u0627\u0631\u062f. \u0644\u0648\u06af\u0648 \u0631\u0627 \u0627\u0648\u0644 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
        )
        return

    # Show inline keyboard for size selection
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("\u06a9\u0648\u0686\u06a9 (\u22488%)", callback_data="logo_size:small"),
            InlineKeyboardButton("\u0645\u062a\u0648\u0633\u0637 (\u224813%)", callback_data="logo_size:medium"),
            InlineKeyboardButton("\u0628\u0632\u0631\u06af (\u224818%)", callback_data="logo_size:large"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "\U0001f4cf \u0627\u0646\u062f\u0627\u0632\u0647 \u0644\u0648\u06af\u0648 \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:\n\n"
        "\u2022 \u06a9\u0648\u0686\u06a9 \u2248 8% \u0639\u0631\u0636 \u0639\u06a9\u0633 \u0639\u06a9\u0633\n"
        "\u2022 \u0645\u062a\u0648\u0633\u0637 \u2248 13% \u0639\u0631\u0636 \u0639\u06a9\u0633 \u0639\u06a9\u0633\n"
        "\u2022 \u0628\u0632\u0631\u06af \u2248 18% \u0639\u0631\u0636 \u0639\u06a9\u0633 \u0639\u06a9\u0633\n\n"
        "\u06cc\u06a9 \u062f\u06af\u0645\u0647 \u0631\u0627 \u06a9\u0644\u06cc\u06a9 \u06a9\u0646\u06cc\u062f.",
        reply_markup=reply_markup
    )


# ─── Logo Upload Handler ──────────────────────────────────────────
async def handle_logo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo/document upload for logo mode."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO:
        # Not in logo mode, route to watermark handler
        await handle_watermark_upload(update, context)
        return

    # Only accept logo upload if user is in pending state
    if state not in (UserState.NO_LOGO, UserState.LOGO_PENDING, UserState.LOGO_INVALID):
        # User has active logo - this might be an image to process
        await handle_image_processing_logo(update, context)
        return

    # Get the file (photo or document)
    if update.message.photo:
        photo = update.message.photo[-1]
        file_id = photo.file_id
    elif update.message.document:
        document = update.message.document
        # Check if it's a PNG
        mime_type = document.mime_type
        file_name = document.file_name or ""
        is_png = (
            mime_type == "image/png" or
            file_name.lower().endswith(".png")
        )
        if not is_png:
            await update.message.reply_text(
                "\u274c \u0641\u0642\u0637 \u0644\u0648\u06af\u0648 \u0628\u0627\u06cc\u062f \u0641\u0631\u0645\u062a PNG \u0628\u0627\u0634\u062f.\n"
                "\u0644\u0637\u0641\u0627\u0646\u0647 \u06cc\u06a9 \u0641\u0627\u06cc\u0644 PNG \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
            )
            user_manager.increment_errors(user_id)
            return
        file_id = document.file_id
    else:
        await update.message.reply_text("\u274c \u0646\u0648\u0639 \u0641\u0627\u06cc\u0644 \u06cc\u0627\u0641\u062a \u0646\u062f\u0627\u0631\u062f.")
        return

    # Send processing message
    status_msg = await update.message.reply_text("\u23f3 \u062f\u0631 \u062d\u0627\u0644 \u0628\u0631\u0631\u0633\u06cc \u0644\u0648\u06af\u0648...")

    try:
        # Download file from Bale
        file_path = bale_get_file_path(file_id)
        img_bytes = bale_download_file(file_path)

        # Validate file size
        if len(img_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            await status_msg.edit_text(f"\u274c \u0641\u0627\u06cc\u0644 \u062e\u06cc\u0644\u06cc \u0628\u0632\u0631\u06af \u0627\u0633\u062a (\u062d\u062f\u0627\u06a9\u062b\u0631 {MAX_FILE_SIZE_MB} \u0645\u06af\u0627\u0628\u0627\u06cc\u062a).")
            user_manager.increment_errors(user_id)
            return

        # Validate as PNG logo
        logo_img, error = validate_logo_image(img_bytes)

        if error:
            await status_msg.edit_text(f"\u274c {error}")
            user_manager.set_state(user_id, UserState.LOGO_INVALID)
            user_manager.increment_errors(user_id)
            return

        # Save to temporary storage
        temp_path = temp_manager.save_uploaded_file(
            user_id, img_bytes, suffix=".png", prefix="logo_"
        )

        if not temp_path:
            await status_msg.edit_text("\u274c \u062e\u0637\u0627 \u062f\u0631 \u0630\u062e\u06cc\u0631\u0647 \u0645\u0648\u0642\u062a \u0641\u0627\u06cc\u0644. \u0644\u0637\u0641\u0627\u0646\u0647 \u062f\u0648\u0628\u0627\u0631\u0647 \u062a\u0644\u0627\u0634 \u06a9\u0646\u06cc\u062f.")
            user_manager.increment_errors(user_id)
            return

        # Update user state
        user_manager.set_logo_info(
            user_id,
            str(temp_path),
            WatermarkFormat.PNG,
            logo_img.size
        )

        await status_msg.edit_text(
            f"\u2705 \u0644\u0648\u06af\u0648 \u0628\u0627 \u0645\u0648\u0641\u0642\u06cc\u062a \u062a\u0646\u0638\u06cc\u0645 \u0634\u062f!\n\n"
            f"\U0001f4d0 \u0627\u0628\u0639\u0627\u062f: {logo_img.width}\u00d7{logo_img.height}\n"
            f"\U0001f4c1 \u0641\u0631\u0645\u062a: PNG\n\n"
            f"\u0627\u06a9\u0646\u0648\u0646 \u0645\u0648\u0642\u0639\u06cc\u062a \u0648 \u0627\u0646\u062f\u0627\u0632\u0647 \u0644\u0648\u06af\u0648 \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:\n"
            f"\u2022 /changeposition \u2014 \u0627\u0646\u062a\u062e\u0627\u0628 \u0645\u0648\u0642\u0639\u06cc\u062a\n"
            f"\u2022 /changesize \u2014 \u0627\u0646\u062a\u062e\u0627\u0628 \u0627\u0646\u062f\u0627\u0632\u0647"
        )

        logger.info(f"User {user_id} set logo: {logo_img.size} PNG")

    except Exception as e:
        logger.error(f"Logo upload error for user {user_id}: {type(e).__name__}: {e}")
        await status_msg.edit_text(f"\u274c \u062e\u0637\u0627 \u062f\u0631 \u067e\u0631\u062f\u0627\u0632\u0634 \u0644\u0648\u06af\u0648:\n{type(e).__name__}")
        user_manager.increment_errors(user_id)
        # Keep error message visible, don't delete
    # On success, keep the success message visible (don't delete)


# ─── Callback Query Handlers for Logo Position/Size ───────────────
async def handle_logo_position_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callback for logo position selection."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_manager.is_session_expired(user_id):
        await query.edit_message_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO or state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await query.edit_message_text("\u274c \u062d\u0627\u0644\u062a \u0644\u0648\u06af\u0648 \u0641\u0639\u0627\u0644 \u0646\u06cc\u0633\u062a. \u0644\u0648\u06af\u0648 \u0631\u0627 \u0627\u0648\u0644 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f.")
        return

    # Parse callback data
    data = query.data
    if not data.startswith("logo_pos:"):
        return

    pos_str = data.split(":")[1]
    try:
        position = LogoPosition(pos_str)
    except ValueError:
        await query.edit_message_text("\u274c \u0645\u0648\u0642\u0639\u06cc\u062a \u0646\u0627\u0645\u0639\u062a\u0628\u0631.")
        return

    # Set position
    user_manager.set_logo_position(user_id, position)

    # Get current size preset if already set
    info = user_manager.get_logo_info(user_id)
    size_preset_str = info['size_preset'] if info and info['size_preset'] else "\u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647"

    await query.edit_message_text(
        f"\u2705 \u0645\u0648\u0642\u0639\u06cc\u062a \u062a\u0646\u0638\u06cc\u0645 \u0634\u062f: {position.value}\n\n"
        f"\u0627\u0646\u062f\u0627\u0632\u0647 \u0641\u0639\u0644\u06cc: {size_preset_str}\n\n"
        f"\u0628\u0631\u0627\u06cc \u062a\u063a\u06cc\u0631 \u0627\u0646\u062f\u0627\u0632\u0647: /changesize\n"
        f"\u0628\u0631\u0627\u06cc \u0627\u0646\u062a\u062e\u0627\u0628 \u0645\u0648\u0642\u0639\u06cc\u062a \u062f\u06cc\u06af\u0631: /changeposition"
    )


async def handle_logo_size_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callback for logo size selection."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_manager.is_session_expired(user_id):
        await query.edit_message_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO or state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await query.edit_message_text("\u274c \u062d\u0627\u0644\u062a \u0644\u0648\u06af\u0648 \u0641\u0639\u0627\u0644 \u0646\u06cc\u0633\u062a. \u0644\u0648\u06af\u0648 \u0631\u0627 \u0627\u0648\u0644 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f.")
        return

    # Parse callback data
    data = query.data
    if not data.startswith("logo_size:"):
        return

    size_str = data.split(":")[1]
    try:
        size = LogoSize(size_str)
    except ValueError:
        await query.edit_message_text("\u274c \u0627\u0646\u062f\u0627\u0632\u0647 \u0646\u0627\u0645\u0639\u062a\u0628\u0631.")
        return

    # Set size
    user_manager.set_logo_size(user_id, size)

    # Get current position if already set
    info = user_manager.get_logo_info(user_id)
    pos_str = info['position'] if info and info['position'] else "\u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647"

    await query.edit_message_text(
        f"\u2705 \u0627\u0646\u062f\u0627\u0632\u0647 \u062a\u0646\u0638\u06cc\u0645 \u0634\u062f: {size.value}\n\n"
        f"\u0645\u0648\u0642\u0639\u06cc\u062a \u0641\u0639\u0644\u06cc: {pos_str}\n\n"
        f"\U0001f389 \u0644\u0648\u06af\u0648 \u06a9\u0627\u0645\u0644 \u062a\u0646\u0638\u06cc\u0645 \u0634\u062f\u0647 \u0648 \u0622\u0645\u0627\u062f\u0647 \u0628\u0631\u0627\u06cc \u0627\u0639\u0645\u0627\u0644!\n"
        f"\u0627\u06a9\u0646\u0648\u0646 \u0645\u06cc\u062a\u0648\u0627\u0646\u06cc\u062f \u0639\u06a9\u0633\u0647\u0627\u06cc \u062e\u0648\u062f \u0631\u0627 \u0628\u0641\u0631\u0633\u062a\u06cc\u062f \u062a\u0627 \u0644\u0648\u06af\u0648 \u0631\u0648\u06cc \u0627\u0639\u0645\u0627\u0644 \u0634\u0648\u062f."
    )


# ─── Logo Image Processing ────────────────────────────────────────
async def handle_image_processing_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user's image with their logo overlay."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO or state != UserState.LOGO_READY:
        await update.message.reply_text(
            "\u26a0\ufe0f \u0644\u0648\u06af\u0648 \u0648 \u062a\u0646\u0638\u06cc\u0645\u0627\u062a \u0627\u0646\u062e\u0627\u0628 \u0646\u0634\u062f\u0647.\n"
            "\u0644\u0648\u06af\u0648 \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f \u0648 \u0645\u0648\u0642\u0639\u06cc\u062a/\u0627\u0646\u062f\u0627\u0632\u0647 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f."
        )
        return

    info = user_manager.get_logo_info(user_id)
    if not info or not info['path'] or not info['position'] or not info['size_preset']:
        await update.message.reply_text(
            "\u26a0\ufe0f \u062a\u0646\u0638\u06cc\u0645\u0627\u062a \u0644\u0648\u06af\u0648 \u06a9\u0627\u0645\u0644 \u0646\u06cc\u0633\u062a.\n"
            "/changelogo \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f \u0648 \u0628\u0627\u0639\u062f /changeposition \u0648 /changesize."
        )
        return

    # Load logo from temp file
    logo_path = Path(info['path'])
    if not logo_path.exists():
        user_manager.clear_logo(user_id)
        await update.message.reply_text(
            "\u26a0\ufe0f \u0644\u0648\u06af\u0648 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. \u0628\u0627 /changelogo \u0628\u0631\u0627\u06cc \u0627\u0648\u0644 \u0627\u0631\u0633\u0627\u0644."
        )
        return

    try:
        logo_img = Image.open(logo_path).convert("RGBA")
    except Exception as e:
        logger.error(f"Failed to load logo for user {user_id}: {e}")
        user_manager.clear_logo(user_id)
        await update.message.reply_text(
            "\u26a0\ufe0f \u0644\u0648\u06af\u0648 \u062e\u0631\u0627\u0628 \u0634\u062f\u0647. \u0628\u0627 /changelogo \u0628\u0631\u0627\u06cc \u0627\u0648\u0644 \u0627\u0631\u0633\u0627\u0644."
        )
        return

    # Get the file (photo or document)
    if update.message.photo:
        photo = update.message.photo[-1]
        file_id = photo.file_id
    elif update.message.document:
        document = update.message.document
        # Check if it's an image
        mime_type = document.mime_type or ""
        file_name = document.file_name or ""
        is_image = (
            mime_type.startswith("image/") or
            any(file_name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"])
        )
        if not is_image:
            await update.message.reply_text(
                "\u274c \u0641\u0642\u0637 \u0639\u06a9\u0633 \u062a\u0635\u0648\u06cc\u0631\u06cc \u067e\u0630\u06cc\u0631\u0641\u062a\u0647 \u0628\u0627\u0634\u062f.\n"
                "\u0644\u0637\u0641\u0627\u0646\u0647 \u06cc\u06a9 \u0639\u06a9\u0633 (PNG, JPG, WEBP) \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
            )
            user_manager.increment_errors(user_id)
            return
        file_id = document.file_id
    else:
        await update.message.reply_text("\u274c \u0646\u0648\u0639 \u0641\u0627\u06cc\u0644 \u06cc\u0627\u0641\u062a \u0646\u062f\u0627\u0631\u062f.")
        return

    status_msg = await update.message.reply_text("\u23f3 \u062f\u0631 \u062d\u0627\u0644 \u0627\u0639\u0645\u0627\u0644 \u0644\u0648\u06af\u0648...")

    try:
        # Download user's image
        file_path = bale_get_file_path(file_id)
        img_bytes = bale_download_file(file_path)

        # Validate file size
        if len(img_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            await status_msg.edit_text(f"\u274c \u0641\u0627\u06cc\u0644 \u062e\u06cc\u0644\u06cc \u0628\u0632\u0631\u06af \u0627\u0633\u062a (\u062d\u062f\u0627\u06a9\u062b\u0631 {MAX_FILE_SIZE_MB} \u0645\u06af\u0627\u0628\u0627\u06cc\u062a).")
            user_manager.increment_errors(user_id)
            return

        # Open image
        img = Image.open(BytesIO(img_bytes))
        orig_w, orig_h = img.size

        # Apply logo overlay
        result = apply_logo_overlay(
            img,
            logo_img,
            info['position'],
            info['size_preset']
        )

        # Save to bytes
        output = BytesIO()
        result.convert("RGB").save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        output.seek(0)
        result_bytes = output.read()

        # Send result
        bale_send_photo(
            chat_id=chat_id,
            image_bytes=result_bytes,
            caption=f"\u2705 \u0644\u0648\u06af\u0648 \u0627\u0639\u0645\u0627\u0644 \u0634\u062f (\u00d7{orig_w}\u00d7{orig_h})"
        )

        # Update stats
        user_manager.increment_processed(user_id)

        logger.info(f"User {user_id} processed image with logo: {orig_w}x{orig_h}")

    except Exception as e:
        logger.error(f"Logo image processing error for user {user_id}: {type(e).__name__}: {e}")
        await status_msg.edit_text(f"\u274c \u062e\u0637\u0627 \u062f\u0631 \u067e\u0631\u062f\u0627\u0632\u0634 \u062a\u0635\u0648\u06cc\u0631:\n{type(e).__name__}")
        user_manager.increment_errors(user_id)
        # Keep error message visible, don't delete


# ─── Photo Handler (Watermark Upload) ──────────────────────────
async def handle_watermark_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo upload - treat as watermark if user needs one."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نشست شما منقضی شده. /start را بزنید.")
        return

    state = user_manager.get_state(user_id)

    # Only accept watermark upload if user is in pending state or has no watermark
    if state not in (UserState.NO_WATERMARK, UserState.WATERMARK_PENDING, UserState.WATERMARK_INVALID):
        # User has active watermark - this might be an image to process
        await handle_image_processing(update, context)
        return

    # Get the highest quality photo
    photo = update.message.photo[-1]
    file_id = photo.file_id

    # Send processing message
    status_msg = await update.message.reply_text("⏳ در حال بررسی واترمارک...")

    try:
        # Download file from Bale
        file_path = bale_get_file_path(file_id)
        img_bytes = bale_download_file(file_path)

        # Validate file size
        if len(img_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            await status_msg.edit_text(f"❌ فایل خیلی بزرگ است (حداکثر {MAX_FILE_SIZE_MB} مگابایت).")
            user_manager.increment_errors(user_id)
            return

        # Validate as PNG watermark
        watermark_img, error = validate_watermark_image(img_bytes)

        if error:
            await status_msg.edit_text(f"❌ {error}")
            user_manager.set_state(user_id, UserState.WATERMARK_INVALID)
            user_manager.increment_errors(user_id)
            return

        # Save to temporary storage
        temp_path = temp_manager.save_uploaded_file(
            user_id, img_bytes, suffix=".png", prefix="watermark_"
        )

        if not temp_path:
            await status_msg.edit_text("❌ خطا در ذخیره موقت فایل. لطفاً دوباره تلاش کنید.")
            user_manager.increment_errors(user_id)
            return

        # Store watermark in provider (in-memory)
        provider = provider_factory.get_provider(user_id)
        await provider.set_watermark(user_id, watermark_img)

        # Update user state
        user_manager.set_watermark_info(
            user_id,
            str(temp_path),
            WatermarkFormat.PNG,
            watermark_img.size
        )

        await status_msg.edit_text(
            f"✅ واترمارک با موفقیت تنظیم شد!\n\n"
            f"📐 ابعاد: {watermark_img.width}×{watermark_img.height}\n"
            f"📁 فرمت: PNG\n\n"
            f"اکنون عکس‌های خود را بفرستید تا واترمارک روی آن‌ها اعمال شود."
        )

        logger.info(f"User {user_id} set watermark: {watermark_img.size} PNG")

    except Exception as e:
        logger.error(f"Watermark upload error for user {user_id}: {type(e).__name__}: {e}")
        await status_msg.edit_text(f"❌ خطا در پردازش واترمارک:\n{type(e).__name__}")
        user_manager.increment_errors(user_id)
        # Keep error message visible, don't delete
    # On success, keep the success message visible (don't delete)


# ─── Image Processing Handler ──────────────────────────────────
async def handle_image_processing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user's image with their watermark."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نشست شما منقضی شده. /start را بزنید.")
        return

    state = user_manager.get_state(user_id)

    if state != UserState.WATERMARK_READY:
        await update.message.reply_text(
            "⚠️ ابتدا باید واترمارک خود را آپلود کنید.\n"
            "فایل PNG واترمارک را ارسال کنید یا /start بزنید."
        )
        return

    # Get user's watermark from provider
    provider = provider_factory.get_provider(user_id)
    watermark = await provider.get_watermark(user_id)

    if watermark is None:
        # Watermark expired or lost
        user_manager.clear_watermark(user_id)
        await update.message.reply_text(
            "⚠️ واترمارک شما منقضی شده یا حذف شده.\n"
            "لطفاً دوباره واترمارک PNG خود را ارسال کنید."
        )
        return

    # Get the highest quality photo
    photo = update.message.photo[-1]
    file_id = photo.file_id

    status_msg = await update.message.reply_text("⏳ در حال اعمال واترمارک تمام‌صفحه...")

    try:
        # Download user's image
        file_path = bale_get_file_path(file_id)
        img_bytes = bale_download_file(file_path)

        # Validate file size
        if len(img_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            await status_msg.edit_text(f"❌ فایل خیلی بزرگ است (حداکثر {MAX_FILE_SIZE_MB} مگابایت).")
            user_manager.increment_errors(user_id)
            return

        # Open image
        img = Image.open(BytesIO(img_bytes))
        orig_w, orig_h = img.size

        # Apply watermark (preserved original algorithm)
        result = apply_fullscreen_watermark(img, watermark)

        # Save to bytes
        output = BytesIO()
        result.convert("RGB").save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        output.seek(0)
        result_bytes = output.read()

        # Send result
        bale_send_photo(
            chat_id=chat_id,
            image_bytes=result_bytes,
            caption=f"✅ واترمارک اعمال شد ({orig_w}×{orig_h})"
        )

        # Update stats
        user_manager.increment_processed(user_id)

        logger.info(f"User {user_id} processed image: {orig_w}×{orig_h}")

    except Exception as e:
        logger.error(f"Image processing error for user {user_id}: {type(e).__name__}: {e}")
        await status_msg.edit_text(f"❌ خطا در پردازش تصویر:\n{type(e).__name__}")
        user_manager.increment_errors(user_id)
        # Keep error message visible, don't delete
    # On success, result is sent as a new photo message; processing message can be deleted
    # But we'll keep it for now to avoid race conditions


# ─── Unified Photo Handler ─────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Unified photo handler that routes to watermark/logo upload or image processing
    based on user state and processing mode.
    Handles photos sent as "photo" type (compressed by Telegram/Bale).
    """
    user_id = update.effective_user.id
    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode == ProcessingMode.LOGO:
        # Logo mode handling
        if state in (UserState.NO_LOGO, UserState.LOGO_PENDING, UserState.LOGO_INVALID):
            await handle_logo_upload(update, context)
        elif state == UserState.LOGO_READY:
            await handle_image_processing_logo(update, context)
        else:
            await update.message.reply_text("\u0648\u0636\u0639\u06cc\u062a \u0646\u0627\u0645\u0639\u062a\u0628\u0631. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
    else:
        # Watermark mode handling (default)
        if state in (UserState.NO_WATERMARK, UserState.WATERMARK_PENDING, UserState.WATERMARK_INVALID):
            await handle_watermark_upload(update, context)
        elif state == UserState.WATERMARK_READY:
            await handle_image_processing(update, context)
        else:
            await update.message.reply_text("\u0648\u0636\u0639\u06cc\u062a \u0646\u0627\u0645\u0639\u062a\u0628\u0631. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")

# ─── Document Handler (PNG files sent as documents) ────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle document uploads - specifically PNG files sent as documents.
    This is needed because users often send PNGs as documents to preserve quality.
    Routes to appropriate handler based on processing mode.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\u0646\u0634\u0633\u062a \u0634\u0645\u0627 \u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
        return

    document = update.message.document
    mode = user_manager.get_processing_mode(user_id)
    state = user_manager.get_state(user_id)

    # Check if it's a PNG image
    mime_type = document.mime_type
    file_name = document.file_name or ""

    is_png = (
        mime_type == "image/png" or
        file_name.lower().endswith(".png")
    )

    is_image = (
        mime_type.startswith("image/") or
        any(file_name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"])
    )

    # Check file size
    if document.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await update.message.reply_text(f"\u274c \u0641\u0627\u06cc\u0644 \u062e\u06cc\u0644\u06cc \u0628\u0632\u0631\u06af \u0627\u0633\u062a (\u062d\u062f\u0627\u06a9\u062b\u0631 {MAX_FILE_SIZE_MB} \u0645\u06af\u0627\u0628\u0627\u06cc\u062a).")
        user_manager.increment_errors(user_id)
        return

    if mode == ProcessingMode.LOGO:
        # Logo mode
        if state in (UserState.NO_LOGO, UserState.LOGO_PENDING, UserState.LOGO_INVALID):
            # Expecting logo upload - must be PNG
            if not is_png:
                await update.message.reply_text(
                    "\u274c \u0641\u0642\u0637 \u0644\u0648\u06af\u0648 \u0628\u0627\u06cc\u062f \u0641\u0631\u0645\u062a PNG \u0628\u0627\u0634\u062f.\n"
                    "\u0644\u0637\u0641\u0627\u0646\u0647 \u06cc\u06a9 \u0641\u0627\u06cc\u0644 PNG \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
                )
                user_manager.increment_errors(user_id)
                return
            await handle_logo_upload(update, context)
        elif state == UserState.LOGO_READY:
            # Processing image with logo - accept any image format
            if not is_image:
                await update.message.reply_text(
                    "\u274c \u0641\u0642\u0637 \u0639\u06a9\u0633 \u062a\u0635\u0648\u06cc\u0631\u06cc \u067e\u0630\u06cc\u0631\u0641\u062a\u0647 \u0628\u0627\u0634\u062f.\n"
                    "\u0644\u0637\u0641\u0627\u0646\u0647 \u06cc\u06a9 \u0639\u06a9\u0633 (PNG, JPG, WEBP) \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
                )
                user_manager.increment_errors(user_id)
                return
            await handle_image_processing_logo(update, context)
        else:
            await update.message.reply_text("\u0648\u0636\u0639\u06cc\u062a \u0646\u0627\u0645\u0639\u062a\u0628\u0631. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
    else:
        # Watermark mode (default)
        if state in (UserState.NO_WATERMARK, UserState.WATERMARK_PENDING, UserState.WATERMARK_INVALID):
            # Expecting watermark upload - must be PNG
            if not is_png:
                await update.message.reply_text(
                    "\u274c \u0641\u0642\u0637 \u0634\u0645\u0627 \u0676\u0647 \u0641\u0627\u06cc\u0644\u0647\u0627\u06cc **PNG** \u067e\u0634\u062a\u06cc\u0628\u0627\u0646 \u0645\u06cc\u200c\u0628\u0627\u0634\u062f.\n\n"
                    "\u0644\u0637\u0641\u0627\u0646\u0647 \u0648\u0627\u062a\u0631\u0645\u0627\u0631\u06a9 \u062e\u0648\u062f \u0631\u0627 \u0628\u0647 \u0641\u0631\u0645\u062a PNG \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f.\n"
                    "\u0645\u06cc\u062a\u0648\u0627\u0646\u06cc\u062f \u0641\u0627\u06cc\u0644 \u0631\u0627 \u0628\u0647 \u0635\u0648\u0631\u062a \u06cc\u0631 \u0641\u0631\u0633\u062a\u06cc\u0646 \u200c\u0628\u0647 \u0635\u0648\u0631\u062a \u0628\u0641\u0631\u0633\u062a\u06cc\u062f."
                )
                user_manager.increment_errors(user_id)
                return
            await handle_watermark_upload(update, context)
        elif state == UserState.WATERMARK_READY:
            # Processing image with watermark - accept any image format
            if not is_image:
                await update.message.reply_text(
                    "\u274c \u0641\u0642\u0637 \u0639\u06a9\u0633 \u062a\u0635\u0648\u06cc\u0631\u06cc \u067e\u0630\u06cc\u0631\u0641\u062a\u0647 \u0628\u0627\u0634\u062f.\n"
                    "\u0644\u0637\u0641\u0627\u0646\u0647 \u06cc\u06a9 \u0639\u06a9\u0633 (PNG, JPG, WEBP) \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f."
                )
                user_manager.increment_errors(user_id)
                return
            await handle_image_processing_from_document(update, context)
        else:
            await update.message.reply_text("\u0648\u0636\u0639\u06cc\u062a \u0646\u0627\u0645\u0639\u062a\u0628\u0631. /start \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f.")
async def handle_image_processing_from_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user's image sent as document with their watermark."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نشست شما منقضی شده. /start را بزنید.")
        return

    state = user_manager.get_state(user_id)

    if state != UserState.WATERMARK_READY:
        await update.message.reply_text(
            "⚠️ ابتدا باید واترمارک خود را آپلود کنید.\n"
            "فایل PNG واترمارک را ارسال کنید یا /start بزنید."
        )
        return

    document = update.message.document

    # Check if it's an image (PNG, JPEG, etc.)
    mime_type = document.mime_type or ""
    file_name = document.file_name or ""

    is_image = (
        mime_type.startswith("image/") or
        any(file_name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"])
    )

    if not is_image:
        await update.message.reply_text(
            "❌ فقط فایل‌های تصویری پشتیبانی می‌شوند.\n"
            "لطفاً یک عکس (PNG, JPG, WEBP) ارسال کنید."
        )
        user_manager.increment_errors(user_id)
        return

    # Check file size
    if document.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await update.message.reply_text(f"❌ فایل خیلی بزرگ است (حداکثر {MAX_FILE_SIZE_MB} مگابایت).")
        user_manager.increment_errors(user_id)
        return

    # Get user's watermark from provider
    provider = provider_factory.get_provider(user_id)
    watermark = await provider.get_watermark(user_id)

    if watermark is None:
        # Watermark expired or lost
        user_manager.clear_watermark(user_id)
        await update.message.reply_text(
            "⚠️ واترمارک شما منقضی شده یا حذف شده.\n"
            "لطفاً دوباره واترمارک PNG خود را ارسال کنید."
        )
        return

    file_id = document.file_id
    status_msg = await update.message.reply_text("⏳ در حال اعمال واترمارک تمام‌صفحه...")

    try:
        # Download user's image
        file_path = bale_get_file_path(file_id)
        img_bytes = bale_download_file(file_path)

        # Open image
        img = Image.open(BytesIO(img_bytes))
        orig_w, orig_h = img.size

        # Apply watermark (preserved original algorithm)
        result = apply_fullscreen_watermark(img, watermark)

        # Save to bytes
        output = BytesIO()
        result.convert("RGB").save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        output.seek(0)
        result_bytes = output.read()

        # Send result
        bale_send_photo(
            chat_id=chat_id,
            image_bytes=result_bytes,
            caption=f"✅ واترمارک اعمال شد ({orig_w}×{orig_h})"
        )

        # Update stats
        user_manager.increment_processed(user_id)

        logger.info(f"User {user_id} processed image from document: {orig_w}×{orig_h}")

    except Exception as e:
        logger.error(f"Document image processing error for user {user_id}: {type(e).__name__}: {e}")
        await status_msg.edit_text(f"❌ خطا در پردازش تصویر:\n{type(e).__name__}")
        user_manager.increment_errors(user_id)
        # Keep error message visible, don't delete
    # On success, result is sent as a new photo message; processing message can be deleted
    # But we'll keep it for now to avoid race conditions


# ─── Unsupported File Type Handler ──────────────────────────────
async def handle_unsupported_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unsupported file types with a helpful error message."""
    await update.message.reply_text(
        "❌ این نوع فایل پشتیبانی نمی‌شود.\n\n"
        "✅ **فرمت‌های پشتیبانی شده:**\n"
        "• PNG (به عنوان عکس یا فایل)\n"
        "• JPG/JPEG (برای عکس‌های پردازش)\n"
        "• WEBP\n\n"
        "📋 **نحوه استفاده:**\n"
        "1. واترمارک: فایل PNG بفرستید\n"
        "2. عکس‌ها: عکس یا فایل تصویری بفرستید\n\n"
        "برای راهنما /help را بزنید."
    )
    user_manager.increment_errors(update.effective_user.id)


# ─── Background Cleanup Task ───────────────────────────────────
async def periodic_cleanup(app: Application):
    """Periodic cleanup of expired watermarks, temp files, and user sessions."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            # Cleanup expired watermarks
            watermark_cleaned = await provider_factory.cleanup_all_expired()

            # Cleanup expired temp files
            temp_cleaned = temp_manager.cleanup_expired()

            # Cleanup expired user sessions
            session_cleaned = user_manager.cleanup_expired_sessions()

            if watermark_cleaned or temp_cleaned or session_cleaned:
                logger.info(
                    f"Cleanup: {watermark_cleaned} watermarks, "
                    f"{temp_cleaned} temp files, {session_cleaned} sessions"
                )
        except Exception as e:
            logger.error(f"Periodic cleanup error: {e}")


# ─── Startup/Shutdown ──────────────────────────────────────────
async def on_startup(app: Application):
    """Initialize components on startup."""
    global provider_factory, temp_manager, user_manager

    logger.info("Initializing bot components...")

    # Initialize provider factory (temporary provider for all users now)
    provider_factory = WatermarkProviderFactory()

    # Initialize temp file manager
    temp_manager = get_temp_file_manager(
        ttl_seconds=TEMP_FILE_TTL_SECONDS,
        cleanup_interval=CLEANUP_INTERVAL_SECONDS,
        max_file_size_mb=MAX_FILE_SIZE_MB
    )

    # Initialize user manager
    user_manager = get_user_manager(
        inactivity_timeout=SESSION_TIMEOUT_SECONDS
    )

    # Start background cleanup task
    asyncio.create_task(periodic_cleanup(app))

    logger.info("Bot started successfully!")


async def on_shutdown(app: Application):
    """Cleanup on shutdown."""
    logger.info("Shutting down...")
    shutdown_temp_file_manager()
    logger.info("Shutdown complete.")


# ─── Main Entry Point ──────────────────────────────────────────
def main():
    """Main entry point."""
    app = (
        Application.builder()
        .token(TOKEN)
        .base_url(BASE_URL)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("change", cmd_change))
    app.add_handler(CommandHandler("remove", cmd_remove))

    # Mode selection commands
    app.add_handler(CommandHandler("watermark", cmd_watermark))
    app.add_handler(CommandHandler("logo", cmd_logo))
    app.add_handler(CommandHandler("mode", cmd_mode))

    # Logo mode commands
    app.add_handler(CommandHandler("changelogo", cmd_changelogo))
    app.add_handler(CommandHandler("changeposition", cmd_changeposition))
    app.add_handler(CommandHandler("changesize", cmd_changesize))

    # Callback query handlers for inline keyboards
    app.add_handler(CallbackQueryHandler(handle_logo_position_selection, pattern=r"^logo_pos:"))
    app.add_handler(CallbackQueryHandler(handle_logo_size_selection, pattern=r"^logo_size:"))

    # Photo handler (handles both watermark/logo upload and image processing)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Document handler for PNG files sent as documents (preserves quality)
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))

    # Fallback handler for unsupported document types
    app.add_handler(MessageHandler(filters.Document.ALL, handle_unsupported_file))

    print("[BOT] Watermark Bot started successfully.")
    print("   - Temporary watermarks for all users (Free tier)")
    print("   - Auto cleanup every 60 seconds")
    print("   - Session timeout: 300 seconds inactivity")
    print("   - Press Ctrl+C to exit.")
    print()

    app.run_polling()


if __name__ == "__main__":
    import time  # For status command
    main()