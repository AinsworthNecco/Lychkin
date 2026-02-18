import os
import sys
import sqlite3
import subprocess
import time
import shutil
import urllib.request
from colorama import Fore, Style, init

# Khởi tạo màu sắc
init(autoreset=True)

# Cấu hình
TEMP_DIR = os.path.join(os.getcwd(), "RobloxInjector_Temp") 
COOKIE_FILENAME = "Cookies"
COOKIE_URL = "https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/cookieInject"

# [USER CONFIG]
TARGET_PACKAGE = "com.roblox.client" 

def log(msg, type="INFO"):
    if type == "INFO":
        print(f"{Fore.GREEN}[INFO] {msg}{Style.RESET_ALL}")
    elif type == "WARN":
        print(f"{Fore.YELLOW}[WARN] {msg}{Style.RESET_ALL}")
    elif type == "ERROR":
        print(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}")
    elif type == "DEBUG":
        print(f"{Fore.CYAN}[DEBUG] {msg}{Style.RESET_ALL}")

def run_root_cmd(command):
    try:
        # log(f"Exec: {command}", "DEBUG")
        full_cmd = f"su -c '{command}'"
        result = subprocess.run(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        log(f"Exception executing command: {e}", "ERROR")
        return None, str(e), -1

def check_root():
    log("Đang yêu cầu quyền Root...", "WARN")
    stdout, stderr, code = run_root_cmd("id")
    if code == 0 and "uid=0" in stdout:
        log("Quyền Root: OK", "INFO")
        return True
    else:
        log("KHÔNG CÓ QUYỀN ROOT!", "ERROR")
        return False

def get_remote_cookie():
    log(f"Đang kết nối tới Github...", "INFO")
    try:
        req = urllib.request.Request(COOKIE_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                log(f"Lỗi HTTP: {response.status}", "ERROR")
                return None
            data = response.read().decode('utf-8').strip()
            if "_|WARNING:-DO-NOT-SHARE" in data:
                start_index = data.find("_|WARNING:-DO-NOT-SHARE")
                cookie = data[start_index:].strip()
                return cookie.splitlines()[0]
            return None
    except Exception as e:
        log(f"Lỗi tải cookie: {e}", "ERROR")
        return None

def kill_app(package_name):
    run_root_cmd(f"am force-stop {package_name}")
    time.sleep(1)

def prepare_db(cookie_value):
    db_path = os.path.join(TEMP_DIR, COOKIE_FILENAME)
    if not os.path.exists(db_path):
        log(f"File không tồn tại: {db_path}", "ERROR")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check bảng
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies';")
        if not cursor.fetchone():
            log("DB lỗi (thiếu bảng cookies).", "ERROR")
            return False

        host_key = ".roblox.com"
        name = ".ROBLOSECURITY"
        
        # Xóa cookie cũ
        try:
            cursor.execute("DELETE FROM cookies WHERE host_key = ? AND name = ?", (host_key, name))
        except Exception as e:
            log(f"Lỗi khi xóa cookie cũ: {e}", "WARN")

        now = int(time.time() * 1000000)
        expires = 99999999999999999
        
        # --- CÁC PHIÊN BẢN QUERY ---
        
        # 1. Schema Mới Nhất (Có top_frame_site_key) - Đây là cái fix lỗi của bạn
        query_v3_latest = """
        INSERT INTO cookies (creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, last_access_utc, has_expires, is_persistent, priority, samesite, source_scheme, top_frame_site_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # 2. Schema Hiện đại (14 cột)
        query_v2_modern = """
        INSERT INTO cookies (creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, last_access_utc, has_expires, is_persistent, priority, samesite, source_scheme)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # 3. Schema Cũ (9 cột)
        query_v1_legacy = """
        INSERT INTO cookies (creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, last_access_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Thử chèn lần lượt từ mới nhất đến cũ nhất
        success = False
        
        try:
            # Thử V3 (Fix lỗi NOT NULL top_frame_site_key)
            cursor.execute(query_v3_latest, (now, host_key, name, cookie_value, "/", expires, 1, 1, now, 1, 1, 1, 0, 1, 0)) # Số 0 cuối cùng là top_frame_site_key
            success = True
            log("Sử dụng Schema V3 (Latest - 15 cột)", "DEBUG")
        except sqlite3.Error:
            try:
                # Thử V2
                cursor.execute(query_v2_modern, (now, host_key, name, cookie_value, "/", expires, 1, 1, now, 1, 1, 1, 0, 1))
                success = True
                log("Sử dụng Schema V2 (Modern - 14 cột)", "DEBUG")
            except sqlite3.Error:
                try:
                    # Thử V1
                    cursor.execute(query_v1_legacy, (now, host_key, name, cookie_value, "/", expires, 1, 1, now))
                    success = True
                    log("Sử dụng Schema V1 (Legacy - 9 cột)", "DEBUG")
                except sqlite3.Error as e:
                    log(f"Không thể chèn Cookie vào DB với mọi Schema. Lỗi cuối: {e}", "ERROR")

        conn.commit()
        conn.close()
        return success
    except Exception as e:
        log(f"Lỗi SQLite tổng quát: {e}", "ERROR")
        return False

def find_real_cookie_path(package_name):
    base_path = f"/data/data/{package_name}/app_webview"
    possible_paths = [
        f"{base_path}/Default/Cookies",
        f"{base_path}/Cookies"
    ]
    
    log(f"Đang quét tìm file Cookies cho {package_name}...", "DEBUG")
    
    for path in possible_paths:
        _, _, code = run_root_cmd(f"[ -f '{path}' ]")
        if code == 0:
            log(f"Đã tìm thấy file Cookies tại: {path}", "INFO")
            return path
            
    log("Không tìm thấy file Cookies ở bất kỳ đâu!", "ERROR")
    return None

def inject_cookie(package_name, cookie_value):
    check_pkg, _, _ = run_root_cmd(f"pm path {package_name}")
    if not check_pkg:
        log(f"Gói {package_name} chưa cài đặt!", "ERROR")
        return

    target_path = find_real_cookie_path(package_name)
    if not target_path:
        log("Hãy mở game lên, đăng nhập một nick rác để game tạo file Cookies rồi thử lại.", "WARN")
        return

    log("=== BẮT ĐẦU QUY TRÌNH TIÊM ===", "INFO")
    kill_app(package_name)
    
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    
    cmd_cp_out = f"cp {target_path} {TEMP_DIR}/{COOKIE_FILENAME}"
    _, err, code = run_root_cmd(cmd_cp_out)
    
    if code != 0:
        log(f"Lỗi copy: {err}", "ERROR")
        return

    run_root_cmd(f"chmod 777 {TEMP_DIR}/{COOKIE_FILENAME}")
    
    if not prepare_db(cookie_value):
        log("Thất bại khi xử lý DB.", "ERROR")
        return

    cmd_cp_in = f"cp {TEMP_DIR}/{COOKIE_FILENAME} {target_path}"
    run_root_cmd(cmd_cp_in)
    
    parent_dir = os.path.dirname(target_path)
    owner_raw, _, _ = run_root_cmd(f"stat -c '%U:%G' {parent_dir}")
    owner = owner_raw.strip()
    
    if owner:
        run_root_cmd(f"chown {owner} {target_path}")
        run_root_cmd(f"chmod 600 {target_path}")
    
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    
    log(f"THÀNH CÔNG! Đã nạp cookie vào {target_path}", "INFO")

def main():
    print(f"{Fore.CYAN}=== ROBLOX AUTO INJECTOR (SQLITE FIX) ==={Style.RESET_ALL}")
    
    if not check_root():
        sys.exit(1)
        
    target = TARGET_PACKAGE
    check_main, _, _ = run_root_cmd(f"pm path {target}")
    if not check_main:
        log(f"{target} không thấy, thử tìm com.roblox.client2...", "WARN")
        target = "com.roblox.client2"
    
    log(f"Mục tiêu: {target}", "INFO")

    cookie = get_remote_cookie()
    if not cookie:
        log("Lỗi lấy cookie.", "ERROR")
        sys.exit(1)
        
    inject_cookie(target, cookie)

if __name__ == "__main__":
    main()
