#!/usr/bin/env bash

# ==============================================================================
# ROBLOX MASTER SCRIPT v12.0
#
# Khởi chạy Scanner và Launcher như hai tiến trình độc lập, chạy song song.
#
# - TASK SCANNER: Liên tục tải config, quét server, và lưu kết quả.
# - TASK LAUNCHER: Liên tục kiểm tra trạng thái các tài khoản và khởi động lại
#   chúng vào một VIP server cố định.
# ==============================================================================

CONFIG_URL="https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/config"
REMOTE_CONFIG_FILE="./remote_config.conf"

# --- TỰ ĐỘNG KIỂM TRA ROOT ---
if [[ $EUID -ne 0 ]]; then
    echo "Script này cần quyền root để thực thi 'kill'. Đang chạy lại với 'su'..."
    su -c "bash \"$0\" \"$@\""
    exit 0
fi

# ==============================================================================
# -- TASK 1: SCANNER (QUÉT SERVER) --
# Chạy trong một vòng lặp vô tận.
# ==============================================================================
function task_scanner() {
    echo "[SCANNER]: Tiến trình quét đã khởi động."
    local proxy_index=0
    local failed_proxy_count=0
    local -a formatted_proxy_list=()
    local -a collected_ids=()

    while true; do
        # Tải config mới nhất ở mỗi chu kỳ
        echo "[SCANNER]: Đang tải cấu hình từ xa..."
        if curl -sL "$CONFIG_URL" -o "$REMOTE_CONFIG_FILE"; then
            sed -i 's/\r$//' "$REMOTE_CONFIG_FILE"; source "$REMOTE_CONFIG_FILE"
            if [[ -z "${PLACE_ID:-}" ]]; then
                 echo "[SCANNER]: Lỗi cấu hình. Thử lại sau 30 giây."; sleep 30; continue
            fi
            echo "[SCANNER]: Tải cấu hình thành công. Bắt đầu quét..."
        else
            echo "[SCANNER]: Lỗi tải cấu hình. Thử lại sau 30 giây."; sleep 30; continue
        fi
        
        # Xử lý lại danh sách proxy mỗi lần tải config
        formatted_proxy_list=()
        if [[ ${#PROXY_LIST[@]} -gt 0 && -n "${PROXY_LIST[0]}" ]]; then
            for proxy_string in "${PROXY_LIST[@]}"; do
                IFS=':' read -r -a parts <<< "$proxy_string"; local formatted_proxy=""
                if [[ ${#parts[@]} -eq 4 ]]; then formatted_proxy="http://${parts[2]}:${parts[3]}@${parts[0]}:${parts[1]}"; fi
                if [[ -n "$formatted_proxy" ]]; then formatted_proxy_list+=("$formatted_proxy"); fi
            done
        fi
        
        local num_proxies=${#formatted_proxy_list[@]}
        local output_file="${OUTPUT_DIR}/${OUTPUT_FILE_NAME}"
        local min_p=$(awk "BEGIN {print ${MIN_PLAYER_PERCENTAGE}/100}")
        local max_p=$(awk "BEGIN {print ${MAX_PLAYER_PERCENTAGE}/100}")
        collected_ids=()
        mkdir -p "$OUTPUT_DIR"
        
        local next_cursor=""
        while true; do # Vòng lặp quét các trang
            local api_url="https://games.roblox.com/v1/games/${PLACE_ID}/servers/Public?sortOrder=Desc&limit=100"
            [[ -n "$next_cursor" && "$next_cursor" != "null" ]] && api_url="${api_url}&cursor=${next_cursor}"

            # Vòng lặp xử lý proxy/kết nối
            local response_body=""
            while true; do
                if (( num_proxies > 0 && failed_proxy_count >= num_proxies )); then
                    echo -e "\n[SCANNER]: Tất cả proxies đều thất bại. Tạm dừng 5 giây..."
                    sleep 5; failed_proxy_count=0; proxy_index=0
                fi

                local curl_cmd=("curl" "--silent" "--max-time" "20" "-w" "\n%{http_code}")
                local proxy_status="IP Gốc"; if (( num_proxies > 0 )); then
                    curl_cmd+=("--proxy" "${formatted_proxy_list[$proxy_index]}")
                    proxy_status="Proxy ${proxy_index}/${num_proxies}"
                fi
                curl_cmd+=("$api_url")
                printf "\r[SCANNER]: Quét trang... | Thu thập: %-5s | Kết nối: %-15s" "${#collected_ids[@]}" "$proxy_status"
                
                local response_with_code=$("${curl_cmd[@]}")
                local http_code=$(echo "$response_with_code" | tail -n1)
                
                if [[ "$http_code" == "200" ]]; then
                    response_body=$(echo "$response_with_code" | sed '$d')
                    failed_proxy_count=0; break
                else
                    if (( num_proxies > 0 )); then
                        ((failed_proxy_count++)); ((proxy_index = (proxy_index + 1) % num_proxies)); sleep 1
                    else
                        echo -e "\n[SCANNER]: IP Gốc thất bại. Tạm dừng 60 giây..."; sleep 60
                    fi
                fi
            done
            
            next_cursor=$(echo "$response_body" | grep -o '"nextPageCursor":"[^"]*"' | sed 's/"nextPageCursor":"//; s/"$//')
            # ... (Phần logic xử lý JSON không thay đổi) ...
            while IFS= read -r server; do
                if [[ -z "$server" ]]; then continue; fi
                local playing=$(echo "$server" | grep -o '"playing":[0-9]*' | sed 's/"playing"://'); local max_players=$(echo "$server" | grep -o '"maxPlayers":[0-9]*' | sed 's/"maxPlayers"://')
                if [[ -n "$playing" && -n "$max_players" && "$max_players" -gt 0 ]]; then
                    local p_percent=$(awk "BEGIN {print ${playing}/${max_players}}")
                    local is_valid=$(awk -v p="$p_percent" -v min="$min_p" -v max="$max_p" 'BEGIN {print (p >= min && p <= max)}')
                    if [[ "$is_valid" -eq 1 ]]; then
                        local server_id=$(echo "$server" | grep -o '"id":"[^"]*"' | sed 's/"id":"//; s/"$//'); if [[ -n "$server_id" ]]; then collected_ids+=("$server_id"); fi
                    fi
                fi
            done < <(echo "$response_body" | awk 'match($0, /"data":\[(.*)\]/, a) { print a[1] }' | sed 's/},{/}\n{/g')
            
            if [[ -z "$next_cursor" || "$next_cursor" == "null" ]]; then break; fi
        done
        
        echo -e "\n[SCANNER]: Quét xong. Ghi ${#collected_ids[@]} ID vào file."
        printf "%s\n" "${collected_ids[@]}" > "$output_file"
        
        echo "[SCANNER]: Chu kỳ hoàn tất. Nghỉ ${SCANNER_INTERVAL_SECONDS} giây."
        sleep "$SCANNER_INTERVAL_SECONDS"
    done
}


# ==============================================================================
# -- TASK 2: LAUNCHER (QUẢN LÝ CLIENT) --
# Chạy trong một vòng lặp vô tận.
# ==============================================================================
function task_launcher() {
    echo "[LAUNCHER]: Tiến trình launcher đã khởi động."
    while true; do
        # Chỉ source file config cục bộ, không tải lại
        if [[ -f "$REMOTE_CONFIG_FILE" ]]; then
            source "$REMOTE_CONFIG_FILE"
        else
            echo "[LAUNCHER]: Không tìm thấy file config. Chờ 60 giây..."
            sleep 60; continue
        fi
        
        echo "================================================="
        echo "[LAUNCHER] [$(date '+%H:%M:%S')] Bắt đầu chu kỳ làm mới..."

        read -r -a account_pairs <<< "$AccountMap"
        if [[ ${#account_pairs[@]} -eq 0 ]]; then
             echo "[LAUNCHER]: Lỗi: 'AccountMap' không được định nghĩa."; sleep 60; continue
        fi

        for pair in "${account_pairs[@]}"; do
            local suffix="${pair%%:*}"; local user_id="${pair##*:}"
            local package_name="${BasePackageName}${suffix}"
            echo "---"
            echo "-> [LAUNCHER] Kiểm tra '$suffix' (ID: $user_id)..."

            local presence_api="https://presence.roblox.com/v1/presence/users"
            local presence_payload="{\"userIds\": [$user_id]}"
            local presence_data_raw=$(curl --max-time 10 -s -X POST -H "Content-Type: application/json" -d "$presence_payload" "$presence_api")
            local presence_type=$(echo "$presence_data_raw" | grep -o '"userPresenceType":[0-9]*' | sed 's/"userPresenceType"://')

            if [[ "$presence_type" -ne 2 ]]; then
                echo "   -> Trạng thái: NOT IN GAME. Khởi động lại..."
                local pid_to_kill=$(ps -A | grep "$package_name" | grep -v grep | awk '{print $2}')
                if [[ -n "$pid_to_kill" ]]; then
                    echo "      => Đang tắt PID: $pid_to_kill"
                    kill -9 "$pid_to_kill"; sleep 3
                fi
            else
                echo "   -> Trạng thái: IN GAME. Gửi lệnh join để làm mới..."
            fi

            echo "      => Gửi lệnh join đến: $package_name"
            am start -a android.intent.action.VIEW -d "$VipServerUrl" -p "$package_name"
            sleep "$OpenDelay"
        done
        
        echo "================================================="
        echo "[LAUNCHER]: Chu kỳ hoàn tất. Nghỉ ${LAUNCHER_CYCLE_INTERVAL} giây."
        sleep "$LAUNCHER_CYCLE_INTERVAL"
    done
}

# ==============================================================================
# -- ĐIỂM KHỞI ĐẦU SCRIPT --
# ==============================================================================
clear
echo "--- ROBLOX MASTER SCRIPT ---"

# Tải config lần đầu để các biến sẵn sàng
echo "[MASTER]: Tải cấu hình lần đầu..."
curl -sL "$CONFIG_URL" -o "$REMOTE_CONFIG_FILE"
if [[ ! -s "$REMOTE_CONFIG_FILE" ]]; then
    echo "[MASTER]: LỖI NGHIÊM TRỌNG: Không thể tải file config lần đầu. Thoát."
    exit 1
fi
source "$REMOTE_CONFIG_FILE"

# Dừng tất cả các phiên bản cũ trước khi bắt đầu
echo "[MASTER]: Dọn dẹp các phiên bản Roblox cũ..."
read -r -a account_pairs <<< "$AccountMap"
for pair in "${account_pairs[@]}"; do
    suffix="${pair%%:*}"; package_to_stop="${BasePackageName}${suffix}"
    pid_to_kill=$(ps -A | grep "$package_to_stop" | grep -v grep | awk '{print $2}')
    if [[ -n "$pid_to_kill" ]]; then
        kill -9 "$pid_to_kill"
    fi
done
sleep 5

# Kích hoạt Wake Lock và chạy 2 tác vụ trong nền
echo "[MASTER]: Kích hoạt Wake Lock."
termux-wake-lock
echo "[MASTER]: Khởi chạy các tiến trình SCANNER và LAUNCHER trong nền."
task_scanner &
task_launcher &

# Chờ các tiến trình nền (sẽ không bao giờ kết thúc)
echo "[MASTER]: Script đang chạy. Để dừng lại, hãy dùng lệnh 'killall bash'."
wait

