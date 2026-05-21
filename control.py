"""
Digital Twin - Command sender

Send a command to the real device through the twin:
  python control.py fan on
  python control.py fan off
"""

import sys
import paho.mqtt.publish as publish

MQTT_HOST = "localhost"
MQTT_PORT = 1883


def send_fan_command(state: str):
    state = state.upper()
    if state not in ("ON", "OFF"):
        print("Usage: python control.py fan on|off")
        sys.exit(1)
    publish.single(
        topic="room/fan/control",
        payload=state,
        hostname=MQTT_HOST,
        port=MQTT_PORT,
        qos=1,
    )
    print(f"Command sent: fan {state}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1].lower() != "fan":
        print("Usage: python control.py fan on|off")
        sys.exit(1)
    send_fan_command(sys.argv[2])
