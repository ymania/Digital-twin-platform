"""
Sensors API Router
"""
from fastapi import APIRouter, HTTPException
from typing import List

from database import get_pool

router = APIRouter(prefix="/api/sensors", tags=["Sensors"])


@router.get("")
async def list_sensors(asset_id: int = None):
    pool = await get_pool()
    if asset_id:
        rows = await pool.fetch(
            "SELECT * FROM sensor WHERE asset_id = $1 ORDER BY sensor_id", asset_id
        )
    else:
        rows = await pool.fetch("SELECT * FROM sensor ORDER BY sensor_id")
    return [dict(r) for r in rows]


@router.get("/{sensor_id}")
async def get_sensor(sensor_id: int):
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM sensor WHERE sensor_id = $1", sensor_id)
    if not row:
        raise HTTPException(404, "Sensor not found")
    return dict(row)


@router.get("/mapping/registers")
async def get_mapping_by_registers(registers: str = ""):
    """批量查询寄存器→资产映射, registers=100,101,102"""
    pool = await get_pool()
    reg_list = [int(r) for r in registers.split(",") if r.strip().isdigit()]
    if not reg_list:
        return {}
    rows = await pool.fetch(
        """SELECT s.register, s.asset_id, s.sensor_id, s.unit,
                  m.measurement, m.factor, m.offset_val
           FROM sensor s
           JOIN mapping m ON m.sensor_id = s.sensor_id
           WHERE s.register = ANY($1::int[])""",
        reg_list
    )
    result = {}
    for r in rows:
        result[str(r["register"])] = {
            "asset_id": r["asset_id"],
            "sensor_id": r["sensor_id"],
            "measurement": r["measurement"],
            "factor": float(r["factor"]) if r["factor"] else 1.0,
            "offset": float(r["offset_val"]) if r["offset_val"] else 0.0,
        }
    return result


@router.get("/{sensor_id}/mappings")
async def get_sensor_mappings(sensor_id: int):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM mapping WHERE sensor_id = $1 ORDER BY mapping_id", sensor_id
    )
    return [dict(r) for r in rows]


@router.get("/{sensor_id}/telemetry")
async def get_sensor_telemetry(sensor_id: int, limit: int = 100):
    """Get latest telemetry for a sensor from InfluxDB"""
    from database.influx import query_api
    import os

    bucket = os.getenv("INFLUXDB_BUCKET", "telemetry")
    org = os.getenv("INFLUXDB_ORG", "dt_platform")

    flux = f'''
    from(bucket: "{bucket}")
        |> range(start: -24h)
        |> filter(fn: (r) => r.sensor_id == "{sensor_id}")
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: {limit})
    '''

    tables = query_api().query(flux, org=org)
    results = []
    for table in tables:
        for record in table.records:
            results.append({
                "asset_id": int(record.values.get("asset_id", 0)),
                "sensor_id": int(record.values.get("sensor_id", sensor_id)),
                "measurement": record.values.get("measurement", ""),
                "value": record.get_value(),
                "unit": record.values.get("unit", ""),
                "timestamp": record.get_time().isoformat(),
            })
    return results
