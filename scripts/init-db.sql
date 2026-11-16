-- ============================================================
-- PdM System MySQL 8.0 初始化脚本
-- ============================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

USE pdm_system;

-- ============================================================
-- 表 1: equipment —— 设备资产
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    equipment_code  VARCHAR(64) UNIQUE NOT NULL COMMENT '设备编码，如 WT-GEAR-001',
    name            VARCHAR(255) NOT NULL COMMENT '设备名称',
    model           VARCHAR(128) COMMENT '型号',
    manufacturer    VARCHAR(128) COMMENT '厂商',
    install_date    DATE COMMENT '安装日期',
    location        VARCHAR(255) COMMENT '所在位置',
    equipment_type  ENUM('CNC_SPINDLE','COMPRESSOR','WIND_GEARBOX') NOT NULL COMMENT '设备类型',
    health_score    DECIMAL(5,2) DEFAULT 100.00 COMMENT '健康分数 0-100',
    status          ENUM('RUNNING','STOPPED','MAINTENANCE','CRITICAL') DEFAULT 'RUNNING',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (equipment_type),
    INDEX idx_status (status),
    INDEX idx_health (health_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 表 2: sensor —— 传感器定义
-- ============================================================
CREATE TABLE IF NOT EXISTS sensor (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    equipment_id    BIGINT NOT NULL,
    sensor_code     VARCHAR(64) NOT NULL COMMENT '传感器编码',
    sensor_type     ENUM('TEMPERATURE','VIBRATION','CURRENT','OIL_PRESSURE','SPECTRUM') NOT NULL,
    channel         VARCHAR(32) COMMENT '振动通道 X/Y/Z',
    sampling_freq   INT COMMENT '采样频率 Hz',
    unit            VARCHAR(16),
    normal_min      DECIMAL(10,4),
    normal_max      DECIMAL(10,4),
    warning_min     DECIMAL(10,4),
    warning_max     DECIMAL(10,4),
    critical_min    DECIMAL(10,4),
    critical_max    DECIMAL(10,4),
    baseline_value  DECIMAL(10,4) COMMENT '健康基线值',
    FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE,
    UNIQUE KEY uk_equip_sensor (equipment_id, sensor_code),
    INDEX idx_type (sensor_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 表 3: sensor_data_agg —— 时序数据（分钟级聚合）
-- ============================================================
CREATE TABLE IF NOT EXISTS sensor_data_agg (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    sensor_id       BIGINT NOT NULL,
    ts              DATETIME NOT NULL COMMENT '时间戳（分钟粒度）',
    val_min         DECIMAL(10,4),
    val_max         DECIMAL(10,4),
    val_avg         DECIMAL(10,4),
    val_std         DECIMAL(10,4),
    anomaly_flag    TINYINT DEFAULT 0 COMMENT '0正常 1可疑 2异常',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sensor_ts (sensor_id, ts),
    INDEX idx_ts (ts),
    INDEX idx_sensor_ts (sensor_id, ts),
    FOREIGN KEY (sensor_id) REFERENCES sensor(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 表 4: alert —— 告警
-- ============================================================
CREATE TABLE IF NOT EXISTS alert (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    equipment_id        BIGINT NOT NULL,
    alert_type          ENUM('ANOMALY','RUL_WARNING','CRITICAL','SENSOR_FAILURE','MANUAL') NOT NULL,
    severity            ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    feature_snapshot    JSON COMMENT '触发告警的特征值快照',
    rul_hours           INT COMMENT '预估剩余寿命小时数',
    risk_score          DECIMAL(5,2),
    status              ENUM('OPEN','ACKNOWLEDGED','ESCALATED','RESOLVED','IGNORED') DEFAULT 'OPEN',
    agent_diagnosis     TEXT COMMENT '智能体诊断结论',
    agent_rca           TEXT COMMENT '根因分析链（JSON 字符串）',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at     DATETIME,
    resolved_at         DATETIME,
    created_by          VARCHAR(64) DEFAULT 'SYSTEM',
    FOREIGN KEY (equipment_id) REFERENCES equipment(id),
    INDEX idx_equip_status (equipment_id, status),
    INDEX idx_severity (severity),
    INDEX idx_created (created_at),
    INDEX idx_type (alert_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 表 5: work_order —— 维修工单
-- ============================================================
CREATE TABLE IF NOT EXISTS work_order (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_no            VARCHAR(64) UNIQUE NOT NULL COMMENT '工单编号，自动生成',
    alert_id            BIGINT COMMENT '关联告警',
    equipment_id        BIGINT NOT NULL,
    order_type          ENUM('PREVENTIVE','CORRECTIVE','EMERGENCY','SHUTDOWN_REQUEST') NOT NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    diagnosis           TEXT COMMENT '故障诊断结论',
    actions_taken       TEXT COMMENT '已执行的操作',
    spare_parts         JSON COMMENT '备件清单 [{name, qty, part_no, unit_price}]',
    status              ENUM('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','IN_PROGRESS','COMPLETED','CANCELLED') DEFAULT 'DRAFT',
    priority            ENUM('LOW','MEDIUM','HIGH','CRITICAL') DEFAULT 'MEDIUM',
    planned_start       DATETIME,
    planned_end         DATETIME,
    actual_start        DATETIME,
    actual_end          DATETIME,
    created_by          VARCHAR(64) DEFAULT 'SYSTEM',
    approved_by         VARCHAR(64),
    approved_at         DATETIME,
    rejected_reason     TEXT,
    -- HITL 审批相关
    requires_human_approval TINYINT DEFAULT 1,
    approval_policy     VARCHAR(32) COMMENT 'AUTO / LEVEL1 / LEVEL2 / CRITICAL',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alert(id),
    FOREIGN KEY (equipment_id) REFERENCES equipment(id),
    INDEX idx_status (status),
    INDEX idx_equip (equipment_id),
    INDEX idx_approval (requires_human_approval, status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 表 6: approval_record —— 审批记录
-- ============================================================
CREATE TABLE IF NOT EXISTS approval_record (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    work_order_id   BIGINT NOT NULL,
    action          ENUM('APPROVE','REJECT','EDIT','ESCALATE') NOT NULL,
    comment         TEXT,
    edited_payload  JSON COMMENT '编辑后的工单字段',
    approver        VARCHAR(64) NOT NULL,
    approver_role   VARCHAR(32) DEFAULT 'TECHNICIAN_LEAD',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (work_order_id) REFERENCES work_order(id) ON DELETE CASCADE,
    INDEX idx_wo (work_order_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 表 7: maintenance_manual —— 维修手册
-- ============================================================
CREATE TABLE IF NOT EXISTS maintenance_manual (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    equipment_type  VARCHAR(64) NOT NULL,
    title           VARCHAR(255) NOT NULL,
    vendor          VARCHAR(128),
    version         VARCHAR(32),
    minio_path      VARCHAR(512) COMMENT 'MinIO 对象路径',
    content_text    MEDIUMTEXT COMMENT '纯文本内容（用于 RAG）',
    chunk_count     INT,
    uploaded_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type (equipment_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 表 8: manual_chunk —— 手册切块（RAG 检索用）
-- ============================================================
CREATE TABLE IF NOT EXISTS manual_chunk (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    manual_id       BIGINT NOT NULL,
    chunk_index     INT NOT NULL,
    chapter         VARCHAR(64),
    section_title   VARCHAR(255),
    content         TEXT NOT NULL,
    keywords        VARCHAR(512) COMMENT '逗号分隔的关键词',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (manual_id) REFERENCES maintenance_manual(id) ON DELETE CASCADE,
    INDEX idx_manual (manual_id),
    INDEX idx_chapter (chapter)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 表 9: agent_conversation —— LLM 对话历史（溯源）
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_conversation (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id      VARCHAR(64) NOT NULL,
    alert_id        BIGINT,
    role            ENUM('SYSTEM','USER','ASSISTANT','TOOL') NOT NULL,
    content         MEDIUMTEXT,
    tool_name       VARCHAR(64),
    tool_args       JSON,
    latency_ms      INT,
    model           VARCHAR(64),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    INDEX idx_alert (alert_id),
    FOREIGN KEY (alert_id) REFERENCES alert(id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 种子数据：风力发电机齿轮箱（WT-GEAR-001/002/003）
-- ============================================================
INSERT INTO equipment (equipment_code, name, model, manufacturer, install_date, location, equipment_type, health_score, status) VALUES
('WT-GEAR-001', '1#风机齿轮箱', 'Flender S380', 'Flender', '2021-06-15', 'A区1号机位', 'WIND_GEARBOX', 95.00, 'RUNNING'),
('WT-GEAR-002', '2#风机齿轮箱', 'Flender S380', 'Flender', '2022-03-20', 'A区2号机位', 'WIND_GEARBOX', 78.50, 'RUNNING'),
('WT-GEAR-003', '3#风机齿轮箱', 'Flender S420', 'Flender', '2020-11-08', 'B区1号机位', 'WIND_GEARBOX', 62.30, 'RUNNING'),
('WT-GEAR-004', '4#风机齿轮箱', 'Flender S380', 'Flender', '2023-01-10', 'B区2号机位', 'WIND_GEARBOX', 98.00, 'RUNNING');

-- WT-GEAR-001 的传感器（作为默认模拟器设备）
INSERT INTO sensor (equipment_id, sensor_code, sensor_type, channel, sampling_freq, unit, normal_min, normal_max, warning_min, warning_max, critical_min, critical_max, baseline_value) VALUES
-- 低速轴振动（三轴）
(1, 'VIB_LS_X', 'VIBRATION', 'X', 100, 'mm/s', 0.30, 2.00, NULL, 3.00, NULL, 4.50, 1.20),
(1, 'VIB_LS_Y', 'VIBRATION', 'Y', 100, 'mm/s', 0.30, 2.00, NULL, 3.00, NULL, 4.50, 1.20),
(1, 'VIB_LS_Z', 'VIBRATION', 'Z', 100, 'mm/s', 0.20, 1.50, NULL, 2.50, NULL, 4.00, 0.90),
-- 高速轴振动
(1, 'VIB_HS_X', 'VIBRATION', 'X', 100, 'mm/s', 0.20, 1.80, NULL, 2.80, NULL, 4.00, 1.00),
-- 轴承温度（低速轴前轴承）
(1, 'TEMP_BEARING_LS_FRONT', 'TEMPERATURE', NULL, 1, '℃', 40.00, 60.00, NULL, 68.00, NULL, 75.00, 50.00),
-- 润滑油温度
(1, 'TEMP_OIL', 'TEMPERATURE', NULL, 1, '℃', 45.00, 65.00, NULL, 72.00, NULL, 80.00, 55.00),
-- 润滑油压力
(1, 'OIL_PRESS', 'OIL_PRESSURE', NULL, 1, 'bar', 2.50, 4.00, 2.00, NULL, 1.50, NULL, 3.20),
-- 电机电流
(1, 'CURRENT_RMS', 'CURRENT', NULL, 1, 'A', 25.00, 45.00, 20.00, 50.00, 15.00, 55.00, 35.00);

-- WT-GEAR-002 的传感器（相同配置）
INSERT INTO sensor (equipment_id, sensor_code, sensor_type, channel, sampling_freq, unit, normal_min, normal_max, warning_min, warning_max, critical_min, critical_max, baseline_value) VALUES
(2, 'VIB_LS_X', 'VIBRATION', 'X', 100, 'mm/s', 0.30, 2.00, NULL, 3.00, NULL, 4.50, 1.30),
(2, 'VIB_LS_Y', 'VIBRATION', 'Y', 100, 'mm/s', 0.30, 2.00, NULL, 3.00, NULL, 4.50, 1.25),
(2, 'VIB_LS_Z', 'VIBRATION', 'Z', 100, 'mm/s', 0.20, 1.50, NULL, 2.50, NULL, 4.00, 0.95),
(2, 'VIB_HS_X', 'VIBRATION', 'X', 100, 'mm/s', 0.20, 1.80, NULL, 2.80, NULL, 4.00, 1.10),
(2, 'TEMP_BEARING_LS_FRONT', 'TEMPERATURE', NULL, 1, '℃', 40.00, 60.00, NULL, 68.00, NULL, 75.00, 52.00),
(2, 'TEMP_OIL', 'TEMPERATURE', NULL, 1, '℃', 45.00, 65.00, NULL, 72.00, NULL, 80.00, 56.00),
(2, 'OIL_PRESS', 'OIL_PRESSURE', NULL, 1, 'bar', 2.50, 4.00, 2.00, NULL, 1.50, NULL, 3.00),
(2, 'CURRENT_RMS', 'CURRENT', NULL, 1, 'A', 25.00, 45.00, 20.00, 50.00, 15.00, 55.00, 36.00);

-- WT-GEAR-003 的传感器（较旧，有退化趋势）
INSERT INTO sensor (equipment_id, sensor_code, sensor_type, channel, sampling_freq, unit, normal_min, normal_max, warning_min, warning_max, critical_min, critical_max, baseline_value) VALUES
(3, 'VIB_LS_X', 'VIBRATION', 'X', 100, 'mm/s', 0.30, 2.50, NULL, 3.50, NULL, 5.00, 1.80),
(3, 'VIB_LS_Y', 'VIBRATION', 'Y', 100, 'mm/s', 0.30, 2.50, NULL, 3.50, NULL, 5.00, 1.75),
(3, 'VIB_LS_Z', 'VIBRATION', 'Z', 100, 'mm/s', 0.20, 2.00, NULL, 3.00, NULL, 4.50, 1.30),
(3, 'VIB_HS_X', 'VIBRATION', 'X', 100, 'mm/s', 0.20, 2.00, NULL, 3.00, NULL, 4.50, 1.40),
(3, 'TEMP_BEARING_LS_FRONT', 'TEMPERATURE', NULL, 1, '℃', 40.00, 65.00, NULL, 72.00, NULL, 80.00, 58.00),
(3, 'TEMP_OIL', 'TEMPERATURE', NULL, 1, '℃', 45.00, 68.00, NULL, 75.00, NULL, 82.00, 62.00),
(3, 'OIL_PRESS', 'OIL_PRESSURE', NULL, 1, 'bar', 2.30, 3.80, 1.80, NULL, 1.40, NULL, 2.60),
(3, 'CURRENT_RMS', 'CURRENT', NULL, 1, 'A', 25.00, 48.00, 20.00, 52.00, 15.00, 56.00, 38.00);

-- 预埋维修手册（3 章）
INSERT INTO maintenance_manual (equipment_type, title, vendor, version, chunk_count, content_text) VALUES
('WIND_GEARBOX', '齿轮箱故障诊断与维护手册', 'Flender', 'v2.3', 3, 'Flender S 系列齿轮箱故障诊断与维护手册 v2.3'),
('WIND_GEARBOX', '滚动轴承故障诊断手册', 'SKF', 'v5.1', 2, 'SKF 滚动轴承故障诊断手册 v5.1'),
('WIND_GEARBOX', '润滑油系统维护指南', 'Mobil', 'v1.8', 1, 'Mobil 润滑油系统维护指南 v1.8');

INSERT INTO manual_chunk (manual_id, chunk_index, chapter, section_title, content, keywords) VALUES
(1, 1, '3.2', '轴承退化与更换指南',
'当轴承外圈振动频谱中出现特征频率 BPFO（约 3.5x转频）的谐波分量，且边频带能量比超过 0.15 时，判定为早期点蚀。此时建议将齿轮箱润滑油更换周期缩短 50%，并增加振动监测频率（建议每 4 小时采样一次）。若振动 RMS 值超过 4.5 mm/s，应计划在下一个维护窗口更换轴承。轴承更换操作步骤见附录 A.12。更换时注意轴颈表面检查，若有磨损需先进行刷镀修复。',
'轴承,点蚀,BPFO,振动,边频带,更换'),

(1, 2, '4.1', '齿轮啮合异常诊断',
'齿轮点蚀、剥落和断齿会产生冲击调制响应。啮合频率 GMF 的 2 次谐波能量比超过 0.3 时，说明轮齿已发生明显磨损。低速轴转频约 20Hz，齿轮齿数 25，则 GMF = 20 x 25 = 500Hz。同时伴随电机电流中出现 2xGMF (1000Hz) 分量。建议对齿轮箱进行内窥镜检查（参考 5.3 节），若确认断齿，应立即申请停机更换。内窥镜检查周期建议为每 6 个月或在检测到异常振动时。',
'齿轮,点蚀,断齿,GMF,谐波,振动,冲击'),

(1, 3, '5.3', '内窥镜检查流程',
'内窥镜检查前需将齿轮箱冷却至 40℃ 以下，排空部分润滑油至低位。检查顺序：先看齿面（点蚀/剥落/裂纹），再看轴承保持架和滚动体，最后检查箱体内部有无金属磨粒。检查完毕后记录所有异常部位并拍照。若发现任何裂纹迹象，必须立即安排停机检修。',
'内窥镜,检查,齿面,裂纹,磨粒'),

(2, 1, '2.1', '轴承故障特征频率计算',
'特征频率计算公式：BPFO = (Z/2) x (1 - d/D x cosα) x fn；BPFI = (Z/2) x (1 + d/D x cosα) x fn；BSF = (D/(2d)) x (1 - (d/D)^2 x cos^2α) x fn。其中 Z 为滚动体数量，d 为滚动体直径，D 为节圆直径，α 为接触角，fn 为内圈转频。以 230/560 调心滚子轴承为例，BPFO ≈ 0.38 x Z x fn，BPFI ≈ 0.62 x Z x fn。',
'轴承,特征频率,BPFO,BPFI,BSF,计算公式'),

(2, 2, '3.4', '早期故障预警指标',
'建议监测以下指标：1) 边频带能量比（目标值 < 0.10）；2) 包络谱峰值（对比基线上升 3dB 即预警）；3) 振动温度相关系数（轴承温度与振动 RMS 的相关系数若 > 0.7 表明轴承劣化）。当任意一项超过阈值时，应提高监测频率并在 72 小时内安排人工巡检。',
'预警,边频带,包络谱,温度相关,阈值'),

(3, 1, '6.5', '润滑油压力异常处理',
'正常运行油压范围 2.5-4.0 bar（取决于油温）。若油压持续低于 2.0 bar 超过 10 分钟，或油压波动幅度超过 ±0.8 bar，应按以下顺序检查：①滤油器压差（正常 < 0.5 bar，若 > 1.2 bar 说明堵塞）；②油泵密封件（启动油泵听声音判断）；③油路泄漏（检查箱体接缝处）。可在不停机状态下先检查滤油器压差，若滤油器堵塞，可通过旁路阀临时切换，尽快安排更换滤芯。',
'润滑油,油压,滤油器,旁路,油泵,泄漏');

-- 历史维修工单（用于 RAG 相似案例）
INSERT INTO alert (equipment_id, alert_type, severity, title, description, rul_hours, risk_score, status, created_at, agent_diagnosis) VALUES
(3, 'RUL_WARNING', 'HIGH', '低速轴振动持续上升', '过去 7 天 VIB_LS_X 从 1.8 mm/s 升至 2.9 mm/s，趋势明显', 120, 72.50, 'RESOLVED', DATE_SUB(NOW(), INTERVAL 90 DAY), '低速轴轴承外圈早期点蚀，BPFO 边频带能量比 0.18'),
(3, 'ANOMALY', 'MEDIUM', '润滑油温度偏高', 'TEMP_OIL 稳定在 62℃，接近 warning 上限 68℃', 400, 45.00, 'RESOLVED', DATE_SUB(NOW(), INTERVAL 60 DAY), '正常退化趋势，建议缩短换油周期'),
(2, 'SENSOR_FAILURE', 'LOW', 'OIL_PRESS 数据异常跳变', '过去 24 小时出现 3 次负值（-0.2 bar），疑似传感器松动', NULL, 15.00, 'RESOLVED', DATE_SUB(NOW(), INTERVAL 30 DAY), '传感器安装松动');

INSERT INTO work_order (order_no, alert_id, equipment_id, order_type, title, description, diagnosis, actions_taken, spare_parts, status, priority, created_by, approved_by, approved_at, created_at, requires_human_approval, approval_policy) VALUES
('WO-2024-0815-001', 1, 3, 'CORRECTIVE', '低速轴轴承更换', '振动持续上升，需在下次维护窗口更换轴承', '低速轴轴承外圈点蚀（BPFO 谐波能量比 0.18）', '更换 NSK 230/560 轴承 2 套，更换润滑油 120L', '[{"name":"轴承","part_no":"NSK-230/560","qty":2,"unit_price":18000},{"name":"润滑油","part_no":"Mobil-gear-626","qty":120,"unit_price":85}]', 'COMPLETED', 'HIGH', 'AGENT', '李工', DATE_SUB(NOW(), INTERVAL 85 DAY), DATE_SUB(NOW(), INTERVAL 90 DAY), 1, 'LEVEL2'),
('WO-2024-0901-001', NULL, 3, 'PREVENTIVE', '润滑油更换周期调整', '将 WT-GEAR-003 的换油周期从 6 个月缩短为 3 个月', '退化趋势监测中', '下次计划维护时执行', '[{"name":"润滑油","part_no":"Mobil-gear-626","qty":120,"unit_price":85}]', 'COMPLETED', 'MEDIUM', 'AGENT', '张主管', DATE_SUB(NOW(), INTERVAL 55 DAY), DATE_SUB(NOW(), INTERVAL 60 DAY), 1, 'LEVEL1');

INSERT INTO approval_record (work_order_id, action, comment, approver, approver_role, created_at) VALUES
(1, 'APPROVE', '同意更换，备件已到位', '李工', 'TECHNICIAN_LEAD', DATE_SUB(NOW(), INTERVAL 85 DAY)),
(2, 'APPROVE', '同意调整换油周期', '张主管', 'SUPERVISOR', DATE_SUB(NOW(), INTERVAL 55 DAY));
