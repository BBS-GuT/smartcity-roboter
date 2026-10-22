# Laedt eine gespeicherte Karte (map_server) und zeigt sie in RViz.
# Start ueber scripts/karte_laden.sh NAME
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    karte = LaunchConfiguration('map')
    return LaunchDescription([
        DeclareLaunchArgument('map', description='Pfad zur Karte (.yaml)'),
        DeclareLaunchArgument('rviz_config', default_value=''),
        DeclareLaunchArgument('rviz', default_value='true'),
        # map_server liest die Karte und stellt sie auf dem Topic /map bereit
        Node(package='nav2_map_server', executable='map_server', name='map_server', output='screen',
             parameters=[{'yaml_filename': karte, 'frame_id': 'map'}]),
        # lifecycle_manager schaltet den map_server ein (nav2-Knoten starten "ausgeschaltet")
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager_karte',
             output='screen', parameters=[{'node_names': ['map_server'], 'autostart': True}]),
        Node(package='rviz2', executable='rviz2', name='rviz2', arguments=['-d', LaunchConfiguration('rviz_config')],
             condition=IfCondition(LaunchConfiguration('rviz'))),
    ])
