#!/bin/bash
# Phase 1 本地运行脚本（脱离 Docker）
# 用法: bash run_phase1.sh

set -e

PID_DIR="/tmp/dt-phase1-pids"
mkdir -p "$PID_DIR"

cleanup() {
    echo ""
    echo "=== Stopping all Phase 1 processes ==="
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] && kill "$(cat "$pidfile")" 2>/dev/null && rm "$pidfile"
    done
    echo "Done"
}
trap cleanup EXIT INT TERM

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ==============================
# 1. Modbus Simulator
# ==============================
echo "[1/3] Starting Modbus Simulator (port 5020)..."
cd "$PROJECT_DIR/simulation/modbus"
pip install -q pymodbus 2>/dev/null
python3 simulator.py &
echo $! > "$PID_DIR/simulator.pid"
sleep 2
echo "  Simulator PID: $(cat "$PID_DIR/simulator.pid")"

# ==============================
# 2. Edge Collector
# ==============================
echo "[2/3] Starting Edge Collector (Modbus → MQTT)..."
cd "$PROJECT_DIR/edge/python-collector"
pip install -q -r requirements.txt 2>/dev/null
MQTT_HOST=localhost MQTT_PORT=1883 MODBUS_HOST=localhost MODBUS_PORT=5020 CACHE_DB_PATH=/tmp/edge_cache.db \
  python3 edge_collector.py &
echo $! > "$PID_DIR/edge-collector.pid"
echo "  Collector PID: $(cat "$PID_DIR/edge-collector.pid")"

# ==============================
# 3. Start MQTT subscription monitor
# ==============================
echo "[3/3] Starting MQTT monitor (subscribe to telemetry topic in 3s)..."
sleep 3
echo ""
echo "=== Phase 1 Running ==="
echo "EMQX Dashboard: http://localhost:18083"
echo "Modbus Simulator: localhost:5020"
echo "Edge Collector → EMQX: industrial_twin/edge_node_01/telemetry/data"
echo ""
echo "Starting MQTT subscriber (ctrl+c to stop all)..."
pip install -q paho-mqtt 2>/dev/null
python3 -c "
import paho.mqtt.client as mqtt, json, os

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        timestamp = payload.get('timestamp', '')
        metrics = payload.get('metrics', {})
        status = payload.get('status', {})
        alarms = [k for k,v in status.items() if v == 'Alarm']
        print(f'[{timestamp}] Metrics: ' + json.dumps(metrics) + ('  ⚠ ALARMS: ' + json.dumps(alarms) if alarms else ''))

def on_connect(client, userdata, flags, rc):
    print(f'Subscribed (rc={rc}) — listening on industrial_twin/#')
    client.subscribe('industrial_twin/#', qos=2)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect('localhost', 1883, 60)
client.loop_forever()
"
