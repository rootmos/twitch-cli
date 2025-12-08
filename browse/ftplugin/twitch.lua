local function go(url)
    print(string.format("opening: %s", url))
    vim.uv.spawn(vim.fn.expand("$HOME/bin/twitch.sh"), {
        args = { url },
        detached = true,
    })
end

vim.b.yank = {
    { "word", go },
    "word",
}

vim.wo.cursorline = true
vim.wo.wrap = false
vim.wo.number = false
vim.wo.spell = false
vim.bo.readonly = true
vim.o.laststatus = 0
vim.o.cmdheight = 0

local period = 60*1000
vim.uv.new_timer():start(period, period, function()
    vim.schedule(function()
        vim.api.nvim_command("checktime")
    end)
end)
