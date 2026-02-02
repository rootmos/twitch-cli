local function go(url)
    print(string.format("opening: %s", url))
    vim.system({ "www", url }, { detached = true })
end

vim.b.yank = {
    { "url", go },
    "url",
}

-- TODO make sure these are actually local
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
            vim.system({"twitch", "videos-file", "--in-place", path }, {
                stdio = { nil, nil, 2 },
                detached = true,
            }, function()
                vim.schedule(function()
                    vim.api.nvim_command("checktime")
                end)
            end)
        end,
    })
end
