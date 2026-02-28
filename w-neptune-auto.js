// ==UserScript==
// @name         Neptune's Auto - Luarmor & Linkvertise
// @namespace    http://tampermonkey.net/
// @version      2.6
// @description  Tự động hóa chu trình Luarmor -> Linkvertise. Thêm độ trễ 5 giây cho mọi thao tác để tăng tính ổn định.
// @author       Gemini
// @match        *://ads.luarmor.net/*
// @match        *://*.linkvertise.com/*
// @match        *://linkvertise.com/*
// @grant        window.close
// @updateURL    https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/w-neptune-auto.js
// @downloadURL  https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/w-neptune-auto.js
// ==/UserScript==

(function() {
    'use strict';

    // --- CẤU HÌNH CƠ BẢN ---
    const WAIT_TIME_MINUTES = 15; // Thay đổi số phút chờ ở đây (Mặc định 15 phút)
    // -----------------------

    const currentHost = window.location.hostname;
    const isLuarmor = currentHost.includes('luarmor.net');
    const isLinkvertise = currentHost.includes('linkvertise.com');
    const COOLDOWN_KEY = 'luarmor_cooldown_until';

    // -- GIAO DIỆN CONSOLE NEPTUNE'S AUTO --
    let consoleEl;
    function initConsole() {
        if (!document.body) {
            setTimeout(initConsole, 500);
            return;
        }
        if (document.getElementById('neptune-auto-console')) return;
        
        consoleEl = document.createElement('div');
        consoleEl.id = 'neptune-auto-console';
        
        consoleEl.style.cssText = `
            position: fixed;
            top: 20%;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(rgba(15, 20, 30, 0.75), rgba(15, 20, 30, 0.75)), url('https://i.pinimg.com/736x/26/27/df/2627df32c9282724dbc6ba23fd191551.jpg') center/cover no-repeat;
            backdrop-filter: blur(8px);
            padding: 30px 40px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            z-index: 9999999;
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            text-align: center;
            pointer-events: none;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 280px;
        `;
        
        const imageUrl = "https://i.pinimg.com/originals/a9/5e/94/a95e941785991c66adc761b5f71f2268.gif";

        consoleEl.innerHTML = `
            <img src="${imageUrl}" style="width: 150px; height: 150px; border: 2px solid rgba(255, 255, 255, 0.9); border-radius: 4px; object-fit: cover; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
            <div style="color: #ffffff; font-size: 22px; font-weight: bold; margin-top: 20px; letter-spacing: 0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">Neptune's Auto</div>
            <div id="auto-status" style="color: #c0c8d0; font-size: 14px; margin-top: 8px; font-weight: 500; text-shadow: 0 1px 3px rgba(0,0,0,0.8);">Đang khởi động...</div>
            <div id="auto-countdown" style="color: #ff69b4; font-size: 42px; font-weight: bold; margin-top: 15px; display: none; text-shadow: 0 0 10px rgba(255,105,180,0.5);"></div>
        `;
        document.body.appendChild(consoleEl);
    }

    function logToConsole(msg) {
        console.log(`[Neptune's Auto] ${msg}`);
        if (!consoleEl) initConsole();
        const statusEl = document.getElementById('auto-status');
        if (statusEl) {
            statusEl.innerText = msg;
        }
    }

    initConsole();
    
    setTimeout(() => {
        logToConsole(`Đang hoạt động trên: ${currentHost}`);
    }, 500);

    const clickedButtons = new Set();

    const isVisible = (elem) => {
        return !!(elem.offsetWidth || elem.offsetHeight || elem.getClientRects().length);
    };

    const findButtonByText = (targetText) => {
        const elements = document.querySelectorAll('button, a, div[role="button"]');
        for (const el of elements) {
            if (!isVisible(el)) continue;

            const text = (el.textContent || el.innerText).toUpperCase();
            if (text.includes(targetText)) {
                if (targetText === 'OK') {
                    const cleanText = text.replace(/[^A-Z]/g, '');
                    if (cleanText !== 'OK') continue;
                }
                return el;
            }
        }
        return null;
    };

    const clickLowestTimeKey = () => {
        const buttons = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
        const plus12Btns = buttons.filter(btn => (btn.textContent || btn.innerText).toUpperCase().includes('+ 12H') && isVisible(btn));

        if (plus12Btns.length === 0) {
            logToConsole("Không tìm thấy nút '+ 12H' nào trên trang.");
            return false;
        }

        let minTime = Infinity;
        let targetBtn = null;

        plus12Btns.forEach(btn => {
            let current = btn;
            let timeMatch = null;
            
            for(let i = 0; i < 6; i++) {
                if(current.parentElement) {
                    current = current.parentElement;
                    let text = current.innerText || "";
                    let match = text.match(/(\d{2}):(\d{2}):(\d{2})/);
                    if(match) {
                        timeMatch = match;
                        break;
                    }
                }
            }

            if(timeMatch) {
                let h = parseInt(timeMatch[1], 10);
                let m = parseInt(timeMatch[2], 10);
                let s = parseInt(timeMatch[3], 10);
                let totalSeconds = h * 3600 + m * 60 + s;

                if (totalSeconds < minTime) {
                    minTime = totalSeconds;
                    targetBtn = btn;
                }
            }
        });

        if (targetBtn) {
            logToConsole(`Tự động chọn key thấp nhất (${minTime} giây)...`);
            
            // Ghi thời gian chờ vào Local Storage TRƯỚC khi click để đảm bảo không bị mất do reload
            localStorage.setItem(COOLDOWN_KEY, Date.now() + (WAIT_TIME_MINUTES * 60 * 1000)); 
            
            targetBtn.click();
            return true;
        }
        
        return false;
    };

    // Hàm kiểm tra xem có đang trong thời gian chờ (Cooldown) hay không
    const checkAndRunCooldown = () => {
        const cooldownUntil = localStorage.getItem(COOLDOWN_KEY);
        if (cooldownUntil) {
            const now = Date.now();
            const timeTarget = parseInt(cooldownUntil, 10);
            
            if (now < timeTarget) {
                // Đang trong thời gian chờ
                const countEl = document.getElementById('auto-countdown');
                if (countEl) countEl.style.display = 'block';

                const timer = setInterval(() => {
                    const currentTime = Date.now();
                    const remaining = Math.ceil((timeTarget - currentTime) / 1000);
                    
                    if (remaining > 0) {
                        logToConsole(`Đã cộng thời gian! Đang chờ làm mới...`);
                        if (countEl) countEl.innerText = remaining + 's';
                    } else {
                        // Hết thời gian chờ
                        clearInterval(timer);
                        if (countEl) countEl.innerText = '0s';
                        localStorage.removeItem(COOLDOWN_KEY);
                        logToConsole("Đang tải lại trang...");
                        window.location.reload();
                    }
                }, 1000);
                
                return true; // Trả về true báo hiệu đang ở chế độ đếm ngược
            } else {
                // Thời gian chờ đã là quá khứ (lỗi hoặc đã qua), xoá đi
                localStorage.removeItem(COOLDOWN_KEY);
            }
        }
        return false;
    };

    // --- VÒNG LẶP CHÍNH ---
    
    // Nếu đang ở Luarmor, kiểm tra thời gian chờ trước khi chạy bất kỳ logic nào
    if (isLuarmor && checkAndRunCooldown()) {
        return; // Dừng chạy đoạn script phía dưới, chỉ hiển thị UI đếm ngược
    }

    const intervalId = setInterval(() => {
        
        // 1. TRÊN LINKVERTISE
        if (isLinkvertise) {
            let getLinkBtn = findButtonByText('GET LINK') || findButtonByText('GETLINK');
            if (getLinkBtn && !clickedButtons.has('GET LINK')) {
                clickedButtons.add('GET LINK'); 
                
                logToConsole("Phát hiện [GET LINK], chờ 5s để xử lý...");
                setTimeout(() => {
                    logToConsole("Đang xử lý [GET LINK]...");
                    getLinkBtn.click();
                }, 5000); // Trễ 5 giây
                return;
            }

            let openBtn = findButtonByText('OPEN');
            if (openBtn && !clickedButtons.has('OPEN')) {
                clickedButtons.add('OPEN');
                
                logToConsole("Phát hiện [OPEN], chuẩn bị click sau 5s...");
                setTimeout(() => {
                    openBtn.click();
                    logToConsole("Đã mở. Tự động đóng tab Linkvertise sau 1.5s...");
                    setTimeout(() => {
                        window.close(); // Tự động đóng Linkvertise sau khi nhảy
                    }, 1500);
                }, 5000); // Trễ 5 giây
                return;
            }
        }

        // 2. TRÊN LUARMOR
        if (isLuarmor) {
            let okBtn = findButtonByText('OK');
            if (okBtn && !clickedButtons.has('OK')) {
                clickedButtons.add('OK');
                logToConsole("Phát hiện Popup, chờ 5s trước khi click [OK]...");
                setTimeout(() => {
                    logToConsole("Đang xử lý [OK]...");
                    okBtn.click();
                }, 5000); // Trễ 5 giây
                return;
            }

            let startBtn = findButtonByText('START');
            if (startBtn && !clickedButtons.has('START')) {
                clickedButtons.add('START');
                logToConsole("Phát hiện [START], chờ 5s trước khi click...");
                setTimeout(() => {
                    logToConsole("Đang nhấn [START]...");
                    startBtn.click();
                    
                    logToConsole("Đã mở Linkvertise. Đang đóng tab Luarmor cũ...");
                    setTimeout(() => {
                        window.close(); // Tự động đóng Luarmor sau khi nhảy
                    }, 1500);
                }, 5000); // Trễ 5 giây
                return;
            }

            let doneBtn = findButtonByText('DONE');
            if (doneBtn && !clickedButtons.has('DONE_PROCESSED')) {
                logToConsole("Đã xong Checkpoint. Chờ 5s trước khi quét Key...");
                clickedButtons.add('DONE_PROCESSED');
                
                setTimeout(() => {
                    let clickedPlus12 = clickLowestTimeKey();
                    if (clickedPlus12) {
                        clearInterval(intervalId); // Dừng quét tìm nút vì trang sẽ tự reload hoặc đi vào cooldown
                    } else {
                        logToConsole("Lỗi: Không tìm thấy nút +12H.");
                    }
                }, 5000); // Trễ 5 giây
            }
        }

    }, 1000);

})();
