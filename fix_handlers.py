with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update handle_photo function
old_handle_photo = '''async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Unified photo handler that routes to watermark upload or image processing
    based on user state.
    Handles photos sent as "photo" type (compressed by Telegram/Bale).
    """
    user_id = update.effective_user.id
    state = user_manager.get_state(user_id)

    if state in (UserState.NO_WATERMARK, UserState.WATERMARK_PENDING, UserState.WATERMARK_INVALID):
        await handle_watermark_upload(update, context)
    elif state == UserState.WATERMARK_READY:
        await handle_image_processing(update, context)
    else:
        await update.message.reply_text("\\u0648\\u0636\\u0639\\u06cc\\u062a \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")'''

new_handle_photo = '''async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text("\\u0648\\u0636\\u0639\\u06cc\\u062a \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")'''

if old_handle_photo in content:
    content = content.replace(old_handle_photo, new_handle_photo)
    print('handle_photo updated')
else:
    print('Could not find old handle_photo')

# Update handle_document function
old_handle_document = '''# ─── Document Handler (PNG files sent as documents) ────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle document uploads - specifically PNG files sent as documents.
    This is needed because users often send PNGs as documents to preserve quality.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    document = update.message.document

    # Check if it's a PNG image
    mime_type = document.mime_type
    file_name = document.file_name or ""

    is_png = (
        mime_type == "image/png" or
        file_name.lower().endswith(".png")
    )

    if not is_png:
        await update.message.reply_text(
            "\\u274c \\u0641\\u0642\\u0637 \\u0634\\u0645\\u0627 \\u0676\\u0647 \\u0641\\u0627\\u06cc\\u0644\\u0647\\u0627\\u06cc **PNG** \\u067e\\u0634\\u062a\\u06cc\\u0628\\u0627\\u0646 \\u0645\\u06cc\\u200c\\u0628\\u0627\\u0634\\u062f.\\n\\n"
            "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u0648\\u0627\\u062a\\u0631\\u0645\\u0627\\u0631\\u06a9 \\u062e\\u0648\\u062f \\u0631\\u0627 \\u0628\\u0647 \\u0641\\u0631\\u0645\\u062a PNG \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f.\\n"
            "\\u0645\\u06cc\\u062a\\u0648\\u0627\\u0646\\u06cc\\u062f \\u0641\\u0627\\u06cc\\u0644 \\u0631\\u0627 \\u0628\\u0647 \\u0635\\u0648\\u0631\\u062a \\u06cc\\u0631 \\u0641\\u0631\\u0633\\u062a\\u06cc\\u0646 \\u200c\\u0628\\u0647 \\u0635\\u0648\\u0631\\u062a \\u0628\\u0641\\u0631\\u0633\\u062a\\u06cc\\u062f."
        )
        user_manager.increment_errors(user_id)
        return

    # Check file size
    if document.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await update.message.reply_text(f"\\u274c \\u0641\\u0627\\u06cc\\u0644 \\u062e\\u06cc\\u0644\\u06cc \\u0628\\u0632\\u0631\\u06af \\u0627\\u0633\\u062a (\\u062d\\u062f\\u0627\\u06a9\\u062b\\u0631 {MAX_FILE_SIZE_MB} \\u0645\\u06af\\u0627\\u0628\\u0627\\u06cc\\u062a).")
        user_manager.increment_errors(user_id)
        return

    state = user_manager.get_state(user_id)

    # Only accept watermark upload if user is in pending state or has no watermark
    if state not in (UserState.NO_WATERMARK, UserState.WATERMARK_PENDING, UserState.WATERMARK_INVALID):
        # User has active watermark - this might be an image to process
        await handle_image_processing_from_document(update, context)
        return'''

new_handle_document = '''# ─── Document Handler (PNG files sent as documents) ────────────────
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

if old_handle_document in content:
    content = content.replace(old_handle_document, new_handle_document)
    print('handle_document updated')
else:
    print('Could not find old handle_document')

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')