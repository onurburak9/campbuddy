#!/bin/sh
# Recreation.gov silently rejects logins from headless Chromium, so the browser
# runs headed against a virtual display. Starting Xvfb once here (rather than
# wrapping the server in `xvfb-run`) means `docker compose exec` shares the same
# display — otherwise ad-hoc commands like selector_check fail with
# "Missing X server or $DISPLAY".
set -e

: "${DISPLAY:=:99}"
export DISPLAY

if ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
    Xvfb "$DISPLAY" -screen 0 1440x900x24 -nolisten tcp &
    # Poll for readiness rather than sleeping a guessed interval.
    i=0
    while [ "$i" -lt 100 ]; do
        if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
            break
        fi
        i=$((i + 1))
        sleep 0.1
    done
    if ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        echo "entrypoint: Xvfb failed to start on $DISPLAY" >&2
        exit 1
    fi
fi

exec "$@"
