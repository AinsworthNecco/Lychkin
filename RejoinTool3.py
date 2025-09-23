#!/data/data/com.termux/files/usr/bin/python
# -*- coding: utf-8 -*-

import subprocess
import time
from datetime import datetime

# ---------------------------------------------------
# -- CÀI ĐẶT CHÍNH --
# ---------------------------------------------------

# Danh sách các hậu tố tài khoản Roblox.
ACCOUNT_SUFFIXES = ["b", "c", "d", "e", "f"]

# URL của VIP Server bạn muốn tham gia.
VIP_SERVER_URL = "roblox://placeId=8737602449"

# Thời gian (giây) chờ giữa mỗi lần gửi lệnh join.
OPEN_DELAY_SECONDS = 15

# Tên gói cơ bản của Roblox.
BASE_PACKAGE_NAME = "com.roblox.clien"

# Thời gian (giây) cho mỗi chu kỳ lặp lại (300 giây = 5 phút).
CYCLE_INTERVAL_SECONDS = 300

# ---------------------------------------------------
# -- CÁC HÀM CHỨC NĂNG --
# ---------------------------------------------------

def launch_roblox_instances():
    """
    Hàm này lặp qua danh sách tài khoản và gửi lệnh 'am start'
    để tham gia vào VIP server cho mỗi tài khoản.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Bắt đầu gửi lệnh tham gia server...")

    if not ACCOUNT_SUFFIXES:
        print("Lỗi: Danh sách 'ACCOUNT_SUFFIXES' đang trống.")
        return

    for suffix in ACCOUNT_SUFFIXES:
        package_name = f"{BASE_PACKAGE_NAME}{suffix}"
        command = [
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", VIP_SERVER_URL,
            "-p", package_name
        ]

        print(f"-> Đang gửi lệnh join đến tài khoản '{suffix}'...")
        try:
            # Lưu ý: Lệnh 'am' thường yêu cầu quyền root để hoạt động.
            subprocess.run(command, check=True, capture_output=True, text=True)
        except Exception as e:
            # In ra lỗi nếu có nhưng không dừng script.
            print(f"   Lỗi khi thực thi lệnh cho '{suffix}': {e}")

        time.sleep(OPEN_DELAY_SECONDS)

# ---------------------------------------------------
# -- VÒNG LẶP CHÍNH --
# ---------------------------------------------------

if __name__ == "__main__":
    print("--- KHỞI ĐỘNG SCRIPT TỰ ĐỘNG MỞ ROBLOX MỖI 5 PHÚT ---")
    print("Nhấn Ctrl+C để dừng script.")
    
    try:
        while True:
            launch_roblox_instances()
            print(f"\n--- ĐÃ HOÀN TẤT CHU KỲ. Đang chờ {CYCLE_INTERVAL_SECONDS} giây (5 phút)... ---")
            
            # Đếm ngược thời gian để người dùng dễ theo dõi
            for i in range(CYCLE_INTERVAL_SECONDS, 0, -1):
                # \r di chuyển con trỏ về đầu dòng, end='' để không xuống dòng mới
                print(f"Thời gian chờ còn lại: {i} giây   ", end='\r')
                time.sleep(1)
            print("\n") # Xuống dòng mới sau khi đếm ngược xong

    except KeyboardInterrupt:
        print("\nĐã nhận lệnh dừng từ người dùng. Tạm biệt!")
    except Exception as e:
        print(f"\nĐã xảy ra lỗi không mong muốn: {e}")

