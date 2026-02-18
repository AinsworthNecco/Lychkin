# -*- coding: utf-8 -*-
# Script Bot Discord cho VMOS Cloud (Phiên bản Ultimate - Full Uncut)
# Tính năng tích hợp:
# 1. Playwright: Tự động mở Chrome (System), đăng nhập và treo nick.
# 2. Mail API: MAIL.TM (Dùng Proxy toàn bộ quy trình).
# 3. Quản lý Config: Token đọc từ file local, Proxy tải từ GitHub.
# 4. Anti-Rate Limit: Cơ chế cập nhật tin nhắn Discord chậm (10s/lần).
# 5. Logging: Xuất log chi tiết.
# 6. Luồng: Giới hạn 50 luồng.
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
from collections import defaultdict

# Tắt cảnh báo insecure request (do dùng verify=False với Proxy)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# THƯ VIỆN MỚI CHO TRÌNH DUYỆT
from playwright.async_api import async_playwright

# ==============================================================
# ==>> CẤU HÌNH & HẰNG SỐ <<==
# ==============================================================

TOKEN_FILE_NAME = "token.txt"
PROXY_CONFIG_URL = "https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/info"
CODE_FILE_NAME = "CODE.txt"
THUMBNAIL_URL = "https://media.tenor.com/uKqSgjwq-jcAAAAM/hatsune-miku-oshi-no-ko.gif"

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

def fetch_proxies_from_github():
    print(f"🌐 Đang kết nối GitHub để lấy Proxy: {PROXY_CONFIG_URL} ...")
    try:
        resp = requests.get(PROXY_CONFIG_URL, timeout=15)
        
        if resp.status_code != 200:
            print(f"❌ Lỗi tải Proxy: HTTP {resp.status_code}")
            return []
            
        text = resp.text.strip()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        print(f"✅ Đã tải thành công {len(lines)} proxies từ GitHub.")
        return lines
    except Exception as e:
        print(f"❌ Exception khi tải Proxy GitHub: {e}")
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
        line = re.sub(r'^https?://', '', line)
        try:
            # IP:Port
            if ':' in line and '@' not in line:
                return f"http://{line}" # Đảm bảo có http:// cho requests
            # User:Pass@IP:Port
            if '@' in line:
                return f"http://{line}"
            # IP:Port:User:Pass
            parts = line.split(':')
            if len(parts) >= 4:
                return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            return f"http://{line}"
        except:
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

# ==============================================================
# ==>> BROWSER <<==
# ==============================================================

async def open_browser_and_login(email, password):
    print(f"[BROWSER] 🌐 Mở Chromium...")
    try:
        p = await async_playwright().start()
        
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium", 
            headless=True,
            args=["--guest", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--window-size=400,600", "--window-position=1500,500"]
        )
        context = await browser.new_context()
        page = await context.new_page()
        print(f"[BROWSER] 🔗 Truy cập VMOS...")
        await page.goto("https://cloud.vsphone.com/event/202602", timeout=60000)
        print(f"[BROWSER] ✍️ Login...")
        await page.wait_for_selector('input[placeholder="Please enter your email address"]', timeout=30000)
        await page.fill('input[placeholder="Please enter your email address"]', email)
        await page.fill('input[placeholder="Please enter your login password"]', password)
        await page.click('button:has-text("Sign in")')
        print(f"[BROWSER] ✅ Treo trình duyệt.")
        return p, browser, page
    except Exception as e:
        print(f"[BROWSER] ❌ Lỗi: {e}")
        return None, None, None

async def close_browser_session(p, browser):
    if browser:
        print(f"[BROWSER] 🛑 Đóng trình duyệt.")
        try:
            await browser.close()
        except: pass
    if p:
        try:
            await p.stop()
        except: pass

# ==============================================================
# ==>> API VMOS <<==
# ==============================================================

def safe_request(method, url, proxy, **kwargs):
    # Cấu hình Proxy chuẩn cho requests
    proxies_dict = None
    if proxy:
        # Proxy từ ProxyManager đã có prefix http://, nhưng requests cần dict rõ ràng
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
# ==>> MAIL.TM LOGIC (PROXY ENABLED) <<==
# ==============================================================

def get_temp_email(proxy):
    """
    Tạo email từ Mail.tm (CÓ PROXY, VERIFY=FALSE).
    """
    proxies_dict = None
    if proxy:
        proxies_dict = {
            "http": proxy,
            "https": proxy
        }

    try:
        # 1. Lấy Domain
        # print(f"   [MAIL-TM] ⏳ Lấy domain với proxy...")
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
        password = "Password123!"
        
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
        # Ném lỗi ra để worker biết mà đổi proxy
        raise e
        
    return None, None

def get_code_from_email(mail_token, email, proxy):
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
    
    for _ in range(10):
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

def send_code_vmos(email, proxy, user_agent=None):
    ua = user_agent if user_agent else get_random_ua()
    
    url = "https://api.vsphone.com/vsphone/api/sms/smsSend"
    headers = {
        "content-type": "application/json", 
        "origin": "https://cloud.vmoscloud.com",
        "referer": "https://cloud.vmoscloud.com/", 
        "user-agent": ua
    }
    # Đây là chuỗi dài, hãy chắc chắn nó không bị cắt dòng
    payload = {
        "smsType": 2, 
        "mobilePhone": email, 
        "captchaVerifyParam": "{\"sceneId\":\"5jvar3wp\",\"certifyId\":\"Sz5A7mJjnc\",\"deviceToken\":\"U0dfV0VCIzM3OTVkMjgyNDJhMTE2MTliYzI1Zjc4NmY4NGU1M2Q0LWgtMTc1MTI0ODM0NzQ5OC1lOTBiNzJmZGZkZDg0YjUzYTdiZjU0YTRiNWQ3MDIzNiNkOGJCS21wMjdYVGc5bUdPVDVUaUN1N3lWeERuRkZXL2dXSmFOYnYrcjMzTmlWUkVFVUVGVVI2OE9IWnM5U2xyYnZXMnF6WXRsVHZwRGtlclNxUFJrcGlPcGRFaXI2TW5wZUpqTnhtNHB5N29kTUlldnllYXRGbWtXUFRUNm9ldFlUOXowcnB3emJYeGdRNTJ1UVNOSFI5NlVqdGV6YnBJSTh6RU1uN2I0OERZckY1SmZxR3RwbXM1aVUyY3RWTXE2UWVjaXhrZjIvZEZqOVcrc3RqS0NDbUFKUURUUTRZcTFObGR2bm80OG1UZEs2c3hBV29lTWpUZHBOZUI2MCtZYnp6WGI3ZVpjS2ZoMCtwRWN0UkFsWC9XV0EzaDRjb1pwT1dVZzZXejI2WkhtMVNTQll1WEtmYXpsQmhyNUMza3pRcy8zM1BlVW4xd2Q2VFk4dEduVUlxVURLclhUU3ZJS2xlSk9aOWRaYzBOZldEQmdBaXZ2NEkxa09pcHkwdmhpUnphc3ZkczAyOGtPbHlDTFlmUkdyaXYvTS9tUXVxTjl4TzN2VXFtTE9OM2ltZWQ1SGxKNHNVM294ZE5lZGJMN2JvcnNxUEV6ZEVIKy9vNWFGUnI3VnBEOURVWHozZUFyeE9zZU13RHRFdzRTaDR3R1hXNS9FWEVNcXpOM0xwbkFDeHhuRlZIemxLeGM4aHB6a2ZxM1U4NGl1K2hMdE11RVBaamNVdHlWbFVXL0tvazBXUkVpcWVsQUZLcTljQmJUcWJPdy9kZXgzanNLWVIvckNPY3MvcDV6N0lpalIvcDBWbnk5TWp1U2U0U2V0b3djdStFUm9GUzFudW90U1ROIzExOSNkOTYzNzA0ZDk1NTdiODhlMjJhYWJlYjNmMzJjZDA3Nw==\",\"data\":\"JRMmbUseGiM6eQ4LaxVYLx32sUc6EyJfYRA4MlBCDPQgclpB/24VVyx4AK1qL+ksP1FoEwpQJ229/9gCqZA8AoswNlp9L0UPC07tEHBWYVhZOy0lQs9LIuVqNH9xGWPVpShRCh8WNi4eeEoyZGY28h+zdokDk9hbE1BJTaLWjK1KpiBUFiVpTEhefg1bRjg71Flk+x9SfSU+cB15wB9UAVNydxoYuBgbK1lQewIicctfr3JTCci1Xv9rtSsoYJUiaS55ZDlBLnh2WRo9XG05JA57Ly8IT2UVqiBuT9dHcdcubW9BgDh+l2Jg4gNoU2WSAgHRZWUwNyB/PdZ9L1tRVHkeLQW1OT1RV3xJb784Z0JAY2ozCawXcgUGR3pfQAlVDKJQ0nw7ttA7/gT35RIEpd7jJ/kNP6314kJXxpC/U3eyV08JQjqMeQ1kv1IaICsVaW1BCg==\"}"
    }
    
    resp = safe_request("POST", url, proxy, headers=headers, json=payload, timeout=10)
    
    if resp and resp.status_code == 200:
        data = resp.json()
        return data.get("code") == 200 and "success" in data.get("msg", "").lower()
    return False

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
    # Cập nhật logic: In log debug nếu lấy về 0 hoặc lỗi
    for _ in range(2):
        try:
            # Ưu tiên POST theo document chuẩn nếu có, hoặc thử GET nếu POST không về data
            # Thực tế API này thường là POST với body rỗng hoặc GET đều được
            
            # Thử POST trước
            resp = safe_request("POST", url, proxy, headers=headers, json={})
            
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    d_obj = data.get("data") or {}
                    # Log để debug nếu cần thiết: print(f"DEBUG Assets: {d_obj}")
                    return d_obj.get("assetsNum", 0)
            
            # Nếu POST không được, thử GET
            resp = safe_request("GET", url, proxy, headers=headers)
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    d_obj = data.get("data") or {}
                    return d_obj.get("assetsNum", 0)
                    
        except Exception as e:
            # print(f"Lỗi check buff: {e}")
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

# BỔ SUNG HÀM GET INVITE CODE BỊ THIẾU
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
                await update_callback(f"🔄 Đang thử proxy: {proxy_short}...")
            
            # LOG STEP 1: Lấy Mail (Mail.tm) - DÙNG PROXY
            print(f"[{worker_id}] 🌐 [PROXY] Get Email (Mail.tm)...")
            
            # Unpack tuple: email string, jwt token
            email_data = await asyncio.to_thread(get_temp_email, proxy)
            # Kiểm tra xem có dữ liệu trả về không
            email, mail_token = email_data if email_data else (None, None)
            
            if not email:
                # Log đã in ở get_temp_email
                proxy_manager.mark_bad(proxy)
                continue 

            if update_callback:
                await update_callback(f"📩 Đang gửi mã OTP về {email}...")
            
            # LOG STEP 2: Gửi OTP (Dùng Proxy)
            print(f"[{worker_id}] 📤 [PROXY] Gửi OTP tới {email}...")
            sent = await asyncio.to_thread(send_code_vmos, email, proxy, current_ua)
            
            if not sent:
                print(f"[{worker_id}] ❌ [SEND-FAIL] Lỗi gửi mã.")
                proxy_manager.mark_bad(proxy)
                continue
            
            if update_callback:
                await update_callback(f"⏳ Đang chờ mã OTP...")
            
            # LOG STEP 3: Lấy Code (Dùng Token, DÙNG PROXY, CHECK BODY)
            print(f"[{worker_id}] ⏳ [PROXY] Check inbox (Full Body)...")
            code = await asyncio.to_thread(get_code_from_email, mail_token, email, proxy)
            
            if not code:
                print(f"[{worker_id}] ❌ [TIMEOUT] Không thấy code.")
                continue

            if update_callback:
                await update_callback(f"🔑 Đang đăng nhập...")
            
            # LOG STEP 4: Login (Dùng Proxy)
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
                "proxy_used": proxy
            }
        except Exception as e:
            # print(f"[{worker_id}] 💥 [CRASH] {e}") 
            proxy_manager.mark_bad(proxy)
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
            print(f"[HOST] 🚀 Bắt đầu tạo Host Account...")
            host_acc = await task_worker(invite_code=None, update_callback=update_host_status)
            if not host_acc:
                await msg.edit(content=f"❌ Không thể tạo tài khoản chủ {host_idx}.", embed=None)
                host_idx += 1
                continue
            
            host_token = host_acc['token']
            host_userid = host_acc['userId']
            host_proxy = host_acc['proxy_used']

            # 2. KHỞI ĐỘNG BROWSER & LOGIN (THEO YÊU CẦU PLAYWRIGHT)
            init_embed.description = "🌐 Đang mở trình duyệt để Login..."
            await msg.edit(embed=init_embed)
            
            pw_obj, browser_obj, page_obj = await open_browser_and_login(host_acc['email'], host_acc['password'])

            # 3. LẤY MÃ MỜI (API)
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
            embed_run.add_field(name="📊 Tiến độ Buff", value=f"Đang chạy {num_buffs} luồng (Browser đang treo)...", inline=False)
            if THUMBNAIL_URL:
                embed_run.set_thumbnail(url=THUMBNAIL_URL)
            await msg.edit(embed=embed_run)

            total_proxies = proxy_manager.get_count()
            concurrency = min(total_proxies, 50)
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
                    
                    if proxy_manager.get_live_count() > 0:
                        desired_running = min(concurrency, num_buffs - current_assets_num)
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
                                for t in active_tasks:
                                    t.cancel()
                                active_tasks.clear()
                                break

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
                
            # 6. ĐÓNG TRÌNH DUYỆT
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
    proxies_list = fetch_proxies_from_github()
    
    if not token_local:
        print("❌ KHÔNG THỂ KHỞI ĐỘNG: Thiếu Token trong file 'token.txt'.")
    else:
        if not proxies_list:
            print("⚠️ CẢNH BÁO: Không lấy được proxy nào từ GitHub.")
            
        proxy_manager = ProxyManager(proxies_list)
        
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
