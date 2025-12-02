vim.o.cursorline = true
vim.o.wrap = false
vim.o.number = false
vim.o.spell = false
vim.defer_fn(function()
    vim.o.laststatus = 0
end, 100)

local period = 60*1000
vim.uv.new_timer():start(period, period, function()
    vim.schedule(function()
        vim.api.nvim_command("checktime")
    end)
end)
