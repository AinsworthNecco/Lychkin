#!/data/data/com.termux/files/usr/bin/bash
# Script Dieu Khien Roblox Dua Tren Gist
# PHIEN BAN 2.1: Sua loi so sanh trang thai do ky tu xuong dong (CRLF).
# Lien ket phien ban bang Tên người dùng va lay trang thai tu GitHub Gist.
#---------------------------------------------------
# -- CAI DAT CHINH --
#---------------------------------------------------

# [QUAN TRONG] Lien ket hau to phien ban voi TEN TAI KHOAN Roblox.
# Dinh dang: "hau_to_1:username_1 hau_to_2:username_2"
# VI DU: "b:Player1 c:Player_Two"
AccountMap="b:WolfCodeFusion c:ArrowStarHaz3 d:Sab3r_Aqua2007 e:XxJacksonUltraxX14 f:XxAlpha_ZAPXX2007"

# URL RAW cua file Gist chua trang thai tai khoan (username:status)
GistStatusUrl="https://gist.githubusercontent.com/AinsworthNecco/2582fc470f4594f789b3441605d3a442/raw/cd1d886b675e46d72bfa2d1df5869e4a4246ce92/server_list.txt"

# URL cua VIP Server ban muon tham gia
VipServerUrl="roblox://placeId=8737602449"

# Thoi gian (giay) giua moi lan MO tat ca cac phien ban (600 giay = 10 phut)
LaunchInterval=600

# Thoi gian (giay) giua moi lan KIEM TRA trang thai tu Gist (1800 giay = 30 phut)
CheckInterval=1800

# Thoi gian (giay) cho giua moi lan gui lenh 'am start' trong mot chu ky
OpenDelay=1

# Ten goi co ban cua Roblox (khong nen thay doi)
BasePackageName="com.roblox.clien"

#---------------------------------------------------
# -- TU DONG KIEM TRA --
#---------------------------------------------------
# Kiem tra quyen root
if [[ $EUID -ne 0 ]]; then
    echo "Script nay can quyen root. Dang co gang chay lai voi 'su'..."
    su -c "bash \"$0\" \"$@\""
    exit 0
fi

#---------------------------------------------------
# -- CAC HAM HO TRO --
#---------------------------------------------------

# Ham dung mot phien ban cu the dua vao hau to
function kill_instance_by_suffix() {
    local suffix="$1"
    if [[ -z "$suffix" ]]; then return; fi
    
    local package_to_stop="${BasePackageName}${suffix}"
    local pid_to_kill=$(ps -ef | grep "$package_to_stop" | grep -v grep | awk '{print $2}')
    
    if [[ -n "$pid_to_kill" ]]; then
        echo "  => Phat hien trang thai khong hop le. Dang dung phien ban $package_to_stop (PID: $pid_to_kill)."
        kill -9 "$pid_to_kill"
    else
        echo "  => Phien ban $package_to_stop da dung san."
    fi
}

#---------------------------------------------------
# -- VONG LAP CHINH --
#---------------------------------------------------

# Vong lap 1: Chi de mo game (chay moi 10 phut)
function launch_loop() {
    while true; do
        echo "================================================="
        echo "[$(date '+%Y-%-m-%d %H:%M:%S')] KHOI DONG CHU KY MO GAME (Lap lai sau ${LaunchInterval}s)..."
        
        read -r -a account_pairs <<< "$AccountMap"
        if [[ ${#account_pairs[@]} -eq 0 ]]; then
            echo "Loi: 'AccountMap' chua duoc cau hinh. Vui long them 'hau_to:username'."
        else
            for pair in "${account_pairs[@]}"; do
                local suffix="${pair%%:*}"
                local package_name="${BasePackageName}${suffix}"
                echo "-> Gui lenh join den phien ban '$suffix' ($package_name)"
                am start -a android.intent.action.VIEW -d "$VipServerUrl" -p "$package_name"
                sleep "$OpenDelay"
            done
        fi
        
        echo "Hoan tat chu ky mo game. Dang cho..."
        sleep "$LaunchInterval"
    done
}

# Vong lap 2: Kiem tra Gist va dung phien ban neu can (chay moi 30 phut)
function check_and_kill_loop() {
    while true; do
        echo "================================================="
        echo "[$(date '+%Y-%-m-%d %H:%M:%S')] KHOI DONG CHU KY KIEM TRA GIST (Lap lai sau ${CheckInterval}s)..."

        echo "-> Dang tai du lieu trang thai tu Gist..."
        local gist_content=$(curl --max-time 15 -s "$GistStatusUrl")

        if [[ -z "$gist_content" ]]; then
            echo "LOI: Khong the tai du lieu tu Gist. Co the do loi mang hoac URL sai. Bo qua chu ky nay."
        else
            echo "-> Tai du lieu Gist thanh cong. Bat dau kiem tra tung tai khoan."
            read -r -a account_pairs <<< "$AccountMap"
            for pair in "${account_pairs[@]}"; do
                local suffix="${pair%%:*}"
                local username="${pair##*:}"
                
                echo "---"
                echo "-> Kiem tra '$username' (phien ban '$suffix')..."
                
                # Tim dong tuong ung voi username trong Gist
                local user_line=$(echo "$gist_content" | grep "^${username}:")
                
                if [[ -z "$user_line" ]]; then
                    echo "  -> Canh bao: Khong tim thay username '$username' trong file Gist."
                    continue
                fi
                
                # Lay trang thai (so sau dau ':') va loai bo ky tu \r
                local status=$(echo "$user_line" | cut -d':' -f2 | tr -d '\r')
                
                if [[ "$status" == "0" ]]; then
                    echo "  -> Trang thai: 0 (In-Game). Bo qua."
                else
                    echo "  -> Trang thai: $status (Khong phai In-Game). Tien hanh dung phien ban."
                    kill_instance_by_suffix "$suffix"
                fi
            done
        fi
        
        echo "Hoan tat chu ky kiem tra. Dang cho..."
        sleep "$CheckInterval"
    done
}


# --- DIEM KHOI DAU CUA SCRIPT ---
clear
echo "--- KHOI DONG SCRIPT DIEU KHIEN ROBLOX ---"
echo "Kich hoat Wake Lock de giu cho thiet bi thuc..."
termux-wake-lock &

# Chay ca hai vong lap dong thoi o che do nen
launch_loop &
check_and_kill_loop &

# Doi cho cac tac vu nen hoan thanh (se khong bao gio xay ra, giup script chay mai mai)
wait
