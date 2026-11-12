import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find cmd_status function and replace it
old_status = '''async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show current watermark status."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نشست شما منقضی شده. /start را بزنید.")
        return

    state = user_manager.get_state(user_id)

    if state == UserState.WATERMARK_READY:
        info = user_manager.get_watermark_info(user_id)
        stats = user_manager.get_stats(user_id)
        size_str = f"{info['size'][0]}×{info['size'][1]}" if info and info['size'] else "نامشخص"
        await update.message.reply_text(
            f"\U0001f4ca وضعیت شما:\\n\\n"
            f"✅ واترمارک: فعال ({info['format'].upper()}, {size_str})\\n"
            f"\U0001f5bc عکسهای پرداز شده: {stats['images_processed']}\\n"
            f"❌ خطاها: {stats['errors_count']}\\n"
            f"⏱ آخرین فعالیت: {int(time.time() - stats['last_activity'])} ثانیه پیش"
        )
    elif state == UserState.WATERMARK_INVALID:
        await update.message.reply_text(
            "⚠️ واترمارک قبلی معتبر معتبر نبود.\\n"
            "لطفان یک فایل PNG معتبر ارسال کنید."
        )
    else:
        await update.message.reply_text(
            "ℹ️ هیچ واترمارکی تنظیم نشده.\\n"
            "فایل PNG واترمارک خود را ارسال کنید یا /start بزنید."
        )'''

new_status = '''async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show current status based on mode."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نشست شما منقضی شده. /start را بزنید.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)
    stats = user_manager.get_stats(user_id)

    if mode == ProcessingMode.WATERMARK:
        if state == UserState.WATERMARK_READY:
            info = user_manager.get_watermark_info(user_id)
            size_str = f"{info['size'][0]}×{info['size'][1]}" if info and info['size'] else "نامشخص"
            await update.message.reply_text(
                f"\U0001f4ca وضعیت شما:\\n\\n"
                f"\U0001f539 حالت: واترمارک\\n"
                f"✅ واترمارک: فعال ({info['format'].upper()}, {size_str})\\n"
                f"\U0001f5bc عکسهای پرداز شده: {stats['images_processed']}\\n"
                f"❌ خطاها: {stats['errors_count']}\\n"
                f"⏱ آخرین فعالیت: {int(time.time() - stats['last_activity'])} ثانیه پیش"
            )
        elif state == UserState.WATERMARK_INVALID:
            await update.message.reply_text(
                "⚠️ واترمارک قبلی معتبر معتبر نبود.\\n"
                "لطفان یک فایل PNG معتبر ارسال کنید."
            )
        else:
            await update.message.reply_text(
                "ℹ️ هیچ واترمارکی تنظیم نشده.\\n"
                "فایل PNG واترمارک خود را ارسال کنید یا /watermark بزنید."
            )
    elif mode == ProcessingMode.LOGO:
        if state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
            info = user_manager.get_logo_info(user_id)
            if info:
                size_str = f"{info['size'][0]}×{info['size'][1]}" if info and info['size'] else "نامشخص"
                pos_str = info['position'] or "تنظیم نشده"
                size_preset_str = info['size_preset'] or "تنظیم نشده"
                await update.message.reply_text(
                    f"\U0001f4ca وضعیت شما:\\n\\n"
                    f"\U0001f539 حالت: لوگو\\n"
                    f"✅ لوگو: فعال ({info['format'].upper()}, {size_str})\\n"
                    f"\U0001f4cd موقعیت: {pos_str}\\n"
                    f"\U0001f4cf اندازه: {size_preset_str}\\n"
                    f"\U0001f5bc عکسهای پرداز شده: {stats['images_processed']}\\n"
                    f"❌ خطاها: {stats['errors_count']}\\n"
                    f"⏱ آخرین فعالیت: {int(time.time() - stats['last_activity'])} ثانیه پیش"
                )
            else:
                await update.message.reply_text(
                    "ℹ️ لوگو تنظیم نشده.\\n"
                    "فایل PNG لوگو خود را ارسال کنید یا /logo بزنید."
                )
        elif state == UserState.LOGO_INVALID:
            await update.message.reply_text(
                "⚠️ لوگو قبلی معتبر معتبر نبود.\\n"
                "لطفان یک فایل PNG معتبر ارسال کنید."
            )
        else:
            await update.message.reply_text(
                "ℹ️ هیچ لوگوی تنظیم نشده.\\n"
                "فایل PNG لوگو خود را ارسال کنید یا /logo بزنید."
            )
    else:
        await update.message.reply_text(
            "ℹ️ حالت انتخاب نشده.\\n"
            "/start را بزنید تا حالت را انتخاب کنید."
        )'''

if old_status in content:
    content = content.replace(old_status, new_status)
    with open('bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('cmd_status updated successfully')
else:
    print('Could not find old cmd_status function')
    # Let's search for it
    idx = content.find('async def cmd_status')
    if idx >= 0:
        print(f'Found at index {idx}')
        print(content[idx:idx+500])