from setuptools import setup

package_name = 'gripper_trail'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='David Seyser',
    maintainer_email='david.t.seyser@gmail.com',
    description='Draws the gripper path as a fading line in RViz.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'trail_node = gripper_trail.trail_node:main',
        ],
    },
)
