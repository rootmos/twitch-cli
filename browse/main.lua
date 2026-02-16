local files = {
    "$STATE_DIR/live.twitch",
    "$STATE_DIR/videos.twitch",
    "$LISTS_DIR/watch-later.twitch",
}

local paths = {}
for _, f in ipairs(files) do
    local p = vim.fn.expand(f)
    if vim.uv.fs_stat(p) then
        table.insert(paths, 1, p)
    end
end

for i, p in ipairs(paths) do
    vim.cmd {
        cmd = i == 1 and "edit" or "split",
        args = { p },
    }
end
