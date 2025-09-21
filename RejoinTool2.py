import subprocess
import os
import sys

# ---------------------------------------------------
# -- CÀI ĐẶT CHÍNH --
# ---------------------------------------------------

# Hậu tố của phiên bản Roblox bạn muốn tắt.
SUFFIX_TO_KILL = "b"

# Tên gói cơ bản của Roblox (không nên thay đổi).
BASE_PACKAGE_NAME = "com.roblox.clien"

# ---------------------------------------------------
# -- CÁC HÀM CHỨC NĂNG --
# ---------------------------------------------------

def check_root():
    """Kiểm tra xem script có đang chạy với quyền root hay không."""
    if os.geteuid() != 0:
        print("Lỗi: Script này cần quyền root để hoạt động.")
        print("Vui lòng chạy lại bằng lệnh: su -c \"python your_script_name.py\"")
        sys.exit(1)

def kill_specific_roblox_instance(suffix):
    """
    Tìm và dừng một tiến trình Roblox cụ thể dựa trên hậu tố được cung cấp.
    """
    package_to_stop = f"{BASE_PACKAGE_NAME}{suffix}"
    print(f"Đang tìm và dừng phiên bản Roblox: {package_to_stop}...")

    try:
        # Lấy danh sách tất cả các tiến trình đang chạy
        result = subprocess.run(['ps', '-ef'], capture_output=True, text=True, check=True)
        processes = result.stdout.strip().split('\n')
        
        found = False
        for line in processes:
            # Tìm dòng chứa tên gói và không phải là tiến trình grep
            if package_to_stop in line and 'grep' not in line:
                parts = line.split()
                pid = parts[1]
                print(f"  => Đã tìm thấy! Dừng phiên bản {package_to_stop} (PID: {pid}).")
                subprocess.run(['kill', '-9', pid], check=True)
                found = True
                break # Dừng lại sau khi tìm thấy và xử lý
        
        if not found:
            print(f"  - Không tìm thấy tiến trình nào đang chạy cho {package_to_stop}.")

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  Không thể thực thi lệnh. Lỗi: {e}")
    except Exception as e:
        print(f"  Đã xảy ra lỗi không mong muốn: {e}")

    print("Đã hoàn tất.")

# ---------------------------------------------------
# -- ĐIỂM KHỞI ĐẦU CỦA SCRIPT --
# ---------------------------------------------------
if __name__ == "__main__":
    print("--- SCRIPT KIỂM TRA TẮT PHIÊN BẢN ROBLOX CỤ THỂ ---")
    
    # 1. Kiểm tra quyền root
    check_root()

    # 2. Gọi hàm để tắt phiên bản đã chỉ định
    kill_specific_roblox_instance(SUFFIX_TO_KILL)
