#!/usr/bin/env python3
"""Opt-in measurements against explicitly named, already running containers.

Example (coordinate container names/paths before running):
  python3 tests/benchmark.py --docker-name ros2 --container-name ros2-perf

File tests create and remove only their own rosdev-benchmark-* directories in
the selected existing directory. No container is created, stopped or deleted.
Optional --up-command runs exactly the supplied argv; prepare that environment
first so the measurements represent repeated `up`, not initial installation.
"""

import argparse
import json
import shlex
import statistics
import subprocess
import time


GUEST = r'''
import json, os, pathlib, platform, shutil, statistics, subprocess, sys, tempfile, time
parent, count, size, repeats = sys.argv[1:]
parent = pathlib.Path(parent).resolve(strict=True)
count, size, repeats = int(count), int(size), int(repeats)

def summary(samples):
    return {"samples_s": samples, "median_s": statistics.median(samples)}

mount = {"mountpoint": "", "type": "unknown"}
for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines():
    fields, _, filesystem = line.partition(' - ')
    point = fields.split()[4].replace(r'\040', ' ')
    if str(parent) == point or str(parent).startswith(point.rstrip('/') + '/'):
        if len(point) > len(mount['mountpoint']):
            mount = {"mountpoint": point, "type": filesystem.split()[0]}
result = {"path": str(parent), "filesystem": mount, "architecture": platform.machine(),
          "cpus": os.cpu_count(), "files_per_sample": count, "bytes_per_file": size}
samples = {"write": [], "stat": [], "read": []}
cold, warm = [], []
compiler, cache = shutil.which('c++'), shutil.which('ccache')
with tempfile.TemporaryDirectory(prefix='rosdev-benchmark-', dir=parent) as temporary:
    root = pathlib.Path(temporary)
    payload = b'x' * size
    for repeat in range(repeats):
        run = root / str(repeat)
        run.mkdir()
        files = [run / f'{index}.dat' for index in range(count)]
        start = time.perf_counter()
        for path in files:
            path.write_bytes(payload)
        samples['write'].append(time.perf_counter() - start)
        start = time.perf_counter()
        total = sum(path.stat().st_size for path in files)
        samples['stat'].append(time.perf_counter() - start)
        assert total == count * size
        start = time.perf_counter()
        total = sum(len(path.read_bytes()) for path in files)
        samples['read'].append(time.perf_counter() - start)
        assert total == count * size
        if compiler and cache:
            source = run / 'compile.cpp'
            source.write_text('#include <vector>\n#include <numeric>\n#include <string>\n'
                              'int sum() { std::vector<int> v(100, 7); '
                              'return std::accumulate(v.begin(), v.end(), 0); }\n')
            env = {k: v for k, v in os.environ.items() if not k.startswith('CCACHE_')}
            env['CCACHE_DIR'] = str(run / 'ccache')
            command = [cache, compiler, '-std=c++17', '-c', str(source), '-o', str(run / 'compile.o')]
            for measurements in (cold, warm):
                start = time.perf_counter()
                subprocess.run(command, env=env, check=True, capture_output=True)
                measurements.append(time.perf_counter() - start)
            result['ccache_last_sample_stats'] = subprocess.check_output(
                [cache, '--show-stats'], env=env, text=True)
result['small_files'] = {name: summary(values) for name, values in samples.items()}
result['compiler_cache'] = ({'cold': summary(cold), 'warm': summary(warm)} if cold
                            else {'skipped': 'c++ or ccache unavailable'})
print(json.dumps(result))
'''


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def timed(command, repeats):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        subprocess.run(command, check=True, capture_output=True, text=True)
        samples.append(time.perf_counter() - start)
    return {"command": command, "samples_s": samples, "median_s": statistics.median(samples)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--docker-name', help='explicit existing Docker container name')
    parser.add_argument('--container-name', help='explicit existing Apple container name')
    parser.add_argument('--docker-dir', default='/home/ros/ws/build', help='existing directory on the Docker bind mount')
    parser.add_argument('--container-dir', default='/home/ros/ws/build', help='existing directory on the Apple native volume')
    parser.add_argument('--files', type=positive, default=2000)
    parser.add_argument('--bytes', type=positive, default=4096)
    parser.add_argument('--repeats', type=positive, default=3)
    parser.add_argument('--up-command', action='append', default=[],
                        help='opt-in command to time; shell quoting accepted, shell expansion disabled; repeat for comparisons')
    args = parser.parse_args()
    if not (args.docker_name or args.container_name or args.up_command):
        parser.error('provide at least one explicit container name or --up-command')
    result = {'note': 'Buffered I/O, no fsync; stat/read follow writes. Synthetic workload, not ROS/RViz or disk throughput.',
              'runtimes': {}, 'steady_up': []}
    for runtime, name, directory in (('docker', args.docker_name, args.docker_dir),
                                     ('container', args.container_name, args.container_dir)):
        if not name:
            continue
        # Both CLIs accept argv directly; -i forwards only the guest Python script.
        latency = timed([runtime, 'exec', name, 'true'], args.repeats)
        command = [runtime, 'exec', '-i', name, 'python3', '-', directory,
                   str(args.files), str(args.bytes), str(args.repeats)]
        response = subprocess.run(command, input=GUEST, text=True, capture_output=True, check=True)
        result['runtimes'][runtime] = {'name': name, 'exec_latency': latency,
                                        'command': command, 'workload': json.loads(response.stdout)}
    for command in args.up_command:
        argv = shlex.split(command)
        if not argv:
            parser.error('--up-command cannot be empty')
        result['steady_up'].append(timed(argv, args.repeats))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Command failed ({error.returncode}): {shlex.join(error.cmd)}\n{error.stderr or ''}")
