with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix print statements with emojis
old_print = '''    print("🤖 ربات واترمارک چندکاربره بله روشن شد.")
    print("   - واترمارک موقت برای همه کاربران (Free tier)")
    print("   - تمیزکاری خودکار هر ۶۰ ثانیه")
    print("   - انقضای جلسه: ۳۰۰ ثانیه غیرفعالیتی")
    print("   - برای خروج Ctrl+C بزنید.")'''

new_print = '''    print("[BOT] Watermark Bot started successfully.")
    print("   - Temporary watermarks for all users (Free tier)")
    print("   - Auto cleanup every 60 seconds")
    print("   - Session timeout: 300 seconds inactivity")
    print("   - Press Ctrl+C to exit.")'''

if old_print in content:
    content = content.replace(old_print, new_print)
    with open('bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Print statements fixed')
else:
    print('Could not find print statements')