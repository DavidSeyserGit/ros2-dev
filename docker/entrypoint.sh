#!/bin/bash
set -e
export HOME=/home/ros USER=ros
# Clean stale X locks from a previous run of this container
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
if [ $# -gt 0 ]; then
  exec "$@"
fi
exec /usr/bin/supervisord -c /etc/supervisor/desktop.conf
