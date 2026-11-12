with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update imports to add CallbackQueryHandler
old_import = '''from telegram.ext import (
    Application, MessageHandler, CommandHandler, filters, ContextTypes
)'''

new_import = '''from telegram.ext import (
    Application, MessageHandler, CommandHandler, filters, ContextTypes, CallbackQueryHandler
)'''

if old_import in content:
    content = content.replace(old_import, new_import)
    with open('bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Imports updated successfully')
else:
    print('Could not find old imports')