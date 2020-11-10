export PREFIX ?= $(HOME)/.local

install:
	install -D -t $(PREFIX)/bin twitch-cli

install-service:
	envsubst < twitch.service \
		| install -D /dev/stdin $(HOME)/.config/systemd/user/twitch.service
	systemctl --user enable twitch.service
	systemctl --user restart twitch.service
