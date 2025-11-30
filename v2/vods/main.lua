vim.o.cursorline = true
vim.o.wrap = false
vim.o.number = false
vim.o.spell = false
vim.schedule(function()
    vim.o.laststatus = 0
end)

local period = %INTERVAL%*100 -- ms/10
vim.uv.new_timer():start(period, period, function()
    vim.schedule(function()
        vim.api.nvim_command("checktime")
    end)
end)
