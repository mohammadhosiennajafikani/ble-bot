with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find cmd_change function
start_idx = None
for i, line in enumerate(lines):
    if 'async def cmd_change' in line:
        start_idx = i
        break

# Find end of function
end_idx = None
for i in range(start_idx + 1, len(lines)):
    if lines[i].strip().startswith('async def ') or lines[i].strip().startswith('class ') or lines[i].strip().startswith('def '):
        end_idx = i
        break

if end_idx is None:
    end_idx = len(lines)

new_function = '''async def cmd_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /change command - prompt for new watermark or logo based on mode."""
    user_id = update.effective_user.id

    if user_manager.is_session_expired(user_id):
        await update.message.reply_text("\\u0646\\u0634\\u0633\\u062a \\u0634\\u0645\\u0627 \\u0645\\u0646\\u0642\\u0636\\u06cc \\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.")
        return

    state = user_manager.get_state(user_id)
    mode = user_manager.get_processing_mode(user_id)

    if mode == ProcessingMode.WATERMARK:
        if state == UserState.WATERMARK_READY:
            await update.message.reply_text(
                "\\U0001f504 \\u0628\\u0631\\u0627\\u06cc \\u062a\\u063a\\u06cc\\u0631 \\u0648\\u0627\\u062a\\u0631\\u0645\\u0627\\u0631\\u06a9, \\u0641\\u0627\\u06cc\\u0644 PNG \\u062c\\u062f\\u06cc\\u062f \\u0631\\u0627 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f.\\n"
                "\\u0648\\u0627\\u062a\\u0631\\u0645\\u0627\\u0631\\u06a9 \\u0642\\u0628\\u0644\\u06cc \\u062c\\u0627\\u06cc\\u06af\\u0632\\u06cc\\u0646 \\u062e\\u0648\\u0627\\u0647\\u062f \\u062c\\u0627\\u06cc\\u06af\\u0632\\u06cc\\u0646 \\u062e\\u0648\\u0627\\u0647\\u062f \\u0634\\u062f."
            )
        else:
            await update.message.reply_text(
                "\\u0634\\u0645\\u0627 \\u0648\\u0627\\u062a\\u0631\\u0645\\u0627\\u0631\\u06a9 \\u0641\\u0639\\u0627\\u0644\\u06cc \\u0646\\u062f\\u0627\\u0631\\u06cc\\u062f. \\u0641\\u0627\\u06cc\\u0644 PNG \\u0648\\u0627\\u062a\\u0631\\u0645\\u0627\\u0631\\u06a9 \\u062e\\u0648\\u062f \\u0631\\u0627 \\u0627\\u0631\\u0633\\u0627\\u0644 \\u06a9\\u0646\\u06cc\\u062f."
            )

        # Set state to expecting watermark
        user_manager.set_state(user_id, UserState.WATERMARK_PENDING)

    elif mode == ProcessingMode.LOGO:
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
        from user_manager import get_user_manager
        um = get_user_manager()
        um.clear_logo(user_id)
        user_manager.set_state(user_id, UserState.LOGO_PENDING)

    else:
        await update.message.reply_text(
            "\\u062d\\u0627\\u0644\\u062a \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u0646\\u0634\\u062f\\u0647. /start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f \\u062a\\u0627 \\u062d\\u0627\\u0644\\u062a \\u0631\\u0627 \\u0627\\u0646\\u062a\\u062e\\u0627\\u0628 \\u06a9\\u0646\\u06cc\\u062f."
        )
'''

# Replace the function
new_lines = lines[:start_idx] + [new_function + '\n'] + lines[end_idx:]

with open('bot.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('cmd_change updated successfully')