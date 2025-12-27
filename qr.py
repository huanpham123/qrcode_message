import os
import uuid
import base64
from datetime import datetime
from io import BytesIO
from flask import Flask, request, jsonify, render_template
import qrcode
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Khởi tạo Flask với thư mục templates cùng cấp với file qr.py
app = Flask(__name__, template_folder='templates')

# MongoDB connection string
MONGODB_URI = "mongodb+srv://qrmessage:qrmessage123@cluster0.kyyfm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Biến toàn cục để giữ kết nối (giảm độ trễ cho Serverless Function)
db_client = None

def get_db():
    global db_client
    if db_client is None:
        try:
            # Cấu hình tối ưu để tránh lỗi DNS và Timeout trên Vercel
            db_client = MongoClient(
                MONGODB_URI,
                server_api=ServerApi('1'),
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                serverSelectionTimeoutMS=5000,
                retryWrites=True
            )
            # Kiểm tra kết nối
            db_client.admin.command('ping')
        except Exception as e:
            print(f"Lỗi kết nối MongoDB: {e}")
            return None
    return db_client['qr_messages_db']

@app.route('/')
def home():
    """Trang chủ hiển thị giao diện tạo QR"""
    return render_template('qr.html')

@app.route('/api/create', methods=['POST'])
def create_message():
    """API tạo tin nhắn và sinh mã QR"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Không có dữ liệu'}), 400
            
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'error': 'Nội dung tin nhắn không được để trống'}), 400
        
        # Tạo ID ngắn cho tin nhắn
        msg_id = str(uuid.uuid4())[:8]
        
        # Tự động xác định Hostname (Vercel hoặc Local)
        host = request.headers.get('Host')
        protocol = 'https' if host and not host.startswith('localhost') else 'http'
        base_url = f"{protocol}://{host}"
        view_url = f"{base_url}/view/{msg_id}"
        
        # Tạo QR code chứa link xem tin nhắn
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(view_url)
        qr.make(fit=True)
        
        # Chuyển hình ảnh QR sang Base64 để hiển thị trên web
        img_buffer = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(img_buffer, format="PNG")
        qr_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        message_doc = {
            '_id': msg_id,
            'message': message,
            'created_at': datetime.utcnow().isoformat(),
            'view_url': view_url,
            'qr_base64': qr_base64
        }
        
        # Lưu vào Database
        db = get_db()
        if db is not None:
            db.messages.insert_one(message_doc)
        else:
            return jsonify({'error': 'Không thể kết nối Database. Hãy kiểm tra IP Access trên Atlas.'}), 500
        
        return jsonify({
            'success': True,
            'id': msg_id,
            'view_url': view_url,
            'qr_image': f"data:image/png;base64,{qr_base64}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/view/<msg_id>')
def view_message(msg_id):
    """Trang hiển thị nội dung tin nhắn khi quét mã QR"""
    try:
        db = get_db()
        message_doc = db.messages.find_one({'_id': msg_id}) if db is not None else None
        
        if not message_doc:
            return "<h1>Không tìm thấy tin nhắn</h1><a href='/'>Quay lại</a>", 404
        
        # Chuyển đổi thời gian hiển thị
        dt = datetime.fromisoformat(message_doc['created_at'])
        created_time = dt.strftime('%H:%M:%S %d-%m-%Y')
        
        return render_view_template(message_doc['message'], created_time)
    except Exception as e:
        return f"Lỗi hệ thống: {str(e)}", 500

@app.route('/api/messages')
def get_messages():
    """Lấy danh sách các tin nhắn gần đây"""
    try:
        db = get_db()
        messages = []
        if db is not None:
            for msg in db.messages.find().sort('created_at', -1).limit(15):
                messages.append({
                    'id': msg['_id'],
                    'message': msg['message'][:50] + '...' if len(msg['message']) > 50 else msg['message'],
                    'created_at': msg['created_at'],
                    'view_url': msg.get('view_url', f"/view/{msg['_id']}")
                })
        return jsonify({'messages': messages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/<msg_id>', methods=['DELETE'])
def delete_message(msg_id):
    """Xóa một tin nhắn"""
    try:
        db = get_db()
        if db is not None:
            db.messages.delete_one({'_id': msg_id})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def render_view_template(content, time):
    """Template HTML cho trang xem tin nhắn đơn giản"""
    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Xem Tin Nhắn</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; padding: 20px; background: #f4f7f6; }}
            .card {{ background: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.05); max-width: 500px; width: 100%; }}
            h2 {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            .msg {{ font-size: 1.1rem; line-height: 1.6; white-space: pre-wrap; margin: 20px 0; padding: 15px; background: #fafafa; border-radius: 8px; color: #444; }}
            .time {{ color: #888; font-size: 0.85rem; }}
            .btn {{ display: block; text-align: center; margin-top: 25px; text-decoration: none; background: #667eea; color: white; padding: 10px; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>📨 Nội dung tin nhắn</h2>
            <div class="msg">{content}</div>
            <p class="time">🕒 Gửi vào: {time} (UTC)</p>
            <a href="/" class="btn">Tạo tin nhắn của riêng bạn</a>
        </div>
    </body>
    </html>
    """

# Yêu cầu bắt buộc để Vercel nhận diện app Flask
app.debug = False
app = app
