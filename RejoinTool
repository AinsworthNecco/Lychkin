#!/data/data/com.termux/files/usr/bin/bash
# Script Roblox Toan Dien voi 2 chu ky hoat dong doc lap:
# 1. Chu ky 10 phut: Lien tuc gui lenh khoi dong Roblox.
# 2. Chu ky 3 gio: Tat toan bo cac phien ban Roblox.
# (Da loai bo chu ky 4 gio khoi dong lai Termux)
#---------------------------------------------------
# -- CAI DAT CHINH --
#---------------------------------------------------

# Lien ket hau to phien ban voi ID tai khoan Roblox tuong ung.
# Dinh dang: "b c d e f g"
AccountMap="b c d e f"

# URL cua VIP Server ban muon tham gia
VipServerUrl="roblox://placeId=8737602449"

# Thoi gian (giay) giua moi lan gui lenh khoi dong (600 giay = 10 phut)
CycleInterval=600

# Thoi gian (giay) de tat toan bo Roblox (10800 giay = 3 gio)
RobloxKillInterval=30800

# Thoi gian (giay) cho giua moi lan gui lenh join trong mot chu ky
OpenDelay=15

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
# -- CAC HAM CHUC NANG --
#---------------------------------------------------

# Ham tat toan bo cac phien ban Roblox
function kill_all_roblox_instances() {
    echo "Dang dung tat ca cac phien ban Roblox dang chay..."
    read -r -a account_pairs <<< "$AccountMap"
    if [[ ${#account_pairs[@]} -eq 0 ]]; then return; fi

    for pair in "${account_pairs[@]}"; do
        suffix="${pair%%:*}"
        package_to_stop="${BasePackageName}${suffix}"
        
        pid_to_kill=$(ps -ef | grep "$package_to_stop" | grep -v grep | awk '{print $2}')
        if [[ -n "$pid_to_kill" ]]; then
            echo "  => Dung phien ban $package_to_stop (PID: $pid_to_kill)."
            kill -9 "$pid_to_kill"
        fi
    done
    echo "Da hoan tat viec dung cac phien ban Roblox."
}

# Ham chi de gui lenh khoi dong (cho chu ky 10 phut)
function simple_join_instances() {
    echo "[$(date '+%Y-%-m-%d %H:%M:%S')] Gui lenh khoi dong (chu ky 10 phut)..."
    read -r -a account_pairs <<< "$AccountMap"
    if [[ ${#account_pairs[@]} -eq 0 ]]; then
        echo "Loi: Vui long dinh nghia tai khoan trong 'AccountMap'."
        return
    fi
    
    for pair in "${account_pairs[@]}"; do
        suffix="${pair%%:*}"
        package_name="${BasePackageName}${suffix}"
        echo "-> Gui lenh join den '$suffix' ($package_name)"
        am start -a android.intent.action.VIEW -d "$VipServerUrl" -p "$package_name"
        sleep "$OpenDelay"
    done
}


# Ham cho VONG LAP QUAN LY ROBLOX (chay o luong chinh)
function roblox_manager_loop() {
    # Vong lap vo tan de quan ly cac chu ky 3 gio
    while true; do
        echo "--- BAT DAU CHU KY 3 GIO MOI ---"
        
        # Tinh toan so lan lap 10 phut trong mot chu ky 3 gio
        local num_cycles=$((RobloxKillInterval / CycleInterval))

        # Vong lap 10 phut: Lien tuc gui lenh join trong 3 gio
        for (( i=1; i<=num_cycles; i++ )); do
            clear
            echo "--- Chu ky 3 gio (Vong lap $i/$num_cycles) ---"
            simple_join_instances
            
            echo "================================================="
            echo "Da hoan tat. Dang cho $CycleInterval giay..."
            sleep "$CycleInterval"
        done

        # Sau khi hoan tat chu ky 3 gio, dung tat ca cac phien ban Roblox
        echo "--- DA HOAN TAT CHU KY 3 GIO. DANG DUNG TOAN BO ROBLOX ---"
        kill_all_roblox_instances
        sleep 5 # Cho mot chut truoc khi bat dau chu ky 3 gio moi
    done
}

# --- DIEM KHOI DAU CUA SCRIPT ---
clear
echo "--- KHOI DONG HE THONG SCRIPT VOI 2 CHU KY ---"
kill_all_roblox_instances # Don dep truoc khi bat dau
sleep 5

echo "Kich hoat Wake Lock de giu cho thiet bi thuc..."
termux-wake-lock &

# Chay vong lap quan ly Roblox (chu ky 10 phut & 3 gio) o che do CHINH
# Script se chay vo tan o day cho den khi ban tu tat.
roblox_manager_loop
