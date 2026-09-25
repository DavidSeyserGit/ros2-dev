"""Follow the gripper with TF and publish its path as a fading LINE_STRIP marker."""
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.duration import Duration
from tf2_ros import Buffer, TransformListener, TransformException
from visualization_msgs.msg import Marker
from geometry_msgs.msg import Point
from std_msgs.msg import ColorRGBA


class TrailNode(Node):
    def __init__(self):
        super().__init__('gripper_trail')
        # Parameters: which frames to track, how long the trail lives, etc.
        self.fixed_frame = self.declare_parameter('fixed_frame', 'panda_link0').value
        self.tip_frame = self.declare_parameter('tip_frame', 'panda_hand_tcp').value
        self.lifetime = self.declare_parameter('trail_lifetime', 10.0).value  # seconds until a point fully fades
        self.min_step = self.declare_parameter('min_step', 0.002).value       # metres; skip points closer than this
        self.width = self.declare_parameter('line_width', 0.005).value
        rate = self.declare_parameter('rate', 30.0).value

        # TF: the buffer stores recent transforms, the listener fills it from /tf and /tf_static.
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.pub = self.create_publisher(Marker, 'gripper_trail', 10)
        self.points = []  # list of (Point, stamp_seconds)
        self.create_timer(1.0 / rate, self.tick)
        self.get_logger().info(f'Tracking {self.tip_frame} in {self.fixed_frame}, publishing on /gripper_trail')

    def tick(self):
        now = self.get_clock().now()
        now_s = now.nanoseconds * 1e-9

        # Ask TF where the gripper is right now (Time() = latest available).
        try:
            t = self.tf_buffer.lookup_transform(self.fixed_frame, self.tip_frame, Time())
        except TransformException as e:
            self.get_logger().warn(f'TF not available yet: {e}', throttle_duration_sec=5.0)
            return

        p = Point(x=t.transform.translation.x, y=t.transform.translation.y, z=t.transform.translation.z)
        if not self.points or self._dist(p, self.points[-1][0]) > self.min_step:
            self.points.append((p, now_s))

        # Drop points that have fully faded out.
        self.points = [(pt, s) for pt, s in self.points if now_s - s < self.lifetime]

        m = Marker()
        m.header.frame_id = self.fixed_frame
        m.header.stamp = now.to_msg()
        m.ns = 'gripper_trail'
        m.id = 0
        m.type = Marker.LINE_STRIP
        m.action = Marker.ADD
        m.pose.orientation.w = 1.0
        m.scale.x = self.width  # line width; only scale.x is used for LINE_STRIP
        m.lifetime = Duration(seconds=1.0).to_msg()
        # Per-vertex colors: new points are bright/opaque, old points fade to transparent.
        for pt, s in self.points:
            age = (now_s - s) / self.lifetime  # 0 = new, 1 = gone
            m.points.append(pt)
            m.colors.append(ColorRGBA(r=1.0, g=0.3 + 0.5 * age, b=0.0, a=max(0.0, 1.0 - age)))

        if len(m.points) >= 2:  # a LINE_STRIP needs at least two points
            self.pub.publish(m)
        else:
            m.action = Marker.DELETE
            self.pub.publish(m)

    @staticmethod
    def _dist(a, b):
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def main():
    rclpy.init()
    node = TrailNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
