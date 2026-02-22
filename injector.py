#!/data/data/com.termux/files/usr/bin/bash

# ==============================================================================
# SCRIPT: Cookie Injector Pure (Bash Version)
# Chức năng: CHỈ Tải Cookie và Nạp vào máy bằng Bash Script.
# ==============================================================================

# ---------------------------------------------------
# -- CẤU HÌNH (SỬA TRỰC TIẾP TẠI ĐÂY) --
# ---------------------------------------------------

# 1. Danh sách hậu tố tài khoản (Ngăn cách bằng khoảng trắng)
ACCOUNT_SUFFIXES_STR="b c d e f"

# 2. Tên gói gốc (Thường không cần sửa)
BASE_PACKAGE_NAME="com.roblox.clien"

# 3. URL lấy Cookie
COOKIE_URL="https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/cookieInject"

# ---------------------------------------------------
# -- BIẾN CỤC BỘ --
# ---------------------------------------------------
TEMP_DIR="$(pwd)/RobloxInjector_Temp"
COOKIE_FILENAME="Cookies"
REMOTE_COOKIES=()

# ==============================================================================
# -- HÀM HỆ THỐNG CƠ BẢN --
# ==============================================================================

check_requirements() {
    echo "[SYSTEM] Đang kiểm tra hệ thống..."
    
    # Kiểm tra Root
    if [ "$(su -c whoami)" != "root" ]; then
        echo "[SYSTEM] -> Lỗi: Không có quyền root. Hãy cấp quyền Root cho Termux!"
        exit 1
    else
        echo "[SYSTEM] -> Quyền root: OK."
    fi

    # Kiểm tra thư viện SQLite3 trong Termux
    if ! command -v sqlite3 &> /dev/null; then
        echo "[SYSTEM] -> Thiếu thư viện sqlite3. Đang tự động cài đặt..."
        pkg install sqlite -y > /dev/null 2>&1
        echo "[SYSTEM] -> Cài đặt sqlite3 hoàn tất."
    fi
}

# ==============================================================================
# -- HÀM INJECTOR LOGIC --
# ==============================================================================

get_remote_cookies_list() {
    echo "[COOKIE] Đang tải danh sách Cookie từ GitHub..."
    local response
    response=$(curl -sSL -A "Mozilla/5.0" "$COOKIE_URL")
    
    if [ -z "$response" ]; then
        echo "[COOKIE] Lỗi: Không tải được dữ liệu từ link."
        return
    fi

    # Lọc lấy các dòng cookie chuẩn (Chứa warning của Roblox)
    while IFS= read -r line; do
        if [[ "$line" == *"_|WARNING:-DO-NOT-SHARE"* ]]; then
            REMOTE_COOKIES+=("$line")
        fi
    done <<< "$response"
    
    echo "[COOKIE] Tìm thấy ${#REMOTE_COOKIES[@]} cookie hợp lệ."
}

find_real_cookie_path() {
    local pkg=$1
    local base_path="/data/data/$pkg/app_webview"
    local paths=("$base_path/Default/Cookies" "$base_path/Cookies")

    for path in "${paths[@]}"; do
        if [ "$(su -c "[ -f '$path' ] && echo YES || echo NO")" = "YES" ]; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

get_local_cookie_injector() {
    local pkg=$1
    local target_path
    target_path=$(find_real_cookie_path "$pkg")
    
    if [ -z "$target_path" ]; then
        echo ""
        return
    fi

    mkdir -p "$TEMP_DIR"
    local temp_check_path="$TEMP_DIR/Cookies_Check"
    
    # Copy file ra môi trường Termux và cấp quyền để đọc
    su -c "cp '$target_path' '$temp_check_path' && chmod 777 '$temp_check_path'"

    # Dùng sqlite3 để truy vấn giá trị
    local local_cookie
    local_cookie=$(sqlite3 "$temp_check_path" "SELECT value FROM cookies WHERE name = '.ROBLOSECURITY';" 2>/dev/null)
    
    # Dọn dẹp file tạm
    rm -f "$temp_check_path"
    echo "$local_cookie"
}

inject_cookie_process() {
    local pkg=$1
    local cookie_value=$2

    local check_pkg=$(su -c "pm path $pkg")
    if [ -z "$check_pkg" ]; then
        echo "[COOKIE] Gói $pkg chưa cài đặt -> Bỏ qua."
        return 1
    fi

    local target_path
    target_path=$(find_real_cookie_path "$pkg")
    if [ -z "$target_path" ]; then
        echo "[COOKIE] ⚠️ Không tìm thấy file Cookies của $pkg."
        echo "[COOKIE] -> Hãy mở app lên ít nhất 1 lần để tạo file."
        return 1
    fi

    # Dừng app
    su -c "am force-stop $pkg"
    sleep 1

    # Chuẩn bị thư mục tạm
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    local temp_db="$TEMP_DIR/$COOKIE_FILENAME"

    # Copy database ra Termux và cấp quyền chỉnh sửa
    su -c "cp '$target_path' '$temp_db'" || { echo "[COOKIE] Lỗi copy file gốc"; return 1; }
    su -c "chmod 777 '$temp_db'"

    # Kiểm tra tính hợp lệ của DB
    local table_exists=$(sqlite3 "$temp_db" "SELECT name FROM sqlite_master WHERE type='table' AND name='cookies';")
    if [ -z "$table_exists" ]; then
        echo "[COOKIE] Lỗi xử lý DB: Không tìm thấy bảng cookies."
        return 1
    fi

    # Thông số cho bảng Cookie
    local host_key=".roblox.com"
    local name=".ROBLOSECURITY"
    local now=$(($(date +%s) * 1000000))
    local expires="99999999999999999"

    # Xóa Cookie cũ
    sqlite3 "$temp_db" "DELETE FROM cookies WHERE host_key = '$host_key' AND name = '$name';"

    # Nạp Cookie mới (Thử câu lệnh đầy đủ trước, nếu lỗi do khác phiên bản Android thì dùng fallback)
    local query_full="INSERT INTO cookies (creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, last_access_utc, has_expires, is_persistent, priority, samesite, source_scheme) VALUES ($now, '$host_key', '$name', '$cookie_value', '/', $expires, 1, 1, $now, 1, 1, 1, 0, 1);"
    local query_fallback="INSERT INTO cookies (creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, last_access_utc) VALUES ($now, '$host_key', '$name', '$cookie_value', '/', $expires, 1, 1, $now);"

    local insert_res=$(sqlite3 "$temp_db" "$query_full" 2>&1)
    if [[ "$insert_res" == *"Error"* ]] || [[ "$insert_res" == *"no such column"* ]]; then
        sqlite3 "$temp_db" "$query_fallback"
    fi

    # Copy file đã sửa vào lại vị trí cũ
    su -c "cp '$temp_db' '$target_path'"

    # Fix quyền sở hữu file (Rất quan trọng)
    local parent_dir=$(dirname "$target_path")
    local owner=$(su -c "stat -c '%U:%G' '$parent_dir'")
    
    if [ -n "$owner" ]; then
        su -c "chown $owner '$target_path'"
        su -c "chmod 600 '$target_path'"
    fi

    # Dọn dẹp
    rm -rf "$TEMP_DIR"
    echo "[COOKIE] -> Đã nạp Cookie mới cho: $pkg"
    return 0
}

# ==============================================================================
# -- MAIN EXECUTION --
# ==============================================================================

run_main_sequence() {
    echo ""
    echo "[MAIN] === COOKIE INJECTOR PURE (BASH SCRIPT) ==="
    
    get_remote_cookies_list
    if [ ${#REMOTE_COOKIES[@]} -eq 0 ]; then
        echo "[MAIN] Không lấy được danh sách Cookie -> Dừng."
        return
    fi

    echo ""
    echo "[PROCESS] Bắt đầu kiểm tra và inject..."
    
    # Duyệt qua từng tài khoản được thiết lập
    local i=0
    for suffix in $ACCOUNT_SUFFIXES_STR; do
        local pkg_name="${BASE_PACKAGE_NAME}${suffix}"
        
        # Gán cookie theo thứ tự
        if [ $i -lt ${#REMOTE_COOKIES[@]} ]; then
            local assigned_cookie="${REMOTE_COOKIES[$i]}"
        else
            echo "[COOKIE] ⚠️ Không đủ Cookie cho '$suffix' (Acc #$((i+1))). Bỏ qua."
            continue
        fi

        echo -n "[ACC] '$suffix' -> "
        
        # Kiểm tra cookie hiện tại
        local local_cookie
        local_cookie=$(get_local_cookie_injector "$pkg_name")

        if [ "$local_cookie" == "$assigned_cookie" ]; then
            echo "OK (Khớp)."
        else
            if [ -z "$local_cookie" ]; then
                echo "MISSING -> Injecting..."
            else
                echo "MISMATCH -> Injecting..."
            fi
            inject_cookie_process "$pkg_name" "$assigned_cookie"
        fi
        
        i=$((i+1))
    done
    
    echo ""
    echo "[MAIN] === HOÀN TẤT ==="
}

# Bắt đầu chạy
check_requirements
run_main_sequence
