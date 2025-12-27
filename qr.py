import os
import uuid
import base64
from datetime import datetime
from io import BytesIO
from flask import Flask, request, jsonify, render_template
import qrcode
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Khởi tạo app với folder templates cùng cấp
app = Flask(__name__, template_folder='templates')

# Link kết nối (Đảm bảo mật khẩu và tên cluster chính xác)
MONGODB_URI = "mongodb+srv://qrmessage:qrmessage123@cluster0.kyyfm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Cache connection
db_client = None

def get_db():
    global db_client
    if db_client is None:
        try:
            # Cấu hình tối ưu để tránh lỗi DNS và treo server trên Vercel
            db_client = MongoClient(
                MONGODB_URI,
                server_api=ServerApi('1'),
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                serverSelectionTimeoutMS=10000 # Tăng thời gian chờ DNS
            )
            # Kiểm tra kết nối nhanh
            db_client.admin.command('ping')
        except Exception as e:
            print(f"Lỗi DNS hoặc Kết nối MongoDB: {e}")
            return None
    return db_client['qr_messages_db']

@app.route('/')
def home():
    return render_template('qr.html')

@app.route('/api/create', methods=['POST'])
def create_message():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'error': 'Nội dung không được để trống'}), 400
        
        msg_id = str(uuid.uuid4())[:8]
        
        # Lấy domain động
        host = request.headers.get('Host')
        protocol = 'https' if host and not host.startswith('localhost') else 'http'
        view_url = f"{protocol}://{host}/view/{msg_id}"
        
        # Tạo mã QR
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(view_url)
        qr.make(fit=True)
        
        img_buffer = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(img_buffer, format="PNG")
        qr_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        db = get_db()
        if db is None:
            return jsonify({'error': 'Lỗi DNS: Không thể tìm thấy máy chủ Database. Hãy kiểm tra requirements.txt đã có dnspython chưa.'}), 500

        message_doc = {
            '_id': msg_id,
            'message': message,
            'created_at': datetime.utcnow().isoformat(),
            'view_url': view_url,
            'qr_base64': qr_base64
        }
        db.messages.insert_one(message_doc)
        
        return jsonify({
            'success': True,
            'qr_image': f"data:image/png;base64,{qr_base64}",
            'view_url': view_url
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/view/<msg_id>')
def view_message(msg_id):
    try:
        db = get_db()
        if db is None: return "Lỗi kết nối Database", 500
        
        doc = db.messages.find_one({'_id': msg_id})
        if not doc: return "Không tìm thấy tin nhắn", 404
        
        return render_view_template(doc['message'], doc['created_at'])
    except Exception as e:
        return str(e), 500

def render_view_template(content, time):
    return f"""
    <html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{{font-family:sans-serif;background:#f0f2f5;display:flex;justify-content:center;padding:20px}}
    .card{{background:#fff;padding:2rem;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);max-width:500px;width:100%}}
    .msg{{background:#f8f9fa;padding:1rem;border-left:4px solid #667eea;margin:1rem 0;white-space:pre-wrap}}</style></head>
    <body><div class="card"><h2>📨 Nội dung tin nhắn</h2><div class="msg">{content}</div><p style="color:999">Gửi lúc: {time}</p><a href="/">Quay lại</a></div></body></html>
    """

app = app # Để Vercel nhận diện
