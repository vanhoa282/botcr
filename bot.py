import telebot
from telebot import types
import threading
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import json
import os
from datetime import datetime
from pytz import timezone
from flask import Flask
import sys

# Thay bằng token bot của bạn
BOT_TOKEN = os.getenv('BOT_TOKEN', '7474109511:AAGBtIgLFGOSxNOTzNujV1uhQeSz9W_bbb0')
bot = telebot.TeleBot(BOT_TOKEN)

# File lưu trữ dữ liệu
DATA_FILE = 'bot_data.json'

# Load data từ file
def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                # Đảm bảo các key cần thiết tồn tại
                if 'users' not in data:
                    data['users'] = {}
                if 'notifications' not in data:
                    data['notifications'] = {}
                if 'registered_users' not in data:
                    data['registered_users'] = {}
                return data
        return {'users': {}, 'notifications': {}, 'registered_users': {}}
    except json.JSONDecodeError as e:
        return {'users': {}, 'notifications': {}, 'registered_users': {}}
    except Exception as e:
        return {'users': {}, 'notifications': {}, 'registered_users': {}}

# Save data to file
def save_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        pass

data = load_data()

# Khởi tạo scheduler với múi giờ
scheduler = BackgroundScheduler(timezone=timezone('Asia/Ho_Chi_Minh'))
scheduler.start()

# Hàm kiểm tra đăng ký
def check_registration(user_id, message):
    if user_id not in data['registered_users']:
        bot.reply_to(message, "Bạn cần đăng ký trước bằng lệnh /dky!")
        return False
    return True

# Hàm gửi request
def send_request(cron_info):
    link = cron_info['link']
    method = cron_info['method']
    user_id = cron_info['user_id']
    try:
        if method.upper() == 'GET':
            response = requests.get(link, timeout=10)
        elif method.upper() == 'POST':
            response = requests.post(link, timeout=10)
        else:
            return  # Invalid method
        
        # Thông báo nếu user bật
        if user_id in data['notifications'] and data['notifications'][user_id]:
            bot.send_message(user_id, f"Cron chạy thành công: {link} - Status: {response.status_code} - Time: {datetime.now(timezone('Asia/Ho_Chi_Minh'))}")
    except Exception as e:
        if user_id in data['notifications'] and data['notifications'][user_id]:
            bot.send_message(user_id, f"Lỗi cron: {link} - {e}")

# Thêm cron job
def add_cron(user_id, link, method, time_seconds):
    if user_id not in data['users']:
        data['users'][user_id] = []
    
    job_id = f"{user_id}_{len(data['users'][user_id])}_{datetime.now().timestamp()}"
    
    cron_info = {
        'link': link,
        'method': method,
        'time': time_seconds,
        'user_id': user_id,
        'job_id': job_id
    }
    
    data['users'][user_id].append(cron_info)
    save_data(data)
    
    # Lập lịch job
    trigger = IntervalTrigger(seconds=time_seconds)
    scheduler.add_job(
        send_request,
        trigger=trigger,
        id=job_id,
        args=[cron_info],
        replace_existing=True
    )
    
    return job_id

# Xóa cron job
def remove_cron(link, user_id=None):
    removed = False
    for uid, crons in list(data['users'].items()):
        if user_id and uid != user_id:
            continue
        for cron in crons[:]:
            if cron['link'] == link:
                try:
                    scheduler.remove_job(cron['job_id'])
                except Exception as e:
                    pass
                crons.remove(cron)
                removed = True
                if not crons:
                    del data['users'][uid]
    if removed:
        save_data(data)
    return removed

# Lệnh /dky
@bot.message_handler(commands=['dky'])
def dky_handler(message):
    user_id = str(message.from_user.id)
    
    # Kiểm tra nếu user đã đăng ký
    if user_id in data['registered_users']:
        bot.reply_to(message, "Bạn đã đăng ký rồi!")
        return
    
    # Tạo nút inline
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton(
        text="Đồng ý share thông tin",
        callback_data="request_user_info"
    )
    markup.add(button)
    
    bot.reply_to(message, "Vui lòng bấm đồng ý share thông tin", reply_markup=markup)

# Xử lý callback từ nút inline
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "request_user_info":
        user_id = str(call.from_user.id)
        
        # Tạo nút Đồng Ý và Từ Chối
        markup = types.InlineKeyboardMarkup()
        agree_button = types.InlineKeyboardButton(
            text="Đồng Ý",
            callback_data="agree_register"
        )
        decline_button = types.InlineKeyboardButton(
            text="Từ Chối",
            callback_data="decline_register"
        )
        markup.add(agree_button, decline_button)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Bạn có đồng ý chia sẻ thông tin (ID, username, tên)?",
            reply_markup=markup
        )

    elif call.data == "agree_register":
        user_id = str(call.from_user.id)
        user_info = {
            'user_id': user_id,
            'username': call.from_user.username or "N/A",
            'first_name': call.from_user.first_name or "N/A",
            'last_name': call.from_user.last_name or "N/A",
            'registered_at': datetime.now(timezone('Asia/Ho_Chi_Minh')).isoformat()
        }
        
        data['registered_users'][user_id] = user_info
        save_data(data)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Đăng ký thành công! Bạn có thể dùng các lệnh của bot."
        )

    elif call.data == "decline_register":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Bạn đã từ chối đăng ký. Dùng /dky để thử lại."
        )

# Lệnh /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if not check_registration(user_id, message):
        return
    bot.reply_to(message, "Chào! Dùng /cron {link} {GET/POST} {TIME} để tạo cron.\n/quanly để xem số cron.\n/thongbao bat/tat để bật/tắt thông báo.\n/allcron để xem tất cả cron.\n/off {link} để tắt cron.")

# Lệnh /cron {link} {method} {time}
@bot.message_handler(commands=['cron'])
def cron_handler(message):
    user_id = str(message.from_user.id)
    if not check_registration(user_id, message):
        return
    
    try:
        parts = message.text.split()[1:]
        if len(parts) != 3:
            bot.reply_to(message, "Sử dụng: /cron {link} {GET/POST} {TIME}")
            return
        
        link, method, time_str = parts
        time_seconds = int(time_str)
        
        if time_seconds < 1:
            bot.reply_to(message, "TIME phải >= 1 giây.")
            return
        
        job_id = add_cron(user_id, link, method, time_seconds)
        
        if job_id:
            bot.reply_to(message, f"Đã tạo cron: {link} {method} mỗi {time_seconds}s. Job ID: {job_id}")
            if user_id in data['notifications'] and data['notifications'][user_id]:
                next_time = datetime.now(timezone('Asia/Ho_Chi_Minh')).timestamp() + time_seconds
                bot.reply_to(message, f"Lần chạy tiếp theo: {datetime.fromtimestamp(next_time, tz=timezone('Asia/Ho_Chi_Minh'))}")
            
    except ValueError:
        bot.reply_to(message, "TIME phải là số giây.")
    except Exception as e:
        bot.reply_to(message, f"Lỗi: {e}")

# Lệnh /quanly
@bot.message_handler(commands=['quanly'])
def quanly_handler(message):
    user_id = str(message.from_user.id)
    if not check_registration(user_id, message):
        return
    num_crons = len(data['users'].get(user_id, []))
    bot.reply_to(message, f"Bạn đã tạo {num_crons} cron.")

# Lệnh /thongbao bat/tat
@bot.message_handler(commands=['thongbao'])
def thongbao_handler(message):
    user_id = str(message.from_user.id)
    if not check_registration(user_id, message):
        return
    
    try:
        parts = message.text.split()[1:]
        
        if not parts:
            status = data['notifications'].get(user_id, False)
            bot.reply_to(message, f"Thông báo hiện tại: {'Bật' if status else 'Tắt'}")
            return
        
        action = parts[0].lower()
        
        if action in ['bat', 'bật']:
            data['notifications'][user_id] = True
            bot.reply_to(message, "Đã bật thông báo lần chạy cron tiếp theo.")
        elif action in ['tat', 'tắt']:
            data['notifications'][user_id] = False
            bot.reply_to(message, "Đã tắt thông báo.")
        else:
            bot.reply_to(message, "Sử dụng: /thongbao bat hoặc /thongbao tat")
        
        save_data(data)
    except Exception as e:
        bot.reply_to(message, f"Lỗi: {e}")

# Lệnh /allcron
@bot.message_handler(commands=['allcron'])
def allcron_handler(message):
    user_id = str(message.from_user.id)
    if not check_registration(user_id, message):
        return
    
    if not data['users']:
        bot.reply_to(message, "Chưa có cron nào.")
        return
    
    response = "Tất cả cron:\n"
    for uid, crons in data['users'].items():
        response += f"User {uid}: {len(crons)} cron\n"
        for cron in crons:
            response += f"  - {cron['link']} {cron['method']} mỗi {cron['time']}s\n"
    
    bot.reply_to(message, response)

# Lệnh /off {link}
@bot.message_handler(commands=['off'])
def off_handler(message):
    user_id = str(message.from_user.id)
    if not check_registration(user_id, message):
        return
    
    try:
        parts = message.text.split()[1:]
        if not parts:
            bot.reply_to(message, "Sử dụng: /off {link}")
            return
        
        link = parts[0]
        removed = remove_cron(link, user_id)
        
        if removed:
            bot.reply_to(message, f"Đã tắt cron: {link}")
        else:
            bot.reply_to(message, f"Không tìm thấy cron: {link}")
    except Exception as e:
        bot.reply_to(message, f"Lỗi: {e}")

# Flask app cho health check Koyeb
app = Flask(__name__)

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    # Chạy bot polling trong thread riêng
    def run_bot():
        try:
            bot.infinity_polling()
        except Exception as e:
            pass  # Không log, bỏ qua

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Chạy Flask trên port Koyeb
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
