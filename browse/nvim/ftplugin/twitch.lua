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

if vim.bo.readonly then
    local period = 60*1000
    vim.uv.new_timer():start(period, period, function()
        vim.schedule(function()
            vim.api.nvim_command("checktime")
        end)
    end)
else
    vim.api.nvim_create_autocmd({ "BufWritePost", "FileWritePost" }, {
        buffer = 0,
        callback = function()
            local path = vim.api.nvim_buf_get_name(0)
            vim.uv.spawn("/home/gustav/.local/bin/twitch", {
                args = { "videos-file", "--in-place", path },
                stdio = { nil, nil, 2 },
                detached = true,
            }, function(code, signal)
                if code == 0 then
                    vim.schedule(function()
                        vim.api.nvim_command("checktime")
                    end)
                end
            end)
        end,
    })
end
