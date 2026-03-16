from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import requests
import os

app = FastAPI()

# Cấu hình CORS để cho phép ReactJS (chạy ở port 5173) gọi được API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping")
def ping():
    return {"status": "ok", "message": "pong"}

# Chuỗi kết nối Database (Nhớ thay mật khẩu của bạn, database tên là 'datdoan' như trong hình)

# Định nghĩa dữ liệu nhận từ Frontend
class ReferralRequest(BaseModel):
    code: str

# Thêm class này ở phần đầu file (dưới class ReferralRequest)
class OrderRequest(BaseModel):
    store_id: int
    items_text: str
    delivery_time: str
    notes: str

@app.post("/api/check-referral")
def check_referral(request: ReferralRequest):
    try:
        # Thay đổi phần kết nối DB thành các tham số rời như sau:
        conn = psycopg2.connect(
            # 1. Host: Copy đoạn từ sau dấu @ đến trước dấu :6543
            host=os.getenv("DB_HOST"),
            
            # 2. Port: Chắc chắn là 6543
            port=os.getenv("DB_PORT"),
            
            # 3. Database: Mặc định là postgres
            database=os.getenv("DB_NAME"),
            
            # 4. User: Copy đoạn từ sau dấu // đến trước dấu :[YOUR-PASSWORD]
            user=os.getenv("DB_USER"),
            
            # 5. Password: Gõ tay mật khẩu Supabase của bạn vào đây
            password=os.getenv("DB_PASSWORD")
        )
        cursor = conn.cursor()
        
        # Tìm mã giới thiệu trong database
        cursor.execute("SELECT is_used FROM referral_codes WHERE code = %s", (request.code,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Xử lý các trường hợp
        if result is None:
            raise HTTPException(status_code=404, detail="Mã giới thiệu không tồn tại!")
        elif result[0] is True:
            raise HTTPException(status_code=400, detail="Mã giới thiệu đã được sử dụng!")
        
        return {"success": True, "message": "Mã hợp lệ!"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
    
@app.get("/api/stores")
def get_stores():
    try:
        # Nhớ dùng đúng chuỗi kết nối (host, port, user, password, db) đã chạy thành công lúc nãy nhé
        conn = psycopg2.connect(
            # 1. Host: Copy đoạn từ sau dấu @ đến trước dấu :6543
            host=os.getenv("DB_HOST"),
            
            # 2. Port: Chắc chắn là 6543
            port=os.getenv("DB_PORT"),
            
            # 3. Database: Mặc định là postgres
            database=os.getenv("DB_NAME"),
            
            # 4. User: Copy đoạn từ sau dấu // đến trước dấu :[YOUR-PASSWORD]
            user=os.getenv("DB_USER"),
            
            # 5. Password: Gõ tay mật khẩu Supabase của bạn vào đây
            password=os.getenv("DB_PASSWORD")
        )
        cursor = conn.cursor()
        
        # Lấy dữ liệu các quán ăn đang hoạt động
        cursor.execute("SELECT id, name, category, image_url FROM stores WHERE is_active = TRUE")
        stores_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Biến đổi dữ liệu thô từ Database thành dạng Danh sách (List) cho React dễ đọc
        stores_list = []
        for row in stores_data:
            stores_list.append({
                "id": row[0], 
                "name": row[1], 
                "category": row[2], 
                "image_url": row[3]
            })
            
        return {"success": True, "stores": stores_list}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")

@app.post("/api/orders")
def create_order(request: OrderRequest):
    try:
        # 1. KẾT NỐI DATABASE (Hiện tại vẫn dùng local, lát nữa sẽ đổi sang Cloud)
        conn = psycopg2.connect(
            # 1. Host: Copy đoạn từ sau dấu @ đến trước dấu :6543
            host=os.getenv("DB_HOST"),
            
            # 2. Port: Chắc chắn là 6543
            port=os.getenv("DB_PORT"),
            
            # 3. Database: Mặc định là postgres
            database=os.getenv("DB_NAME"),
            
            # 4. User: Copy đoạn từ sau dấu // đến trước dấu :[YOUR-PASSWORD]
            user=os.getenv("DB_USER"),
            
            # 5. Password: Gõ tay mật khẩu Supabase của bạn vào đây
            password=os.getenv("DB_PASSWORD")
        )
        cursor = conn.cursor()
        
        # Tạm thời gán user_id = 1 (vì chúng ta chưa làm luồng đăng nhập thật)
        user_id = 1 
        
        # 2. LƯU ĐƠN HÀNG VÀO DATABASE
        cursor.execute(
            """
            INSERT INTO orders (user_id, store_id, custom_items_text, delivery_time, notes, status) 
            VALUES (%s, %s, %s, %s, %s, 'PENDING')
            """,
            (user_id, request.store_id, request.items_text, request.delivery_time, request.notes)
        )
        
        conn.commit() # Chốt lưu dữ liệu vào DB
        
        # 3. GỬI THÔNG BÁO QUA TELEGRAM (BỎ N8N)
        try:
            BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
            CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
            
            # Cấu trúc nội dung tin nhắn gửi về điện thoại
            tin_nhan = f"""🚨 CÓ ĐƠN MUA HỘ MỚI!
- Món khách đặt: {request.items_text}
- Giờ giao: {request.delivery_time}
- Ghi chú: {request.notes}"""
            
            # Gọi API của Telegram để gửi tin nhắn
            telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(telegram_url, json={"chat_id": CHAT_ID, "text": tin_nhan}, timeout=5)
            
        except Exception as e:
            # Nếu Telegram lỗi thì in ra màn hình Terminal chứ không làm sập web
            print(f"Lỗi gửi Telegram: {e}") 

        # Đóng kết nối Database
        cursor.close()
        conn.close()
        
        return {"success": True, "message": "Đặt đơn mua hộ thành công!"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")