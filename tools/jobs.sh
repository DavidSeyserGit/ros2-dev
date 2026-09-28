#!/bin/bash
# Named background processes (launches, nodes, bags) for rosdev start/launch/jobs/logs/stop.
# Run in a shell with ROS already sourced. State lives in the container's /tmp,
# so jobs end with the container.
set -euo pipefail
DIR=/tmp/rosdev-jobs
mkdir -p "$DIR"

fail() { echo "$*" >&2; exit 1; }
valid() { [[ "${1:-}" =~ ^[A-Za-z0-9_.-]+$ ]] || fail "Invalid job name: '${1:-}' (letters, digits, . _ -)"; }
running() { [ -f "$DIR/$1.pid" ] && kill -0 "$(cat "$DIR/$1.pid")" 2>/dev/null; }

case "${1:-}" in
  start)
    name=${2:-}; valid "$name"; shift 2
    [ $# -gt 0 ] || fail 'Usage: rosdev start NAME <command...>'
    ! running "$name" || fail "Job '$name' is already running. Stop it first: rosdev stop $name"
    # One argument is a shell command line; several are an argv, quoted exactly.
    if [ $# -eq 1 ]; then cmd=$1; else cmd=$(printf '%q ' "$@"); fi
    printf '%s\n' "$cmd" > "$DIR/$name.cmd"
    date +%s > "$DIR/$name.started"
    rm -f "$DIR/$name.exit"
    # setsid: the job gets its own process group, so stop reaches every child.
    setsid bash -c "cd ~/ws; $cmd; echo \$? > '$DIR/$name.exit'" > "$DIR/$name.log" 2>&1 < /dev/null &
    echo $! > "$DIR/$name.pid"
    sleep 0.5
    if running "$name"; then
      echo "Started '$name' (pid $(cat "$DIR/$name.pid")). Output: rosdev logs $name"
    else
      echo "Job '$name' exited immediately (code $(cat "$DIR/$name.exit" 2>/dev/null || echo '?')):" >&2
      tail -20 "$DIR/$name.log" >&2
      exit 1
    fi ;;
  list)
    json=false; [ "${2:-}" = --json ] && json=true
    python3 - "$DIR" "$json" <<'PY'
import json, os, pathlib, sys, time
d, as_json = pathlib.Path(sys.argv[1]), sys.argv[2] == "true"
jobs = []
for cmd in sorted(d.glob("*.cmd")):
    name = cmd.stem
    read = lambda ext: (d / f"{name}.{ext}").read_text().strip() if (d / f"{name}.{ext}").exists() else None
    pid = int(read("pid") or 0)
    try:
        os.kill(pid, 0); alive = pid > 0
    except OSError:
        alive = False
    code = read("exit")
    jobs.append({"name": name, "pid": pid, "running": alive,
                 "exit_code": None if alive or code is None else int(code),
                 "seconds": int(time.time()) - int(read("started") or time.time()),
                 "command": read("cmd"), "log": str(d / f"{name}.log")})
if as_json:
    print(json.dumps(jobs, indent=2))
elif not jobs:
    print("No jobs. Start one with: rosdev launch NAME PKG FILE")
else:
    print(f"{'NAME':<16} {'STATE':<10} {'PID':>7} {'AGE':>8}  COMMAND")
    for j in jobs:
        state = "running" if j["running"] else f"exit {j['exit_code']}" if j["exit_code"] is not None else "killed"
        print(f"{j['name']:<16} {state:<10} {j['pid']:>7} {j['seconds']:>7}s  {j['command']}")
PY
    ;;
  log)
    name=${2:-}; valid "$name"; shift 2
    [ -f "$DIR/$name.log" ] || fail "No job named '$name'. See: rosdev jobs"
    follow=false; lines=50
    while [ $# -gt 0 ]; do
      case "$1" in
        -f|--follow) follow=true ;;
        -n) lines=${2:?-n needs a number}; shift ;;
        *) fail "Unknown option: $1" ;;
      esac
      shift
    done
    [[ "$lines" =~ ^[0-9]+$ ]] || fail "-n needs a number"
    if "$follow"; then tail -n "$lines" -f "$DIR/$name.log"; else tail -n "$lines" "$DIR/$name.log"; fi ;;
  stop)
    name=${2:-}
    if [ "$name" = --all ]; then
      for f in "$DIR"/*.pid; do [ -e "$f" ] || continue; bash "$0" stop "$(basename "$f" .pid)"; done
      exit 0
    fi
    valid "$name"
    [ -f "$DIR/$name.pid" ] || fail "No job named '$name'. See: rosdev jobs"
    pid=$(cat "$DIR/$name.pid")
    if ! running "$name"; then
      rm -f "$DIR/$name".{pid,cmd,started,exit}
      echo "Job '$name' had already exited; removed it (log kept at $DIR/$name.log)."
      exit 0
    fi
    # SIGINT first, like Ctrl-C: ros2 launch shuts its nodes down cleanly.
    for sig in INT TERM KILL; do
      kill -"$sig" -- "-$pid" 2>/dev/null || true
      for _ in $(seq 50); do kill -0 "$pid" 2>/dev/null || break 2; sleep 0.2; done
    done
    rm -f "$DIR/$name".{pid,cmd,started,exit}
    echo "Stopped '$name' (log kept at $DIR/$name.log)." ;;
  *) fail 'Usage: jobs.sh start|list|log|stop ...' ;;
esac
