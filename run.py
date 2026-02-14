# -*- coding: utf-8 -*-
# Script Bot Discord cho VMOS Cloud (Phiên bản Ultimate - Store Mode + ALL + Fix Freeze + Exclusion Mode + 120 Threads + Ping + Playwright Login)
# Tính năng cập nhật:
# - Tích hợp Playwright: Tự động mở Chrome, đăng nhập và treo nick.
# - LOAD CONFIG TỪ GITHUB: Tải Token và Proxy từ URL online.
# - Fast Skip: Bỏ qua ngay lập tức nếu lỗi gửi mã.
# - Thông báo tổng code trong kho.

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
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# THƯ VIỆN MỚI CHO TRÌNH DUYỆT
from playwright.async_api import async_playwright

# ==============================================================
# ==>> CẤU HÌNH & HẰNG SỐ <<==
# ==============================================================

# URL CHỨA INFO (Dòng 1: Token, Các dòng sau: Proxies)
CONFIG_URL = "https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/info"
CODE_FILE_NAME = "CODE.txt"
THUMBNAIL_URL = "https://media.tenor.com/uKqSgjwq-jcAAAAM/hatsune-miku-oshi-no-ko.gif"

# Danh sách User-Agent để Random hóa Headers
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

# Cấu hình gói VIP
VIP_MAP = {
    "vip": {"target": 5, "exchange_id": 999},
    "kvip": {"target": 10, "exchange_id": 1000},
    "svip": {"target": 20, "exchange_id": 1001},
    "xvip": {"target": 30, "exchange_id": 1002},
    "mvip": {"target": 40, "exchange_id": 1003}
}

# Biến toàn cục để kiểm soát chế độ vô cực
is_inf_running = False

# ==============================================================
# ==>> HÀM LOAD CONFIG TỪ GITHUB <<==
# ==============================================================

def fetch_config_from_github():
    print(f"🌐 Đang tải cấu hình từ GitHub: {CONFIG_URL} ...")
    try:
        resp = requests.get(CONFIG_URL, timeout=15)
        if resp.status_code != 200:
            print(f"❌ Lỗi tải config: HTTP {resp.status_code}")
            return None, []
        
        text = resp.text.strip()
        # Tách dòng và lọc dòng trống
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            print("❌ File config trên GitHub rỗng!")
            return None, []
            
        # Dòng 1 là Token
        token = lines[0]
        # Các dòng còn lại là Proxy
        proxies = lines[1:]
        
        print(f"✅ Đã tải Token: {token[:10]}******")
        print(f"✅ Đã tải {len(proxies)} proxies từ GitHub.")
        return token, proxies
    except Exception as e:
        print(f"❌ Exception khi tải config GitHub: {e}")
        return None, []

# ==============================================================
# ==>> LỚP QUẢN LÝ CODE STORAGE (LƯU TRỮ & TRÍCH XUẤT) <<==
# ==============================================================

class CodeStorageManager:
    def __init__(self, filename):
        self.filename = filename

    def load_data(self):
        """Đọc file CODE.txt và trả về dict {VIP_TYPE: [code1, code2...]}"""
        data = defaultdict(list)
        current_section = None
        
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w', encoding='utf-8') as f:
                    f.write("")
            except: pass
            return data

        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
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
        except Exception as e:
            print(f"[STORAGE] Lỗi đọc file code: {e}")
            
        return data

    def save_data(self, data):
        """Ghi đè lại file CODE.txt với dữ liệu mới nhất"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                sorted_keys = sorted(data.keys())
                for vip_type in sorted_keys:
                    codes = data[vip_type]
                    if not codes: continue
                    
                    f.write(f"{vip_type}\n")
                    for code in codes:
                        f.write(f"{code}\n")
                    f.write("\n")
            return True
        except Exception as e:
            print(f"[STORAGE] Lỗi ghi file code: {e}")
            return False

    def add_codes(self, new_codes_dict):
        """Thêm code mới vào kho (Append mode)"""
        data = self.load_data()
        summary = {}
        
        for vip, codes in new_codes_dict.items():
            if not codes: continue
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
        return summary

    def pop_codes(self, vip_type, amount):
        """Lấy code ra khỏi kho và xóa chúng"""
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
# ==>> LỚP QUẢN LÝ PROXY (CORE - HỖ TRỢ TOÀN BỘ ĐỊNH DẠNG) <<==
# ==============================================================

class ProxyManager:
    def __init__(self, proxy_list=None):
        self.proxies = []
        self.bad_proxies = set()
        if proxy_list:
            self.load_proxies_from_list(proxy_list)
    
    def parse_proxy(self, line):
        line = line.strip()
        if not line or line.startswith('#'): return None
        line = re.sub(r'^https?://', '', line)

        try:
            if '@' in line:
                return f"http://{line}"
            parts = line.split(':')
            if len(parts) == 2:
                host, port = parts
                return f"http://{host}:{port}"
            if len(parts) == 4:
                host, port, user, pwd = parts
                return f"http://{user}:{pwd}@{host}:{port}"
            return f"http://{line}"
        except Exception:
            return None

    def load_proxies_from_list(self, raw_lines):
        for line in raw_lines:
            p = self.parse_proxy(line)
            if p: self.proxies.append(p)
        print(f"[PROXY] Đã xử lý {len(self.proxies)} proxy hợp lệ.")

    def get_live_proxy(self):
        available = [p for p in self.proxies if p not in self.bad_proxies]
        if not available: return None
        return random.choice(available)

    def mark_bad(self, proxy):
        if proxy and proxy not in self.bad_proxies:
            self.bad_proxies.add(proxy)

    def reset_bad_proxies(self):
        self.bad_proxies.clear()
        print(f"[PROXY] Đã RESET danh sách proxy lỗi.")

    def get_count(self): return len(self.proxies)
    def get_live_count(self): return len(self.proxies) - len(self.bad_proxies)

# Khởi tạo tạm, sẽ load data thật ở main
proxy_manager = ProxyManager([])

# ==============================================================
# ==>> HÀM HỖ TRỢ BROWSER (PLAYWRIGHT) <<==
# ==============================================================

async def open_browser_and_login(email, password):
    """
    Mở trình duyệt, đăng nhập và TRẢ VỀ đối tượng browser để giữ nó mở.
    """
    print(f"[BROWSER] 🌐 Đang khởi động Chrome Guest Mode cho: {email}")
    try:
        p = await async_playwright().start()
        # Chỉnh sửa: Cửa sổ nhỏ và ở góc phải dưới (ước lượng cho màn 1920x1080)
        # --window-position=x,y. 
        # x=1500, y=500 sẽ đẩy về góc phải dưới màn hình.
        # --window-size=400,600 tạo cửa sổ dọc nhỏ.
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=[
                "--guest",
                "--window-size=400,600",
                "--window-position=1500,500"
            ]
        )
        context = await browser.new_context()
        page = await context.new_page()

        print(f"[BROWSER] 🔗 Đang truy cập trang sự kiện...")
        await page.goto("https://cloud.vsphone.com/event/202602")

        # Logic điền form như yêu cầu
        await page.wait_for_selector('input[placeholder="Please enter your email address"]')
        await page.fill('input[placeholder="Please enter your email address"]', email)
        await page.fill('input[placeholder="Please enter your login password"]', password)
        
        await page.click('button:has-text("Sign in")')
        print(f"[BROWSER] ✅ Đã click Sign in. Đang treo trình duyệt...")
        
        # Trả về p, browser để sau này có thể close()
        return p, browser, page
    except Exception as e:
        print(f"[BROWSER] ❌ Lỗi khởi động trình duyệt: {e}")
        # Nếu lỗi thì cố gắng dọn dẹp luôn
        return None, None, None

async def close_browser_session(p, browser):
    """Đóng trình duyệt sau khi buff xong"""
    if browser:
        print(f"[BROWSER] 🛑 Đang đóng trình duyệt...")
        try:
            await browser.close()
        except: pass
    if p:
        try:
            await p.stop()
        except: pass

# ==============================================================
# ==>> HÀM API VMOS (NHƯ CŨ) <<==
# ==============================================================

def safe_request(method, url, proxy, **kwargs):
    proxies_dict = {"http": proxy, "https": proxy} if proxy else None
    if 'timeout' not in kwargs: kwargs['timeout'] = 20
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

def get_temp_email(proxy):
    # Sử dụng UA ngẫu nhiên cho Temp Mail cũng tốt
    ua = get_random_ua()
    url = "https://api.internal.temp-mail.io/api/v3/email/new"
    headers = {"User-Agent": ua, "Content-Type": "application/json"}
    payload = {"min_name_length": 10, "max_name_length": 10}
    try:
        resp = safe_request("POST", url, proxy, headers=headers, json=payload, timeout=15)
        if resp and resp.status_code == 200: return resp.json().get("email")
    except: pass
    return None

def send_code_vmos(email, proxy, user_agent=None):
    # RANDOM HEADERS Ở ĐÂY
    ua = user_agent if user_agent else get_random_ua()
    
    url = "https://api.vsphone.com/vsphone/api/sms/smsSend"
    headers = {
        "content-type": "application/json", 
        "origin": "https://cloud.vmoscloud.com",
        "referer": "https://cloud.vmoscloud.com/", 
        "user-agent": ua # Random UA
    }
    payload = {
        "smsType": 2, "mobilePhone": email,
        "captchaVerifyParam": "{\"sceneId\":\"5jvar3wp\",\"certifyId\":\"Sz5A7mJjnc\",\"deviceToken\":\"U0dfV0VCIzM3OTVkMjgyNDJhMTE2MTliYzI1Zjc4NmY4NGU1M2Q0LWgtMTc1MTI0ODM0NzQ5OC1lOTBiNzJmZGZkZDg0YjUzYTdiZjU0YTRiNWQ3MDIzNiNkOGJCS21wMjdYVGc5bUdPVDVUaUN1N3lWeERuRkZXL2dXSmFOYnYrcjMzTmlWUkVFVUVGVVI2OE9IWnM5U2xyYnZXMnF6WXRsVHZwRGtlclNxUFJrcGlPcGRFaXI2TW5wZUpqTnhtNHB5N29kTUlldnllYXRGbWtXUFRUNm9ldFlUOXowcnB3emJYeGdRNTJ1UVNOSFI5NlVqdGV6YnBJSTh6RU1uN2I0OERZckY1SmZxR3RwbXM1aVUyY3RWTXE2UWVjaXhrZjIvZEZqOVcrc3RqS0NDbUFKUURUUTRZcTFObGR2bm80OG1UZEs2c3hBV29lTWpUZHBOZUI2MCtZYnp6WGI3ZVpjS2ZoMCtwRWN0UkFsWC9XV0EzaDRjb1pwT1dVZzZXejI2WkhtMVNTQll1WEtmYXpsQmhyNUMza3pRcy8zM1BlVW4xd2Q2VFk4dEduVUlxVURLclhUU3ZJS2xlSk9aOWRaYzBOZldEQmdBaXZ2NEkxa09pcHkwdmhpUnphc3ZkczAyOGtPbHlDTFlmUkdyaXYvTS9tUXVxTjl4TzN2VXFtTE9OM2ltZWQ1SGxKNHNVM294ZE5lZGJMN2JvcnNxUEV6ZEVIKy9vNWFGUnI3VnBEOURVWHozZUFyeE9zZU13RHRFdzRTaDR3R1hXNS9FWEVNcXpOM0xwbkFDeHhuRlZIemxLeGM4aHB6a2ZxM1U4NGl1K2hMdE11RVBaamNVdHlWbFVXL0tvazBXUkVpcWVsQUZLcTljQmJUcWJPdy9kZXgzanNLWVIvckNPY3MvcDV6N0lpalIvcDBWbnk5TWp1U2U0U2V0b3djdStFUm9GUzFudW90U1ROIzExOSNkOTYzNzA0ZDk1NTdiODhlMjJhYWJlYjNmMzJjZDA3Nw==\",\"data\":\"JRMmbUseGiM6eQ4LaxVYLx32sUc6EyJfYRA4MlBCDPQgclpB/24VVyx4AK1qL+ksP1FoEwpQJ229/9gCqZA8AoswNlp9L0UPC07tEHBWYVhZOy0lQs9LIuVqNH9xGWPVpShRCh8WNi4eeEoyZGY28h+zdokDk9hbE1BJTaLWjK1KpiBUFiVpTEhefg1bRjg71Flk+x9SfSU+cB15wB9UAVNydxoYuBgbK1lQewIicctfr3JTCci1Xv9rtSsoYJUiaS55ZDlBLnh2WRo9XG05JA57Ly8IT2UVqiBuT9dHcdcubW9BgDh+l2Jg4gNoU2WSAgHRZWUwNyB/PdZ9L1tRVHkeLQW1OT1RV3xJb784Z0JAY2ozCawXcgUGR3pfQAlVDKJQ0nw7ttA7/gT35RIEpd7jJ/kNP6314kJXxpC/U3eyV08JQjqMeQ1kv1IaICsVaW1BCg==\"}"
    }
    # Giảm timeout xuống 10s để skip nhanh nếu lỗi
    resp = safe_request("POST", url, proxy, headers=headers, json=payload, timeout=10)
    if resp and resp.status_code == 200:
        data = resp.json()
        return data.get("code") == 200 and "success" in data.get("msg", "").lower()
    return False

def get_code_from_email(email, proxy):
    ua = get_random_ua()
    url = f"https://api.internal.temp-mail.io/api/v3/email/{email}/messages"
    for _ in range(5):
        try:
            resp = safe_request("GET", url, proxy, headers={"User-Agent": ua}, timeout=10)
            if resp and resp.status_code == 200:
                messages = resp.json()
                if messages:
                    for msg in messages:
                        text = msg.get("body_text", "")
                        match = re.search(r"\b(\d{6})\b", text)
                        if match: return match.group(1)
        except: pass
        time.sleep(3)
    return None

def login_vmos(email, code, proxy, invite_code=None, user_agent=None):
    ua = user_agent if user_agent else get_random_ua()
    
    url = "https://api.vsphone.com/vsphone/api/user/login"
    headers = {
        "Content-Type": "application/json", "origin": "https://cloud.vmoscloud.com",
        "referer": "https://cloud.vmoscloud.com/", 
        "User-Agent": ua,
        "appversion": "1008424", "clienttype": "web"
    }
    if invite_code: headers["channel"] = invite_code
    
    payload = {
        "mobilePhone": email, "loginType": 0, "verifyCode": code,
        "password": "ba71fb4736613b59be75f9c404b945b1"
    }
    if invite_code: payload["channel"] = invite_code

    resp = safe_request("POST", url, proxy, headers=headers, json=payload)
    if resp and resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 200:
            token = data.get("data", {}).get("token")
            if not token: token = resp.headers.get("token") or resp.headers.get("Token")
            
            if token:
                user_info_url = "https://api.vsphone.com/vsphone/api/user/getUserInfo"
                h2 = headers.copy()
                h2["token"] = token
                
                uid = None
                r2 = safe_request("GET", user_info_url, proxy, headers=h2)
                if r2 and r2.status_code == 200 and r2.json().get("code") == 200:
                    uid = r2.json().get("data", {}).get("userId")
                else:
                    r2 = safe_request("POST", user_info_url, proxy, headers=h2, json={})
                    if r2 and r2.status_code == 200 and r2.json().get("code") == 200:
                        uid = r2.json().get("data", {}).get("userId")
                
                return {"token": token, "userId": str(uid) if uid else None}
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
            if not resp or resp.status_code != 200 or resp.json().get("code") != 200:
                resp = safe_request("GET", url, proxy, headers=headers)
                
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    d_obj = data.get("data") or {}
                    return d_obj.get("assetsNum", 0)
        except Exception: pass
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
    print(f"\n[EXCHANGE] 🎁 Mua gói ID {target_id}...")
    
    for attempt in range(5): 
        try:
            resp = safe_request("POST", url, proxy, headers=headers, json=payload)
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    return True
        except Exception: pass
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
        if not resp or resp.status_code != 200: return None
        data = resp.json()
        if data.get("code") != 200: return None
        items = data.get("data", [])
        if not items: return None

        grouped = defaultdict(list)
        for item in items:
            if not item.get("isActivation", True): 
                vip_type = item.get("configName", "UNKNOWN")
                code = item.get("awardCount", "")
                if code: grouped[vip_type].append(code)
        return grouped
    except Exception: return None

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
            if not resp or resp.status_code != 200 or resp.json().get("code") != 200:
                resp = safe_request("GET", agent_info_url, proxy, headers=headers)
            
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    channel_code = data.get("data", {}).get("channelCode", "")
                    if channel_code: return channel_code
                    else: break 
                elif data.get("code") == 500:
                    time.sleep(3)
                    continue
                else: break
        except Exception: break
    return None

async def task_worker(invite_code, update_callback=None):
    worker_id = f"W-{random.randint(100,999)}" 
    while True:
        proxy = proxy_manager.get_live_proxy()
        if not proxy: return None

        # Tạo UA ngẫu nhiên cho session này
        current_ua = get_random_ua()

        try:
            proxy_short = proxy.split('@')[-1]
            if update_callback: await update_callback(f"🔄 Đang thử proxy: {proxy_short}...")
            
            email = await asyncio.to_thread(get_temp_email, proxy)
            if not email:
                continue 

            if update_callback: await update_callback(f"📩 Đang gửi mã OTP về {email}...")
            
            # Gửi mã VMOS với UA ngẫu nhiên
            sent = await asyncio.to_thread(send_code_vmos, email, proxy, current_ua)
            
            # Logic SKIP FAST: Nếu không gửi được (do rate limit, IP chặn...), skip ngay
            if not sent:
                proxy_manager.mark_bad(proxy)
                continue # Lập tức vòng lại while True để lấy proxy khác
            
            if update_callback: await update_callback(f"⏳ Đang chờ mã OTP từ {email}...")
            code = await asyncio.to_thread(get_code_from_email, email, proxy)
            if not code:
                continue

            if update_callback: await update_callback(f"🔑 Đang đăng nhập...")
            
            # Login với cùng UA đã gửi mã (để tăng độ trust)
            creds = await asyncio.to_thread(login_vmos, email, code, proxy, invite_code, current_ua)
            if not creds:
                continue

            print(f"[{worker_id}] 🎉 TẠO TÀI KHOẢN THÀNH CÔNG: {email}")
            return {
                "email": email, "password": "NECONECOLYCONECO", 
                "token": creds['token'], "userId": creds['userId'], "proxy_used": proxy
            }
        except Exception as e:
            proxy_manager.mark_bad(proxy)
            continue

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command(name="use")
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

    if THUMBNAIL_URL: embed.set_thumbnail(url=THUMBNAIL_URL)
    embed.set_footer(text="Bot sẽ đợi lệnh trong 30 giây...")
    panel_msg = await ctx.send(embed=embed)

    if total_codes == 0: return

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
            await ctx.send("❌ Cú pháp sai. Hủy lệnh.")
    except asyncio.TimeoutError:
        await panel_msg.edit(content="⌛ Hết thời gian chờ lệnh `!use`.", embed=None)

@bot.command(name="genstop")
async def genstop(ctx):
    global is_inf_running
    if is_inf_running:
        is_inf_running = False
        await ctx.send("🛑 **Đã nhận lệnh dừng quá trình vô cực!** Sẽ ngừng tạo Host mới sau khi hoàn tất phiên hiện tại.")
    else:
        await ctx.send("⚠️ Không có tiến trình vô cực nào đang chạy.")

@bot.command(name="genbuff")
async def genbuff(ctx, arg1: str = None, arg2: str = None):
    global is_inf_running
    
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

        if proxy_manager.get_live_count() == 0:
            if is_inf_mode:
                msg_err = await ctx.send("⚠️ **Cạn kiệt Proxy!** Ngủ 1 phút...") 
                await asyncio.sleep(60) 
                proxy_manager.reset_bad_proxies()
                await msg_err.delete()
            else:
                await ctx.send(f"❌ **Hết proxy!** Ngừng tại Host {host_idx}/{num_hosts}.")
                break

        print(f"\n[GENBUFF] ---> ĐANG XỬ LÝ HOST {host_idx} <---")
        title_text = f"⚙️ Đang tạo tài khoản chủ ({'Vô cực' if is_inf_mode else f'{host_idx}/{num_hosts}'})..."
        init_embed = discord.Embed(title=title_text, color=discord.Color.orange())
        init_embed.description = "🔄 Đang khởi tạo worker..."
        msg = await ctx.send(embed=init_embed)

        async def update_host_status(status_msg):
            init_embed.description = status_msg
            try: await msg.edit(embed=init_embed)
            except: pass

        # 1. TẠO TÀI KHOẢN (API)
        host_acc = await task_worker(invite_code=None, update_callback=update_host_status)
        if not host_acc:
            await msg.edit(content=f"❌ Không thể tạo tài khoản chủ {host_idx}.", embed=None)
            host_idx += 1
            continue
        
        host_token = host_acc['token']
        host_userid = host_acc['userId']
        host_proxy = host_acc['proxy_used']

        # 2. KHỞI ĐỘNG BROWSER & LOGIN (THEO YÊU CẦU PLAYWRIGHT)
        # Bước này sẽ mở trình duyệt, đăng nhập, và giữ cửa sổ ở đó.
        init_embed.description = "🌐 Đang mở trình duyệt để Login..."
        await msg.edit(embed=init_embed)
        
        pw_obj, browser_obj, page_obj = await open_browser_and_login(host_acc['email'], host_acc['password'])
        # Lưu ý: Nếu mở trình duyệt thất bại, pw_obj sẽ là None. 
        # Tùy ý muốn, ở đây ta cứ tiếp tục chạy API buff, hoặc dừng lại. 
        # Giả sử vẫn chạy tiếp dù browser lỗi (để ko phí acc).

        # 3. LẤY MÃ MỜI (API)
        init_embed.description = "🔄 Đang lấy mã mời (Invite Code)..."
        await msg.edit(embed=init_embed)
        
        invite_code = await asyncio.to_thread(get_invite_code_vmos, host_token, host_userid, host_proxy)
        if not invite_code:
            embed_err = discord.Embed(title=f"⚠️ Lỗi lấy mã mời (Host {host_idx})", description=f"Skip...", color=discord.Color.red())
            await msg.edit(embed=embed_err)
            await close_browser_session(pw_obj, browser_obj) # Dọn dẹp nếu fail
            host_idx += 1
            continue

        # 4. CHẠY BUFF (ĐA LUỒNG) - TRONG KHI BROWSER VẪN MỞ
        embed_run = discord.Embed(title=f"🚀 Auto-Buff {display_type} Started", color=discord.Color.blue())
        embed_run.add_field(name="👤 Tài Khoản Chủ", value=f"Email: `{host_acc['email']}`", inline=False)
        full_invite_link = f"https://cloud.vsphone.com/event/202602?channel={invite_code}"
        embed_run.add_field(name="🎟️ Link Mời", value=f"{full_invite_link}\n(Mã: `{invite_code}`)", inline=False)
        embed_run.add_field(name="📊 Tiến độ Buff", value=f"Đang chạy {num_buffs} luồng (Browser đang treo)...", inline=False)
        if THUMBNAIL_URL: embed_run.set_thumbnail(url=THUMBNAIL_URL)
        await msg.edit(embed=embed_run)

        total_proxies = proxy_manager.get_count()
        concurrency = min(total_proxies, 120)
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
        is_host_failed = False
        
        while active_tasks:
            done, active_tasks = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
            
            for task in done:
                try:
                    res = await task
                    if res:
                        total_success_local += 1
                        current_assets_num = await asyncio.to_thread(check_buff_status, host_token, host_userid, host_proxy)
                    else: total_fail += 1
                except: total_fail += 1
                
                now = time.time()
                if now - last_update_time > 5 or current_assets_num >= num_buffs or not active_tasks:
                    status_text = f"Mục tiêu: **{num_buffs}**\nĐã nhận: **{current_assets_num}/{num_buffs}**\nThành công: **{total_success_local}** | Lỗi: **{total_fail}**"
                    embed_run.set_field_at(2, name="📊 Tiến độ Buff", value=status_text, inline=False)
                    try: 
                        await msg.edit(embed=embed_run)
                        last_update_time = now
                    except: pass
                
                if current_assets_num >= num_buffs:
                    for t in active_tasks: t.cancel()
                    active_tasks.clear()
                    break
                
                if proxy_manager.get_live_count() > 0:
                    desired_running = concurrency 
                    while len(active_tasks) < desired_running:
                        active_tasks.add(asyncio.create_task(protected_worker()))
                else:
                    if not active_tasks:
                        if is_inf_mode:
                            embed_run.set_field_at(2, name="📊 Tiến độ Buff", value=f"⏳ **Hết Proxy Sống!** Chờ 1 phút...", inline=False) 
                            await msg.edit(embed=embed_run)
                            await asyncio.sleep(60) 
                            proxy_manager.reset_bad_proxies()
                            desired_running = min(concurrency, num_buffs - current_assets_num)
                            for _ in range(desired_running):
                                active_tasks.add(asyncio.create_task(protected_worker()))
                        else:
                            is_host_failed = True
                            for t in active_tasks: t.cancel()
                            active_tasks.clear()
                            break

        if is_host_failed: break

        # 5. MUA GÓI & LƯU CODE
        final_code_str = "Không có code nào được lấy."
        if current_assets_num >= num_buffs:
            embed_run.add_field(name="🎁 Đổi Code", value=f"⏳ Đang đổi quà...", inline=False)
            await msg.edit(embed=embed_run)
            
            for ex_id in exchange_list:
                await asyncio.to_thread(exchange_target_gem, host_token, host_userid, host_proxy, ex_id)
            
            codes_dict = await asyncio.to_thread(fetch_codes_as_dict, host_token, host_userid, host_proxy)
            
            if codes_dict:
                # 1. Thêm code mới vào kho
                await asyncio.to_thread(code_storage.add_codes, codes_dict)
                
                # 2. Đọc lại toàn bộ file để lấy tổng số code hiện có
                all_data = await asyncio.to_thread(code_storage.load_data)
                
                # 3. Format hiển thị: VIP: Tổng_số_lượng
                lines = []
                # Sắp xếp key theo độ dài và tên (VD: VIP rồi tới KVIP)
                sorted_keys = sorted(all_data.keys(), key=lambda x: (len(x), x))
                
                for k in sorted_keys:
                    key_upper = k.upper()
                    total_count = len(all_data[k])
                    # Padding left 5 chars để thẳng hàng
                    lines.append(f"{key_upper:<5}: {total_count}")
                
                if lines:
                    final_code_str = "\n".join(lines)
                else:
                    final_code_str = "Kho trống."
            
        # 6. ĐÓNG TRÌNH DUYỆT (QUAN TRỌNG: SAU KHI BUFF XONG)
        await close_browser_session(pw_obj, browser_obj)

        # 7. CẬP NHẬT EMBED HOÀN TẤT (Định dạng lại theo yêu cầu)
        embed_run.title = "✅ Hoàn Tất Buff"
        embed_run.description = None # Xóa description thừa
        embed_run.clear_fields() # Xóa hết các field tiến độ cũ
        
        embed_run.add_field(name="Email", value=f"`{host_acc['email']}`", inline=True)
        embed_run.add_field(name="Password", value=f"`{host_acc['password']}`", inline=True)
        # Sử dụng yaml để highlight màu và căn chỉnh khoảng trắng
        embed_run.add_field(name="Tổng Code trong kho", value=f"```yaml\n{final_code_str}\n```", inline=False)
        
        embed_run.color = discord.Color.green()
        embed_run.set_footer(text=f"Host: {'Vô cực' if is_inf_mode else f'{host_idx}/{num_hosts}'}")

        await msg.edit(embed=embed_run)
        await ctx.send(f"{ctx.author.mention} ✅ Đã xong Host {host_idx}!")
        
        host_idx += 1

    is_inf_running = False
    print("\n[GENBUFF] ĐÃ HOÀN TẤT TOÀN BỘ TIẾN TRÌNH!")

if __name__ == "__main__":
    # Tự động tải config và chạy
    print("🚀 Đang khởi động Bot...")
    token, proxies_list = fetch_config_from_github()
    
    if not token:
        print("❌ KHÔNG THỂ KHỞI ĐỘNG: Thiếu Token hoặc lỗi kết nối GitHub.")
    else:
        # Cập nhật proxy manager với danh sách vừa tải
        proxy_manager = ProxyManager(proxies_list)
        
        print("🚀 Bot Pro Ultimate + Playwright + GitHub Config đang chạy...")
        bot.run(token)
