"""
Digital Twin Backend — Pydantic Schemas
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Asset ──
class AssetBase(BaseModel):
    asset_name: str = Field(max_length=128)
    asset_type: str = Field(max_length=32)
    room: Optional[str] = None
    floor: Optional[int] = None
    bim_guid: Optional[str] = None
    parent_id: Optional[int] = None


class AssetCreate(AssetBase):
    pass


class Asset(AssetBase):
    asset_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Sensor ──
class SensorBase(BaseModel):
    sensor_name: str = Field(max_length=128)
    protocol: str = Field(max_length=16)
    register: Optional[int] = None
    unit: Optional[str] = None
    asset_id: int


class SensorCreate(SensorBase):
    pass


class Sensor(SensorBase):
    sensor_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Mapping ──
class MappingBase(BaseModel):
    sensor_id: int
    measurement: str = Field(max_length=32)
    mapping_type: str = "direct"
    factor: float = 1.0
    offset_val: float = 0.0
    unit: Optional[str] = None


class MappingCreate(MappingBase):
    pass


class Mapping(MappingBase):
    mapping_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Telemetry (InfluxDB) ──
class TelemetryPoint(BaseModel):
    asset_id: int
    sensor_id: int
    measurement: str
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TelemetryResponse(BaseModel):
    asset_id: int
    sensor_name: str
    measurement: str
    value: float
    unit: str
    timestamp: datetime


# ── Alarm ──
class AlarmRuleBase(BaseModel):
    sensor_id: int
    alarm_name: str = Field(max_length=128)
    condition: str = Field(max_length=8)
    threshold: float
    threshold_high: Optional[float] = None
    severity: str = "warning"
    enabled: bool = True


class AlarmRuleCreate(AlarmRuleBase):
    pass


class AlarmRule(AlarmRuleBase):
    rule_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AlarmEvent(BaseModel):
    event_id: int
    rule_id: int
    asset_id: int
    sensor_id: int
    value: Optional[float] = None
    severity: Optional[str] = None
    message: Optional[str] = None
    acknowledged: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ── Room ──
class RoomBase(BaseModel):
    room_name: str = Field(max_length=64)
    floor: Optional[int] = None
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None


class RoomCreate(RoomBase):
    pass


class Room(RoomBase):
    room_id: int

    class Config:
        from_attributes = True


# ── WebSocket ──
class WsTelemetry(BaseModel):
    type: str = "telemetry"
    asset_id: int
    sensor_id: int
    measurement: str
    value: float
    unit: str
    timestamp: str


class WsAlarm(BaseModel):
    type: str = "alarm"
    asset_id: int
    sensor_id: int
    severity: str
    message: str
    timestamp: str
