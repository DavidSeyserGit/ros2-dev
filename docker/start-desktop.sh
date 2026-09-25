#!/bin/bash
# Start XFCE on :1 with its own D-Bus session, once the X server is ready.
export XDG_RUNTIME_DIR=/tmp/runtime-$USER
mkdir -p -m 700 "$XDG_RUNTIME_DIR"
unset DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER
for _ in $(seq 1 100); do
  [ -S /tmp/.X11-unix/X1 ] && xset -display :1 q >/dev/null 2>&1 && break
  sleep 0.2
done
exec dbus-run-session -- startxfce4
