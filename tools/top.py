#!/usr/bin/env python3
"""rosdev top: live overview of nodes, topics (message rates) and container CPU / RAM.

Runs inside the container (mounted at /opt/rosdev). Ctrl+C to quit.
"""
import os
import shutil
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.utilities import get_message

INTERVAL = 2.0  # s per refresh


class Top(Node):
    def __init__(self):
        super().__init__('rosdev_top')
        self.counts = {}
        self.types = {}
        self.subs = {}

    def follow_new_topics(self):
        """Count messages on every topic (raw, no deserialization)."""
        for name, types in self.get_topic_names_and_types():
            if name in self.subs:
                continue
            self.types[name] = types[0]
            self.counts[name] = 0
            try:
                msg = get_message(types[0])
            except (AttributeError, ModuleNotFoundError, ValueError):
                continue
            self.subs[name] = self.create_subscription(
                msg, name, lambda _, n=name: self.counts.__setitem__(n, self.counts[n] + 1),
                qos_profile_sensor_data, raw=True)


def cpu_usage_usec():
    try:
        for line in open('/sys/fs/cgroup/cpu.stat'):
            if line.startswith('usage_usec'):
                return int(line.split()[1])
    except OSError:
        pass
    return None


def memory():
    """(used, total) bytes of the container."""
    try:
        used = int(open('/sys/fs/cgroup/memory.current').read())
        limit = open('/sys/fs/cgroup/memory.max').read().strip()
        if limit != 'max':
            return used, int(limit)
    except OSError:
        return None, None
    total = next(int(l.split()[1]) * 1024 for l in open('/proc/meminfo') if l.startswith('MemTotal'))
    return used, total


def main():
    rclpy.init()
    top = Top()
    cpu_before, t_before = cpu_usage_usec(), time.monotonic()
    try:
        while rclpy.ok():
            top.follow_new_topics()
            for name in top.counts:
                top.counts[name] = 0
            end = time.monotonic() + INTERVAL
            while time.monotonic() < end:
                rclpy.spin_once(top, timeout_sec=0.05)
            cpu_now, t_now = cpu_usage_usec(), time.monotonic()
            cpu = (100.0 * (cpu_now - cpu_before) / 1e6 / (t_now - t_before)
                   if cpu_now is not None and cpu_before is not None else float('nan'))
            cpu_before, t_before = cpu_now, t_now
            used, total = memory()

            width, height = shutil.get_terminal_size((100, 30))
            nodes = sorted(f'{ns.rstrip("/")}/{n}' for n, ns in top.get_node_names_and_namespaces()
                           if n != 'rosdev_top')
            lines = [f'rosdev top  —  {time.strftime("%H:%M:%S")}   (Ctrl+C to quit)',
                     f'container: CPU {cpu:5.0f} % of one core ({os.cpu_count()} cores)   RAM '
                     + (f'{used / 2**30:.1f} / {total / 2**30:.1f} GB' if used else '?'),
                     '', f'NODES ({len(nodes)})']
            lines += [f'  {n}' for n in nodes[:max(3, height // 3)]]
            if len(nodes) > height // 3:
                lines.append(f'  … {len(nodes) - height // 3} more')
            rates = sorted(((c / INTERVAL, n) for n, c in top.counts.items()), reverse=True)
            lines += ['', f'TOPICS ({len(rates)})   {"Hz":>8}   type']
            for rate, name in rates[:max(3, height - len(lines) - 2)]:
                lines.append(f'  {name[:width - 50]:<{min(48, width - 30)}} {rate:8.1f}   {top.types[name]}')
            print('\033[2J\033[H' + '\n'.join(l[:width] for l in lines), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        top.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
