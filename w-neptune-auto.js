task.spawn(function()
    if not game:IsLoaded() then game.Loaded:Wait() end
    
    -- Lấy URL từ GitHub và xóa khoảng trắng/xuống dòng thừa
    local success, url = pcall(function() 
        return game:HttpGet("https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/webhook"):gsub("%s+", "") 
    end)
    
    local req = (syn and syn.request) or (http and http.request) or (fluxus and fluxus.request) or request
    if success and req and url:find("http") then
        pcall(req, {
            Url = url,
            Method = "POST",
            Headers = {["Content-Type"] = "application/json"},
            Body = game:GetService("HttpService"):JSONEncode({
                content = game:GetService("Players").LocalPlayer.Name .. " | RAM: " .. math.floor(game:GetService("Stats"):GetTotalMemoryUsageMb()) .. "MB"
            })
        })
    end
end)
