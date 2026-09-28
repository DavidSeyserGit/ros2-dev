#!/bin/bash
# rosdev test: colcon test with an isolated ROS domain, a time limit and an
# optional memory cap, followed by a short summary of this run's results only.
# Run in a shell with ROS already sourced.
set -euo pipefail
cd ~/ws

usage() {
  cat >&2 <<'USAGE'
Usage: rosdev test [PKG...] [options] [-- colcon test args]
  --filter PATTERN   GoogleTest filter (GTEST_FILTER), e.g. 'Suite.*:-Suite.Slow'
  --timeout SECONDS  stop the whole run after this long (default 900)
  --mem SIZE         virtual-memory cap per test process, e.g. 4G (default: none)
  --no-build         skip building the selected packages first
  --json             print the summary as JSON
USAGE
  exit 2
}

packages=(); extra=(); timeout=900; mem=''; build=true; json=false
while [ $# -gt 0 ]; do
  case "$1" in
    --filter) export GTEST_FILTER=${2:?--filter needs a pattern}; shift ;;
    --timeout) timeout=${2:?--timeout needs seconds}; shift ;;
    --mem) mem=${2:?--mem needs a size}; shift ;;
    --no-build) build=false ;;
    --json) json=true ;;
    -h|--help) usage ;;
    --) shift; extra=("$@"); break ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *) packages+=("$1") ;;
  esac
  shift
done
[[ "$timeout" =~ ^[1-9][0-9]*$ ]] || { echo "--timeout must be a positive number of seconds" >&2; exit 2; }

select=()
[ "${#packages[@]}" -eq 0 ] || select=(--packages-select "${packages[@]}")

# Keep build output off stdout in --json mode, so the summary stays parseable.
if "$build"; then
  if "$json"; then bash /opt/rosdev/build.sh "${select[@]}" >&2; else bash /opt/rosdev/build.sh "${select[@]}"; fi
fi

# A private DDS domain keeps tests from talking to a running move_group or demo.
export ROS_DOMAIN_ID=${ROSDEV_TEST_DOMAIN_ID:-$((100 + RANDOM % 100))}
if [ -n "$mem" ]; then
  kb=$(numfmt --from=iec "${mem^^}" 2>/dev/null) || { echo "--mem: invalid size '$mem'" >&2; exit 2; }
  ulimit -v $((kb / 1024))
fi

marker=$(mktemp)
log=$(mktemp /tmp/rosdev-test-XXXXXX.log)
status=0
timeout --kill-after=15 "$timeout" colcon test "${select[@]}" --event-handlers console_direct- \
  "${extra[@]}" > "$log" 2>&1 || status=$?

python3 /opt/rosdev/test_summary.py --since "$marker" --log "$log" --status "$status" \
  --timeout "$timeout" --domain "$ROS_DOMAIN_ID" $("$json" && echo --json) "${packages[@]}"
