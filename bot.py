import os
import json
import re
from io import BytesIO
import base64

import requests
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler, filters, ContextTypes
)
from PIL import Image, ImageOps
from playwright.async_api import async_playwright

# ─── تنظیمات بله ────────────────────────────────
TOKEN = "451053587:JFrlO7J-1jwlJtvy9n5jffSG1ApRQ6tzSf8"
BASE_URL = "https://tapi.bale.ai/bot"
FILE_URL = "https://tapi.bale.ai/file/bot"

FRAMES_DIR = "frames"
STATE_FILE = "state.json"
TEMPLATE_HTML = "tweet_template.html"
JPEG_QUALITY = 95

DEFAULT_CONFIG = {
    "profile_name": "بسیج دانشجویی دانشگاه خواجه نصیر",
    "handle": "@BorhanKntu",
    "avatar_url": "https://api.dicebear.com/7.x/identicon/png?seed=kntu",
    "default_bg_url": "https://picsum.photos/951/727"
}

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

# ─── ماژول ۱: واترمارک تمام‌صفحه ─────────────────
def apply_fullscreen_watermark(img: Image.Image, watermark_path: str) -> Image.Image:
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img = img.convert("RGBA")
    W, H = img.size
    wm = Image.open(watermark_path).convert("RGBA")
    wm_resized = wm.resize((W, H), getattr(Image, "Resampling", Image).LANCZOS)
    return Image.alpha_composite(img, wm_resized)

# ─── ماژول ۲: تولید توییت‌نوشت فیگما ──────────────
async def render_tweet_card(tweet_text: str, bg_bytes: bytes = None, profile_name: str = None, handle: str = None) -> bytes:
    with open(TEMPLATE_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    # هشتگ‌های آبی‌رنگ
    escaped = tweet_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body_html = re.sub(r'(#[\w_\u0600-\u06FF]+)', r'<span class="hashtag">\1</span>', escaped).replace("\n", "<br/>")

    bg_url = DEFAULT_CONFIG["default_bg_url"]
    if bg_bytes:
        bg_url = f"data:image/jpeg;base64,{base64.b64encode(bg_bytes).decode('utf-8')}"

    html = html.replace("{{bg_image_url}}", bg_url)
    html = html.replace("{{avatar_url}}", DEFAULT_CONFIG["avatar_url"])
    html = html.replace("{{profile_name}}", profile_name or DEFAULT_CONFIG["profile_name"])
    html = html.replace("{{handle}}", handle or DEFAULT_CONFIG["handle"])
    html = html.replace("{{body_html}}", body_html)
    html = re.sub(r'\{\{#has_media\}\}.*?\{\{/has_media\}\}', '', html, flags=re.DOTALL)

    # رندر با Playwright در ابعاد ۹۵۱ در ۷۲۷
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page(viewport={"width": 951, "height": 727})
        await page.set_content(html, wait_until="networkidle")
        screenshot = await page.screenshot(type="jpeg", quality=JPEG_QUALITY)
        await browser.close()
        return screenshot

# ─── توابع بله ──────────────────────────────────
def bale_get_file_path(file_id):
    resp = requests.post(f"{BASE_URL}{TOKEN}/getFile", json={"file_id": file_id}, timeout=60).json()
    return resp["result"]["file_path"]

def bale_download_file(file_path):
    return requests.get(f"{FILE_URL}{TOKEN}/{file_path}", timeout=120).content

def bale_send_photo(chat_id, image_bytes, caption=""):
    files = {"photo": ("result.jpg", image_bytes, "image/jpeg")}
    return requests.post(f"{BASE_URL}{TOKEN}/sendPhoto", data={"chat_id": chat_id, "caption": caption}, files=files, timeout=120).json()

# ─── دستورات ربات ───────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    state = load_state()
    mode = state.get(chat_id, {}).get("mode", "watermark")

    text = "سلام! 👋 به ربات چندکاره خوش آمدید.\n\n"
    text += f"📌 **حالت فعلی شما:** `{mode}`\n\n"
    text += "⚙️ **تغییر حالت کاربری:**\n"
    text += "• `/mode watermark` → حالت واترمارک تمام‌صفحه روی عکس\n"
    text += "• `/mode tweet` → حالت تولید کارت توییت (فیگما)\n\n"
    text += "📝 **ساخت توییت‌نوشت:**\n"
    text += "کافیست دستور زیر را بزنید:\n"
    text += "`/tweet متن توییت شما با #هشتگ`\n"
    text += "یا یک عکس بفرستید و در کپشن آن متن توییت را بنویسید تا پس‌زمینه کارت شود!"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in ("watermark", "tweet"):
        await update.message.reply_text("فرمت صحیح: `/mode watermark` یا `/mode tweet`", parse_mode="Markdown")
        return
    chosen = context.args[0].lower()
    state = load_state()
    chat_id = str(update.effective_chat.id)
    state.setdefault(chat_id, {})["mode"] = chosen
    save_state(state)
    name = "واترمارک تمام‌صفحه" if chosen == "watermark" else "توییت‌نوشت فیگما"
    await update.message.reply_text(f"✅ حالت ربات به «{name}» تغییر یافت.")

async def cmd_tweet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("متن توییت را وارد کنید. مثال:\n`/tweet متن توییت...`", parse_mode="Markdown")
        return
    text = " ".join(context.args)
    msg = await update.message.reply_text("⏳ در حال طراحی کارت توییت فیگما...")
    try:
        card = await render_tweet_card(text)
        bale_send_photo(update.effective_chat.id, card, caption="✨ کارت توییت آماده شد!")
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")
    finally:
        try: await msg.delete()
        except: pass

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    mode = load_state().get(chat_id, {}).get("mode", "watermark")

    photo = update.message.photo[-1]
    file_path = bale_get_file_path(photo.file_id)
    img_bytes = bale_download_file(file_path)
    caption = update.message.caption or ""

    if mode == "tweet":
        # اگر در حالت توییت بود، عکس ارسالی پس‌زمینه کارت می‌شود
        tweet_text = caption if caption else "توییت‌نوشت خودکار"
        msg = await update.message.reply_text("⏳ در حال رندر کارت توییت با این عکس پس‌زمینه...")
        try:
            card = await render_tweet_card(tweet_text, bg_bytes=img_bytes)
            bale_send_photo(update.effective_chat.id, card, caption="✨ کارت توییت آماده شد!")
        except Exception as e:
            await update.message.reply_text(f"خطا: {e}")
        finally:
            try: await msg.delete()
            except: pass
        return

    # حالت واترمارک:
    frames = [f for f in os.listdir(FRAMES_DIR) if f.lower().endswith(".png")] if os.path.exists(FRAMES_DIR) else []
    if not frames:
        await update.message.reply_text("هیچ واترمارکی در پوشه frames نیست!")
        return

    msg = await update.message.reply_text("⏳ در حال اعمال واترمارک تمام‌صفحه...")
    try:
        img = Image.open(BytesIO(img_bytes))
        result = apply_fullscreen_watermark(img, os.path.join(FRAMES_DIR, frames[0]))
        out = BytesIO()
        result.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY)
        out.seek(0)
        bale_send_photo(update.effective_chat.id, out.read(), caption=f"واترمارک: {frames[0]}")
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")
    finally:
        try: await msg.delete()
        except: pass

def main():
    app = Application.builder().token(TOKEN).base_url(BASE_URL).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("tweet", cmd_tweet))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("ربات چندکاره بله (واترمارک + توییت‌نوشت فیگما) روشن شد.")
    app.run_polling()

if __name__ == "__main__":
    main()