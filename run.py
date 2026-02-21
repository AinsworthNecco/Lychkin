# -*- coding: utf-8 -*-
# Script Bot Discord cho VMOS Cloud (Phiên bản Ultimate - Full Uncut)
# Tính năng tích hợp:
# 1. Playwright: Tự động mở Chrome (System), đăng nhập và treo nick.
# 2. Mail API: TEMP-MAIL.IO (Không Proxy, dùng VPN/IP thật toàn bộ).
# 3. Quản lý Config: Token đọc từ file local.
# 4. Anti-Rate Limit: Cơ chế cập nhật tin nhắn Discord chậm (10s/lần).
# 5. Logging: Xuất log chi tiết.
# 6. Sửa lỗi check_buff_status: Debug chi tiết phản hồi API.
# 7. UPDATE: Bypass Captcha Slider bằng Playwright Sync + OpenCV khi gửi OTP.
# 8. UPDATE: Xóa toàn bộ logic Proxy để nhường chỗ cho VPN.
# 9. UPDATE: Nâng cấp lấy mail sang Temp-Mail.io siêu tốc độ.
# 10. UPDATE: Trả về Anti-Detect nguyên bản, soi chính xác trạng thái đếm ngược 59s.
# 11. UPDATE: Phân tách Host_Threads (Đua lấy nick chủ) và Buff_Threads (Cày điểm).

import discord
from discord.ext import commands
import requests
import json
import asyncio
import re
import random
import time
import os
import traceback
import sys
import uuid
import string
import urllib.parse
import urllib3
from collections import defaultdict

# THƯ VIỆN CHO CAPTCHA
import cv2
import numpy as np
import tempfile
import shutil
import base64
import math
import concurrent.futures

# Tắt cảnh báo insecure request
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# THƯ VIỆN BROWSER
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright

# ==============================================================
# ==>> CẤU HÌNH & HẰNG SỐ <<==
# ==============================================================

TOKEN_FILE_NAME = "token.txt"
CODE_FILE_NAME = "CODE.txt"
THUMBNAIL_URL = "https://i.pinimg.com/1200x/c0/d1/59/c0d1591ce31488b9f71313326dcf01f0.jpg"

# CONFIG DÀNH CHO CAPTCHA SOLVER & MULTI-THREADING (DÀNH CHO MÁY MẠNH)
CONFIG = {
    "HOST_THREADS": 3,          # Số luồng đua nhau tạo tài khoản Host
    "BUFF_THREADS": 5,          # Số luồng cày sub-account sau khi đã có Host
    "HEADLESS": True,
    "EXECUTABLE_PATH": "/usr/bin/chromium"
}

# Danh sách User-Agent (Dùng cho VMOS khi call API Login)
USER_AGENTS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0"
]

def get_random_ua():
    return random.choice(USER_AGENTS_LIST)

def random_string(n=10):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))

VIP_MAP = {
    "vip": {"target": 5, "exchange_id": 999},
    "kvip": {"target": 10, "exchange_id": 1000},
    "svip": {"target": 20, "exchange_id": 1001},
    "xvip": {"target": 30, "exchange_id": 1002},
    "mvip": {"target": 40, "exchange_id": 1003}
}

is_inf_running = False

# ==============================================================
# ==>> HÀM LOAD CONFIG <<==
# ==============================================================

def load_local_token():
    print("📂 Đang đọc file token.txt...")
    try:
        if not os.path.exists(TOKEN_FILE_NAME):
            print(f"❌ LỖI: Không tìm thấy file '{TOKEN_FILE_NAME}'!")
            return None
        
        with open(TOKEN_FILE_NAME, 'r', encoding='utf-8') as f:
            token = f.read().strip()
            
        if not token:
            print(f"❌ LỖI: File '{TOKEN_FILE_NAME}' rỗng!")
            return None
            
        print("✅ Đã đọc Token thành công.")
        return token
    except Exception as e:
        print(f"❌ Lỗi đọc token: {e}")
        return None

# ==============================================================
# ==>> LỚP QUẢN LÝ CODE STORAGE (LƯU TRỮ & TRÍCH XUẤT) <<==
# ==============================================================

class CodeStorageManager:
    def __init__(self, filename):
        self.filename = filename

    def load_data(self):
        data = defaultdict(list)
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w', encoding='utf-8') as f:
                    f.write("")
            except:
                pass
            return data
            
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            current_section = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                is_header = False
                for v in VIP_MAP.keys():
                    if line == v.upper():
                        current_section = line
                        is_header = True
                        break
                
                if is_header:
                    continue
                
                if current_section:
                    data[current_section].append(line)
        except:
            pass
        return data

    def save_data(self, data):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                sorted_keys = sorted(data.keys())
                for vip_type in sorted_keys:
                    codes = data[vip_type]
                    if not codes:
                        continue
                    
                    f.write(f"{vip_type}\n")
                    for code in codes:
                        f.write(f"{code}\n")
                    f.write("\n")
            return True
        except:
            return False

    def add_codes(self, new_codes_dict):
        print("💾 Đang lưu Code vào file...")
        data = self.load_data()
        summary = {}
        
        for vip, codes in new_codes_dict.items():
            if not codes:
                continue
            
            vip_upper = vip.upper()
            if vip_upper not in data:
                data[vip_upper] = []
            
            existing_set = set(data[vip_upper])
            added_count = 0
            for c in codes:
                c = c.strip()
                if c and c not in existing_set:
                    data[vip_upper].append(c)
                    existing_set.add(c)
                    added_count += 1
            
            summary[vip_upper] = added_count
            
        self.save_data(data)
        print(f"✅ Đã lưu xong: {summary}")
        return summary

    def pop_codes(self, vip_type, amount):
        data = self.load_data()
        vip_upper = vip_type.upper()
        
        if vip_upper not in data:
            return None, 0
            
        current_list = data[vip_upper]
        if len(current_list) < amount:
            return None, len(current_list)
            
        codes_to_give = current_list[:amount]
        data[vip_upper] = current_list[amount:]
        
        self.save_data(data)
        return codes_to_give, len(data[vip_upper])

code_storage = CodeStorageManager(CODE_FILE_NAME)

# ==============================================================
# ==>> BROWSER GỐC (DÙNG ĐỂ LOGIN TREO ACC) <<==
# ==============================================================

async def open_browser_and_login(email, password):
    print(f"[BROWSER] 🌐 Mở Chromium để treo tài khoản Host...")
    try:
        p = await async_playwright().start()
        
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium", 
            headless=True,
            args=["--guest", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--window-size=400,600", "--window-position=1500,500"]
        )
        context = await browser.new_context(user_agent=get_random_ua())
        page = await context.new_page()
        print(f"[BROWSER] 🔗 Truy cập VMOS...")
        await page.goto("https://cloud.vsphone.com/event/202602", timeout=60000)
        print(f"[BROWSER] ✍️ Login tài khoản Host...")
        await page.wait_for_selector('input[placeholder="Please enter your email address"]', timeout=30000)
        await page.fill('input[placeholder="Please enter your email address"]', email)
        await page.fill('input[placeholder="Please enter your login password"]', password)
        await page.click('button:has-text("Sign in")')
        print(f"[BROWSER] ✅ Tài khoản Host đã được treo trên trình duyệt thành công.")
        return p, browser, page
    except Exception as e:
        print(f"[BROWSER] ❌ Lỗi: {e}")
        return None, None, None

async def close_browser_session(p, browser):
    if browser:
        print(f"[BROWSER] 🛑 Đóng trình duyệt tài khoản Host.")
        try:
            await browser.close()
        except: pass
    if p:
        try:
            await p.stop()
        except: pass

# ==============================================================
# ==>> API VMOS CŨ <<==
# ==============================================================

def safe_request(method, url, **kwargs):
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 20
        
    # Luôn tắt verify SSL để tránh lỗi với proxy/VPN
    if 'verify' not in kwargs:
        kwargs['verify'] = False
    
    try:
        if method.lower() == 'get':
            resp = requests.get(url, **kwargs)
        else:
            resp = requests.post(url, **kwargs)
        
        if resp and "certain foreign ip addresses have been restricted" in resp.text.lower():
            raise requests.exceptions.ConnectionError("IP Restricted by VMOS")
        return resp
    except Exception as e:
        raise e

# ==============================================================
# ==>> TEMP-MAIL.IO LOGIC <<==
# ==============================================================

def get_temp_email():
    """
    Tạo email từ temp-mail.io.
    """
    url = "https://api.internal.temp-mail.io/api/v3/email/new"
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        "Application-Name": "web",
        "Application-Version": "2.4.2",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": ua
    }
    try:
        response = requests.post(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        data = response.json()
        return data.get("email"), None  # Trả về None thay vì token để tương thích logic cũ
    except Exception as e:
        print(f"   [TEMP-MAIL] 🔥 Exception: {e}")
        return None, None

def get_code_from_email(mail_token, email, thread_id="1"):
    if not email:
        return None
    
    url = f"https://api.internal.temp-mail.io/api/v3/email/{email}/messages"
    print(f"[Luồng {thread_id}] ⏳ Bắt đầu quét hộp thư temp-mail.io (Sẽ thử trong vòng 100s)...")
    
    for i in range(20):
        try:
            r = requests.get(url, timeout=15, verify=False)
            if r.status_code == 200:
                messages = r.json()
                if messages:
                    for msg in reversed(messages):
                        body_text = msg.get("body_text", "")
                        if body_text:
                            # Regex tìm đúng 6 số đứng độc lập
                            match = re.search(r"(?<!\d)(\d{6})(?!\d)", body_text)
                            if match:
                                code_found = match.group(1)
                                print(f"[Luồng {thread_id}] 💌 Đã thấy mã OTP: {code_found}")
                                return code_found
        except requests.exceptions.RequestException:
            pass # Bỏ qua lỗi mạng
            
        time.sleep(5)
        
    return None

# ==============================================================
# ==>> HÀM GIẢI CAPTCHA THAY THẾ API GỬI OTP CŨ <<==
# ==============================================================

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

def find_puzzle_gap_raw(bg_path, piece_path, thread_id="1"):
    print(f"[Luồng {thread_id}] 👁️ Đang phân tích ảnh bằng thuật toán Canny Edge...")
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
            
            print(f"[Luồng {thread_id}] ✅ Đã chốt hạ tọa độ! Độ khớp (Confidence): {max_val*100:.1f}%")
            return max(0, target_raw_x), x, y, w, h, max_loc[0], target_raw_y
            
    return max_loc[0], 0, 0, 40, 40, max_loc[0], 0

def feedback_loop_drag(page, start_x, start_y, target_piece_x, thread_id="1"):
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    time.sleep(random.uniform(0.1, 0.2)) 
    
    current_mouse_x = start_x
    
    for _ in range(200): 
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
            print(f"[Luồng {thread_id}] 🎯 Mảnh ghép đã ăn khớp hoàn hảo (Sai số: {distance_left:.2f}px). Chốt sổ!")
            break
            
        if distance_left > 0:
            if distance_left > 40:
                step = random.uniform(6, 12) 
            elif distance_left > 10:
                step = random.uniform(2, 5)
            else:
                step = random.uniform(0.5, 1.5)
            current_mouse_x += step
        else:
            step = random.uniform(0.5, 1.5)
            current_mouse_x -= step
            
        page.mouse.move(current_mouse_x, start_y + random.uniform(-1, 1))
        time.sleep(random.uniform(0.02, 0.04))

    time.sleep(random.uniform(0.4, 0.7)) 
    page.mouse.up()

def auto_drag_slider(page, thread_id="1", stop_event=None):
    print(f"[Luồng {thread_id}] 🤖 Đang tiến hành giải Captcha liên tục...")
        
    attempt = 0
    while True:
        if stop_event and stop_event.is_set():
            print(f"[Luồng {thread_id}] 🛑 Đã nhận tín hiệu dừng, hủy Captcha.")
            return False

        attempt += 1
        if attempt > 10:
            print(f"\n[Luồng {thread_id}] ❌ Fail: Sai quá 10 lần liên tục. Hủy session này để làm lại từ đầu!")
            return False

        print(f"\n[Luồng {thread_id}] 🔄 LẦN THỬ THỨ {attempt}:")
        
        # 1. Kiểm tra trạng thái nút Get Code
        try:
            btn_locator = page.locator("#get-captcha-code")
            btn_text = btn_locator.inner_text(timeout=3000)
            
            # Nếu đang có số (đếm ngược 59s) -> Thành công
            if "s" in btn_text.lower() and any(c.isdigit() for c in btn_text):
                print(f"[Luồng {thread_id}] ✅ Nút đếm ngược ({btn_text.strip()}) xuất hiện! SMS ĐÃ GỬI THÀNH CÔNG.")
                return True
                
            # Nếu hiện Get Code -> Bấm
            if "Get code" in btn_text or "Get Code" in btn_text:
                print(f"[Luồng {thread_id}] 🔎 Tiến hành click nút 'Get code'...")
                btn_locator.click(timeout=3000)
                time.sleep(2)
        except Exception:
            pass

        # 2. Xử lý logic chờ Popup hoặc Loading
        if not page.locator("#aliyunCaptcha-window-popup").is_visible():
            # Kiểm tra xem có đang xoay loading hay đếm ngược không
            try:
                btn_text = page.locator("#get-captcha-code").inner_text(timeout=1000)
                if "s" in btn_text.lower() and any(c.isdigit() for c in btn_text):
                    print(f"[Luồng {thread_id}] ✅ Nút đếm ngược ({btn_text.strip()})! SMS ĐÃ GỬI THÀNH CÔNG.")
                    return True
                if btn_text.strip() == "":
                    print(f"[Luồng {thread_id}] ⏳ Hệ thống đang xử lý (Xoay Loading)... Đợi 3s...")
                    time.sleep(3)
                    continue
            except:
                pass
            time.sleep(1)
            continue
            
        # 3. Tiến hành giải Captcha khi có Popup
        print(f"[Luồng {thread_id}] 🎯 Đã tìm thấy Captcha! Đang tải và phân tích ảnh...")
        time.sleep(0.5) 
        
        bg_locator = page.locator("#aliyunCaptcha-img")
        piece_locator = page.locator("#aliyunCaptcha-puzzle")
        slider_handle = page.locator("#aliyunCaptcha-sliding-slider")
        
        if not bg_locator.is_visible() or not piece_locator.is_visible():
            print(f"[Luồng {thread_id}] ❌ Lỗi hiển thị mảnh ghép Captcha.")
            continue

        bg_url = bg_locator.get_attribute("src")
        piece_url = piece_locator.get_attribute("src")
        
        if not bg_url or not piece_url:
            print(f"[Luồng {thread_id}] ❌ Lỗi không lấy được link ảnh gốc.")
            continue
            
        bg_path = f"raw_bg_{thread_id}.png"
        piece_path = f"raw_piece_{thread_id}.png"
        
        if not download_image(bg_url, bg_path) or not download_image(piece_url, piece_path):
            print(f"[Luồng {thread_id}] ❌ Không thể tải ảnh từ Server.")
            continue

        target_raw_x, raw_x, raw_y, raw_w, raw_h, raw_tgt_x, raw_tgt_y = find_puzzle_gap_raw(bg_path, piece_path, thread_id)
        
        bg_img_raw = cv2.imread(bg_path)
        raw_width = bg_img_raw.shape[1] if bg_img_raw is not None else 1
        
        if os.path.exists(bg_path): os.remove(bg_path)
        if os.path.exists(piece_path): os.remove(piece_path)

        bg_box = bg_locator.bounding_box()
        slider_box = slider_handle.bounding_box()
        
        if bg_box and slider_box:
            scale = bg_box["width"] / raw_width 
            target_piece_x = target_raw_x * scale
            
            print(f"[Luồng {thread_id}] 🎯 Lỗ trống ảnh gốc: {target_raw_x}px | Quãng đường Mảnh Ghép cần đi: {target_piece_x:.2f}px")
            
            if target_piece_x < 10:
                print(f"[Luồng {thread_id}] ⚠️ Lỗi tọa độ (<10px). Đang bấm đổi ảnh mới...")
                try: page.locator("#aliyunCaptcha-btn-refresh").click(timeout=3000)
                except: pass
                time.sleep(1)
                continue

            print(f"[Luồng {thread_id}] 🖱️ Đang giải Captcha (Kéo thanh trượt)...")
            margin_x = slider_box["width"] * 0.2
            margin_y = slider_box["height"] * 0.2
            start_x = slider_box["x"] + random.uniform(margin_x, slider_box["width"] - margin_x)
            start_y = slider_box["y"] + random.uniform(margin_y, slider_box["height"] - margin_y)
            
            feedback_loop_drag(page, start_x, start_y, target_piece_x, thread_id)
            
            print(f"[Luồng {thread_id}] ⏳ Đã kéo xong! Chờ Web xác thực kết quả...")
            time.sleep(2) 
            
            if page.locator("#aliyunCaptcha-window-popup").is_visible():
                print(f"[Luồng {thread_id}] ❌ Fail: Kéo trượt sai tọa độ! Đang đổi ảnh mới...")
                try: page.locator("#aliyunCaptcha-btn-refresh").click(timeout=3000)
                except: pass
                time.sleep(0.5) 
            else:
                print(f"[Luồng {thread_id}] ✅ Khung Captcha đã biến mất! Theo dõi nút Get Code xem có bị chặn WAF không...")
                wait_start = time.time()
                while time.time() - wait_start < 25:
                    if stop_event and stop_event.is_set():
                        return False
                        
                    try:
                        btn_text = page.locator("#get-captcha-code").inner_text(timeout=1000)
                        if "s" in btn_text.lower() and any(c.isdigit() for c in btn_text):
                            print(f"[Luồng {thread_id}] ✅ Đã thấy đếm ngược ({btn_text.strip()})! SMS ĐÃ GỬI THÀNH CÔNG.")
                            return True
                        elif "Get code" in btn_text or "Get Code" in btn_text:
                            print(f"[Luồng {thread_id}] ❌ Bị WAF chặn SMS. Nút đã nhả về 'Get code'. Đang thử lại...")
                            break # Thoát vòng lặp đợi để làm lại Attempt mới
                    except Exception:
                        pass
                    time.sleep(1)

def send_with_browser(email, thread_id="1", stop_event=None):
    print(f"[Luồng {thread_id}] 📨 Bắt đầu với email: {email}")

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

            print(f"[Luồng {thread_id}] 🛡️ Khởi chạy Persistent Context (Sử dụng IP Máy / VPN)...")
            context = p.chromium.launch_persistent_context(**launch_args)
            
            try:
                # SCRIPT ẨN DANH (Y HỆT BẢN HOẠT ĐỘNG TỐT CỦA BẠN)
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
                
                print(f"[Luồng {thread_id}] 🌐 Đang truy cập trang web VMOS...")
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

                print(f"[Luồng {thread_id}] 🔎 Tìm thấy trang web, đang tìm nút 'Sign Up'...")
                page.get_by_text("Sign Up", exact=True).click(timeout=30000)
                time.sleep(1)

                print(f"[Luồng {thread_id}] ✍️ Đang nhập email: {email}")
                email_input = page.locator("input[placeholder='Please enter your email address']").last
                email_input.fill(email)
                time.sleep(0.5)

                box = email_input.bounding_box()
                if box:
                    page.mouse.move(box["x"] + 10, box["y"] + 10, steps=5)
                    time.sleep(0.2)

                is_success = auto_drag_slider(page, thread_id, stop_event)
                
                if is_success:
                    print(f"[Luồng {thread_id}] 🎉 Tự động hóa hoàn tất, đang đóng trình duyệt...")
                else:
                    if stop_event and stop_event.is_set():
                        print(f"[Luồng {thread_id}] 🛑 Đã bị hủy bỏ do luồng khác đã đua thắng.")
                    else:
                        print(f"[Luồng {thread_id}] ❌ Luồng bị gián đoạn do giải Captcha thất bại nhiều lần.")
                    
            except Exception as e:
                if stop_event and stop_event.is_set():
                    pass # Do luồng bị kill ngang
                else:
                    print(f"[Luồng {thread_id}] ❌ Lỗi Timeout tải trang/tìm nút: {e}")
            finally:
                context.close()
    finally:
        try:
            shutil.rmtree(temp_profile_dir, ignore_errors=True)
            print(f"[Luồng {thread_id}] 🧹 Đã dọn dẹp sạch sẽ profile tạm thời.")
        except Exception:
            pass 
            
    return is_success

# ==============================================================
# ==>> VMOS ACTIONS (LOGIN SAU KHI CÓ CODE) <<==
# ==============================================================

def login_vmos(email, code, invite_code=None, user_agent=None):
    ua = user_agent if user_agent else get_random_ua()
    url = "https://api.vsphone.com/vsphone/api/user/login"
    headers = {
        "Content-Type": "application/json", 
        "origin": "https://cloud.vmoscloud.com", 
        "referer": "https://cloud.vmoscloud.com/", 
        "User-Agent": ua, 
        "appversion": "1008424", 
        "clienttype": "web"
    }
    if invite_code:
        headers["channel"] = invite_code
    
    payload = {
        "mobilePhone": email, 
        "loginType": 0, 
        "verifyCode": code, 
        "password": "ba71fb4736613b59be75f9c404b945b1"
    }
    if invite_code:
        payload["channel"] = invite_code

    resp = safe_request("POST", url, headers=headers, json=payload)
    
    if resp and resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 200:
            token = data.get("data", {}).get("token") or resp.headers.get("token") or resp.headers.get("Token")
            
            if token:
                user_info_url = "https://api.vsphone.com/vsphone/api/user/getUserInfo"
                h2 = headers.copy()
                h2["token"] = token
                
                r2 = safe_request("GET", user_info_url, headers=h2)
                
                if r2 and r2.status_code == 200:
                    uid = r2.json().get("data", {}).get("userId")
                    return {"token": token, "userId": str(uid)}
    return None

def trigger_agent_activation(token, userid, headers):
    save_agent_url = "https://api.vsphone.com/vsphone/api/agentUser/saveAgentUser"
    payload = {"name": "VSPhone"}
    try:
        safe_request("POST", save_agent_url, headers=headers, json=payload)
    except Exception: pass
    time.sleep(1)

def check_buff_status(token, userid):
    ua = get_random_ua()
    url = "https://api.vsphone.com/vsphone/api/vcActiveAssets/info"
    headers = {
        "token": token, "userid": str(userid), "Content-Type": "application/json",
        "origin": "https://cloud.vmoscloud.com", "referer": "https://cloud.vmoscloud.com/",
        "User-Agent": ua, "appversion": "1008424", "clienttype": "web"
    }
    for _ in range(2):
        try:
            resp = safe_request("POST", url, headers=headers, json={})
            
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    d_obj = data.get("data") or {}
                    return d_obj.get("assetsNum", 0)
            
            resp = safe_request("GET", url, headers=headers)
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    d_obj = data.get("data") or {}
                    return d_obj.get("assetsNum", 0)
                    
        except Exception:
            pass
        time.sleep(1)
    return 0

def exchange_target_gem(token, userid, target_id):
    ua = get_random_ua()
    url = "https://api.vsphone.com/vsphone/api/vcActiveExchangeGood/gemExchange"
    headers = {
        "token": token, "userid": str(userid), "Content-Type": "application/json",
        "origin": "https://cloud.vsphone.com", "referer": "https://cloud.vsphone.com/",
        "User-Agent": ua, "appversion": "2003004", "clienttype": "web",
        "requestsource": "wechat-miniapp", "suppliertype": "0"
    }
    
    payload = {"id": target_id}
    print(f"[EXCHANGE] 🎁 Mua gói ID {target_id}...")
    for attempt in range(5): 
        try:
            resp = safe_request("POST", url, headers=headers, json=payload)
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    return True
        except: pass
        time.sleep(2)
    return False

def fetch_codes_as_dict(token, userid):
    ua = get_random_ua()
    url = "https://api.vsphone.com/vsphone/api/vcActiveAssetsExchangeLog/list"
    headers = {
        "accept": "application/json, text/plain, */*", "appversion": "2003004",
        "clienttype": "web", "content-type": "application/json",
        "origin": "https://cloud.vsphone.com", "referer": "https://cloud.vsphone.com/",
        "requestsource": "wechat-miniapp", "suppliertype": "0",
        "token": token, "userid": str(userid), "user-agent": ua
    }
    try:
        resp = safe_request("GET", url, headers=headers)
        if not resp or resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("code") != 200:
            return None
        items = data.get("data", [])
        if not items:
            return None

        grouped = defaultdict(list)
        for item in items:
            if not item.get("isActivation", True): 
                vip_type = item.get("configName", "UNKNOWN")
                code = item.get("awardCount", "")
                if code:
                    grouped[vip_type].append(code)
        return grouped
    except: return None

def get_invite_code_vmos(token, userid):
    ua = get_random_ua()
    agent_info_url = "https://api.vsphone.com/vsphone/api/agentUser/agentUserInfo"
    headers = {
        "token": token, "userid": str(userid), "Content-Type": "application/json",
        "origin": "https://cloud.vmoscloud.com", "referer": "https://cloud.vmoscloud.com/",
        "User-Agent": ua, "appversion": "1008424", "clienttype": "web"
    }
    
    trigger_agent_activation(token, userid, headers)

    for attempt in range(3):
        try:
            resp = safe_request("POST", agent_info_url, headers=headers, json={})
            if not resp or resp.status_code != 200:
                resp = safe_request("GET", agent_info_url, headers=headers)
            
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    channel_code = data.get("data", {}).get("channelCode", "")
                    if channel_code:
                        return channel_code
                elif data.get("code") == 500:
                    time.sleep(3)
                    continue
        except: break
    return None

async def task_worker(invite_code=None, update_callback=None, stop_event=None, prefix="W"):
    worker_id = f"{prefix}-{random.randint(1000,9999)}" 
    while True:
        if stop_event and stop_event.is_set(): return None
        
        current_ua = get_random_ua()
        try:
            if update_callback and not stop_event:
                await update_callback(f"🔄 Đang bắt đầu luồng: {worker_id}...")
            
            # LOG STEP 1: Lấy Mail (Temp-mail) 
            print(f"[{worker_id}] 🌐 Get Email (temp-mail.io)...")
            
            email_data = await asyncio.to_thread(get_temp_email)
            email, mail_token = email_data if email_data else (None, None)
            
            if not email:
                await asyncio.sleep(2)
                continue 

            if stop_event and stop_event.is_set(): return None

            if update_callback and not stop_event:
                await update_callback(f"📩 Đang gửi mã OTP về {email} (Qua Trình Duyệt Giải Captcha)...")
            
            # LOG STEP 2: GỬI OTP BẰNG GIẢ LẬP TRÌNH DUYỆT BẮT CAPTCHA
            print(f"[{worker_id}] 📤 Mở Playwright giải Captcha gửi OTP tới {email}...")
            sent = await asyncio.to_thread(send_with_browser, email, worker_id, stop_event)
            
            if not sent:
                if stop_event and not stop_event.is_set():
                    print(f"[{worker_id}] ❌ [SEND-FAIL] Lỗi giải Captcha / Gửi mã.")
                continue
            
            if stop_event and stop_event.is_set(): return None

            if update_callback and not stop_event:
                await update_callback(f"⏳ Đang chờ mã OTP...")
            
            # LOG STEP 3: Lấy Code 
            print(f"[{worker_id}] ⏳ Check inbox (Full Body)...")
            code = await asyncio.to_thread(get_code_from_email, mail_token, email, worker_id)
            
            if not code:
                if stop_event and not stop_event.is_set():
                    print(f"[{worker_id}] ❌ [TIMEOUT] Không thấy code.")
                continue

            if stop_event and stop_event.is_set(): return None

            if update_callback and not stop_event:
                await update_callback(f"🔑 Đang đăng nhập...")
            
            # LOG STEP 4: Login 
            print(f"[{worker_id}] 🔑 Login Code: {code}")
            creds = await asyncio.to_thread(login_vmos, email, code, invite_code, current_ua)
            
            if not creds:
                if stop_event and not stop_event.is_set():
                    print(f"[{worker_id}] ❌ [LOGIN-FAIL] Login thất bại.")
                continue

            print(f"[{worker_id}] ✅ [SUCCESS] {email} -> OK!")
            return {
                "email": email, 
                "password": "NECONECOLYCONECO", 
                "token": creds['token'], 
                "userId": creds['userId']
            }
        except Exception as e:
            await asyncio.sleep(2)
            continue

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        error = error.original
    print(f"❌ LỖI BOT: {error}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command(name="use1")
async def use_code(ctx):
    data = code_storage.load_data()
    embed = discord.Embed(title="📦 KHO CODE DỰ TRỮ", color=discord.Color.gold())
    total_codes = 0
    if not data:
        embed.description = "Kho đang trống trơn! Hãy chạy `!genbuff` để kiếm thêm."
    else:
        desc = "Nhập lệnh chat bên dưới để lấy code:\n`[loại_vip] [số_lượng]`\nVí dụ: `kvip 5`\n\n**Tồn kho hiện tại:**\n"
        for vip, codes in data.items():
            count = len(codes)
            desc += f"- **{vip}**: {count} codes\n"
            total_codes += count
        embed.description = desc

    if THUMBNAIL_URL:
        embed.set_thumbnail(url=THUMBNAIL_URL)
    
    embed.set_footer(text="Bot sẽ đợi lệnh trong 30 giây...")
    panel_msg = await ctx.send(embed=embed)

    if total_codes == 0:
        return

    def check(m): return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
        content = msg.content.strip().lower()
        match = re.match(r"^([a-z]+)\s+(\d+)$", content)
        if match:
            vip_req = match.group(1)
            count_req = int(match.group(2))
            codes, remaining = code_storage.pop_codes(vip_req, count_req)
            if codes is None:
                await ctx.send(f"❌ Không tìm thấy loại VIP `{vip_req.upper()}` trong kho.")
            elif len(codes) < count_req:
                await ctx.send(f"⚠️ Không đủ hàng! Kho chỉ còn **{remaining}** code `{vip_req.upper()}`.")
            else:
                codes_str = "\n".join(codes)
                await ctx.send(f"✅ **Đã lấy {count_req} {vip_req.upper()}** (Còn lại: {remaining}):")
                await ctx.send(f"```\n{codes_str}\n```")
        else:
            await ctx.send("❌ Sai cú pháp. Vui lòng thử lại.")
    except asyncio.TimeoutError:
        await panel_msg.edit(content="⌛ Hết thời gian chờ lệnh `!use`.", embed=None)

@bot.command(name="genstop1")
async def genstop(ctx):
    global is_inf_running
    if is_inf_running:
        is_inf_running = False
        await ctx.send("🛑 **Đã nhận lệnh dừng quá trình vô cực!**")
    else:
        await ctx.send("⚠️ Không có tiến trình vô cực nào đang chạy.")

@bot.command(name="genbuff1")
async def genbuff(ctx, arg1: str = None, arg2: str = None):
    global is_inf_running
    
    try:
        if not arg1 or not arg2:
            await ctx.send("❌ Cú pháp: `!genbuff <số_lượng | inf> <loại_vip | all | all-vip...>`")
            return
        
        vip_type = arg2.lower()
        target_vip_types = []
        
        if vip_type == 'all':
            target_vip_types = list(VIP_MAP.keys())
            display_type = "ALL PACKS"
        elif vip_type.startswith('all-'):
            parts = vip_type.split('-')
            exclusions = parts[1:]
            target_vip_types = [k for k in VIP_MAP.keys() if k not in exclusions]
            if not target_vip_types:
                await ctx.send("❌ Bạn đã trừ hết tất cả các gói!")
                return
            display_type = f"ALL (Trừ: {', '.join([e.upper() for e in exclusions])})"
        elif vip_type in VIP_MAP:
            target_vip_types = [vip_type]
            display_type = vip_type.upper()
        else:
            await ctx.send(f"❌ Loại VIP không hợp lệ!")
            return

        num_buffs = sum(VIP_MAP[t]["target"] for t in target_vip_types)
        exchange_list = [VIP_MAP[t]["exchange_id"] for t in target_vip_types]
        display_type += f" ({num_buffs} BUFF)"
        
        is_inf_mode = (arg1.lower() == "inf")
        num_hosts = 0 if is_inf_mode else int(arg1)
        
        if is_inf_mode:
            is_inf_running = True
            print(f"\n[GENBUFF] BẮT CHẾ ĐỘ VÔ CỰC (INF) - TYPE: {display_type}")
        else:
            print(f"\n[GENBUFF] BẮT ĐẦU CHẾ ĐỘ GIỚI HẠN - {num_hosts} HOST - TYPE: {display_type}")

        host_idx = 1
        
        while True:
            if is_inf_mode and not is_inf_running:
                print("[GENBUFF] Đã dừng vòng lặp vô cực.")
                break
            if not is_inf_mode and host_idx > num_hosts:
                break 

            print(f"\n[GENBUFF] ---> ĐANG XỬ LÝ HOST {host_idx} <---")
            title_text = f"⚙️ Đang tạo tài khoản chủ ({'Vô cực' if is_inf_mode else f'{host_idx}/{num_hosts}'})..."
            init_embed = discord.Embed(title=title_text, color=discord.Color.orange())
            init_embed.description = f"🔄 Đang đua {CONFIG['HOST_THREADS']} luồng để tạo Host..."
            msg = await ctx.send(embed=init_embed)

            # 1. ĐUA LUỒNG (RACING) ĐỂ TẠO TÀI KHOẢN HOST
            print(f"[HOST] 🚀 Bắt đầu tạo Host Account bằng {CONFIG['HOST_THREADS']} luồng đua...")
            stop_host_event = asyncio.Event()
            host_acc_box = []

            async def run_host_racer(idx):
                res = await task_worker(invite_code=None, update_callback=None, stop_event=stop_host_event, prefix=f"H{idx}")
                if res and not stop_host_event.is_set():
                    host_acc_box.append(res)
                    stop_host_event.set()

            racer_tasks = [asyncio.create_task(run_host_racer(i+1)) for i in range(CONFIG["HOST_THREADS"])]
            
            while not stop_host_event.is_set() and any(not t.done() for t in racer_tasks):
                await asyncio.wait(racer_tasks, return_when=asyncio.FIRST_COMPLETED)

            if not host_acc_box:
                await msg.edit(content=f"❌ Không thể tạo tài khoản chủ {host_idx} sau khi đua luồng.", embed=None)
                host_idx += 1
                continue

            host_acc = host_acc_box[0]
            host_token = host_acc['token']
            host_userid = host_acc['userId']

            # 2. KHỞI ĐỘNG BROWSER & LOGIN (ĐỂ TREO ACCOUNT HOST XUYÊN SUỐT)
            init_embed.description = "🌐 Đang mở trình duyệt để treo tài khoản Host..."
            await msg.edit(embed=init_embed)
            
            pw_obj, browser_obj, page_obj = await open_browser_and_login(host_acc['email'], host_acc['password'])

            # 3. LẤY MÃ MỜI CỦA HOST (API)
            init_embed.description = "🔄 Đang lấy mã mời (Invite Code)..."
            await msg.edit(embed=init_embed)
            
            print(f"[HOST] 📨 Đang lấy Invite Code...")
            invite_code = await asyncio.to_thread(get_invite_code_vmos, host_token, host_userid)
            if not invite_code:
                print(f"[HOST] ❌ Không lấy được Invite Code!")
                embed_err = discord.Embed(title=f"⚠️ Lỗi lấy mã mời (Host {host_idx})", description=f"Skip...", color=discord.Color.red())
                await msg.edit(embed=embed_err)
                await close_browser_session(pw_obj, browser_obj)
                host_idx += 1
                continue
            print(f"[HOST] ✅ Invite Code: {invite_code}")

            # 4. CHẠY BUFF CÀY ĐIỂM (ĐA LUỒNG SUB-ACCOUNTS)
            embed_run = discord.Embed(title=f"🚀 Auto-Buff {display_type} Started", color=discord.Color.blue())
            embed_run.add_field(name="👤 Tài Khoản Chủ", value=f"Email: `{host_acc['email']}`", inline=False)
            full_invite_link = f"https://cloud.vsphone.com/event/202602?channel={invite_code}"
            embed_run.add_field(name="🎟️ Link Mời", value=f"{full_invite_link}\n(Mã: `{invite_code}`)", inline=False)
            embed_run.add_field(name="📊 Tiến độ Buff", value=f"Đang chạy {CONFIG['BUFF_THREADS']} luồng Buff...", inline=False)
            if THUMBNAIL_URL:
                embed_run.set_thumbnail(url=THUMBNAIL_URL)
            await msg.edit(embed=embed_run)

            concurrency = CONFIG["BUFF_THREADS"]
            semaphore = asyncio.Semaphore(concurrency)
            
            current_assets_num = 0
            total_success_local = 0
            total_fail = 0
            
            async def protected_worker():
                async with semaphore:
                    return await task_worker(invite_code=invite_code)

            active_tasks = set()
            for _ in range(concurrency):
                active_tasks.add(asyncio.create_task(protected_worker()))
                
            last_update_time = 0
            
            while active_tasks:
                done, active_tasks = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
                
                for task in done:
                    try:
                        res = await task
                        if res:
                            total_success_local += 1
                            current_assets_num = await asyncio.to_thread(check_buff_status, host_token, host_userid)
                        else:
                            total_fail += 1
                    except:
                        total_fail += 1
                    
                    # LOGIC RATE LIMIT: CHỈ UPDATE DISCORD MỖI 10 GIÂY
                    now = time.time()
                    if now - last_update_time > 10:
                        status_text = f"Mục tiêu: **{num_buffs}**\nĐã nhận: **{current_assets_num}/{num_buffs}**\nThành công: **{total_success_local}** | Lỗi: **{total_fail}**"
                        embed_run.set_field_at(2, name="📊 Tiến độ Buff", value=status_text, inline=False)
                        try: 
                            await msg.edit(embed=embed_run)
                            last_update_time = now
                        except discord.HTTPException as e:
                            print(f"⚠️ Discord Rate Limit: {e}. Bỏ qua lần update này.")
                        except Exception: pass
                    
                    if current_assets_num >= num_buffs:
                        for t in active_tasks:
                            t.cancel()
                        active_tasks.clear()
                        break
                    
                    desired_running = min(concurrency, num_buffs - current_assets_num)
                    while len(active_tasks) < desired_running:
                        active_tasks.add(asyncio.create_task(protected_worker()))

            # 5. MUA GÓI & LƯU CODE
            final_code_str = "Không có code nào được lấy."
            if current_assets_num >= num_buffs:
                print(f"[HOST] 🎁 Đủ điều kiện. Bắt đầu đổi quà...")
                embed_run.add_field(name="🎁 Đổi Code", value=f"⏳ Đang đổi quà...", inline=False)
                await msg.edit(embed=embed_run)
                
                for ex_id in exchange_list:
                    await asyncio.to_thread(exchange_target_gem, host_token, host_userid, ex_id)
                
                codes_dict = await asyncio.to_thread(fetch_codes_as_dict, host_token, host_userid)
                
                if codes_dict:
                    await asyncio.to_thread(code_storage.add_codes, codes_dict)
                    all_data = await asyncio.to_thread(code_storage.load_data)
                    lines = []
                    sorted_keys = sorted(all_data.keys(), key=lambda x: (len(x), x))
                    for k in sorted_keys:
                        lines.append(f"{k.upper():<5}: {len(all_data[k])}")
                    
                    if lines:
                        final_code_str = "\n".join(lines)
                    else:
                        final_code_str = "Kho trống."
                
            # 6. ĐÓNG TRÌNH DUYỆT CỦA HOST (Sau khi đã đổi quà xong)
            await close_browser_session(pw_obj, browser_obj)

            # 7. HOÀN TẤT
            embed_run.title = "✅ Hoàn Tất Buff"
            embed_run.description = None 
            embed_run.clear_fields() 
            
            embed_run.add_field(name="Email", value=f"`{host_acc['email']}`", inline=True)
            embed_run.add_field(name="Password", value=f"`{host_acc['password']}`", inline=True)
            embed_run.add_field(name="Tổng Code trong kho", value=f"```yaml\n{final_code_str}\n```", inline=False)
            
            embed_run.color = discord.Color.green()
            embed_run.set_footer(text=f"Host: {'Vô cực' if is_inf_mode else f'{host_idx}/{num_hosts}'}")

            await msg.edit(embed=embed_run)
            await ctx.send(f"{ctx.author.mention} ✅ Đã xong Host {host_idx}!")
            
            host_idx += 1
            
    except Exception as e:
        print(f"Lỗi Critical trong quá trình genbuff: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("==========================================")
    print("🚀 VMOS BOT ULTIMATE - PHIÊN BẢN 1.10 - HOST RACING & BUFF CONCURRENCY")
    print("==========================================")
    print("🚀 Đang khởi động Bot...")
    token_local = load_local_token()
    
    if not token_local:
        print("❌ KHÔNG THỂ KHỞI ĐỘNG: Thiếu Token trong file 'token.txt'.")
    else:
        print(f"🚀 Bot Pro Ultimate + Captcha Bypass đang chạy...")
        while True:
            try:
                bot.run(token_local)
            except Exception as e:
                print(f"⚠️ Bot bị crash: {e}")
                time.sleep(5)
            except KeyboardInterrupt:
                print("🛑 Đã dừng thủ công.")
                break
