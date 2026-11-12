with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the location after cmd_mode function
marker = '''async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mode command - show mode selection."""
    await show_mode_selection(update, context)


# ─── Photo Handler (Watermark Upload)'''

new_handlers = '''async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mode command - show mode selection."""
    await show_mode_selection(update, context)


# ─── Logo Mode Command Handlers ───────────────────────────────────
async def cmd_changelogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /changelogo command - prompt for new logo."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO:
        await update.message.reply_text(
            "\\u0634\\u0645\\u0627 \\u062f\\u0631 \\u062d\\u0627\\u0644\\u062a \\u0648\\u0627\\u062a\\u0645\\u0631\\u0627\\u06a9 \\u0647\\u0633\\u062a\\u06cc\\u062f. \\u0628\\u0631\\u0627\\u06cc \\u062a\\u063a\\u06cc\\u0631 \\u0644\\u0648\\u06af\\u0648, \\u0627\\u0648\\u0644\\u06cc\\u0646 /logo \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f."
        )
        return

    if state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await update.message.reply_text(
            "\\U0001f504 \\u0628\\u0631\\u0627\\u06cc \\u062a\\u063a\\u06cc\\u0631 \\u0644\\u0648\\u06af\\u0648, \\u0641\\u0627\\u06cc\\u0644 PNG \\u062c\\u062f\\u06cc\\u062f \\u0631\\u0627 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f.\\n"
            "\\u0644\\u0648\\u06af\\u0648 \\u0642\\u0628\\u0644\\u06cc \\u062c\\u0627\\u06cc\\u06af\\u0632\\u06cc\\u0646 \\u062e\\u0648\\u0627\\u0647\\u062f \\u062c\\u0627\\u06cc\\u06af\\u0632\\u06cc\\u0646 \\u062e\\u0648\\u0627\\u0647\\u062f \\u0634\\u062f.\\n"
            "\\u0628\\u0639\\u062f \\u0627\\u0632 \\u0627\\u0631\\u0633\\u0627\\u0644, \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u0648 \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u0628\\u0627\\u06cc\\u062f \\u0628\\u0631\\u0627\\u06cc \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628."
        )
    else:
        await update.message.reply_text(
            "\\u0634\\u0645\\u0627 \\u0644\\u0648\\u06af\\u0648 \\u0641\\u0639\\u0627\\u0644\\u06cc \\u0646\\u062f\\u0627\\u0631\\u06cc\\u062f. \\u0641\\u0627\\u06cc\\u0644 PNG \\u0644\\u0648\\u06af\\u0648 \\u062e\\u0648\\u062f \\u0631\\u0627 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
        )

    # Clear old logo and set state to expecting logo
    user_manager.clear_logo(user_id)
    user_manager.set_state(user_id, UserState.LOGO_PENDING)


async def cmd_changeposition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /changeposition command - show position selection keyboard."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO:
        await update.message.reply_text(
            "\\u0634\\u0645\\u0627 \\u062f\\u0631 \\u062d\\u0627\\u0644\\u062a \\u0648\\u0627\\u062a\\u0645\\u0631\\u0627\\u06a9 \\u0647\\u0633\\u062a\\u06cc\\u062f. \\u0628\\u0631\\u0627\\u06cc \\u062a\\u063a\\u06cc\\u0631 \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u0644\\u0648\\u06af\\u0648, \\u0627\\u0648\\u0644\\u06cc\\u0646 /logo \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f."
        )
        return

    if state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await update.message.reply_text(
            "\\u0647\\u06cc\\u0686 \\u0644\\u0648\\u06af\\u0648\\u06cc \\u0628\\u0631\\u0627\\u06cc \\u062a\\u063a\\u06cc\\u0631 \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u0648\\u062c\\u0648\\u062f \\u0646\\u062f\\u0627\\u0631\\u062f. \\u0644\\u0648\\u06af\\u0648 \\u0631\\u0627 \\u0627\\u0648\\u0644 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
        )
        return

    # Show inline keyboard for position selection
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("\\u067e\\u0627\\u06cc\\u06cc\\u0646 \\u0686\\u067e", callback_data="logo_pos:bottom_left"),
            InlineKeyboardButton("\\u067e\\u0627\\u06cc\\u06cc\\u0646 \\u0648\\u0633\\u0637", callback_data="logo_pos:bottom_center"),
            InlineKeyboardButton("\\u067e\\u0627\\u06cc\\u06cc\\u0646 \\u0631\\u0627\\u0633\\u062a", callback_data="logo_pos:bottom_right"),
        ],
        [
            InlineKeyboardButton("\\u0628\\u0627\\u0644\\u0627 \\u0686\\u067e", callback_data="logo_pos:top_left"),
            InlineKeyboardButton("\\u0628\\u0627\\u0644\\u0627 \\u0648\\u0633\\u0637", callback_data="logo_pos:top_center"),
            InlineKeyboardButton("\\u0628\\u0627\\u0644\\u0627 \\u0631\\u0627\\u0633\\u062a", callback_data="logo_pos:top_right"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "\\U0001f4cd \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u0644\\u0648\\u06af\\u0648 \\u0631\\u0627 \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u06a9\\u0646\\u06cc\\u062f:\\n\\n"
        "\\u2022 \\u067e\\u0627\\u06cc\\u06cc\\u0646 \\u0686\\u067e (Bottom Left)\\n"
        "\\u2022 \\u067e\\u0627\\u06cc\\u06cc\\u0646 \\u0648\\u0633\\u0637 (Bottom Center)\\n"
        "\\u2022 \\u067e\\u0627\\u06cc\\u06cc\\u0646 \\u0631\\u0627\\u0633\\u062a (Bottom Right)\\n"
        "\\u2022 \\u0628\\u0627\\u0644\\u0627 \\u0686\\u067e (Top Left)\\n"
        "\\u2022 \\u0628\\u0627\\u0644\\u0627 \\u0648\\u0633\\u0637 (Top Center)\\n"
        "\\u2022 \\u0628\\u0627\\u0644\\u0627 \\u0631\\u0627\\u0633\\u062a (Top Right)\\n\\n"
        "\\u06cc\\u06a9 \\u062f\\u06af\\u0645\\u0647 \\u0631\\u0627 \\u06a9\\u0644\\u06cc\\u06a9 \\u06a9\\u0646\\u06cc\\u062f.",
        reply_markup=reply_markup
    )


async def cmd_changesize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /changesize command - show size selection keyboard."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO:
        await update.message.reply_text(
            "\\u0634\\u0645\\u0627 \\u062f\\u0631 \\u062d\\u0627\\u0644\\u062a \\u0648\\u0627\\u062a\\u0645\\u0631\\u0627\\u06a9 \\u0647\\u0633\\u062a\\u06cc\\u062f. \\u0628\\u0631\\u0627\\u06cc \\u062a\\u063a\\u06cc\\u0631 \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u0644\\u0648\\u06af\\u0648, \\u0627\\u0648\\u0644\\u06cc\\u0646 /logo \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f."
        )
        return

    if state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await update.message.reply_text(
            "\\u0647\\u06cc\\u0686 \\u0644\\u0648\\u06af\\u0648\\u06cc \\u0628\\u0631\\u0627\\u06cc \\u062a\\u063a\\u06cc\\u0631 \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u0648\\u062c\\u0648\\u062f \\u0646\\u062f\\u0627\\u0631\\u062f. \\u0644\\u0648\\u06af\\u0648 \\u0631\\u0627 \\u0627\\u0648\\u0644 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
        )
        return

    # Show inline keyboard for size selection
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("\\u06a9\\u0648\\u0686\\u06a9 (\\u22488%)", callback_data="logo_size:small"),
            InlineKeyboardButton("\\u0645\\u062a\\u0648\\u0633\\u0637 (\\u224813%)", callback_data="logo_size:medium"),
            InlineKeyboardButton("\\u0628\\u0632\\u0631\\u06af (\\u224818%)", callback_data="logo_size:large"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "\\U0001f4cf \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u0644\\u0648\\u06af\\u0648 \\u0631\\u0627 \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u06a9\\u0646\\u06cc\\u062f:\\n\\n"
        "\\u2022 \\u06a9\\u0648\\u0686\\u06a9 \\u2248 8% \\u0639\\u0631\\u0636 \\u0639\\u06a9\\u0633 \\u0639\\u06a9\\u0633\\n"
        "\\u2022 \\u0645\\u062a\\u0648\\u0633\\u0637 \\u2248 13% \\u0639\\u0631\\u0636 \\u0639\\u06a9\\u0633 \\u0639\\u06a9\\u0633\\n"
        "\\u2022 \\u0628\\u0632\\u0631\\u06af \\u2248 18% \\u0639\\u0631\\u0636 \\u0639\\u06a9\\u0633 \\u0639\\u06a9\\u0633\\n\\n"
        "\\u06cc\\u06a9 \\u062f\\u06af\\u0645\\u0647 \\u0631\\u0627 \\u06a9\\u0644\\u06cc\\u06a9 \\u06a9\\u0646\\u06cc\\u062f.",
        reply_markup=reply_markup
    )


# ─── Logo Upload Handler ──────────────────────────────────────────
async def handle_logo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo/document upload for logo mode."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
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
                "\\u274c \\u0641\\u0642\\u0637 \\u0644\\u0648\\u06af\\u0648 \\u0628\\u0627\\u06cc\\u062f \\u0641\\u0631\\u0645\\u062a PNG \\u0628\\u0627\\u0634\\u062f.\\n"
                "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u06cc\\u06a9 \\u0641\\u0627\\u06cc\\u0644 PNG \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
            )
            user_manager.increment_errors(user_id)
            return
        file_id = document.file_id
    else:
        await update.message.reply_text("\\u274c \\u0646\\u0648\\u0639 \\u0641\\u0627\\u06cc\\u0644 \\u06cc\\u0627\\u0641\\u062a \\u0646\\u062f\\u0627\\u0631\\u062f.")
        return

    # Send processing message
    status_msg = await update.message.reply_text("\\u23f3 \\u062f\\u0631 \\u062d\\u0627\\u0644 \\u0628\\u0631\\u0631\\u0633\\u06cc \\u0644\\u0648\\u06af\\u0648...")

    try:
        # Download file from Bale
        file_path = bale_get_file_path(file_id)
        img_bytes = bale_download_file(file_path)

        # Validate file size
        if len(img_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            await status_msg.edit_text(f"\\u274c \\u0641\\u0627\\u06cc\\u0644 \\u062e\\u06cc\\u0644\\u06cc \\u0628\\u0632\\u0631\\u06af \\u0627\\u0633\\u062a (\\u062d\\u062f\\u0627\\u06a9\\u062b\\u0631 {MAX_FILE_SIZE_MB} \\u0645\\u06af\\u0627\\u0628\\u0627\\u06cc\\u062a).")
            user_manager.increment_errors(user_id)
            return

        # Validate as PNG logo
        logo_img, error = validate_logo_image(img_bytes)

        if error:
            await status_msg.edit_text(f"\\u274c {error}")
            user_manager.set_state(user_id, UserState.LOGO_INVALID)
            user_manager.increment_errors(user_id)
            return

        # Save to temporary storage
        temp_path = temp_manager.save_uploaded_file(
            user_id, img_bytes, suffix=".png", prefix="logo_"
        )

        if not temp_path:
            await status_msg.edit_text("\\u274c \\u062e\\u0637\\u0627 \\u062f\\u0631 \\u0630\\u062e\\u06cc\\u0631\\u0647 \\u0645\\u0648\\u0642\\u062a \\u0641\\u0627\\u06cc\\u0644. \\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u062f\\u0648\\u0628\\u0627\\u0631\\u0647 \\u062a\\u0644\\u0627\\u0634 \\u06a9\\u0646\\u06cc\\u062f.")
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
            f"\\u2705 \\u0644\\u0648\\u06af\\u0648 \\u0628\\u0627 \\u0645\\u0648\\u0641\\u0642\\u06cc\\u062a \\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0634\\u062f!\\n\\n"
            f"\\U0001f4d0 \\u0627\\u0628\\u0639\\u0627\\u062f: {logo_img.width}\\u00d7{logo_img.height}\\n"
            f"\\U0001f4c1 \\u0641\\u0631\\u0645\\u062a: PNG\\n\\n"
            f"\\u0627\\u06a9\\u0646\\u0648\\u0646 \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u0648 \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u0644\\u0648\\u06af\\u0648 \\u0631\\u0627 \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u06a9\\u0646\\u06cc\\u062f:\\n"
            f"\\u2022 /changeposition \\u2014 \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a\\n"
            f"\\u2022 /changesize \\u2014 \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647"
        )

        logger.info(f"User {user_id} set logo: {logo_img.size} PNG")

    except Exception as e:
        logger.error(f"Logo upload error for user {user_id}: {type(e).__name__}: {e}")
        await status_msg.edit_text(f"\\u274c \\u062e\\u0637\\u0627 \\u062f\\u0631 \\u067e\\u0631\\u062f\\u0627\\u0632\\u0634 \\u0644\\u0648\\u06af\\u0648:\\n{type(e).__name__}")
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
        await query.edit_message_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO or state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await query.edit_message_text("\\u274c \\u062d\\u0627\\u0644\\u062a \\u0644\\u0648\\u06af\\u0648 \\u0641\\u0639\\u0627\\u0644 \\u0646\\u06cc\\u0633\\u062a. \\u0644\\u0648\\u06af\\u0648 \\u0631\\u0627 \\u0627\\u0648\\u0644 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f.")
        return

    # Parse callback data
    data = query.data
    if not data.startswith("logo_pos:"):
        return

    pos_str = data.split(":")[1]
    try:
        position = LogoPosition(pos_str)
    except ValueError:
        await query.edit_message_text("\\u274c \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631.")
        return

    # Set position
    user_manager.set_logo_position(user_id, position)

    # Get current size preset if already set
    info = user_manager.get_logo_info(user_id)
    size_preset_str = info['size_preset'] if info and info['size_preset'] else "\\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0646\\u0634\\u062f\\u0647"

    await query.edit_message_text(
        f"\\u2705 \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0634\\u062f: {position.value}\\n\\n"
        f"\\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u0641\\u0639\\u0644\\u06cc: {size_preset_str}\\n\\n"
        f"\\u0628\\u0631\\u0627\\u06cc \\u062a\\u063a\\u06cc\\u0631 \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647: /changesize\\n"
        f"\\u0628\\u0631\\u0627\\u06cc \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u062f\\u06cc\\u06af\\u0631: /changeposition"
    )


async def handle_logo_size_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callback for logo size selection."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_manager.is_session_expired(user_id):
        await query.edit_message_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO or state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
        await query.edit_message_text("\\u274c \\u062d\\u0627\\u0644\\u062a \\u0644\\u0648\\u06af\\u0648 \\u0641\\u0639\\u0627\\u0644 \\u0646\\u06cc\\u0633\\u062a. \\u0644\\u0648\\u06af\\u0648 \\u0631\\u0627 \\u0627\\u0648\\u0644 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f.")
        return

    # Parse callback data
    data = query.data
    if not data.startswith("logo_size:"):
        return

    size_str = data.split(":")[1]
    try:
        size = LogoSize(size_str)
    except ValueError:
        await query.edit_message_text("\\u274c \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u0646\\u0627\\u0645\\u0639\\u062a\\u0628\\u0631.")
        return

    # Set size
    user_manager.set_logo_size(user_id, size)

    # Get current position if already set
    info = user_manager.get_logo_info(user_id)
    pos_str = info['position'] if info and info['position'] else "\\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0646\\u0634\\u062f\\u0647"

    await query.edit_message_text(
        f"\\u2705 \\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0634\\u062f: {size.value}\\n\\n"
        f"\\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a \\u0641\\u0639\\u0644\\u06cc: {pos_str}\\n\\n"
        f"\\U0001f389 \\u0644\\u0648\\u06af\\u0648 \\u06a9\\u0627\\u0645\\u0644 \\u062a\\u0646\\u0638\\u06cc\\u0645 \\u0634\\u062f\\u0647 \\u0648 \\u0622\\u0645\\u0627\\u062f\\u0647 \\u0628\\u0631\\u0627\\u06cc \\u0627\\u0639\\u0645\\u0627\\u0644!\\n"
        f"\\u0627\\u06a9\\u0646\\u0648\\u0646 \\u0645\\u06cc\\u062a\\u0648\\u0627\\u0646\\u06cc\\u062f \\u0639\\u06a9\\u0633\\u0647\\u0627\\u06cc \\u062e\\u0648\\u062f \\u0631\\u0627 \\u0628\\u0641\\u0631\\u0633\\u062a\\u06cc\\u062f \\u062a\\u0627 \\u0644\\u0648\\u06af\\u0648 \\u0631\\u0648\\u06cc \\u0627\\u0639\\u0645\\u0627\\u0644 \\u0634\\u0648\\u062f."
    )


# ─── Logo Image Processing ────────────────────────────────────────
async def handle_image_processing_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user's image with their logo overlay."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode != ProcessingMode.LOGO or state != UserState.LOGO_READY:
        await update.message.reply_text(
            "\\u26a0\\ufe0f \\u0644\\u0648\\u06af\\u0648 \\u0648 \\u062a\\u0646\\u0638\\u06cc\\u0645\\u0627\\u062a \\u0627\\u0646\\u062e\\u0627\\u0628 \\u0646\\u0634\\u062f\\u0647.\\n"
            "\\u0644\\u0648\\u06af\\u0648 \\u0631\\u0627 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f \\u0648 \\u0645\\u0648\\u0642\\u0639\\u06cc\\u062a/\\u0627\\u0646\\u062f\\u0627\\u0632\\u0647 \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u06a9\\u0646\\u06cc\\u062f."
        )
        return

    info = user_manager.get_logo_info(user_id)
    if not info or not info['path'] or not info['position'] or not info['size_preset']:
        await update.message.reply_text(
            "\\u26a0\\ufe0f \\u062a\\u0646\\u0638\\u06cc\\u0645\\u0627\\u062a \\u0644\\u0648\\u06af\\u0648 \\u06a9\\u0627\\u0645\\u0644 \\u0646\\u06cc\\u0633\\u062a.\\n"
            "/changelogo \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f \\u0648 \\u0628\\u0627\\u0639\\u062f /changeposition \\u0648 /changesize."
        )
        return

    # Load logo from temp file
    logo_path = Path(info['path'])
    if not logo_path.exists():
        user_manager.clear_logo(user_id)
        await update.message.reply_text(
            "\\u26a0\\ufe0f \\u0644\\u0648\\u06af\\u0648 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. \\u0628\\u0627 /changelogo \\u0628\\u0631\\u0627\\u06cc \\u0627\\u0648\\u0644 \\u0627\\u0631\\u0633\\u0627\\u0644."
        )
        return

    try:
        logo_img = Image.open(logo_path).convert("RGBA")
    except Exception as e:
        logger.error(f"Failed to load logo for user {user_id}: {e}")
        user_manager.clear_logo(user_id)
        await update.message.reply_text(
            "\\u26a0\\ufe0f \\u0644\\u0648\\u06af\\u0648 \\u062e\\u0631\\u0627\\u0628 \\u0634\\u062f\\u0647. \\u0628\\u0627 /changelogo \\u0628\\u0631\\u0627\\u06cc \\u0627\\u0648\\u0644 \\u0627\\u0631\\u0633\\u0627\\u0644."
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
                "\\u274c \\u0641\\u0642\\u0637 \\u0639\\u06a9\\u0633 \\u062a\\u0635\\u0648\\u06cc\\u0631\\u06cc \\u067e\\u0630\\u06cc\\u0631\\u0641\\u062a\\u0647 \\u0628\\u0627\\u0634\\u062f.\\n"
                "\\u0644\\u0637\\u0641\\u0627\\u0646\\u0647 \\u06cc\\u06a9 \\u0639\\u06a9\\u0633 (PNG, JPG, WEBP) \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
            )
            user_manager.increment_errors(user_id)
            return
        file_id = document.file_id
    else:
        await update.message.reply_text("\\u274c \\u0646\\u0648\\u0639 \\u0641\\u0627\\u06cc\\u0644 \\u06cc\\u0627\\u0641\\u062a \\u0646\\u062f\\u0627\\u0631\\u062f.")
        return

    status_msg = await update.message.reply_text("\\u23f3 \\u062f\\u0631 \\u062d\\u0627\\u0644 \\u0627\\u0639\\u0645\\u0627\\u0644 \\u0644\\u0648\\u06af\\u0648...")

    try:
        # Download user's image
        file_path = bale_get_file_path(file_id)
        img_bytes = bale_download_file(file_path)

        # Validate file size
        if len(img_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            await status_msg.edit_text(f"\\u274c \\u0641\\u0627\\u06cc\\u0644 \\u062e\\u06cc\\u0644\\u06cc \\u0628\\u0632\\u0631\\u06af \\u0627\\u0633\\u062a (\\u062d\\u062f\\u0627\\u06a9\\u062b\\u0631 {MAX_FILE_SIZE_MB} \\u0645\\u06af\\u0627\\u0628\\u0627\\u06cc\\u062a).")
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
            caption=f"\\u2705 \\u0644\\u0648\\u06af\\u0648 \\u0627\\u0639\\u0645\\u0627\\u0644 \\u0634\\u062f (\\u00d7{orig_w}\\u00d7{orig_h})"
        )

        # Update stats
        user_manager.increment_processed(user_id)

        logger.info(f"User {user_id} processed image with logo: {orig_w}x{orig_h}")

    except Exception as e:
        logger.error(f"Logo image processing error for user {user_id}: {type(e).__name__}: {e}")
        await status_msg.edit_text(f"\\u274c \\u062e\\u0637\\u0627 \\u062f\\u0631 \\u067e\\u0631\\u062f\\u0627\\u0632\\u0634 \\u062a\\u0635\\u0648\\u06cc\\u0631:\\n{type(e).__name__}")
        user_manager.increment_errors(user_id)
        # Keep error message visible, don't delete


# ─── Photo Handler (Watermark Upload)'''

if marker in content:
    content = content.replace(marker, new_handlers)
    with open('bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Logo handlers added successfully')
else:
    print('Could not find marker')
    idx = content.find('async def cmd_mode')
    if idx >= 0:
        print(f'Found cmd_mode at {idx}')
    idx2 = content.find('# ─── Photo Handler')
    if idx2 >= 0:
        print(f'Found Photo Handler at {idx2}')