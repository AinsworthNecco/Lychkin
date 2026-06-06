// ==UserScript==
// @name         Bloxflip Auto Crash Pro (DYNAMIC LOADER)
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Trình khởi chạy tải code trực tiếp từ GitHub MỖI LẦN VÀO WEB (100% Không Cache)
// @match        https://bloxflip.com/*
// @grant        GM_xmlhttpRequest
// @connect      raw.githubusercontent.com
// ==/UserScript==

(function () {
    'use strict';

    // ⚠️ LINK RAW GITHUB CHỨA SCRIPT CHÍNH CỦA BẠN:
    const SCRIPT_URL = 'https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/Bloxflip';

    GM_xmlhttpRequest({
        method: 'GET',
        url: SCRIPT_URL + '?_=' + Date.now(), // Thêm thời gian thực để tránh cache hoàn toàn
        onload: function (res) {
            if (res.status !== 200) {
                console.error('❌ [Loader] Không tải được script. Mã lỗi:', res.status);
                return;
            }

            try {
                // Thực thi code vừa kéo về từ GitHub
                console.log('✅ [Loader] Đã tải và chạy thành công code mới nhất từ GitHub!');
                new Function(res.responseText)();
            } catch (err) {
                console.error('❌ [Loader] Lỗi khi thực thi script:', err);
            }
        },
        onerror: function (err) {
            console.error('❌ [Loader] Lỗi kết nối mạng khi tải script từ GitHub:', err);
        }
    });
})();
