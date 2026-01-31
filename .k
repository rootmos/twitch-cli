export TWITCH_CLI_LOG_LEVEL=DEBUG

export XDG_CONFIG_HOME=$K_DIR/xdg/config
export XDG_CACHE_HOME=$K_DIR/xdg/cache
export XDG_STATE_HOME=$K_DIR/xdg/state

in_venv() {
    if python -c 'import sys; sys.exit(1 if sys.prefix == sys.base_prefix else 0)'; then
        "$@"
    else
        poetry run -- "$@"
    fi
}

test() {
    in_venv pytest -vv "$@"
}

run() {
    in_venv twitch "$@"
}

go() {
    #run sandbox
    run videos-file -i foo.twitch
}
