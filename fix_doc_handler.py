import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the document handler function and add logging
# We'll do a more targeted replacement - just add the logging lines

# Replace the session check block
old_session = '''    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نست شما منقضی شده. /start را بزنید.")
        return

    document = update.message.document
    mode = user_manager.get_processing_mode(user_id)
    state = user_manager.get_state(user_id)

    # Check if it's a PNG image'''

new_session = '''    # Check session
    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("نست شما منقضی شده. /start را بزنید.")
        return

    document = update.message.document
    mode = user_manager.get_processing_mode(user_id)
    state = user_manager.get_state(user_id)

    logger.debug(f"Document handler: user {user_id}, mode={mode.value if mode else None}, state={state.value if state else None}, mime={document.mime_type}, name={document.file_name}, size={document.file_size}")

    # Check if it's a PNG image'''

content = content.replace(old_session, new_session)

# Add logging before each handler call
old_logo_upload = '''            await handle_logo_upload(update, context)'''
new_logo_upload = '''            logger.debug(f"Document handler: routing to handle_logo_upload for user {user_id}")
            await handle_logo_upload(update, context)'''

content = content.replace(old_logo_upload, new_logo_upload)

old_logo_process = '''            await handle_image_processing_logo(update, context)'''
new_logo_process = '''            logger.debug(f"Document handler: routing to handle_image_processing_logo for user {user_id}")
            await handle_image_processing_logo(update, context)'''

content = content.replace(old_logo_process, new_logo_process)

old_watermark_upload = '''            await handle_watermark_upload(update, context)'''
new_watermark_upload = '''            logger.debug(f"Document handler: routing to handle_watermark_upload for user {user_id}")
            await handle_watermark_upload(update, context)'''

content = content.replace(old_watermark_upload, new_watermark_upload)

old_watermark_process = '''            await handle_image_processing_from_document(update, context)'''
new_watermark_process = '''            logger.debug(f"Document handler: routing to handle_image_processing_from_document for user {user_id}")
            await handle_image_processing_from_document(update, context)'''

content = content.replace(old_watermark_process, new_watermark_process)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Replacement successful')