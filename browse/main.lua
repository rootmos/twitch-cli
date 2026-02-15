local live = vim.fn.expand("$STATE_DIR/live.twitch")
local videos = vim.fn.expand("$STATE_DIR/videos.twitch")
local watch_later = vim.fn.expand("$HOME/lists/twitch/watch-later.twitch")
vim.cmd { cmd = "edit", args = { watch_later } }
vim.cmd { cmd = "split", args = { videos } }
vim.cmd { cmd = "split", args = { live } }
