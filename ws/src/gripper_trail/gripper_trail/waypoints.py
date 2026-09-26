"""Drive the Panda gripper through a list of waypoints using MoveIt's /move_action."""
import rclpy
from rclpy.action import ActionClient
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, PositionConstraint, OrientationConstraint
from shape_msgs.msg import SolidPrimitive
from geometry_msgs.msg import Pose

# ---- Edit these ------------------------------------------------------------
# (x, y, z) in metres, relative to the robot base (panda_link0).
# The gripper always points straight down.
WAYPOINTS = [
    (0.4, 0.2, 0.5),
    (0.4, -0.2, 0.5),
    (0.5, -0.2, 0.3),
    (0.5, 0.2, 0.3),
    (0.3, 0.0, 0.6),
]
SPEED = 0.5            # 0..1, fraction of max velocity/acceleration
PLANNER = 'ompl'       # 'ompl', 'pilz_industrial_motion_planner', 'chomp', 'stomp'
# ----------------------------------------------------------------------------

GROUP, LINK, FRAME = 'panda_arm', 'panda_hand', 'panda_link0'


def make_goal(x, y, z):
    pos = PositionConstraint(header=_hdr(), link_name=LINK, weight=1.0)
    pos.constraint_region.primitives.append(SolidPrimitive(type=SolidPrimitive.SPHERE, dimensions=[0.001]))
    pose = Pose()
    pose.position.x, pose.position.y, pose.position.z = x, y, z
    pos.constraint_region.primitive_poses.append(pose)

    ori = OrientationConstraint(header=_hdr(), link_name=LINK, weight=1.0)
    ori.orientation.x, ori.orientation.w = 1.0, 0.0  # pointing down
    ori.absolute_x_axis_tolerance = ori.absolute_y_axis_tolerance = ori.absolute_z_axis_tolerance = 0.01

    goal = MoveGroup.Goal()
    r = goal.request
    r.group_name = GROUP
    r.pipeline_id = PLANNER
    if PLANNER == 'pilz_industrial_motion_planner':
        r.planner_id = 'PTP'
    r.num_planning_attempts = 5
    r.allowed_planning_time = 5.0
    r.max_velocity_scaling_factor = r.max_acceleration_scaling_factor = SPEED
    r.goal_constraints.append(Constraints(position_constraints=[pos], orientation_constraints=[ori]))
    goal.planning_options.plan_only = False  # plan AND execute
    return goal


def _hdr():
    from std_msgs.msg import Header
    return Header(frame_id=FRAME)


def main():
    rclpy.init()
    node = rclpy.create_node('waypoints')
    client = ActionClient(node, MoveGroup, 'move_action')
    node.get_logger().info('Waiting for move_group...')
    client.wait_for_server()

    for i, wp in enumerate(WAYPOINTS, 1):
        node.get_logger().info(f'[{i}/{len(WAYPOINTS)}] going to {wp}')
        send = client.send_goal_async(make_goal(*wp))
        rclpy.spin_until_future_complete(node, send)
        handle = send.result()
        if not handle.accepted:
            node.get_logger().error('Goal rejected'); break
        res = handle.get_result_async()
        rclpy.spin_until_future_complete(node, res)
        code = res.result().result.error_code.val
        if code != 1:  # 1 = SUCCESS
            node.get_logger().error(f'Failed with MoveIt error code {code}'); break

    node.get_logger().info('Done.')
    rclpy.shutdown()


if __name__ == '__main__':
    main()
