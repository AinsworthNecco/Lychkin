import requests
import time
import random
import os
import base64
import math
import concurrent.futures
import tempfile
import shutil
# YÊU CẦU CÀI ĐẶT TRƯỚC KHI CHẠY: 
# pip install playwright opencv-python numpy requests
# playwright install
from playwright.sync_api import sync_playwright
import cv2
import numpy as np

# ========================================================
# CẤU HÌNH HỆ THỐNG (TÙY CHỈNH TẠI ĐÂY)
# ========================================================
CONFIG = {
    "NUM_THREADS": 1,           # Số lượng luồng chạy song song cùng lúc
    "HEADLESS": True,           # Đã bật True để tối ưu hiệu suất tối đa
    "PROXY_LIST": [             # Tùy chọn danh sách proxy (để trống nếu không dùng)
        # "http://user:pass@ip:port",
    ],
    "EXECUTABLE_PATH": "/usr/bin/chromium" # Dành cho Termux/Debian ARM. Để "" (rỗng) nếu chạy trên Windows/PC bình thường.
}

def get_temp_email():
    url = "https://api.internal.temp-mail.io/api/v3/email/new"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Application-Name": "web",
        "Application-Version": "2.4.2",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("email")
        else:
            print(f"❌ Lỗi tạo email: {response.status_code}")
    except Exception as e:
        print(f"❌ Lỗi kết nối Temp-mail: {e}")
    return None

# ========================================================
# HÀM TẢI/LƯU ẢNH GỐC TỪ URL HOẶC CHUỖI BASE64
# ========================================================
def download_image(url, save_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://cloud.vsphone.com/"
    }
    try:
        if url.startswith("data:image"):
            header, encoded = url.split(",", 1)
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(encoded))
            return True
        else:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                return True
            return False
    except Exception as e:
        error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
        print(f"⚠️ Lỗi khi lấy ảnh: {error_msg}")
        return False

# ========================================================
# HÀM XỬ LÝ ẢNH CHUẨN XÁC
# ========================================================
def find_puzzle_gap_raw(bg_path, piece_path, thread_id="1"):
    print(f"[Luồng {thread_id}] 👁️ Đang phân tích ảnh bằng Canny Edge...")
    bg_img = cv2.imread(bg_path)
    piece_img = cv2.imread(piece_path, cv2.IMREAD_UNCHANGED) 
    
    if bg_img is None or piece_img is None:
        print(f"[Luồng {thread_id}] ❌ Lỗi: Không thể đọc được file ảnh đã tải về.")
        return 0, 0, 0, 0, 0, 0, 0

    bg_gray = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY)
    bg_edge = cv2.Canny(bg_gray, 50, 150)
    
    if len(piece_img.shape) == 3 and piece_img.shape[2] == 4:
        alpha = piece_img[:, :, 3]
        _, alpha_mask = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
        
        x, y, w, h = cv2.boundingRect(alpha_mask) 
        
        if w > 0 and h > 0:
            piece_crop = piece_img[y:y+h, x:x+w]
            piece_crop_gray = cv2.cvtColor(piece_crop, cv2.COLOR_BGR2GRAY)
            piece_crop_gray[alpha_mask[y:y+h, x:x+w] == 0] = 0
            
            piece_edge = cv2.Canny(piece_crop_gray, 100, 200)
            
            margin = 3
            y_start = max(0, y - margin)
            y_end = min(bg_edge.shape[0], y + h + margin)
            bg_strip = bg_edge[y_start:y_end, :]
            
            result = cv2.matchTemplate(bg_strip, piece_edge, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            target_raw_x = max_loc[0] - x
            target_raw_y = y_start + max_loc[1] 
            
            print(f"[Luồng {thread_id}] ✅ Đã chốt tọa độ! Độ khớp: {max_val*100:.1f}%")
            return max(0, target_raw_x), x, y, w, h, max_loc[0], target_raw_y
            
    return max_loc[0], 0, 0, 40, 40, max_loc[0], 0

# ========================================================
# HÀM RÊ CHUỘT DÒ ĐƯỜNG THỜI GIAN THỰC (FEEDBACK LOOP DRAG)
# Đã điều chỉnh chậm lại để ổn định hơn
# ========================================================
def feedback_loop_drag(page, start_x, start_y, target_piece_x, thread_id="1"):
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    time.sleep(random.uniform(0.1, 0.2)) 
    
    current_mouse_x = start_x
    
    for _ in range(200): 
        # Thêm tiền tố 'r' để loại bỏ lỗi SyntaxWarning: invalid escape sequence
        piece_left_str = page.evaluate(r"""() => {
            let el = document.getElementById('aliyunCaptcha-puzzle');
            if (!el) return '0';
            let left = el.style.left;
            if (left && left !== '0px' && left !== '0') return left;
            let transform = el.style.transform;
            if (transform && transform.includes('translate')) {
                let match = transform.match(/translate[X]?\((.+?)px/);
                if (match) return match[1];
            }
            return left || '0';
        }""")
        
        piece_left = float(piece_left_str.replace('px', '').strip()) if piece_left_str else 0.0
        
        distance_left = target_piece_x - piece_left
        
        if abs(distance_left) <= 1.0:
            print(f"[Luồng {thread_id}] 🎯 Mảnh ghép khớp hoàn hảo. Chốt sổ!")
            break
            
        if distance_left > 0:
            if distance_left > 40:
                step = random.uniform(6, 12) # Chậm lại một chút so với bản cũ
            elif distance_left > 10:
                step = random.uniform(2, 5)
            else:
                step = random.uniform(0.5, 1.5)
            current_mouse_x += step
        else:
            step = random.uniform(0.5, 1.5)
            current_mouse_x -= step
            
        page.mouse.move(current_mouse_x, start_y + random.uniform(-1, 1))
        # Tăng delay lên 20-40ms mỗi bước để chuột đi đằm hơn, tránh kẹt do quá nhanh
        time.sleep(random.uniform(0.02, 0.04))

    time.sleep(random.uniform(0.4, 0.7)) 
    page.mouse.up()

# ========================================================
# HÀM CHÍNH: XỬ LÝ CAPTCHA LIÊN TỤC (CÓ FAIL-SAFE)
# ========================================================
def auto_drag_slider(page, thread_id="1"):
    print(f"[Luồng {thread_id}] 🤖 Đang tiến hành giải Captcha liên tục...")
        
    attempt = 0
    while True:
        get_code_btn = page.get_by_text("Get code", exact=True)
        if not get_code_btn.is_visible():
            print(f"\n[Luồng {thread_id}] ✅ Nút 'Get code' biến mất! SMS ĐÃ GỬI THÀNH CÔNG.")
            return True
            
        attempt += 1
        
        # CƠ CHẾ FAIL-SAFE: Quá 10 lần sai sẽ bỏ qua để làm lại
        if attempt > 10:
            print(f"\n[Luồng {thread_id}] ❌ Sai quá 10 lần liên tục. Hủy session này để làm lại từ đầu!")
            return False

        print(f"\n[Luồng {thread_id}] 🔄 LẦN THỬ THỨ {attempt}:")
        try:
            if not page.locator("#aliyunCaptcha-window-popup").is_visible():
                print(f"[Luồng {thread_id}] 👉 Đang thử bấm nút 'Get code'...")
                try:
                    get_code_btn.click(timeout=3000)
                    time.sleep(1)
                except Exception:
                    pass
            
            if not page.locator("#aliyunCaptcha-window-popup").is_visible():
                time.sleep(1)
                continue
                
            time.sleep(0.5) 
            
            bg_locator = page.locator("#aliyunCaptcha-img")
            piece_locator = page.locator("#aliyunCaptcha-puzzle")
            slider_handle = page.locator("#aliyunCaptcha-sliding-slider")
            
            if not bg_locator.is_visible() or not piece_locator.is_visible():
                continue

            bg_url = bg_locator.get_attribute("src")
            piece_url = piece_locator.get_attribute("src")
            
            if not bg_url or not piece_url:
                continue
                
            bg_path = f"raw_bg_{thread_id}.png"
            piece_path = f"raw_piece_{thread_id}.png"
            
            if not download_image(bg_url, bg_path) or not download_image(piece_url, piece_path):
                continue

            # 2. TÍNH TOÁN OPENCV
            target_raw_x, raw_x, raw_y, raw_w, raw_h, raw_tgt_x, raw_tgt_y = find_puzzle_gap_raw(bg_path, piece_path, thread_id)
            
            bg_img_raw = cv2.imread(bg_path)
            raw_width = bg_img_raw.shape[1] if bg_img_raw is not None else 1
            
            if os.path.exists(bg_path): os.remove(bg_path)
            if os.path.exists(piece_path): os.remove(piece_path)

            # 3. QUY ĐỔI TỶ LỆ 
            bg_box = bg_locator.bounding_box()
            slider_box = slider_handle.bounding_box()
            
            if bg_box and slider_box:
                scale = bg_box["width"] / raw_width 
                target_piece_x = target_raw_x * scale
                
                print(f"[Luồng {thread_id}] 🎯 Quãng đường Mảnh Ghép cần đi: {target_piece_x:.2f}px")
                
                if target_piece_x < 10:
                    page.locator("#aliyunCaptcha-btn-refresh").click()
                    time.sleep(1)
                    continue

                # 4. THỰC HIỆN RÊ CHUỘT DÒ ĐƯỜNG
                margin_x = slider_box["width"] * 0.2
                margin_y = slider_box["height"] * 0.2
                start_x = slider_box["x"] + random.uniform(margin_x, slider_box["width"] - margin_x)
                start_y = slider_box["y"] + random.uniform(margin_y, slider_box["height"] - margin_y)
                
                feedback_loop_drag(page, start_x, start_y, target_piece_x, thread_id)
                
                print(f"[Luồng {thread_id}] ⏳ Chờ Web xác thực kết quả...")
                time.sleep(2) 
                
                if page.locator("#aliyunCaptcha-window-popup").is_visible():
                    print(f"[Luồng {thread_id}] ⚠️ Bị WAF từ chối! Đang bấm đổi ảnh mới...")
                    try:
                        refresh_btn = page.locator("#aliyunCaptcha-btn-refresh")
                        if refresh_btn.is_visible():
                            refresh_btn.click()
                    except:
                        pass
                    time.sleep(0.5) 
            
        except Exception as e:
             print(f"[Luồng {thread_id}] ⚠️ Lỗi: {e}")
             time.sleep(1)

# ========================================================
# HÀM MỞ TRÌNH DUYỆT (TỐI ƯU SIÊU NHẸ CHO TERMUX)
# Trả về True nếu thành công, False nếu thất bại
# ========================================================
def send_with_browser(email, proxy_server=None, thread_id="1"):
    print(f"[Luồng {thread_id}] 📨 Bắt đầu với email: {email} | Proxy: {proxy_server}")

    temp_profile_dir = tempfile.mkdtemp(prefix=f"vmos_profile_{thread_id}_")
    is_success = False

    try:
        with sync_playwright() as p:
            launch_args = {
                "user_data_dir": temp_profile_dir,
                "headless": CONFIG["HEADLESS"], 
                "viewport": {"width": 1280, "height": 720},
                "device_scale_factor": 1,
                "has_touch": False,
                "is_mobile": False,
                "args": [
                    '--disable-blink-features=AutomationControlled', 
                    '--disable-infobars',                            
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',        
                    '--disable-gpu',                  
                    '--disable-software-rasterizer',
                    '--disable-extensions',           
                    '--mute-audio',                   
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-sync'                  
                ]
            }
            
            if CONFIG.get("EXECUTABLE_PATH"):
                launch_args["executable_path"] = CONFIG["EXECUTABLE_PATH"]
            else:
                launch_args["channel"] = "chrome"
            
            if proxy_server:
                launch_args["proxy"] = {"server": proxy_server} 

            print(f"[Luồng {thread_id}] 🛡️ Khởi chạy Persistent Context...")
            context = p.chromium.launch_persistent_context(**launch_args)
            
            try:
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    window.chrome = { runtime: {} };
                """)
                
                page = context.pages[0] if context.pages else context.new_page()

                page.route("**/*", lambda route: route.abort() 
                           if route.request.resource_type in ["media", "font"] 
                           else route.continue_())

                target_url = "https://cloud.vsphone.com/?channel=web"
                
                # CẬP NHẬT CHỐNG TIMEOUT: Đổi từ "networkidle" sang "domcontentloaded" và nới lỏng timeout
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

                page.get_by_text("Sign Up", exact=True).click(timeout=30000)
                time.sleep(1)

                email_input = page.locator("input[placeholder='Please enter your email address']").last
                email_input.fill(email)
                time.sleep(0.5)

                box = email_input.bounding_box()
                if box:
                    page.mouse.move(box["x"] + 10, box["y"] + 10, steps=5)
                    time.sleep(0.2)

                # Chạy giải captcha, nếu fail quá 10 lần sẽ trả về False
                is_success = auto_drag_slider(page, thread_id)
                
                if is_success:
                    print(f"[Luồng {thread_id}] 🎉 Tự động hóa hoàn tất, đang đóng trình duyệt...")
                else:
                    print(f"[Luồng {thread_id}] ❌ Luồng bị gián đoạn do giải Captcha thất bại nhiều lần.")
                    
            except Exception as e:
                print(f"[Luồng {thread_id}] ❌ Lỗi xảy ra: {e}")
            finally:
                context.close()
    finally:
        try:
            shutil.rmtree(temp_profile_dir, ignore_errors=True)
            print(f"[Luồng {thread_id}] 🧹 Đã dọn dẹp sạch sẽ profile tạm thời.")
        except Exception as cleanup_error:
            pass # Không cần in ra cảnh báo nếu dọn rác thất bại nhẹ
            
    return is_success

# ========================================================
# HÀM THỰC THI (TỰ ĐỘNG LÀM LẠI NẾU FAIL)
# ========================================================
def worker_task(thread_id):
    """Hàm đại diện cho 1 luồng làm việc. Sẽ lặp lại liên tục đến khi gửi thành công."""
    while True:
        print(f"\n[Luồng {thread_id}] 🟢 BẮT ĐẦU PHIÊN LÀM VIỆC MỚI...")
        my_proxy = None
        if CONFIG["PROXY_LIST"]:
            my_proxy = random.choice(CONFIG["PROXY_LIST"])
        
        email = get_temp_email()
        if email:
            # Gửi SMS
            success = send_with_browser(email, proxy_server=my_proxy, thread_id=str(thread_id))
            
            # Nếu thành công thì thoát vòng lặp (nghỉ ngơi)
            if success:
                print(f"[Luồng {thread_id}] 🏆 HOÀN THÀNH NHIỆM VỤ!")
                break 
            else:
                print(f"[Luồng {thread_id}] 🔁 Thất bại, đang chuẩn bị reset và làm lại từ đầu...")
        
        # Nghỉ một chút trước khi làm lại vòng lặp để tránh bị Block IP
        time.sleep(2)

if __name__ == "__main__":
    threads = CONFIG["NUM_THREADS"]
    
    if threads == 1:
        worker_task(thread_id=1)
    else:
        print(f"🚀 KHỞI ĐỘNG CHẾ ĐỘ ĐA LUỒNG: Mở {threads} trình duyệt cùng lúc...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            for i in range(threads):
                time.sleep(random.uniform(0.5, 2.0))
                executor.submit(worker_task, i + 1)
