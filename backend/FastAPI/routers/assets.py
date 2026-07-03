"""
Asset API Router
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from database import get_pool

router = APIRouter(prefix="/api/assets", tags=["Assets"])


@router.get("")
async def list_assets(asset_type: str = None):
    pool = await get_pool()
    if asset_type:
        rows = await pool.fetch(
            "SELECT * FROM asset WHERE asset_type = $1 ORDER BY asset_id", asset_type
        )
    else:
        rows = await pool.fetch("SELECT * FROM asset ORDER BY asset_id")
    return [dict(r) for r in rows]


@router.get("/{asset_id}")
async def get_asset(asset_id: int):
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM asset WHERE asset_id = $1", asset_id)
    if not row:
        raise HTTPException(404, "Asset not found")
    return dict(row)


@router.get("/{asset_id}/sensors")
async def get_asset_sensors(asset_id: int):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM sensor WHERE asset_id = $1 ORDER BY sensor_id", asset_id
    )
    return [dict(r) for r in rows]


@router.get("/{asset_id}/telemetry")
async def get_asset_telemetry(asset_id: int, measurement: str = None, limit: int = 100):
    """Get latest telemetry for an asset from InfluxDB"""
    from database.influx import query_api
    import os

    bucket = os.getenv("INFLUXDB_BUCKET", "telemetry")
    org = os.getenv("INFLUXDB_ORG", "dt_platform")

    if measurement:
        flux = f'''
        from(bucket: "{bucket}")
            |> range(start: -24h)
            |> filter(fn: (r) => r.asset_id == "{asset_id}" and r.measurement == "{measurement}")
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: {limit})
        '''
    else:
        flux = f'''
        from(bucket: "{bucket}")
            |> range(start: -24h)
            |> filter(fn: (r) => r.asset_id == "{asset_id}")
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: {limit})
        '''

    tables = query_api().query(flux, org=org)
    results = []
    for table in tables:
        for record in table.records:
            results.append({
                "asset_id": int(record.values.get("asset_id", asset_id)),
                "sensor_id": int(record.values.get("sensor_id", 0)),
                "measurement": record.values.get("measurement", ""),
                "value": record.get_value(),
                "unit": record.values.get("unit", ""),
                "timestamp": record.get_time().isoformat(),
            })
    return results
