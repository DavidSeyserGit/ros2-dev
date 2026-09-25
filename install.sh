#!/usr/bin/env bash
# One-shot setup of the ROS 2 Jazzy + MoveIt browser-desktop env on a Mac.
#   curl -fsSL https://raw.githubusercontent.com/DavidSeyserGit/ros2-dev/main/install.sh | bash
set -euo pipefail

REPO="${ROS2_DEV_REPO:-https://github.com/DavidSeyserGit/ros2-dev.git}"
DIR="${ROS2_DEV_DIR:-$HOME/ros2}"
CPUS="${COLIMA_CPUS:-6}"; MEM="${COLIMA_MEM:-8}"; DISK="${COLIMA_DISK:-80}"
LOG="${TMPDIR:-/tmp}/ros2-dev-install.log"; : > "$LOG"
TOTAL=7; STEP=0

# ---------- UI ----------
if [ -t 1 ]; then
  B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'; RED=$'\033[31m'; GRN=$'\033[32m'
  YEL=$'\033[33m'; BLU=$'\033[34m'; MAG=$'\033[35m'; CYN=$'\033[36m'
else B= D= R= RED= GRN= YEL= BLU= MAG= CYN=; fi
cols() { tput cols 2>/dev/null || echo 80; }
hide_cursor() { [ -t 1 ] && printf '\033[?25l' || true; }
show_cursor() { [ -t 1 ] && printf '\033[?25h' || true; }
trap show_cursor EXIT

banner() {
  printf '\n%s' "$CYN$B"
  cat <<'ART'
   ____   ___  ____    ____        _
  |  _ \ / _ \/ ___|  |___ \    __| | _____   __
  | |_) | | | \___ \    __) |  / _` |/ _ \ \ / /
  |  _ <| |_| |___) |  / __/  | (_| |  __/\ V /
  |_| \_\\___/|____/  |_____|  \__,_|\___| \_/
ART
  printf '%s' "$R"
  printf '  %sJazzy · MoveIt 2 · OMPL/CHOMP/Pilz/STOMP · browser desktop%s\n' "$D" "$R"
  printf '  %s%s%s\n\n' "$D" "$(printf '─%.0s' $(seq 1 56))" "$R"
}

step() { STEP=$((STEP+1)); }

# run "label" cmd...  -> spinner, ✓/✗, output to log; last log line shown live
run() {
  local label="$1"; shift
  local frames=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏) i=0 start=$SECONDS tail w
  printf '\n==== %s\n' "$label" >> "$LOG"
  "$@" >> "$LOG" 2>&1 &
  local pid=$!
  hide_cursor
  while kill -0 $pid 2>/dev/null; do
    if [ -t 1 ]; then
      w=$(( $(cols) - 60 )); [ $w -lt 10 ] && w=10
      tail=$(tail -n 1 "$LOG" 2>/dev/null | tr -d '\r' | sed 's/\x1b\[[0-9;]*m//g' | cut -c1-$w)
      printf '\r\033[K  %s%s%s %s[%d/%d]%s %-34s %s%3ds  %s%s' \
        "$MAG" "${frames[i]}" "$R" "$D" "$STEP" "$TOTAL" "$R" "$label" "$D" $((SECONDS-start)) "$tail" "$R"
      i=$(( (i+1) % ${#frames[@]} ))
    fi
    sleep 0.1
  done
  show_cursor
  if wait $pid; then
    printf '\r\033[K  %s✓%s %s[%d/%d]%s %-34s %s%ds%s\n' "$GRN" "$R" "$D" "$STEP" "$TOTAL" "$R" "$label" "$D" $((SECONDS-start)) "$R"
  else
    printf '\r\033[K  %s✗%s %s[%d/%d]%s %s\n\n' "$RED" "$R" "$D" "$STEP" "$TOTAL" "$R" "$label"
    printf '  %sLast log lines:%s\n' "$YEL" "$R"; tail -n 15 "$LOG" | sed 's/^/    /'
    printf '\n  Full log: %s\n\n' "$LOG"; exit 1
  fi
}
skip() { printf '  %s•%s %s[%d/%d]%s %-34s %s%s%s\n' "$BLU" "$R" "$D" "$STEP" "$TOTAL" "$R" "$1" "$D" "$2" "$R"; }

# ---------- steps ----------
banner
[ "$(uname -s)" = Darwin ] || { echo "  macOS only. On Linux: install Docker Engine, git clone $REPO, docker compose up -d"; exit 1; }
printf '  %sMac:%s %s (%s) · VM: %s CPU / %s GB RAM / %s GB disk\n  %sLog:%s %s\n\n' \
  "$B" "$R" "$(sw_vers -productVersion)" "$(uname -m)" "$CPUS" "$MEM" "$DISK" "$B" "$R" "$LOG"

step
if command -v brew >/dev/null || [ -x /opt/homebrew/bin/brew ] || [ -x /usr/local/bin/brew ]; then
  skip "Homebrew" "already installed"
else
  printf '  %s→%s [%d/%d] Installing Homebrew %s(may ask for your password)%s\n' "$YEL" "$R" "$STEP" "$TOTAL" "$D" "$R"
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty
fi
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"

step; run "Installing colima + docker CLI" brew install colima docker docker-compose docker-buildx git

configure_docker() {
  mkdir -p ~/.docker; local cfg=~/.docker/config.json
  [ -f "$cfg" ] || echo '{}' > "$cfg"
  /usr/bin/python3 - "$cfg" "$(brew --prefix)/lib/docker/cli-plugins" <<'PY'
import json, sys, shutil
p, d = sys.argv[1], sys.argv[2]
c = json.load(open(p))
dirs = c.setdefault("cliPluginsExtraDirs", [])
if d not in dirs: dirs.append(d)
if c.get("credsStore") == "desktop" and not shutil.which("docker-credential-desktop"):
    c.pop("credsStore")
json.dump(c, open(p, "w"), indent=2)
PY
}
step; run "Configuring docker plugins" configure_docker

start_vm() {
  local flags=(); [ "$(uname -m)" = arm64 ] && flags=(--vm-type vz --vz-rosetta --mount-type virtiofs)
  colima start --cpu "$CPUS" --memory "$MEM" --disk "$DISK" "${flags[@]}"
  docker context use colima
}
step
if colima status >/dev/null 2>&1; then docker context use colima >>"$LOG" 2>&1; skip "Colima VM" "already running"
else run "Starting Colima VM" start_vm; fi

step
if [ -d "$DIR/.git" ]; then run "Updating repo → $DIR" git -C "$DIR" pull --ff-only
else run "Cloning repo → $DIR" git clone "$REPO" "$DIR"; fi

link_cmd() { ln -sf "$DIR/rosdev" "$(brew --prefix)/bin/rosdev"; }
run "Linking global 'rosdev' command" link_cmd

step; run "Building image (first time ~10 min)" docker compose -f "$DIR/compose.yaml" --progress plain build

start_container() {
  docker compose -f "$DIR/compose.yaml" up -d
  for _ in $(seq 1 60); do curl -fs -o /dev/null http://localhost:6080/vnc.html && return 0; sleep 1; done
  return 1
}
step; run "Starting desktop container" start_container

URL="http://localhost:6080/vnc.html?autoconnect=1&resize=scale"
open "$URL" 2>/dev/null || true

printf '\n  %s%s✓ All set!%s\n\n' "$GRN" "$B" "$R"
printf '  %sDesktop%s   %s\n' "$B" "$R" "$URL"
printf '  %sShell%s     rosdev shell   %s(works from any folder)%s\n' "$B" "$R" "$D" "$R"
printf '  %sDemo%s      ros2 launch arm_bringup moveit_demo.launch.py\n' "$B" "$R"
printf '  %sStop%s      rosdev stop-vm\n\n' "$B" "$R"
