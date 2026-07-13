-- ============================================================
-- Digital Twin Data Center Platform
-- PostgreSQL Initialization
-- ============================================================

-- Asset: 现实世界的物理对象
CREATE TABLE IF NOT EXISTS asset (
    asset_id    SERIAL PRIMARY KEY,
    asset_name  VARCHAR(128) NOT NULL,
    asset_type  VARCHAR(32)  NOT NULL,  -- cabinet, wall, floor, roof, space, sensor
    room        VARCHAR(64),
    floor       INTEGER,
    bim_guid    VARCHAR(64)  UNIQUE,    -- IFC GlobalId
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
-- Seed Data: IFC 建筑资产 + 传感器
-- ============================================================

-- 机房
INSERT INTO room (room_name, floor, grid_x, grid_y) VALUES
    ('Main Room', 1, 4, 5);

-- 资产（从 IFC 模型 Building-Architecture.ifc 提取）
INSERT INTO asset (asset_name, asset_type, room, floor, bim_guid) VALUES
    ('floor',          'slab',  'Main Room', 1, '3zR0BOEcLADRKln4HYporH'),
    ('wall_right_front','wall', 'Main Room', 1, '1AQAupaRP1txwK1AGiN61V'),
    ('wall_right_back', 'wall', 'Main Room', 1, '3wdauVJT5Fx9drrREiDqA$'),
    ('wall_left',      'wall',  'Main Room', 1, '0OfZwWc8j9QP5uX8xPTxDH'),
    ('wall_plumbing',  'wall',  'Main Room', 1, '1uS5vfZPn9R8PlAaVd73on'),
    ('roof_left',      'roof',  'Main Room', 2, '0ZTBBPo6f6bxqV2K7Oelrq'),
    ('roof_right',     'roof',  'Main Room', 2, '12UVOn4wvAJPMUExKdZLb8'),
    ('kitchen',        'furniture', 'Main Room', 1, '2e9pghUJbBqR4jTInsONQT'),
    ('living_room',    'space', 'Main Room', 1, '0xY$LvXaDEswJDk_VU74C_'),
    ('entry_hall',     'space', 'Main Room', 1, '18QhMtUIXBvQktPHXXxs7H');

-- 传感器（每个 asset 一个或多个传感器）
INSERT INTO sensor (sensor_name, protocol, register, unit, asset_id) VALUES
    ('FLOOR-TEMP',  'modbus', 100, '°C', 1),
    ('FLOOR-HUM',   'modbus', 101, '%',  1),
    ('WALL-RF-TEMP','modbus', 102, '°C', 2),
    ('WALL-RF-HUM', 'modbus', 103, '%',  2),
    ('WALL-RB-TEMP','modbus', 104, '°C', 3),
    ('WALL-L-TEMP', 'modbus', 105, '°C', 4),
    ('WALL-PL-TEMP','modbus', 106, '°C', 5),
    ('WALL-PL-HUM', 'modbus', 107, '%',  5),
    ('ROOF-L-TEMP', 'modbus', 108, '°C', 6),
    ('ROOF-R-TEMP', 'modbus', 109, '°C', 7),
    ('KITCHEN-TEMP','modbus', 110, '°C', 8),
    ('KITCHEN-PWR', 'modbus', 111, 'kW', 8),
    ('LIVING-TEMP', 'modbus', 112, '°C', 9),
    ('LIVING-HUM',  'modbus', 113, '%',  9),
    ('ENTRY-TEMP',  'modbus', 114, '°C', 10);

-- 数据映射
INSERT INTO mapping (sensor_id, measurement, mapping_type, factor, offset_val, unit) VALUES
    (1,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (2,  'humidity',    'direct', 1.0, 0.0, '%'),
    (3,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (4,  'humidity',    'direct', 1.0, 0.0, '%'),
    (5,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (6,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (7,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (8,  'humidity',    'direct', 1.0, 0.0, '%'),
    (9,  'temperature', 'direct', 1.0, 0.0, '°C'),
    (10, 'temperature', 'direct', 1.0, 0.0, '°C'),
    (11, 'temperature', 'direct', 1.0, 0.0, '°C'),
    (12, 'power',       'direct', 0.1, 0.0, 'kW'),
    (13, 'temperature', 'direct', 1.0, 0.0, '°C'),
    (14, 'humidity',    'direct', 1.0, 0.0, '%'),
    (15, 'temperature', 'direct', 1.0, 0.0, '°C');

-- 告警规则
INSERT INTO alarm_rule (sensor_id, alarm_name, condition, threshold, threshold_high, severity) VALUES
    (1,  'Floor Temp High', 'gt', 30.0, NULL, 'warning'),
    (5,  'Wall-RB Temp High','gt', 35.0, NULL, 'critical'),
    (12, 'Kitchen PWR High', 'gt', 5.0,  NULL, 'warning');
