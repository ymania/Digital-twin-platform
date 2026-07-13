"""
Digital Twin Backend — Models (SQLAlchemy ORM)
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "asset"

    asset_id = Column(Integer, primary_key=True)
    asset_name = Column(String(128), nullable=False)
    asset_type = Column(String(32), nullable=False)
    room = Column(String(64))
    floor = Column(Integer)
    bim_guid = Column(String(64), unique=True)
    parent_id = Column(Integer, ForeignKey("asset.asset_id"))
    metadata_ = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    sensors = relationship("Sensor", back_populates="asset")
    children = relationship("Asset", backref="parent", remote_side=[asset_id])


class Sensor(Base):
    __tablename__ = "sensor"

    sensor_id = Column(Integer, primary_key=True)
    sensor_name = Column(String(128), nullable=False)
    protocol = Column(String(16), nullable=False)
    register = Column(Integer)
    unit = Column(String(16))
    asset_id = Column(Integer, ForeignKey("asset.asset_id"), nullable=False)
    metadata_ = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    asset = relationship("Asset", back_populates="sensors")
    mappings = relationship("Mapping", back_populates="sensor")


class Mapping(Base):
    __tablename__ = "mapping"

    mapping_id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey("sensor.sensor_id"), nullable=False)
    measurement = Column(String(32), nullable=False)
    mapping_type = Column(String(16), default="direct")
    factor = Column(Float, default=1.0)
    offset_val = Column(Float, default=0.0)
    unit = Column(String(16))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    sensor = relationship("Sensor", back_populates="mappings")


class AlarmRule(Base):
    __tablename__ = "alarm_rule"

    rule_id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey("sensor.sensor_id"), nullable=False)
    alarm_name = Column(String(128), nullable=False)
    condition = Column(String(8), nullable=False)
    threshold = Column(Float, nullable=False)
    threshold_high = Column(Float)
    severity = Column(String(16), default="warning")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AlarmEvent(Base):
    __tablename__ = "alarm_event"

    event_id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("alarm_rule.rule_id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("asset.asset_id"), nullable=False)
    sensor_id = Column(Integer, ForeignKey("sensor.sensor_id"), nullable=False)
    value = Column(Float)
    severity = Column(String(16))
    message = Column(Text)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Room(Base):
    __tablename__ = "room"

    room_id = Column(Integer, primary_key=True)
    room_name = Column(String(64), nullable=False)
    floor = Column(Integer)
    grid_x = Column(Integer)
    grid_y = Column(Integer)
    metadata_ = Column("metadata", JSON)
