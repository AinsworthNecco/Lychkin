# -*- coding: utf-8 -*-
# Script Bot Discord cho VMOS Cloud (Phiên bản Ultimate - Full Uncut)
# Tính năng tích hợp:
# 1. Playwright: Tự động mở Chrome giải Captcha để lấy code (Không Proxy).
# 2. Mail API: MAIL.TM (Lấy mã qua Request API, Dùng Proxy toàn bộ).
# 3. Quản lý Config: Token đọc từ file local, Proxy tải từ file local proxies.txt.
# 4. Anti-Rate Limit: Cơ chế cập nhật tin nhắn Discord chậm (10s/lần).
# 5. Logging: Xuất log chi tiết từng bước.
# 6. Luồng: Giới hạn số luồng.
# 7. Sửa lỗi check_buff_status: Debug chi tiết phản hồi API.

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
import base64
import math
from collections import defaultdict

# THƯ VIỆN MỚI CHO TRÌNH DUYỆT VÀ CAPTCHA
# pip install playwright opencv-python numpy requests
from playwright.async_api import async_playwright
import cv2
import numpy as np

# Tắt cảnh báo insecure request (do dùng verify=False với Proxy)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================
# ==>> CẤU HÌNH HỆ THỐNG (TÙY CHỈNH TẠI ĐÂY) <<==
# ==============================================================
CONFIG = {
    "URL_SIGNUP": "https://cloud.vsphone.com/?channel=web",
    "NUM_THREADS": 10,           # Giới hạn số luồng
    "HEADLESS": False,          # Chế độ ẩn trình duyệt
    "CHROMIUM_PATH": "/usr/bin/chromium", # Đường dẫn Chromium trên Debian/Termux (Để "" nếu chạy Windows dùng channel chrome)
}

# ==============================================================
# ==>> CẤU HÌNH & HẰNG SỐ CŨ <<==
# ==============================================================

TOKEN_FILE_NAME = "token.txt"
PROXY_URL = "https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/info"
HOST_PROXY_URL = "https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/info1"
CODE_FILE_NAME = "code1.txt"
THUMBNAIL_URL = "https://i.pinimg.com/1200x/c0/d1/59/c0d1591ce31488b9f71313326dcf01f0.jpg"

MAIL_TM_BASE = "https://api.mail.tm"

# Danh sách User-Agent (Dùng cho VMOS)
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

def load_proxies_from_url(url):
    print(f"📂 Đang tải proxy từ URL {url} ...")
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            text = response.text.strip()
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            print(f"✅ Đã tải thành công {len(lines)} proxies từ URL.")
            return lines
        else:
            print(f"❌ LỖI: Không thể tải proxy từ URL, mã lỗi {response.status_code}!")
            return []
    except Exception as e:
        print(f"❌ Lỗi tải proxy từ URL: {e}")
        return []

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
# ==>> LỚP QUẢN LÝ PROXY <<==
# ==============================================================

class ProxyManager:
    def __init__(self, proxy_list=None):
        self.proxies = []
        self.bad_proxies = set()
        if proxy_list:
            self.load_proxies_from_list(proxy_list)
    
    def parse_proxy(self, line):
            line = line.strip()
            if not line or line.startswith('#'):
                return None
                
            # Tách scheme nếu có (http, https, socks4, socks5), nếu không mặc định là http
            scheme = "http"
            if "://" in line:
                scheme, line = line.split("://", 1)
                
            try:
                # Format: User:Pass@IP:Port
                if '@' in line:
                    auth, ip_port = line.split('@', 1)
                    user, pwd = auth.split(':', 1)
                    
                    # Encode ký tự đặc biệt trong user/pass
                    user = urllib.parse.quote(user)
                    pwd = urllib.parse.quote(pwd)
                    
                    return f"{scheme}://{user}:{pwd}@{ip_port}"
                    
                # Format: IP:Port:User:Pass
                parts = line.split(':')
                if len(parts) >= 4:
                    ip = parts[0]
                    port = parts[1]
                    user = urllib.parse.quote(parts[2])
                    # Nhỡ password chứa dấu : thì phải join lại
                    pwd = urllib.parse.quote(':'.join(parts[3:])) 
                    
                    return f"{scheme}://{user}:{pwd}@{ip}:{port}"
                    
                # Format: IP:Port (Không có auth)
                if len(parts) == 2:
                    return f"{scheme}://{line}"
                    
                return f"{scheme}://{line}"
            except Exception as e:
                print(f"❌ Lỗi xử lý proxy dòng '{line}': {e}")
                return None

    def load_proxies_from_list(self, raw_lines):
        for line in raw_lines:
            p = self.parse_proxy(line)
            if p:
                self.proxies.append(p)
        print(f"[PROXY] Tổng số proxy đã nạp: {len(self.proxies)}")

    def get_live_proxy(self):
        available = [p for p in self.proxies if p not in self.bad_proxies]
        if not available:
            return None
        return random.choice(available)

    def mark_bad(self, proxy):
        if proxy and proxy not in self.bad_proxies:
            self.bad_proxies.add(proxy)

    def reset_bad_proxies(self):
        print(f"[PROXY] ♻️ Reset {len(self.bad_proxies)} proxy lỗi.")
        self.bad_proxies.clear()

    def get_count(self):
        return len(self.proxies)
        
    def get_live_count(self):
        return len(self.proxies) - len(self.bad_proxies)

proxy_manager = ProxyManager([])
host_proxy_manager = ProxyManager([])

# ========================================================
# ==>> HÀM TẢI/LƯU ẢNH GỐC (PLAYWRIGHT CAPTCHA) <<==
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
# ==>> HÀM XỬ LÝ ẢNH CHUẨN XÁC (PLAYWRIGHT CAPTCHA) <<==
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
# ==>> HÀM RÊ CHUỘT DÒ ĐƯỜNG (PLAYWRIGHT CAPTCHA) ASYNC <<==
# ========================================================
async def feedback_loop_drag_async(page, start_x, start_y, target_piece_x, initial_green_x, thread_id="1"):
    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.1, 0.2)) 
    
    current_mouse_x = start_x
    
    for _ in range(200): 
        piece_left_str = await page.evaluate("""() => {
            let el = document.getElementById('aliyunCaptcha-puzzle');
            if (!el) return '0';
            let left = el.style.left;
            if (left && left !== '0px' && left !== '0') return left;
            let transform = el.style.transform;
            if (transform && transform.includes('translate')) {
                let match = transform.match(/translate[X]?\\((.+?)px/);
                if (match) return match[1];
            }
            return left || '0';
        }""")
        
        piece_left = float(piece_left_str.replace('px', '').strip()) if piece_left_str else 0.0
        
        try:
            await page.evaluate(f"let g = document.getElementById('vmos-green-box'); if(g) g.style.left = '{(initial_green_x + piece_left)}px';")
        except:
            pass
        
        distance_left = target_piece_x - piece_left
        
        if abs(distance_left) <= 1.0:
            print(f"[Luồng {thread_id}] 🎯 Mảnh ghép khớp hoàn hảo. Chốt sổ!")
            break
            
        if distance_left > 0:
            if distance_left > 40:
                step = random.uniform(8, 15)
            elif distance_left > 10:
                step = random.uniform(3, 6)
            else:
                step = random.uniform(0.5, 2)
            current_mouse_x += step
        else:
            step = random.uniform(0.5, 2)
            current_mouse_x -= step
            
        await page.mouse.move(current_mouse_x, start_y + random.uniform(-1, 1))
        await asyncio.sleep(random.uniform(0.01, 0.02))

    await asyncio.sleep(random.uniform(0.4, 0.7)) 
    await page.mouse.up()

# ========================================================
# ==>> HÀM GIẢI CAPTCHA LIÊN TỤC (PLAYWRIGHT) ASYNC <<==
# ========================================================
async def auto_drag_slider_async(page, thread_id="1"):
    print(f"[Luồng {thread_id}] 🤖 Đang tiến hành giải Captcha liên tục...")
    
    data_dir = os.path.join(os.getcwd(), "data", str(thread_id))
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    attempt = 0
    MAX_ATTEMPTS = 15 # Tăng số lần thử lên vì thời gian lặp nhanh hơn khi gặp lỗi
    
    while True:
        if attempt >= MAX_ATTEMPTS:
            print(f"[Luồng {thread_id}] ❌ Hủy luồng Playwright: Đã thất bại {MAX_ATTEMPTS} lần liên tiếp. Lý do có thể: Giải sai lệch liên tục, web không tải được captcha, hoặc IP đã bị chặn cứng.")
            return False

        get_code_btn = page.get_by_text("Get code", exact=True)
        is_btn_visible = await get_code_btn.is_visible()

        if not is_btn_visible:
            print(f"\n[Luồng {thread_id}] ⏳ Nút 'Get code' đã biến mất! Chờ xác nhận Retrieve (tối đa 200s)...")
            # Đợi tối đa 200 giây, check nếu hiện chữ retrieve đếm ngược
            for i in range(200):
                content = await page.content()
                if "Retrieve" in content:
                    print(f"[Luồng {thread_id}] ✅ Đã thấy chữ 'Retrieve'. SMS ĐÃ GỬI THÀNH CÔNG!")
                    return True
                await asyncio.sleep(1)
            
            print(f"[Luồng {thread_id}] ❌ Chờ 200s không thấy Retrieve, xác nhận thất bại.")
            return False
            
        attempt += 1
        print(f"\n[Luồng {thread_id}] 🔄 LẦN THỬ THỨ {attempt}/{MAX_ATTEMPTS}:")
        try:
            # Xử lý đóng thông báo lỗi nếu có sẵn trên màn hình
            error_popup = page.get_by_text("Failed to load the captcha component")
            if await error_popup.is_visible():
                try:
                    await page.get_by_text("OK", exact=True).click(timeout=1000)
                except: pass
                await asyncio.sleep(0.5)

            if not await page.locator("#aliyunCaptcha-window-popup").is_visible():
                print(f"[Luồng {thread_id}] 👉 Đang thử bấm nút 'Get code'...")
                try:
                    await get_code_btn.click(timeout=3000)
                    await asyncio.sleep(1.0) # Rút ngắn từ 2s -> 1s để lặp nhanh hơn
                except Exception:
                    pass
            
            # Kiểm tra lại xem nó có văng lỗi ngay sau khi bấm không
            if await error_popup.is_visible():
                print(f"[Luồng {thread_id}] ⚠️ Proxy yếu: Lỗi 'Failed to load captcha'. Bấm OK & thử lại liền...")
                try:
                    await page.get_by_text("OK", exact=True).click(timeout=1000)
                except: pass
                await asyncio.sleep(0.5)
                continue
            
            if not await page.locator("#aliyunCaptcha-window-popup").is_visible():
                print(f"[Luồng {thread_id}] ⚠️ Lỗi: Không hiện popup Captcha. Đang thử lại...")
                await asyncio.sleep(1.0) # Rút ngắn từ 2s -> 1s
                continue
                
            await asyncio.sleep(1.0) 
            
            bg_locator = page.locator("#aliyunCaptcha-img")
            piece_locator = page.locator("#aliyunCaptcha-puzzle")
            slider_handle = page.locator("#aliyunCaptcha-sliding-slider")
            
            if not await bg_locator.is_visible() or not await piece_locator.is_visible():
                print(f"[Luồng {thread_id}] ⚠️ Lỗi: Popup Captcha có nhưng không hiển thị ảnh.")
                continue

            bg_url = await bg_locator.get_attribute("src")
            piece_url = await piece_locator.get_attribute("src")
            
            if not bg_url or not piece_url:
                print(f"[Luồng {thread_id}] ⚠️ Lỗi: Không trích xuất được link URL của ảnh.")
                continue
                
            bg_path = os.path.join(data_dir, "raw_bg.png")
            piece_path = os.path.join(data_dir, "raw_piece.png")
            
            success_bg = await asyncio.to_thread(download_image, bg_url, bg_path)
            success_piece = await asyncio.to_thread(download_image, piece_url, piece_path)

            if not success_bg or not success_piece:
                print(f"[Luồng {thread_id}] ⚠️ Lỗi: Tải ảnh từ URL thất bại.")
                continue

            # 2. TÍNH TOÁN OPENCV
            res = await asyncio.to_thread(find_puzzle_gap_raw, bg_path, piece_path, thread_id)
            target_raw_x, raw_x, raw_y, raw_w, raw_h, raw_tgt_x, raw_tgt_y = res
            
            bg_img_raw = await asyncio.to_thread(cv2.imread, bg_path)
            raw_width = bg_img_raw.shape[1] if bg_img_raw is not None else 1
            
            if os.path.exists(bg_path): os.remove(bg_path)
            if os.path.exists(piece_path): os.remove(piece_path)

            # 3. QUY ĐỔI TỶ LỆ & VẼ LÊN TRÌNH DUYỆT
            bg_box = await bg_locator.bounding_box()
            slider_box = await slider_handle.bounding_box()
            
            if bg_box and slider_box:
                scale = bg_box["width"] / raw_width 
                
                target_piece_x = target_raw_x * scale
                
                print(f"[Luồng {thread_id}] 🎯 Quãng đường Mảnh Ghép cần đi: {target_piece_x:.2f}px")
                
                if target_piece_x < 10:
                    print(f"[Luồng {thread_id}] ⚠️ Lỗi: Mảnh ghép sát lề (< 10px), nguy cơ bot cao. Đổi ảnh...")
                    await page.locator("#aliyunCaptcha-btn-refresh").click()
                    await asyncio.sleep(1)
                    continue

                if raw_w > 0:
                    await page.evaluate(f"""
                        () => {{
                            document.querySelectorAll('.vmos-debug').forEach(e => e.remove());
                            const imgBox = document.querySelector('#aliyunCaptcha-img-box');
                            if (!imgBox) return;
                            imgBox.style.position = 'relative';
                            
                            const createBox = (id, x, y, w, h, color) => {{
                                let box = document.createElement('div');
                                box.id = id; box.className = 'vmos-debug'; box.style.position = 'absolute';
                                box.style.left = x + 'px'; box.style.top = y + 'px';
                                box.style.width = w + 'px'; box.style.height = h + 'px';
                                box.style.border = '3px solid ' + color; box.style.boxShadow = '0 0 8px ' + color;
                                box.style.zIndex = '9999999'; box.style.pointerEvents = 'none'; 
                                imgBox.appendChild(box);
                            }};
                            
                            createBox('vmos-green-box', {raw_x * scale}, {raw_y * scale}, {raw_w * scale}, {raw_h * scale}, '#00ff00');
                            createBox('vmos-red-box', {raw_tgt_x * scale}, {raw_tgt_y * scale}, {raw_w * scale}, {raw_h * scale}, '#ff0000');
                        }}
                    """)
                    await asyncio.sleep(1.0) 

                # 4. THỰC HIỆN RÊ CHUỘT DÒ ĐƯỜNG
                margin_x = slider_box["width"] * 0.2
                margin_y = slider_box["height"] * 0.2
                start_x = slider_box["x"] + random.uniform(margin_x, slider_box["width"] - margin_x)
                start_y = slider_box["y"] + random.uniform(margin_y, slider_box["height"] - margin_y)
                
                initial_green_x = raw_x * scale
                await feedback_loop_drag_async(page, start_x, start_y, target_piece_x, initial_green_x, thread_id)
                
                print(f"[Luồng {thread_id}] ⏳ Chờ Web xác thực kết quả...")
                await asyncio.sleep(3) 
                
                await page.evaluate("() => { document.querySelectorAll('.vmos-debug').forEach(e => e.remove()); }")

                if await page.locator("#aliyunCaptcha-window-popup").is_visible():
                    print(f"[Luồng {thread_id}] ⚠️ Bị WAF từ chối (Giải sai lệch tọa độ hoặc bị quét Bot)! Đang bấm đổi ảnh mới...")
                    try:
                        refresh_btn = page.locator("#aliyunCaptcha-btn-refresh")
                        if await refresh_btn.is_visible():
                            await refresh_btn.click()
                    except:
                        pass
                await asyncio.sleep(1) 
        
        except Exception as e:
             print(f"[Luồng {thread_id}] ⚠️ Lỗi ngoại lệ trong lúc giải Captcha: {e}")
             await asyncio.sleep(2)

# ========================================================
# ==>> HÀM MỞ TRÌNH DUYỆT ĐỂ GỬI CODE (DÙNG PROXY TỪ proxies1.txt) <<==
# ========================================================
async def async_send_with_browser(email, worker_id="1", proxy_str=None):
    proxy_short = proxy_str.split('@')[-1] if proxy_str and '@' in proxy_str else proxy_str or "NO-PROXY"
    print(f"[Luồng {worker_id}] 🌐 [PROXY1: {proxy_short}] Mở Playwright để yêu cầu gửi code SMS cho: {email}")

    user_data_dir = os.path.join(os.getcwd(), "data", str(worker_id))
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)

    p = await async_playwright().start()
    try:
        proxy_config = None
        if proxy_str:
            parsed = urllib.parse.urlparse(proxy_str)
            proxy_config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
            if parsed.username and parsed.password:
                proxy_config["username"] = urllib.parse.unquote(parsed.username)
                proxy_config["password"] = urllib.parse.unquote(parsed.password)

        launch_args = {
            "user_data_dir": user_data_dir,
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
                '--disable-dev-shm-usage', # Chống lỗi sập RAM trên Linux/Termux
                '--disable-gpu'
            ]
        }
        
        # Nếu cấu hình có CHROMIUM_PATH, ưu tiên xài executable_path (dành cho Debian Termux)
        # Nếu không có (chạy trên Windows), cứ mặc định xài channel=chrome
        if CONFIG.get("CHROMIUM_PATH"):
            launch_args["executable_path"] = CONFIG["CHROMIUM_PATH"]
        else:
            launch_args["channel"] = "chrome" 
            
        if proxy_config:
            launch_args["proxy"] = proxy_config
        
        print(f"[Luồng {worker_id}] 🛡️ Khởi chạy Persistent Context (Chống bot)...")
        context = await p.chromium.launch_persistent_context(**launch_args)
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
        """)
        
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"[Luồng {worker_id}] 🔗 Truy cập trang Sign Up...")
        await page.goto(CONFIG["URL_SIGNUP"], wait_until="networkidle")

        print(f"[Luồng {worker_id}] 🖱️ Bấm nút Sign Up")
        await page.get_by_text("Sign Up", exact=True).click()
        await asyncio.sleep(1)

        print(f"[Luồng {worker_id}] ⌨️ Điền email: {email}")
        email_input = page.locator("input[placeholder='Please enter your email address']").last
        await email_input.fill(email)
        await asyncio.sleep(0.5)

        box = await email_input.bounding_box()
        if box:
            await page.mouse.move(box["x"] + 10, box["y"] + 10, steps=5)
            await asyncio.sleep(0.5)

        # Chạy logic tự động kéo Captcha
        success = await auto_drag_slider_async(page, worker_id)
        
        print(f"[Luồng {worker_id}] 🎉 Quá trình Playwright hoàn tất, đang đóng...")
        await context.close()
        return success
    except Exception as e:
        print(f"[Luồng {worker_id}] ❌ Lỗi Playwright: {e}")
        return False
    finally:
        await p.stop()

# ==============================================================
# ==>> BROWSER HOST (TREO ACC CHỦ CŨA BẠN - ĐA LUỒNG) <<==
# ==============================================================

async def single_browser_login(email, password, proxy_str):
    start_time = time.time()
    p = None
    browser = None
    proxy_short = proxy_str.split('@')[-1] if proxy_str and '@' in proxy_str else proxy_str
    try:
        print(f"[BROWSER HOST] 🔄 Khởi tạo tab với proxy: {proxy_short}")
        p = await async_playwright().start()
        
        proxy_config = None
        if proxy_str:
            parsed = urllib.parse.urlparse(proxy_str)
            proxy_config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
            if parsed.username and parsed.password:
                proxy_config["username"] = urllib.parse.unquote(parsed.username)
                proxy_config["password"] = urllib.parse.unquote(parsed.password)
        
        launch_args = {
            "headless": CONFIG["HEADLESS"], 
            "proxy": proxy_config,
            "args": [
                "--guest", 
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage", # Tối ưu Linux/Termux
                "--disable-gpu",
                "--window-size=400,600", 
                "--window-position=1500,500",
                "--disable-blink-features=AutomationControlled" 
            ]
        }
        
        # Tương tự gửi code, fallback channel=chrome cho PC nếu ko có CHROMIUM_PATH
        if CONFIG.get("CHROMIUM_PATH"):
            launch_args["executable_path"] = CONFIG["CHROMIUM_PATH"]
        else:
            launch_args["channel"] = "chrome"

        browser = await p.chromium.launch(**launch_args)
        
        context = await browser.new_context()
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
        """)
        
        page = await context.new_page()
        # Đợi tối đa 30s để load trang nếu mạng yếu
        await page.goto("https://cloud.vsphone.com/event/202602", timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_selector('input[placeholder="Please enter your email address"]', timeout=15000)
        await page.fill('input[placeholder="Please enter your email address"]', email)
        await page.fill('input[placeholder="Please enter your login password"]', password)
        await page.click('button:has-text("Sign in")')
        
        await asyncio.sleep(2)
        print(f"[BROWSER HOST] ✅ Proxy {proxy_short} đăng nhập THÀNH CÔNG!")
        return p, browser, page, proxy_str
        
    except asyncio.CancelledError:
        print(f"[BROWSER HOST] 🛑 Hủy tab proxy {proxy_short} (Đã có tab khác win).")
        if browser:
            try: await browser.close()
            except: pass
        if p:
            try: await p.stop()
            except: pass
        raise
    except Exception as e:
        # In trực tiếp mã lỗi nguyên thủy (ví dụ: ERR_PROXY_CONNECTION_FAILED) ra để dễ nhận biết lý do chết nhanh
        err_msg = str(e).split('\n')[0] if e else "Unknown Error"
        print(f"[BROWSER HOST] ❌ Tab proxy {proxy_short} lỗi (Proxy die/từ chối): {err_msg}")
        
        # Bắt buộc đợi đủ 30 giây mới đóng tab
        elapsed = time.time() - start_time
        if elapsed < 30.0:
            wait_time = 30.0 - elapsed
            print(f"[BROWSER HOST] ⏳ Ép tab {proxy_short} đợi thêm {wait_time:.1f}s cho đủ 30s...")
            try:
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                pass
                
        if browser:
            try: await browser.close()
            except: pass
        if p:
            try: await p.stop()
            except: pass
        return None

async def task_wrapper(email, password, proxy_str):
    try:
        # Tăng timeout tổng lên 35s để code bên trong có đủ thời gian ép đợi 30s mà không bị văng Exception quá sớm
        return await asyncio.wait_for(single_browser_login(email, password, proxy_str), timeout=35.0)
    except asyncio.TimeoutError:
        proxy_short = proxy_str.split('@')[-1] if proxy_str and '@' in proxy_str else proxy_str
        print(f"[BROWSER HOST] ⏱️ Tab proxy {proxy_short} treo quá thời gian cho phép -> Tắt mở lại!")
        return None
    except Exception:
        return None

async def open_browser_and_login_concurrent(email, password):
    print(f"[BROWSER HOST] 🌐 Bắt đầu duy trì 3 luồng trình duyệt để đăng nhập Acc chủ...")
    tasks = set()
    
    while True:
        while len(tasks) < 3: # Đã giảm xuống 3 luồng
            p_str = host_proxy_manager.get_live_proxy()
            if not p_str:
                if len(tasks) == 0:
                    await asyncio.sleep(5)
                    p_str = host_proxy_manager.get_live_proxy()
                    if not p_str:
                        break
                else:
                    break
            if p_str:
                tasks.add(asyncio.create_task(task_wrapper(email, password, p_str)))
        
        if not tasks:
            print(f"[BROWSER HOST] ❌ Không có luồng nào chạy (Hết proxy cho host).")
            return None, None, None, None
            
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        for t in done:
            tasks.remove(t)
            res = t.result()
            if res: # Success
                print(f"[BROWSER HOST] 🎉 Đã chốt 1 tab thành công, tiến hành đóng các tab còn lại...")
                for p_task in pending:
                    p_task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                return res[0], res[1], res[2], res[3]

async def close_browser_session(p, browser):
    if browser:
        print(f"[BROWSER HOST] 🛑 Đóng trình duyệt Host.")
        try:
            await browser.close()
        except: pass
    if p:
        try:
            await p.stop()
        except: pass

# ==============================================================
# ==>> API VMOS & REQUEST NETWORK <<==
# ==============================================================

def safe_request(method, url, proxy=None, **kwargs):
    # Cấu hình Proxy chuẩn cho requests
    proxies_dict = None
    if proxy:
        proxies_dict = {
            "http": proxy,
            "https": proxy
        }

    if 'timeout' not in kwargs:
        kwargs['timeout'] = 20
        
    # Luôn tắt verify SSL để tránh lỗi với proxy
    if 'verify' not in kwargs:
        kwargs['verify'] = False
    
    try:
        if method.lower() == 'get':
            resp = requests.get(url, proxies=proxies_dict, **kwargs)
        else:
            resp = requests.post(url, proxies=proxies_dict, **kwargs)
        
        if resp and "certain foreign ip addresses have been restricted" in resp.text.lower():
            raise requests.exceptions.ConnectionError("IP Restricted by VMOS")
        return resp
    except Exception as e:
        raise e

# ==============================================================
# ==>> MAIL.TM LOGIC (DÙNG PROXY HOÀN TOÀN TẠO & CHECK MAIL) <<==
# ==============================================================

def get_temp_email(proxy):
    """
    Tạo email từ Mail.tm (DÙNG PROXY, VERIFY=FALSE).
    """
    proxies_dict = None
    if proxy:
        proxies_dict = {
            "http": proxy,
            "https": proxy
        }

    try:
        # 1. Lấy Domain
        r = requests.get(f"{MAIL_TM_BASE}/domains", proxies=proxies_dict, timeout=20, verify=False)
        
        if r.status_code != 200:
            print(f"   [MAIL-TM] ❌ Lỗi Domain: {r.status_code}")
            return None, None
            
        domains_data = r.json()
        if "hydra:member" not in domains_data or not domains_data["hydra:member"]:
             print(f"   [MAIL-TM] ❌ Không lấy được domain member.")
             return None, None

        domain = domains_data["hydra:member"][0]["domain"]
        
        # Tạo thông tin ngẫu nhiên
        email = f"{random_string()}@{domain}"
        password = "NECONECOLYCONECO"
        
        # 2. Tạo Account
        acc_payload = {
            "address": email,
            "password": password
        }
        r_acc = requests.post(f"{MAIL_TM_BASE}/accounts", json=acc_payload, proxies=proxies_dict, timeout=20, verify=False)
        
        if r_acc.status_code not in [200, 201]:
            print(f"   [MAIL-TM] ❌ Lỗi tạo Acc: {r_acc.status_code} {r_acc.text}")
            return None, None
            
        # 3. Lấy Token
        r_token = requests.post(f"{MAIL_TM_BASE}/token", json=acc_payload, proxies=proxies_dict, timeout=20, verify=False)
        
        if r_token.status_code == 200:
            token = r_token.json().get("token")
            return email, token
        else:
            print(f"   [MAIL-TM] ❌ Lỗi Token: {r_token.status_code}")
            
    except Exception as e:
        print(f"   [MAIL-TM] 🔥 Exception: {e}")
        raise e
        
    return None, None

def get_code_from_email(mail_token, email, proxy):
    """
    Dùng API requests (CÓ PROXY) để check inbox và lấy mã 6 số.
    """
    if not mail_token:
        return None
    
    proxies_dict = None
    if proxy:
        proxies_dict = {
            "http": proxy,
            "https": proxy
        }

    headers = {
        "Authorization": f"Bearer {mail_token}"
    }
    
    for _ in range(20):
        try:
            r = requests.get(f"{MAIL_TM_BASE}/messages", headers=headers, proxies=proxies_dict, timeout=20, verify=False)
            
            if r.status_code == 200:
                data = r.json()
                if data.get("hydra:totalItems", 0) > 0:
                    msg = data["hydra:member"][0]
                    
                    # QUÉT TOÀN BỘ NỘI DUNG (Subject, Intro, HTML Body)
                    msg_id = msg.get("id")
                    
                    # Gọi chi tiết tin nhắn để lấy HTML
                    r_detail = requests.get(f"{MAIL_TM_BASE}/messages/{msg_id}", headers=headers, proxies=proxies_dict, timeout=20, verify=False)
                    
                    full_content = ""
                    if r_detail.status_code == 200:
                        detail = r_detail.json()
                        full_content = str(detail.get("html", "")) + " " + str(detail.get("text", "")) + " " + str(detail.get("bodyHtmlContent", ""))
                    else:
                        # Fallback nếu không gọi được detail
                        full_content = str(msg.get("subject", "")) + " " + str(msg.get("intro", ""))
                    
                    match = re.search(r"\b(\d{6})\b", full_content)
                    if match:
                        return match.group(1)

        except:
            pass
        time.sleep(3)
    return None

# ==============================================================
# ==>> VMOS ACTIONS <<==
# ==============================================================

def login_vmos(email, code, proxy, invite_code=None, user_agent=None):
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

    resp = safe_request("POST", url, proxy, headers=headers, json=payload)
    
    if resp and resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 200:
            token = data.get("data", {}).get("token") or resp.headers.get("token") or resp.headers.get("Token")
            
            if token:
                user_info_url = "https://api.vsphone.com/vsphone/api/user/getUserInfo"
                h2 = headers.copy()
                h2["token"] = token
                
                r2 = safe_request("GET", user_info_url, proxy, headers=h2)
                
                if r2 and r2.status_code == 200:
                    uid = r2.json().get("data", {}).get("userId")
                    return {"token": token, "userId": str(uid)}
    return None

def trigger_agent_activation(token, userid, proxy, headers):
    save_agent_url = "https://api.vsphone.com/vsphone/api/agentUser/saveAgentUser"
    payload = {"name": "VSPhone"}
    try:
        safe_request("POST", save_agent_url, proxy, headers=headers, json=payload)
    except Exception: pass
    time.sleep(1)

def check_buff_status(token, userid, proxy):
    ua = get_random_ua()
    url = "https://api.vsphone.com/vsphone/api/vcActiveAssets/info"
    headers = {
        "token": token, "userid": str(userid), "Content-Type": "application/json",
        "origin": "https://cloud.vmoscloud.com", "referer": "https://cloud.vmoscloud.com/",
        "User-Agent": ua, "appversion": "1008424", "clienttype": "web"
    }
    for _ in range(2):
        try:
            resp = safe_request("POST", url, proxy, headers=headers, json={})
            
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    d_obj = data.get("data") or {}
                    return d_obj.get("assetsNum", 0)
            
            resp = safe_request("GET", url, proxy, headers=headers)
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    d_obj = data.get("data") or {}
                    return d_obj.get("assetsNum", 0)
                    
        except Exception as e:
            pass
        time.sleep(1)
    return 0

def exchange_target_gem(token, userid, proxy, target_id):
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
            resp = safe_request("POST", url, proxy, headers=headers, json=payload)
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    return True
        except: pass
        time.sleep(2)
    return False

def fetch_codes_as_dict(token, userid, proxy):
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
        resp = safe_request("GET", url, proxy, headers=headers)
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

def get_invite_code_vmos(token, userid, proxy):
    ua = get_random_ua()
    agent_info_url = "https://api.vsphone.com/vsphone/api/agentUser/agentUserInfo"
    headers = {
        "token": token, "userid": str(userid), "Content-Type": "application/json",
        "origin": "https://cloud.vmoscloud.com", "referer": "https://cloud.vmoscloud.com/",
        "User-Agent": ua, "appversion": "1008424", "clienttype": "web"
    }
    
    trigger_agent_activation(token, userid, proxy, headers)

    for attempt in range(3):
        try:
            resp = safe_request("POST", agent_info_url, proxy, headers=headers, json={})
            if not resp or resp.status_code != 200:
                resp = safe_request("GET", agent_info_url, proxy, headers=headers)
            
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

async def task_worker(invite_code, update_callback=None):
    worker_id = f"W-{random.randint(1000,9999)}" 
    while True:
        proxy = proxy_manager.get_live_proxy()
        if not proxy:
            print(f"[{worker_id}] ❌ Hết Proxy sống!")
            return None
            
        current_ua = get_random_ua()
        try:
            proxy_short = proxy.split('@')[-1]
            if update_callback:
                await update_callback(f"🔄 Đang khởi tạo luồng {worker_id} (Proxy: {proxy_short})...")
            
            # LOG STEP 1: Lấy Mail (Mail.tm) qua API (CÓ PROXY)
            print(f"[{worker_id}] 🌐 [PROXY] Get Email (Mail.tm)...")
            
            email_data = await asyncio.to_thread(get_temp_email, proxy)
            email, mail_token = email_data if email_data else (None, None)
            
            if not email:
                proxy_manager.mark_bad(proxy)
                await asyncio.sleep(2)
                continue 

            if update_callback:
                await update_callback(f"📩 Đang khởi chạy Playwright gửi OTP tới {email}...")
            
            # LOG STEP 2: Gửi OTP BẰNG TRÌNH DUYỆT (Playwright Async - DÙNG PROXY TỪ proxies1.txt)
            pw_proxy = host_proxy_manager.get_live_proxy()
            pw_proxy_short = pw_proxy.split('@')[-1] if pw_proxy else "NO-PROXY"
            print(f"[{worker_id}] 📤 [PROXY1: {pw_proxy_short}] Mở Playwright giải Captcha & Gửi OTP tới {email}...")
            
            sent = await async_send_with_browser(email, worker_id, pw_proxy)
            
            if not sent:
                print(f"[{worker_id}] ❌ [SEND-FAIL] Lỗi gửi mã qua Playwright.")
                if pw_proxy:
                    host_proxy_manager.mark_bad(pw_proxy)
                continue # Do Playwright lỗi
            
            if update_callback:
                await update_callback(f"⏳ Đang chờ mã OTP từ Inbox...")
            
            # LOG STEP 3: Lấy Code bằng API (requests, CÓ PROXY)
            print(f"[{worker_id}] ⏳ [PROXY] Check inbox bằng API (Mail.tm)...")
            code = await asyncio.to_thread(get_code_from_email, mail_token, email, proxy)
            
            if not code:
                print(f"[{worker_id}] ❌ [TIMEOUT] Không thấy code.")
                continue

            if update_callback:
                await update_callback(f"🔑 Đang đăng nhập...")
            
            # LOG STEP 4: Login (CÓ PROXY)
            print(f"[{worker_id}] 🔑 [PROXY] Login Code: {code}")
            creds = await asyncio.to_thread(login_vmos, email, code, proxy, invite_code, current_ua)
            
            if not creds:
                print(f"[{worker_id}] ❌ [LOGIN-FAIL] Login thất bại.")
                continue

            print(f"[{worker_id}] ✅ [SUCCESS] {email} -> OK!")
            return {
                "email": email, 
                "password": "NECONECOLYCONECO", 
                "token": creds['token'], 
                "userId": creds['userId'],
                "proxy_used": proxy # Trả về proxy đã dùng để acc host tiếp tục sử dụng
            }
        except Exception as e:
             print(f"[{worker_id}] ⚠️ Lỗi ngoại lệ worker: {e}")
             proxy_manager.mark_bad(proxy)
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

@bot.command(name="usea")
async def use_code(ctx):
    data = code_storage.load_data()
    embed = discord.Embed(title="📦 KHO CODE DỰ TRỮ", color=discord.Color.gold())
    total_codes = 0
    if not data:
        embed.description = "Kho đang trống trơn! Hãy chạy `!genbuff1` để kiếm thêm."
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
        await panel_msg.edit(content="⌛ Hết thời gian chờ lệnh `!use1`.", embed=None)

@bot.command(name="genstopa")
async def genstop(ctx):
    global is_inf_running
    if is_inf_running:
        is_inf_running = False
        await ctx.send("🛑 **Đã nhận lệnh dừng quá trình vô cực!**")
    else:
        await ctx.send("⚠️ Không có tiến trình vô cực nào đang chạy.")

@bot.command(name="genbuffa")
async def genbuff(ctx, arg1: str = None, arg2: str = None):
    global is_inf_running
    
    try:
        if not arg1 or not arg2:
            await ctx.send("❌ Cú pháp: `!genbuff1 <số_lượng | inf> <loại_vip | all | all-vip...>`")
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
            print(f"\n[GENBUFF] BẮT ĐẦU CHẾ ĐỘ VÔ CỰC (INF) - TYPE: {display_type}")
        else:
            print(f"\n[GENBUFF] BẮT ĐẦU CHẾ ĐỘ GIỚI HẠN - {num_hosts} HOST - TYPE: {display_type}")

        host_idx = 1
        
        while True:
            if is_inf_mode and not is_inf_running:
                print("[GENBUFF] Đã dừng vòng lặp vô cực.")
                break
            if not is_inf_mode and host_idx > num_hosts:
                break 

            while proxy_manager.get_live_count() == 0 or host_proxy_manager.get_live_count() == 0:
                msg_err = await ctx.send("⚠️ **Cạn kiệt Proxy!** Đợi 30 giây để thử lại...") 
                await asyncio.sleep(30) 
                proxy_manager.reset_bad_proxies()
                host_proxy_manager.reset_bad_proxies()
                try: await msg_err.delete()
                except: pass

            print(f"\n[GENBUFF] ---> ĐANG XỬ LÝ HOST {host_idx} <---")
            title_text = f"⚙️ Đang tạo tài khoản chủ ({'Vô cực' if is_inf_mode else f'{host_idx}/{num_hosts}'})..."
            init_embed = discord.Embed(title=title_text, color=discord.Color.orange())
            init_embed.description = "🔄 Đang khởi tạo worker..."
            msg = await ctx.send(embed=init_embed)

            async def update_host_status(status_msg):
                init_embed.description = status_msg
                try: await msg.edit(embed=init_embed)
                except: pass

            # 1. TẠO TÀI KHOẢN (API) - ĐÃ GIẢM XUỐNG 3 LUỒNG
            print(f"[HOST] 🚀 Bắt đầu tạo Host Account (3 luồng)...")
            
            async def create_host_acc_wrapper():
                tasks = set()
                for _ in range(3):
                    tasks.add(asyncio.create_task(task_worker(invite_code=None, update_callback=update_host_status)))
                while tasks:
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for t in done:
                        tasks.remove(t)
                        try:
                            res = t.result()
                            if res:
                                print(f"[HOST] 🎉 Đã chốt 1 luồng tạo tài khoản, đóng các luồng còn lại...")
                                for p in pending: p.cancel()
                                if pending: await asyncio.gather(*pending, return_exceptions=True)
                                return res
                        except: pass
                return None
                
            host_acc = await create_host_acc_wrapper()
            
            if not host_acc:
                await msg.edit(content=f"❌ Không thể tạo tài khoản chủ {host_idx}.", embed=None)
                host_idx += 1
                continue
            
            host_token = host_acc['token']
            host_userid = host_acc['userId']
            host_proxy = host_acc['proxy_used']

            # 2. KHỞI ĐỘNG BROWSER CHỦ & LOGIN (3 LUỒNG)
            init_embed.description = "🌐 Đang mở 3 trình duyệt để Login..."
            await msg.edit(embed=init_embed)
            
            pw_obj, browser_obj, page_obj, win_proxy = await open_browser_and_login_concurrent(host_acc['email'], host_acc['password'])
            if not pw_obj:
                await msg.edit(content=f"❌ Không thể mở tài khoản chủ {host_idx} (Hết proxy hoặc lỗi tất cả luồng).", embed=None)
                host_idx += 1
                continue
                
            if win_proxy:
                host_proxy = win_proxy  # Cập nhật proxy đã đăng nhập thành công để gọi API Host bên dưới

            # 3. LẤY MÃ MỜI (API - CÓ DÙNG PROXY CỦA HOST)
            init_embed.description = "🔄 Đang lấy mã mời (Invite Code)..."
            await msg.edit(embed=init_embed)
            
            print(f"[HOST] 📨 Đang lấy Invite Code...")
            invite_code = await asyncio.to_thread(get_invite_code_vmos, host_token, host_userid, host_proxy)
            if not invite_code:
                print(f"[HOST] ❌ Không lấy được Invite Code!")
                embed_err = discord.Embed(title=f"⚠️ Lỗi lấy mã mời (Host {host_idx})", description=f"Skip...", color=discord.Color.red())
                await msg.edit(embed=embed_err)
                await close_browser_session(pw_obj, browser_obj)
                host_idx += 1
                continue
            print(f"[HOST] ✅ Invite Code: {invite_code}")

            # 4. CHẠY BUFF (ĐA LUỒNG)
            embed_run = discord.Embed(title=f"🚀 Auto-Buff {display_type} Started", color=discord.Color.blue())
            embed_run.add_field(name="👤 Tài Khoản Chủ", value=f"Email: `{host_acc['email']}`", inline=False)
            full_invite_link = f"https://cloud.vsphone.com/event/202602?channel={invite_code}"
            embed_run.add_field(name="🎟️ Link Mời", value=f"{full_invite_link}\n(Mã: `{invite_code}`)", inline=False)
            embed_run.add_field(name="📊 Tiến độ Buff", value=f"Đang chạy {CONFIG['NUM_THREADS']} luồng (Browser đang treo)...", inline=False)
            if THUMBNAIL_URL:
                embed_run.set_thumbnail(url=THUMBNAIL_URL)
            await msg.edit(embed=embed_run)

            # Cố định luôn số luồng là số được đặt ở CONFIG, không quan tâm số buff còn lại
            concurrency = CONFIG["NUM_THREADS"]
            semaphore = asyncio.Semaphore(concurrency)
            
            current_assets_num = 0
            total_success_local = 0
            total_fail = 0
            consecutive_failures = 0 # Biến đếm lỗi liên tục
            
            async def protected_worker():
                async with semaphore:
                    return await task_worker(invite_code=invite_code)

            active_tasks = set()
            for _ in range(concurrency):
                active_tasks.add(asyncio.create_task(protected_worker()))
                
            last_update_time = 0
            is_host_failed = False
            
            while active_tasks:
                done, active_tasks = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
                
                for task in done:
                    try:
                        res = await task
                        if res:
                            total_success_local += 1
                            consecutive_failures = 0 # Reset đếm lỗi nếu gửi mã thành công
                            current_assets_num = await asyncio.to_thread(check_buff_status, host_token, host_userid, host_proxy)
                        else:
                            total_fail += 1
                            consecutive_failures += 1 # Cộng dồn nếu lỗi
                    except:
                        total_fail += 1
                        consecutive_failures += 1 # Cộng dồn nếu lỗi ngoại lệ
                        
                    # Cơ chế nghỉ 5 phút nếu 10 lần liên tục đều xịt
                    if consecutive_failures >= 10:
                        embed_run.set_field_at(2, name="📊 Tiến độ Buff", value=f"⚠️ **Fail 10 lần liên tục!** Đang nghỉ 5 phút (Anti-Ban)...", inline=False)
                        try: await msg.edit(embed=embed_run)
                        except: pass
                        
                        print(f"[GENBUFF] ⚠️ Fail 10 lần liên tục! Đóng băng hệ thống 5 phút (300 giây)...")
                        await asyncio.sleep(300)
                        
                        consecutive_failures = 0
                        proxy_manager.reset_bad_proxies() 
                        host_proxy_manager.reset_bad_proxies()
                        print(f"[GENBUFF] ♻️ Đã hết 5 phút nghỉ ngơi, tiếp tục cày cuốc!")
                    
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
                    
                    if proxy_manager.get_live_count() > 0:
                        # Luôn cố gắng giữ số tác vụ bằng với concurrency
                        desired_running = concurrency
                        while len(active_tasks) < desired_running:
                            active_tasks.add(asyncio.create_task(protected_worker()))
                    else:
                        if not active_tasks:
                            embed_run.set_field_at(2, name="📊 Tiến độ Buff", value=f"⏳ **Hết Proxy Sống!** Chờ 30 giây để thử lại...", inline=False) 
                            try: await msg.edit(embed=embed_run)
                            except: pass
                            
                            await asyncio.sleep(30) 
                            proxy_manager.reset_bad_proxies()
                            host_proxy_manager.reset_bad_proxies()
                            
                            desired_running = concurrency
                            for _ in range(desired_running):
                                active_tasks.add(asyncio.create_task(protected_worker()))

            if is_host_failed:
                break

            # 5. MUA GÓI & LƯU CODE
            final_code_str = "Không có code nào được lấy."
            if current_assets_num >= num_buffs:
                print(f"[HOST] 🎁 Đủ điều kiện. Bắt đầu đổi quà...")
                embed_run.add_field(name="🎁 Đổi Code", value=f"⏳ Đang đổi quà...", inline=False)
                await msg.edit(embed=embed_run)
                
                for ex_id in exchange_list:
                    await asyncio.to_thread(exchange_target_gem, host_token, host_userid, host_proxy, ex_id)
                
                codes_dict = await asyncio.to_thread(fetch_codes_as_dict, host_token, host_userid, host_proxy)
                
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
                
            # 6. ĐÓNG TRÌNH DUYỆT HOST
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
    print("🚀 Đang khởi động Bot...")
    token_local = load_local_token()
    
    proxies_list = load_proxies_from_url(PROXY_URL)
    host_proxies_list = load_proxies_from_url(HOST_PROXY_URL)
    
    if not token_local:
        print("❌ KHÔNG THỂ KHỞI ĐỘNG: Thiếu Token trong file 'token.txt'.")
    else:
        if not proxies_list:
            print(f"⚠️ CẢNH BÁO: Không lấy được proxy nào từ URL '{PROXY_URL}'.")
        if not host_proxies_list:
            print(f"⚠️ CẢNH BÁO: Không lấy được proxy nào từ URL '{HOST_PROXY_URL}' cho tài khoản chủ.")
            
        proxy_manager = ProxyManager(proxies_list)
        host_proxy_manager = ProxyManager(host_proxies_list)
        
        print(f"🚀 Bot Pro Ultimate + Playwright đang chạy...")
        while True:
            try:
                bot.run(token_local)
            except Exception as e:
                print(f"⚠️ Bot bị crash: {e}")
                time.sleep(5)
            except KeyboardInterrupt:
                print("🛑 Đã dừng thủ công.")
                break
