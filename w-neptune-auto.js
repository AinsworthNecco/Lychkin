local url = "https://raw.githubusercontent.com/AinsworthNecco/Lychkin/refs/heads/main/Main"
local q = syn and syn.queue_on_teleport or queue_on_teleport
if q then
    q(("loadstring(game:HttpGet('%s'))()"):format(url))
end
if getgenv().plsdonate_ran then return end
getgenv().plsdonate_ran = true
