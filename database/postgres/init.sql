-- ============================================================
-- Digital Twin Data Center Platform
-- PostgreSQL Initialization
-- ============================================================

-- Asset: 现实世界的物理对象
CREATE TABLE IF NOT EXISTS asset (
    asset_id    SERIAL PRIMARY KEY,
    asset_name  VARCHAR(128) NOT NULL,
    asset_type  VARCHAR(32)  NOT NULL,  -- cabinet, ac, ups, pdu, sensor
    room        VARCHAR(64),
    floor       INTEGER,
    bim_guid    VARCHAR(64)  UNIQUE,    -- IFC GUID
    parent_id   INTEGER      REFERENCES asset(asset_id),
    metadata    JSONB,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- Sensor: 传感器定义
CREATE TABLE IF NOT EXISTS sensor (
    sensor_id   SERIAL PRIMARY KEY,
    sensor_name VARCHAR(128) NOT NULL,
    protocol    VARCHAR(16)  NOT NULL,  -- modbus, bacnet, opcua
    register    INTEGER,                -- Modbus 寄存器地址
    unit        VARCHAR(16),            -- °C, %, kW
    asset_id    INTEGER      NOT NULL REFERENCES asset(asset_id),
    metadata    JSONB,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- Mapping: 数据映射（传感器值与物理量的关系）
CREATE TYPE mapping_type AS ENUM ('direct', 'linear', 'lookup');

CREATE TABLE IF NOT EXISTS mapping (
    mapping_id   SERIAL PRIMARY KEY,
    sensor_id    INTEGER       NOT NULL REFERENCES sensor(sensor_id),
    measurement  VARCHAR(32)   NOT NULL,  -- temperature, humidity, power
    mapping_type mapping_type  DEFAULT 'direct',
    factor       REAL          DEFAULT 1.0,
    offset_val   REAL          DEFAULT 0.0,
    unit         VARCHAR(16),
    created_at   TIMESTAMPTZ   DEFAULT NOW()
);

-- Alarm: 告警规则
CREATE TABLE IF NOT EXISTS alarm_rule (
    rule_id     SERIAL PRIMARY KEY,
    sensor_id   INTEGER       NOT NULL REFERENCES sensor(sensor_id),
    alarm_name  VARCHAR(128)  NOT NULL,
    condition   VARCHAR(8)    NOT NULL,  -- gt, lt, eq, range
    threshold   REAL          NOT NULL,
    threshold_high REAL,
    severity    VARCHAR(16)   DEFAULT 'warning',  -- info, warning, critical
    enabled     BOOLEAN       DEFAULT TRUE,
    created_at  TIMESTAMPTZ   DEFAULT NOW()
);

-- Alarm Event: 告警事件记录
CREATE TABLE IF NOT EXISTS alarm_event (
    event_id    SERIAL PRIMARY KEY,
    rule_id     INTEGER       NOT NULL REFERENCES alarm_rule(rule_id),
    asset_id    INTEGER       NOT NULL REFERENCES asset(asset_id),
    sensor_id   INTEGER       NOT NULL REFERENCES sensor(sensor_id),
    value       REAL,
    severity    VARCHAR(16),
    message     TEXT,
    acknowledged BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMPTZ   DEFAULT NOW()
);

-- Room: 机房布局
CREATE TABLE IF NOT EXISTS room (
    room_id     SERIAL PRIMARY KEY,
    room_name   VARCHAR(64)  NOT NULL,
    floor       INTEGER,
    grid_x      INTEGER,     -- 布局网格坐标
    grid_y      INTEGER,
    metadata    JSONB
);

-- 索引
CREATE INDEX idx_sensor_asset ON sensor(asset_id);
CREATE INDEX idx_mapping_sensor ON mapping(sensor_id);
CREATE INDEX idx_alarm_rule_sensor ON alarm_rule(sensor_id);
CREATE INDEX idx_alarm_event_asset ON alarm_event(asset_id);
CREATE INDEX idx_alarm_event_created ON alarm_event(created_at DESC);
CREATE INDEX idx_asset_bim_guid ON asset(bim_guid);
CREATE INDEX idx_asset_parent ON asset(parent_id);

-- ============================================================
-- Seed Data: 机房 + 设备 + 传感器
-- ============================================================

-- 机房
INSERT INTO room (room_name, floor, grid_x, grid_y) VALUES
    ('Main Server Room', 1, 4, 5);

-- 资产（机柜）
INSERT INTO asset (asset_name, asset_type, room, floor, bim_guid) VALUES
    ('RACK-001', 'cabinet', 'Main Server Room', 1, '3XW2b$f5T9BQ7j1'),
    ('RACK-002', 'cabinet', 'Main Server Room', 1, '4Yx3c$g6U0CR8k2'),
    ('RACK-003', 'cabinet', 'Main Server Room', 1, '5Zy4d$h7V1DS9l3'),
    ('RACK-004', 'cabinet', 'Main Server Room', 1, '6Az5e$i8W2ET0m4');

-- 空调
INSERT INTO asset (asset_name, asset_type, room, floor, bim_guid) VALUES
    ('AC-001', 'ac', 'Main Server Room', 1, '7Ba6f$j9X3FU1n5'),
    ('AC-002', 'ac', 'Main Server Room', 1, '8Cb7g$k0Y4GV2o6');

-- UPS
INSERT INTO asset (asset_name, asset_type, room, floor, bim_guid) VALUES
    ('UPS-001', 'ups', 'Main Server Room', 1, '9Dc8h$l1Z5HW3p7');

-- PDU
INSERT INTO asset (asset_name, asset_type, room, floor, bim_guid, parent_id) VALUES
    ('PDU-001', 'pdu', 'Main Server Room', 1, '0Ed9i$m2A6IX4q8', 1),
    ('PDU-002', 'pdu', 'Main Server Room', 1, '1Fe0j$n3B7JY5r9', 2);

-- 传感器（RACK-001）
INSERT INTO sensor (sensor_name, protocol, register, unit, asset_id) VALUES
    ('RACK-001-TEMP', 'modbus', 100, '°C', 1),
    ('RACK-001-HUM',  'modbus', 101, '%',  1),
    ('RACK-001-PWR',  'modbus', 102, 'kW', 1);

INSERT INTO sensor (sensor_name, protocol, register, unit, asset_id) VALUES
    ('RACK-002-TEMP', 'modbus', 103, '°C', 2),
    ('RACK-002-HUM',  'modbus', 104, '%',  2),
    ('RACK-002-PWR',  'modbus', 105, 'kW', 2);

INSERT INTO sensor (sensor_name, protocol, register, unit, asset_id) VALUES
    ('RACK-003-TEMP', 'modbus', 106, '°C', 3),
    ('RACK-003-HUM',  'modbus', 107, '%',  3),
    ('RACK-003-PWR',  'modbus', 108, 'kW', 3);

INSERT INTO sensor (sensor_name, protocol, register, unit, asset_id) VALUES
    ('RACK-004-TEMP', 'modbus', 109, '°C', 4),
    ('RACK-004-HUM',  'modbus', 110, '%',  4),
    ('RACK-004-PWR',  'modbus', 111, 'kW', 4);

-- 空调传感器
INSERT INTO sensor (sensor_name, protocol, register, unit, asset_id) VALUES
    ('AC-001-TEMP', 'modbus', 200, '°C', 5),
    ('AC-001-PWR',  'modbus', 201, 'kW', 5);

INSERT INTO sensor (sensor_name, protocol, register, unit, asset_id) VALUES
    ('AC-002-TEMP', 'modbus', 202, '°C', 6),
    ('AC-002-PWR',  'modbus', 203, 'kW', 6);

-- UPS 传感器
INSERT INTO sensor (sensor_name, protocol, register, unit, asset_id) VALUES
    ('UPS-001-LOAD',  'modbus', 300, '%',  7),
    ('UPS-001-VOLT',  'modbus', 301, 'V',  7);

-- 数据映射
INSERT INTO mapping (sensor_id, measurement, mapping_type, factor, offset_val, unit) VALUES
    (1,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (2,  'humidity',    'direct', 1.0, 0.0, '%'),
    (3,  'power',       'direct', 0.1, 0.0, 'kW'),
    (4,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (5,  'humidity',    'direct', 1.0, 0.0, '%'),
    (6,  'power',       'direct', 0.1, 0.0, 'kW'),
    (7,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (8,  'humidity',    'direct', 1.0, 0.0, '%'),
    (9,  'power',       'direct', 0.1, 0.0, 'kW'),
    (10, 'temperature', 'direct', 1.0, 0.0, '°C'),
    (11, 'humidity',    'direct', 1.0, 0.0, '%'),
    (12, 'power',       'direct', 0.1, 0.0, 'kW'),
    (13, 'temperature', 'direct', 1.0, 0.0, '°C'),
    (14, 'power',       'direct', 1.0, 0.0, 'kW'),
    (15, 'temperature', 'direct', 1.0, 0.0, '°C'),
    (16, 'power',       'direct', 1.0, 0.0, 'kW'),
    (17, 'power',       'direct', 1.0, 0.0, '%'),
    (18, 'power',       'direct', 1.0, 0.0, 'V');

-- 告警规则
INSERT INTO alarm_rule (sensor_id, alarm_name, condition, threshold, threshold_high, severity) VALUES
    (1,  'RACK-001 Temp High',  'gt',  30.0, NULL, 'warning'),
    (1,  'RACK-001 Temp Crit',  'gt',  35.0, NULL, 'critical'),
    (11, 'RACK-003 Hum High',   'gt',  70.0, NULL, 'warning'),
    (3,  'RACK-001 PWR High',   'gt',  5.0,  NULL, 'warning');
