with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the main function and update the handlers section
old_main = '''    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("change", cmd_change))
    app.add_handler(CommandHandler("remove", cmd_remove))

    # Photo handler (handles both watermark upload and image processing)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Document handler for PNG files sent as documents (preserves quality)
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))

    # Fallback handler for unsupported document types
    app.add_handler(MessageHandler(filters.Document.ALL, handle_unsupported_file))'''

new_main = '''    # Command handlers
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
    app.add_handler(MessageHandler(filters.Document.ALL, handle_unsupported_file))'''

if old_main in content:
    content = content.replace(old_main, new_main)
    with open('bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('main() updated successfully')
else:
    print('Could not find old main handlers section')