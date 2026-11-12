with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find handle_document function
start_doc = None
for i, line in enumerate(lines):
    if 'async def handle_document' in line and 'Handle document uploads' in lines[i+2]:
        start_doc = i
        break

print(f"handle_document starts at line {start_doc+1}")

# Find end of handle_document function (start of next function)
end_doc = None
for i in range(start_doc + 1, len(lines)):
    if lines[i].strip().startswith('async def ') and 'handle_image_processing_from_document' in lines[i]:
        end_doc = i
        break

print(f"handle_document ends at line {end_doc}")

# New handle_document function
new_doc = '''# ─── Document Handler (PNG files sent as documents) ────────────────
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
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
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
        await update.message.reply_text(f"\\u274c \\u0641\\u0627\\u06cc\\u0644 \\u062e\\u06cc\\u0644\\u06cc \\u0628\\u0632\\u0631\\u06af \\u0627\\u0633\\u062a (\\u062d\\u062f\\u0627\\u06a9\\u062b\\u0631 {MAX_FILE_SIZE_MB} \\u0645\\u06af\\u0627\\u0628\\u0627\\u06cc\\u062a).")
        user_manager.increment_errors(user_id)
        return

    if mode == ProcessingMode.LOGO:
        # Logo mode
        if state in (UserState.NO_LOGO, UserState.LOGO_PENDING, UserState.LOGO_INVALID):
            # Expecting logo upload - must be PNG
            if not is_png:
                await update.message.reply_text(
                    "\\u274c \\u0641\\u0642\\u0637 \\u0644\\u0648\\u06af\\u0648 \\u0628\\u0627\\u06cc\\u062f \\u0641\\u0631\\u0645\\u062a PNG \\u0628\\u0627\\u0634\\u062f.\\n"
                    "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u06cc\\u06a9 \\u0641\\u0627\\u06cc\\u0644 PNG \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
                )
                user_manager.increment_errors(user_id)
                return
            await handle_logo_upload(update, context)
        elif state == UserState.LOGO_READY:
            # Processing image with logo - accept any image format
            if not is_image:
                await update.message.reply_text(
                    "\\u274c \\u0641\\u0642\\u0637 \\u0639\\u06a9\\u0633 \\u062a\\u0635\\u0648\\u06cc\\u0631\\u06cc \\u067e\\u0630\\u06cc\\u0631\\u0641\\u062a\\u0647 \\u0628\\u0627\\u0634\\u062f.\\n"
                    "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u06cc\\u06a9 \\u0639\\u06a9\\u0633 (PNG, JPG, WEBP) \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
                )
                user_manager.increment_errors(user_id)
                return
            await handle_image_processing_logo(update, context)
        else:
            await update.message.reply_text("\\u0648\\u0636\\u0639\\u06cc\\u062a \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
    else:
        # Watermark mode (default)
        if state in (UserState.NO_WATERMARK, UserState.WATERMARK_PENDING, UserState.WATERMARK_INVALID):
            # Expecting watermark upload - must be PNG
            if not is_png:
                await update.message.reply_text(
                    "\\u274c \\u0641\\u0642\\u0637 \\u0634\\u0645\\u0627 \\u0676\\u0647 \\u0641\\u0627\\u06cc\\u0644\\u0647\\u0627\\u06cc **PNG** \\u067e\\u0634\\u062a\\u06cc\\u0628\\u0627\\u0646 \\u0645\\u06cc\\u200c\\u0628\\u0627\\u0634\\u062f.\\n\\n"
                    "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u0648\\u0627\\u062a\\u0631\\u0645\\u0627\\u0631\\u06a9 \\u062e\\u0648\\u062f \\u0631\\u0627 \\u0628\\u0647 \\u0641\\u0631\\u0645\\u062a PNG \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f.\\n"
                    "\\u0645\\u06cc\\u062a\\u0648\\u0627\\u0646\\u06cc\\u062f \\u0641\\u0627\\u06cc\\u0644 \\u0631\\u0627 \\u0628\\u0647 \\u0635\\u0648\\u0631\\u062a \\u06cc\\u0631 \\u0641\\u0631\\u0633\\u062a\\u06cc\\u0646 \\u200c\\u0628\\u0647 \\u0635\\u0648\\u0631\\u062a \\u0628\\u0641\\u0631\\u0633\\u062a\\u06cc\\u062f."
                )
                user_manager.increment_errors(user_id)
                return
            await handle_watermark_upload(update, context)
        elif state == UserState.WATERMARK_READY:
            # Processing image with watermark - accept any image format
            if not is_image:
                await update.message.reply_text(
                    "\\u274c \\u0641\\u0642\\u0637 \\u0639\\u06a9\\u0633 \\u062a\\u0635\\u0648\\u06cc\\u0631\\u06cc \\u067e\\u0630\\u06cc\\u0631\\u0641\\u062a\\u0647 \\u0628\\u0627\\u0634\\u062f.\\n"
                    "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u06cc\\u06a9 \\u0639\\u06a9\\u0633 (PNG, JPG, WEBP) \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
                )
                user_manager.increment_errors(user_id)
                return
            await handle_image_processing_from_document(update, context)
        else:
            await update.message.reply_text("\\u0648\\u0636\\u0639\\u06cc\\u062a \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")'''

# Replace the function
new_lines = lines[:start_doc] + [new_doc + '\n'] + lines[end_doc:]

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('handle_document updated successfully')