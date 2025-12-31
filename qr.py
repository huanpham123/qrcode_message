import os
import uuid
import base64
from datetime import datetime
from io import BytesIO
from flask import Flask, request, jsonify, render_template
import qrcode
from pymongo import MongoClient
from flask_cors import CORS

app = Flask(__name__, template_folder='templates')
CORS(app)  # Thêm CORS để frontend gọi API

# Cấu hình MongoDB - có thể dùng localhost hoặc Atlas
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")

# Khởi tạo MongoDB client
try:
    if MONGODB_URI.startswith("mongodb+srv://"):
        client = MongoClient(MONGODB_URI)
    else:
        client = MongoClient(MONGODB_URI)
    
    db = client['qr_messages_db']
    messages_collection = db['messages']
    
    # Test connection
    client.admin.command('ping')
    print("✅ Kết nối MongoDB thành công!")
except Exception as e:
    print(f"❌ Lỗi kết nối MongoDB: {e}")
    # Fallback: lưu tạm trong memory (cho demo)
    messages_collection = None

@app.route('/')
def home():
    return render_template('qr.html')

@app.route('/api/create', methods=['POST'])
def create_message():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Vui lòng nhập nội dung tin nhắn'}), 400
        
        if len(message) > 1000:
            return jsonify({'error': 'Tin nhắn quá dài (tối đa 1000 ký tự)'}), 400
        
        # Tạo ID ngắn
        msg_id = str(uuid.uuid4())[:8]
        
        # Tạo URL xem tin nhắn
        base_url = request.host_url.rstrip('/')
        view_url = f"{base_url}/view/{msg_id}"
        
        # Tạo QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(view_url)
        qr.make(fit=True)
        
        # Chuyển QR code sang base64
        img_buffer = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(img_buffer, format="PNG")
        qr_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        # Tạo document để lưu
        message_doc = {
            '_id': msg_id,
            'message': message,
            'created_at': datetime.utcnow().isoformat(),
            'view_url': view_url,
            'qr_image': f"data:image/png;base64,{qr_base64}"
        }
        
        # Lưu vào MongoDB
        if messages_collection:
            messages_collection.insert_one(message_doc)
        
        return jsonify({
            'success': True,
            'id': msg_id,
            'message': message[:100] + '...' if len(message) > 100 else message,
            'view_url': view_url,
            'qr_image': f"data:image/png;base64,{qr_base64}",
            'created_at': message_doc['created_at']
        })
        
    except Exception as e:
        print(f"Lỗi tạo tin nhắn: {e}")
        return jsonify({'error': f'Lỗi server: {str(e)}'}), 500

@app.route('/view/<msg_id>')
def view_message(msg_id):
    try:
        # Tìm tin nhắn
        if messages_collection:
            message_doc = messages_collection.find_one({'_id': msg_id})
        else:
            return "<h1>Tính năng này cần kết nối database</h1>", 500
        
        if not message_doc:
            return """
            <html>
            <head><title>Không tìm thấy</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>📭 Không tìm thấy tin nhắn</h1>
                <p>Tin nhắn này có thể đã bị xóa hoặc không tồn tại.</p>
                <a href="/" style="color: #4f46e5;">← Quay về trang chủ</a>
            </body>
            </html>
            """, 404
        
        # Định dạng thời gian
        created_at = datetime.fromisoformat(message_doc['created_at'])
        formatted_time = created_at.strftime('%H:%M %d/%m/%Y')
        
        # Trả về trang xem tin nhắn
        return f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Tin nhắn #{msg_id}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }}
                .message-container {{
                    background: white;
                    border-radius: 20px;
                    padding: 40px;
                    max-width: 600px;
                    width: 100%;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                }}
                .message-icon {{
                    font-size: 60px;
                    margin-bottom: 20px;
                    color: #4f46e5;
                }}
                .message-content {{
                    background: #f8fafc;
                    padding: 25px;
                    border-radius: 12px;
                    margin: 25px 0;
                    font-size: 18px;
                    line-height: 1.6;
                    text-align: left;
                    white-space: pre-wrap;
                    border-left: 5px solid #4f46e5;
                }}
                .message-time {{
                    color: #64748b;
                    font-size: 14px;
                    margin: 15px 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                }}
                .back-button {{
                    display: inline-block;
                    background: #4f46e5;
                    color: white;
                    padding: 12px 30px;
                    border-radius: 50px;
                    text-decoration: none;
                    font-weight: 600;
                    margin-top: 20px;
                    transition: all 0.3s;
                    border: none;
                    cursor: pointer;
                    font-size: 16px;
                }}
                .back-button:hover {{
                    background: #4338ca;
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(79, 70, 229, 0.3);
                }}
                .qr-section {{
                    margin: 25px 0;
                    padding: 20px;
                    background: #f1f5f9;
                    border-radius: 12px;
                }}
                .qr-title {{
                    font-size: 14px;
                    color: #64748b;
                    margin-bottom: 10px;
                }}
                .qr-code {{
                    display: inline-block;
                    padding: 15px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .message-id {{
                    font-family: 'Courier New', monospace;
                    background: #1e293b;
                    color: #60a5fa;
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-size: 14px;
                    display: inline-block;
                    margin-bottom: 15px;
                }}
            </style>
        </head>
        <body>
            <div class="message-container">
                <div class="message-icon">📨</div>
                <h1 style="color: #1e293b; margin-bottom: 10px;">Tin nhắn QR</h1>
                <div class="message-id">ID: {msg_id}</div>
                
                <div class="message-content">
                    {message_doc['message']}
                </div>
                
                <div class="message-time">
                    <i class="fas fa-clock"></i> Gửi vào: {formatted_time}
                </div>
                
                <div class="qr-section">
                    <div class="qr-title">Quét QR để chia sẻ tin nhắn này:</div>
                    <div class="qr-code">
                        <img src="{message_doc.get('qr_image', '#')}" alt="QR Code" style="width: 200px; height: 200px;">
                    </div>
                </div>
                
                <a href="/" class="back-button">
                    <i class="fas fa-plus"></i> Tạo tin nhắn mới
                </a>
            </div>
            
            <!-- Font Awesome -->
            <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
        </body>
        </html>
        """
        
    except Exception as e:
        print(f"Lỗi xem tin nhắn: {e}")
        return "<h1>Lỗi server</h1>", 500

@app.route('/api/messages')
def get_messages():
    try:
        messages = []
        if messages_collection:
            # Lấy 20 tin nhắn gần nhất
            for msg in messages_collection.find().sort('created_at', -1).limit(20):
                messages.append({
                    'id': msg['_id'],
                    'message': msg['message'],
                    'created_at': msg['created_at'],
                    'view_url': msg.get('view_url', f"/view/{msg['_id']}"),
                    'qr_image': msg.get('qr_image', '')
                })
        
        return jsonify({'success': True, 'messages': messages})
        
    except Exception as e:
        print(f"Lỗi lấy danh sách tin nhắn: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete/<msg_id>', methods=['DELETE'])
def delete_message(msg_id):
    try:
        if messages_collection:
            result = messages_collection.delete_one({'_id': msg_id})
            if result.deleted_count > 0:
                return jsonify({'success': True, 'message': 'Đã xóa tin nhắn'})
            else:
                return jsonify({'success': False, 'error': 'Không tìm thấy tin nhắn'}), 404
        
        return jsonify({'success': False, 'error': 'Database không khả dụng'}), 500
        
    except Exception as e:
        print(f"Lỗi xóa tin nhắn: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected' if messages_collection else 'disconnected'
    })

if __name__ == '__main__':
    # Tạo thư mục templates nếu chưa tồn tại
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    print("=" * 50)
    print("🚀 Khởi động QR Message Generator")
    print("=" * 50)
    print(f"📂 Template folder: {app.template_folder}")
    print(f"🔗 MongoDB URI: {MONGODB_URI[:20]}...")
    print("=" * 50)
    
    # Chạy server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
