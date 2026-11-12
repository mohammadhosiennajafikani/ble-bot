with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find handle_photo function
start_photo = None
for i, line in enumerate(lines):
    if 'async def handle_photo' in line and 'Unified photo handler' in lines[i+2]:
        start_photo = i
        break

print(f"handle_photo starts at line {start_photo+1}")

# Find end of handle_photo function
end_photo = None
for i in range(start_photo + 1, len(lines)):
    if lines[i].strip().startswith('async def ') and 'handle_document' in lines[i]:
        end_photo = i
        break

print(f"handle_photo ends at line {end_photo}")

# New handle_photo function
new_photo = '''async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text("\\u0648\\u0636\\u0639\\u06cc\\u062a \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
    else:
        # Watermark mode handling (default)
        if state in (UserState.NO_WATERMARK, UserState.WATERMARK_PENDING, UserState.WATERMARK_INVALID):
            await handle_watermark_upload(update, context)
        elif state == UserState.WATERMARK_READY:
            await handle_image_processing(update, context)
        else:
            await update.message.reply_text("\\u0648\\u0636\\u0639\\u06cc\\u062a \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
'''

# Replace the function
new_lines = lines[:start_photo] + [new_photo + '\n'] + lines[end_photo:]

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('handle_photo updated successfully')