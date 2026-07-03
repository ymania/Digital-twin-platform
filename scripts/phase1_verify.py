"""
Phase 1 验证脚本 — 验证 Modbus 模拟器数据通路

用法:
  python3 phase1_verify.py

前提:
  1. Modbus 模拟器在 localhost:5020 运行
  2. mosquitto 在 localhost:1883 运行
"""
import sys
import json
import time
import struct

def test_modbus():
    """验证 Modbus 模拟器能正常读取寄存器"""
    from pymodbus.client import ModbusTcpClient

    client = ModbusTcpClient("localhost", port=5020, timeout=5)
    if not client.connect():
        print("[FAIL] Modbus 模拟器无法连接 localhost:5020")
        return False

    # 读取 40001~40010 (Modbus 地址 0~9)
    result = client.read_holding_registers(0, 10, slave=1)
    if result.isError():
        print(f"[FAIL] 读寄存器失败: {result}")
        client.close()
        return False

    regs = result.registers
    print(f"[PASS] Modbus 寄存器 (40001~40010):")
    names = ["RACK-001 temp", "RACK-001 hum", "RACK-002 temp", "RACK-002 hum",
             "RACK-003 temp", "RACK-003 hum", "RACK-004 temp", "RACK-004 hum",
             "AC-001 temp", "AC-001 power"]
    for i in range(10):
        if i in (0, 2, 4, 6, 8):
            val = regs[i] / 10.0
            unit = "℃"
        elif i == 9:
            val = regs[i] / 100.0
            unit = "kW"
        else:
            val = regs[i]
            unit = "%"
        print(f"  4000{i+1} {names[i]:20s} = {val:8.1f} {unit}  (raw: {regs[i]})")

    client.close()
    return True


def test_mqtt():
    """验证 mosquitto MQTT 能正常收发消息"""
    import paho.mqtt.client as mqtt

    received = []

    def on_msg(client, userdata, msg):
        received.append((msg.topic, msg.payload.decode()))
        print(f"[MQTT] 收到 {msg.topic}: {msg.payload.decode()}")

    client = mqtt.Client()
    client.on_message = on_msg
    client.connect("localhost", 1883, 60)
    client.subscribe("dt/telemetry/#", qos=0)
    client.loop_start()

    # 发一条测试消息
    test_payload = json.dumps({
        "asset_id": 1,
        "sensor_id": 1,
        "measurement": "temperature",
        "value": 26.5,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    })
    client.publish("dt/telemetry/1", test_payload, qos=0)
    time.sleep(1)

    client.loop_stop()
    client.disconnect()

    if received:
        print(f"[PASS] MQTT 收发正常: {received[0][0]}")
        return True
    else:
        print("[WARN] MQTT 未收到消息（可能 mosquitto 没在跑）")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Phase 1 数据通路验证")
    print("=" * 50)

    modbus_ok = test_modbus()
    if not modbus_ok:
        sys.exit(1)

    print()
    test_mqtt()
