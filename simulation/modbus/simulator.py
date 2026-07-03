"""
Modbus TCP Simulator (pymodbus 3.x)

寄存器地址映射 (0-based, 对应 40001+):
  0:  RACK-001 temp (×10)
  1:  RACK-001 hum
  2:  RACK-002 temp
  3:  RACK-002 hum
  4:  RACK-003 temp
  5:  RACK-003 hum
  6:  RACK-004 temp
  7:  RACK-004 hum
  8:  AC-001 temp
  9:  AC-001 power (×100)
"""
import asyncio
import logging
import math
import random
import time

from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SIM] %(message)s")
log = logging.getLogger("modbus-sim")

REG_COUNT = 20
VALUES = [0] * REG_COUNT  # index = Modbus address (0-based)

# (base, amplitude, period_seconds)
SENSOR_PROFILES = {
    0: (300, 100, 30),   # RACK-001 temp  30.0±5℃
    1: (550, 150, 40),   # RACK-001 hum   55±15%
    2: (280, 80,  25),   # RACK-002 temp  28.0±4℃
    3: (500, 100, 35),   # RACK-002 hum   50±10%
    4: (320, 120, 28),   # RACK-003 temp  32.0±6℃
    5: (450, 200, 45),   # RACK-003 hum   45±20%
    6: (260, 100, 32),   # RACK-004 temp  26.0±5℃
    7: (600, 100, 38),   # RACK-004 hum   60±10%
    8: (220, 50,  20),   # AC-001 temp    22.0±2.5℃
    9: (300, 200, 60),   # AC-001 power   3.0±2.0kW
}

GLITCH_ADDRS = {0, 2, 4}


def update():
    now = time.time()
    for addr, (base, amp, period) in SENSOR_PROFILES.items():
        sine = math.sin(2 * math.pi * now / period)
        noise = base * 0.05 * (2 * random.random() - 1)
        raw = base + amp * sine + noise

        if addr in GLITCH_ADDRS and random.random() < 0.02:
            raw += 80 * (1 if random.random() > 0.5 else -1)

        VALUES[addr] = max(0, min(65535, int(round(raw))))

    log.info("Regs: %s", {
        40001 + addr: VALUES[addr] for addr in SENSOR_PROFILES
    })


async def tick():
    while True:
        update()
        await asyncio.sleep(1.0)


async def run():
    block = ModbusSequentialDataBlock(1, VALUES)
    ctx = ModbusDeviceContext(hr=block)
    server_ctx = ModbusServerContext(devices=ctx, single=True)

    update()
    asyncio.create_task(tick())

    log.info("Modbus TCP Simulator -> 0.0.0.0:5020")
    await StartAsyncTcpServer(context=server_ctx, address=("0.0.0.0", 5020))


if __name__ == "__main__":
    asyncio.run(run())
