import os
import uuid
import base64
from datetime import datetime
from io import BytesIO
from flask import Flask, request, jsonify, render_template
import qrcode
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__, template_folder='../templates')

# MongoDB connection
MONGODB_URI = "mongodb+srv://qrmessage:qrmessage123@cluster0.kyyfm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Sử dụng biến global để cache kết nối (tăng hiệu năng trên Serverless)
db_client = None

def get_db():
    global db_client
    if db_client is None:
        try:
            db_client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
        except Exception as e:
            print(f"MongoDB connection error: {e}")
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
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        msg_id = str(uuid.uuid4())[:8]
        
        # Xử lý URL động trên Vercel
        host = request.headers.get('Host')
        protocol = 'https' if not host.startswith('localhost') else 'http'
        base_url = f"{protocol}://{host}"
        view_url = f"{base_url}/view/{msg_id}"
        
        # Tạo QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(view_url)
        qr.make(fit=True)
        
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
        
        db = get_db()
        if db is not None:
            db.messages.insert_one(message_doc)
        
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
    try:
        db = get_db()
        message_doc = db.messages.find_one({'_id': msg_id}) if db is not None else None
        
        if not message_doc:
            return "<h1>Message Not Found</h1><a href='/'>Go Home</a>", 404
        
        # Format thời gian đơn giản
        dt = datetime.fromisoformat(message_doc['created_at'])
        created_time = dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return render_template_string_view(message_doc['message'], created_time)
    except Exception as e:
        return str(e), 500

@app.route('/api/messages')
def get_messages():
    try:
        db = get_db()
        messages = []
        if db is not None:
            for msg in db.messages.find().sort('created_at', -1).limit(20):
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
    try:
        db = get_db()
        if db is not None:
            db.messages.delete_one({'_id': msg_id})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def render_template_string_view(content, time):
    return f"""
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>View Message</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; padding: 20px; background: #f0f2f5; }}
            .card {{ background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; width: 100%; }}
            .msg {{ font-size: 1.2rem; white-space: pre-wrap; margin: 1rem 0; padding: 1rem; background: #f8f9fa; border-left: 5px solid #667eea; }}
            .time {{ color: #666; font-size: 0.9rem; }}
            .btn {{ display: inline-block; margin-top: 1rem; text-decoration: none; color: #667eea; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>📨 Tin nhắn QR</h2>
            <div class="msg">{content}</div>
            <p class="time">Gửi lúc: {time} (UTC)</p>
            <a href="/" class="btn">← Tạo tin nhắn mới</a>
        </div>
    </body>
    </html>
    """

# Cần thiết cho Vercel
app.debug = False