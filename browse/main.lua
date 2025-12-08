local live = vim.fn.expand("$STATE_DIR/live.twitch")
local videos = vim.fn.expand("$STATE_DIR/videos.twitch")
vim.cmd { cmd = "edit", args = { videos } }
vim.cmd { cmd = "split", args = { live } }
