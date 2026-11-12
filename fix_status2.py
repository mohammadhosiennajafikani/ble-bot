with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the cmd_status function (starts around line 418, ends around line 448)
# We'll replace lines 418-448 (0-indexed: 417-447)

new_function = '''async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show current status based on mode."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)
    stats = user_manager.get_stats(user_id)

    if mode == ProcessingMode.WATERMARK:
        if state == UserState.WATERMARK_READY:
            info = user_manager.get_watermark_info(user_id)
            size_str = f"{info['size'][0]}\\u00d7{info['size'][1]}" if info and info['size'] else "\\u0646\\u0627\\u0645\\u0634\\u062e\\u0635"
            await update.message.reply_text(
                f"\\U0001f4ca \\u0648\\u0636\\u0639\\u06cc\\u062a \\u0634\\u0645\\u0627:\\n\\n"
                f"\\U0001f539 \\u062d\\u0627\\u0644\\u062a: \\u0648\\u0627\\u062a\\u0645\\u0631\\u0627\\u06a9\\n"
                f"\\u2705 \\u0648\\u0627\\u062a\\u0631\\u0645\\u0627\\u0631\\u06a9: \\u0641\\u0639\\u0627\\u0644 ({info['format'].upper()}, {size_str})\\n"
                f"\\U0001f5bc \\u0639\\u06a9\\u0633\\u0647\\u0627\\u06cc \\u067e\\u0631\\u062f\\u0627\\u0632 \\u0634\\u062f\\u0647: {stats['images_processed']}\\n"
                f"\\u274c \\u062e\\u0637\\u0627\\u0647\\u0627: {stats['errors_count']}\\n"
                f"\\u23f1 \\u0622\\u062e\\u0631\\u06cc\\u0646 \\u0641\\u0639\\u0627\\u0644\\u06cc\\u062a: {int(__import__('time').time() - stats['last_activity'])} \\u062b\\u0627\\u0646\\u06cc\\u0647 \\u067e\\u06cc\\u0634"
            )
        elif state == UserState.WATERMARK_INVALID:
            await update.message.reply_text(
                "\\u26a0\\ufe0f \\u0648\\u0627\\u062a\\u0631\\u0645\\u0627\\u0631\\u06a9 \\u0642\\u0628\\u0644\\u06cc \\u0645\\u0639\\u062a\\u0628\\u0631 \\u0645\\u0639\\u062a\\u0628\\u0631 \\u0646\\u0628\\u0648\\u062f.\\n"
                "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u06cc\\u06a9 \\u0641\\u0627\\u06cc\\u0644 PNG \\u0645\\u0639\\u062a\\u0628\\u0631 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
            )
        else:
            await update.message.reply_text(
                "\\u2139\\ufe0f \\u0647\\u06cc\\u0686 \\u0648\\u0627\\u062a\\u0645\\u0631\\u0627\\u06a9\\u06cc \\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0646\\u0634\\u062f\\u0647.\\n"
                "\\u0641\\u0627\\u06cc\\u0644 PNG \\u0648\\u0627\\u062a\\u0645\\u0631\\u0627\\u06a9 \\u062e\\u0648\\u062f \\u0631\\u0627 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f \\u06cc\\u0627 /watermark \\u0628\\u0632\\u0646\\u06cc\\u062f."
            )
    elif mode == ProcessingMode.LOGO:
        if state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
            info = user_manager.get_logo_info(user_id)
            if info:
                size_str = f"{info['size'][0]}\\u00d7{info['size'][1]}" if info and info['size'] else "\\u0646\\u0627\\u0645\\u0634\\u062e\\u0635"
                pos_str = info['position'] or "\\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0646\\u0634\\u062f\\u0647"
                size_preset_str = info['size_preset'] or "\\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0646\\u0634\\u062f\\u0647"
                await update.message.reply_text(
                    f"\\U0001f4ca \\u0648\\u0636\\u0639\\u06cc\\u062a \\u0634\\u0645\\u0627:\\n\\n"
                    f"\\U0001f539 \\u062d\\u0627\\u0644\\u062a: \\u0644\\u0648\\u06af\\u0648\\n"
                    f"\\u2705 \\u0644\\u0648\\u06af\\u0648: \\u0641\\u0639\\u0627\\u0644 ({info['format'].upper()}, {size_str})\\n"
                    f"\\U0001f4cd \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a: {pos_str}\\n"
                    f"\\U0001f4cf \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647: {size_preset_str}\\n"
                    f"\\U0001f5bc \\u0639\\u06a9\\u0633\\u0647\\u0627\\u06cc \\u067e\\u0631\\u062f\\u0627\\u0632 \\u0634\\u062f\\u0647: {stats['images_processed']}\\n"
                    f"\\u274c \\u062e\\u0637\\u0627\\u0647\\u0627: {stats['errors_count']}\\n"
                    f"\\u23f1 \\u0622\\u062e\\u0631\\u06cc\\u0646 \\u0641\\u0639\\u0627\\u0644\\u06cc\\u062a: {int(__import__('time').time() - stats['last_activity'])} \\u062b\\u0627\\u0646\\u06cc\\u0647 \\u067e\\u06cc\\u0634"
                )
            else:
                await update.message.reply_text(
                    "\\u2139\\ufe0f \\u0644\\u0648\\u06af\\u0648 \\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0646\\u0634\\u062f\\u0647.\\n"
                    "\\u0641\\u0627\\u06cc\\u0644 PNG \\u0644\\u0648\\u06af\\u0648 \\u062e\\u0648\\u062f \\u0631\\u0627 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062d \\u06cc\\u0627 /logo \\u0628\\u0632\\u0646\\u06cc\\u062f."
                )
        elif state == UserState.LOGO_INVALID:
            await update.message.reply_text(
                "\\u26a0\\ufe0f \\u0644\\u0648\\u06af\\u0648 \\u0642\\u0628\\u0644\\u06cc \\u0645\\u0639\\u062a\\u0628\\u0631 \\u0645\\u0639\\u062a\\u0628\\u0631 \\u0646\\u0628\\u0648\\u062f.\\n"
                "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u06cc\\u06a9 \\u0641\\u0627\\u06cc\\u0644 PNG \\u0645\\u0639\\u062a\\u0628\\u0631 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
            )
        else:
            await update.message.reply_text(
                "\\u2139\\ufe0f \\u0647\\u06cc\\u0686 \\u0644\\u0648\\u06af\\u0648\\u06cc \\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0646\\u0634\\u062f\\u0647.\\n"
                "\\u0641\\u0627\\u06cc\\u0644 PNG \\u0644\\u0648\\u06af\\u0648 \\u062e\\u0648\\u062f \\u0631\\u0627 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f \\u06cc\\u0627 /logo \\u0628\\u0632\\u0646\\u06cc\\u062f."
            )
    else:
        await update.message.reply_text(
            "\\u2139\\ufe0f \\u062d\\u0627\\u0644\\u062a \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u0646\\u0634\\u062f\\u0647.\\n"
            "/start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f \\u062a\\u0627 \\u062d\\u0627\\u0644\\u062a \\u0631\\u0627 \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u06a9\\u0646\\u06cc\\u062f."
        )
'''

# Replace lines 417-447 (0-indexed)
# Line numbers in file are 1-indexed, so 418-448
new_lines = lines[:417] + [new_function + '\n'] + lines[448:]

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('cmd_status updated successfully')