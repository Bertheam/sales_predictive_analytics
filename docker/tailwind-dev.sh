#!/bin/sh
set -eu

npm ci
npm run assets:build

monitor_output() {
    while true; do
        if [ ! -f backend/static/css/tailwind.css ]; then
            echo "tailwind.css absent, reconstruction..."
            npm run css:build
        fi
        sleep 2
    done
}

monitor_output &
monitor_pid=$!

cleanup() {
    kill "$monitor_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM
npm run css:watch
