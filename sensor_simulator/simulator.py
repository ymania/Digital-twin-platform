"""
Digital Twin - Room Sensor Simulator

Mimics a real IoT device publishing sensor readings over MQTT.
Topics published:
  room/temperature   - degrees Celsius
  room/humidity      - percent
  room/fan_speed     - RPM (0 = off)
  room/fan_state     - "ON" / "OFF"
  room/light         - lux
  room/power         - watts consumed

Topic subscribed:
  room/fan/control   - accepts "ON" / "OFF" commands from the twin
"""

import json
import math
import os
import random
import time

import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

# --- Physical model state ---
state = {
    "temperature": 22.0,
    "humidity": 55.0,
    "fan_state": "OFF",
    "fan_speed": 0,
    "light": 300.0,
    "power": 5.0,
}

# Ticks remaining where manual override suppresses auto-control (12 ticks = 60 s)
manual_override_ticks = 0


def on_connect(client, userdata, flags, rc):
    print(f"[simulator] Connected to MQTT broker (rc={rc})")
    client.subscribe("room/fan/control")


def on_message(client, userdata, msg):
    global manual_override_ticks
    command = msg.payload.decode().strip().upper()
    if command in ("ON", "OFF"):
        state["fan_state"] = command
        manual_override_ticks = 12  # suppress auto-control for 60 s
        print(f"[simulator] Fan command received: {command} (manual override active for 60 s)")


def physics_step(tick: int):
    """Advance the physical model by one time step."""
    global manual_override_ticks
    hour = (tick // 12) % 24  # each tick = 5 s → ~12 ticks/min

    # Ambient temperature follows a daily sine wave: 19°C at 5am, 28°C at 2pm
    ambient = 23.5 + 4.5 * math.sin(math.pi * (hour - 5) / 9)
    noise = random.gauss(0, 0.15)

    # Fan cools the room; no fan lets it drift toward ambient
    if state["fan_state"] == "ON":
        state["temperature"] += 0.3 * (ambient - state["temperature"] - 3) + noise
        state["fan_speed"] = int(random.gauss(1200, 30))
        state["power"] = round(random.gauss(85, 3), 1)
    else:
        state["temperature"] += 0.3 * (ambient - state["temperature"]) + noise
        state["fan_speed"] = 0
        state["power"] = round(random.gauss(5, 0.5), 1)

    # Auto-control: skipped while a manual override is active
    if manual_override_ticks > 0:
        manual_override_ticks -= 1
    else:
        if state["temperature"] > 25.0 and state["fan_state"] == "OFF":
            state["fan_state"] = "ON"
            print("[simulator] Auto: fan ON (temp > 25°C)")
        elif state["temperature"] < 22.0 and state["fan_state"] == "ON":
            state["fan_state"] = "OFF"
            print("[simulator] Auto: fan OFF (temp < 22°C)")

    # Humidity rises slightly when fan is off
    humidity_target = 60.0 if state["fan_state"] == "OFF" else 50.0
    state["humidity"] += 0.1 * (humidity_target - state["humidity"]) + random.gauss(0, 0.2)
    state["humidity"] = round(max(30, min(90, state["humidity"])), 1)

    # Light roughly follows daylight
    state["light"] = round(max(10, 500 * math.sin(math.pi * hour / 14) + random.gauss(0, 20)), 1)
    state["temperature"] = round(state["temperature"], 2)


def publish_all(client: mqtt.Client, tick: int):
    physics_step(tick)
    readings = {
        "room/temperature": state["temperature"],
        "room/humidity":    state["humidity"],
        "room/fan_speed":   state["fan_speed"],
        "room/fan_state":   state["fan_state"],
        "room/light":       state["light"],
        "room/power":       state["power"],
    }
    for topic, value in readings.items():
        client.publish(topic, json.dumps({"value": value}), qos=1)

    print(
        f"[simulator] tick={tick:4d} | "
        f"temp={state['temperature']:5.2f}°C | "
        f"hum={state['humidity']:4.1f}% | "
        f"fan={state['fan_state']:3s} @{state['fan_speed']:4d}rpm | "
        f"light={state['light']:5.1f}lux | "
        f"power={state['power']:5.1f}W"
    )


def main():
    client = mqtt.Client(client_id="room-simulator")
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[simulator] Connecting to {MQTT_HOST}:{MQTT_PORT} ...")
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except Exception as e:
            print(f"[simulator] Waiting for broker... ({e})")
            time.sleep(3)

    client.loop_start()

    tick = 0
    while True:
        publish_all(client, tick)
        tick += 1
        time.sleep(5)


if __name__ == "__main__":
    main()
