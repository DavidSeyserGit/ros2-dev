#!/bin/bash
# rosdev new <name> [python|cpp]: a package in ~/ws/src with a small publisher node and a
# launch file, built right away.  Runs inside the container (mounted at /opt/rosdev).
set -euo pipefail
name=${1:?usage: rosdev new <name> [python|cpp]}
kind=${2:-python}
[[ "$name" =~ ^[a-z][a-z0-9_]*$ ]] || { echo "package names: lower case letters, digits, _"; exit 1; }
cd ~/ws/src
[ -e "$name" ] && { echo "~/ws/src/$name exists already"; exit 1; }

launch() {  # launch/<name>.launch.py
  mkdir -p "$name/launch"
  cat > "$name/launch/$name.launch.py" <<PY
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='$name', executable='${name}_node', output='screen'),
    ])
PY
}

case "$kind" in
  python)
    ros2 pkg create "$name" --build-type ament_python --license MIT --node-name "${name}_node" \
      --dependencies rclpy std_msgs >/dev/null
    cat > "$name/$name/${name}_node.py" <<PY
"""Publishes a counter on /$name/hello once per second."""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ${name^}Node(Node):
    def __init__(self):
        super().__init__('${name}_node')
        self.pub = self.create_publisher(String, '$name/hello', 10)
        self.count = 0
        self.create_timer(1.0, self.tick)

    def tick(self):
        self.count += 1
        self.pub.publish(String(data=f'hello {self.count}'))
        self.get_logger().info(f'hello {self.count}')


def main():
    rclpy.init()
    node = ${name^}Node()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
PY
    launch
    python3 - "$name" <<'PY'
import sys
name = sys.argv[1]
path = f'{name}/setup.py'
s = open(path).read()
s = s.replace("        ('share/' + package_name, ['package.xml']),",
              "        ('share/' + package_name, ['package.xml']),\n"
              "        ('share/' + package_name + '/launch', ['launch/' + package_name + '.launch.py']),")
open(path, 'w').write(s)
PY
    ;;
  cpp)
    ros2 pkg create "$name" --build-type ament_cmake --license MIT --node-name "${name}_node" \
      --dependencies rclcpp std_msgs >/dev/null
    cat > "$name/src/${name}_node.cpp" <<CPP
// Publishes a counter on /$name/hello once per second.
#include <chrono>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

using namespace std::chrono_literals;

int main(int argc, char** argv)
{
  rclcpp::init(argc, argv);
  auto node = rclcpp::Node::make_shared("${name}_node");
  auto pub = node->create_publisher<std_msgs::msg::String>("$name/hello", 10);
  int count = 0;
  auto timer = node->create_wall_timer(1s, [&] {
    std_msgs::msg::String msg;
    msg.data = "hello " + std::to_string(++count);
    pub->publish(msg);
    RCLCPP_INFO(node->get_logger(), "%s", msg.data.c_str());
  });
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
CPP
    launch
    sed -i 's|^ament_package()|install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})\n\nament_package()|' "$name/CMakeLists.txt"
    ;;
  *) echo "kind must be python or cpp"; exit 1 ;;
esac

cd ~/ws
bash /opt/rosdev/build.sh --packages-select "$name" 2>&1 | tail -2
echo
echo "Created ~/ws/src/$name ($kind). Try it (in a new terminal, or after 'source ~/ws/install/setup.bash'):"
echo "  ros2 launch $name $name.launch.py"
