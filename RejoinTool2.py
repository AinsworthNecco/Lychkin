import subprocess
import time
from datetime import datetime

# ---------------------------------------------------
# -- CÀI ĐẶT CHÍNH --
# ---------------------------------------------------

# Danh sách các hậu tố tài khoản Roblox.
# Thay đổi danh sách này để phù hợp với các tài khoản của bạn.
# Ví dụ: ["b", "c", "d", "e", "f"]
ACCOUNT_SUFFIXES = ["b", "c", "d", "e", "f"]

# URL của VIP Server bạn muốn tham gia.
VIP_SERVER_URL = "roblox://placeId=8737602449"

# Thời gian (giây) chờ giữa mỗi lần gửi lệnh join.
OPEN_DELAY_SECONDS = 15

# Tên gói cơ bản của Roblox (không nên thay đổi).
BASE_PACKAGE_NAME = "com.roblox.clien"

# ---------------------------------------------------
# -- CÁC HÀM CHỨC NĂNG --
# ---------------------------------------------------

def launch_roblox_instances():
    """
    Hàm này lặp qua danh sách các hậu tố tài khoản và gửi lệnh
    'am start' để tham gia vào VIP server cho mỗi tài khoản.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Bắt đầu gửi lệnh tham gia server...")

    if not ACCOUNT_SUFFIXES:
        print("Lỗi: Danh sách 'ACCOUNT_SUFFIXES' đang trống. Vui lòng thêm hậu tố tài khoản.")
        return

    for suffix in ACCOUNT_SUFFIXES:
        # Xây dựng tên gói đầy đủ cho từng phiên bản Roblox
        package_name = f"{BASE_PACKAGE_NAME}{suffix}"
        
        # Xây dựng lệnh shell để khởi chạy Roblox
        command = [
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", VIP_SERVER_URL,
            "-p", package_name
        ]

        print(f"-> Đang gửi lệnh join đến tài khoản '{suffix}' (gói: {package_name})")
        
        try:
            # Thực thi lệnh. Lệnh này cần quyền root và môi trường Android (như Termux).
            subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"   Lệnh gửi thành công cho '{suffix}'.")
        except FileNotFoundError:
            print("   Lỗi: Lệnh 'am' không tồn tại. Script này phải được chạy trên Android với Termux.")
            break # Dừng script nếu môi trường không phù hợp
        except subprocess.CalledProcessError as e:
            print(f"   Lỗi khi thực thi lệnh cho '{suffix}': {e.stderr.strip()}")
        except Exception as e:
            print(f"   Đã xảy ra một lỗi không mong muốn: {e}")

        # Chờ một khoảng thời gian trước khi khởi chạy phiên bản tiếp theo
        print(f"   Đang chờ {OPEN_DELAY_SECONDS} giây...")
        time.sleep(OPEN_DELAY_SECONDS)

    print("\nĐã hoàn tất chu kỳ gửi lệnh tham gia.")

# ---------------------------------------------------
# -- ĐIỂM KHỞI ĐẦU CỦA SCRIPT --
# ---------------------------------------------------
if __name__ == "__main__":
    # Dòng 'if __name__ == "__main__":' đảm bảo rằng code bên trong nó
    # chỉ chạy khi bạn thực thi trực tiếp file python này.
    
    print("--- KHỞI ĐỘNG SCRIPT KHỞI CHẠY ROBLOX BẰNG PYTHON ---")
    
    # Lưu ý: Script cần quyền root để chạy lệnh 'am'.
    # Bạn có thể cần chạy nó với 'sudo python your_script_name.py' trên các hệ thống phù hợp.
    
    launch_roblox_instances()
