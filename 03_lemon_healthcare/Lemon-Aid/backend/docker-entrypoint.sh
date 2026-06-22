#!/bin/sh
set -e

# The HuggingFace and PaddleX model caches are Docker named volumes
# (lemon-aid-hf-cache, lemon-aid-paddle-cache) that mount root-owned, so the
# non-root "lemon" user cannot write downloaded weights — gated DINOv3 hub
# downloads otherwise fail with PermissionError. When started as root, fix the
# ownership of the mounted cache dirs, then drop privileges to lemon for the
# actual process (uvicorn, or the compose-overridden alembic+uvicorn command).
if [ "$(id -u)" = "0" ]; then
    for cache_dir in /home/lemon/.cache /home/lemon/.paddlex /home/lemon/.config; do
        if [ -d "$cache_dir" ]; then
            chown -R lemon:lemon "$cache_dir" || true
        fi
    done
    exec gosu lemon "$@"
fi

exec "$@"
