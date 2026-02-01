local function go(url)
    print(string.format("opening: %s", url))
    vim.uv.spawn("www", {
        args = { url },
        detached = true,
    })
end

vim.b.yank = {
    { "url", go },
    "url",
}

vim.wo.cursorline = true
vim.wo.wrap = false
vim.wo.number = false
vim.wo.spell = false
vim.o.laststatus = 0
vim.o.cmdheight = 0

local period = 60*1000
vim.uv.new_timer():start(period, period, function()
    vim.schedule(function()
        vim.api.nvim_command("checktime")
    end)
end)
