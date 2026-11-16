# 关键工业设备可预测性维护（PdM）与排障智能体 —— 实现计划

> **文档版本**: v1.0  
> **创建日期**: 2026-11-11  
> **架构约束**: Docker Compose（禁止 Systemd）、MySQL 8.0  
> **项目状态**: 待审批

---

## 一、项目概述

### 1.1 业务背景
工厂关键旋转设备（数控主轴、大型压缩机、风力发电机齿轮箱）的非计划停机损失巨大。本项目构建一套完整的 **预测性维护（Predictive Maintenance）与排障智能体** 系统，覆盖从传感器数据采集 → 异常检测 → 根因分析 → 维护决策 → 人工审批的全链路闭环。

### 1.2 核心目标
| 目标 | 具体指标 |
|------|----------|
| 多通道时序数据流 | 构造温度、振动（三轴+频谱）、电流、油压 4 类传感器，含正常波动、断连噪点、渐进式故障特征 |
| PdM 智能体 | 解决「高频时序数据无法直接塞入 LLM 上下文」的工程难题，实现特征感知 + RAG 根因推演 |
| 业务闭环 | 输出 RUL / 风险等级 → 界面告警 → 工具调用生成检修计划/备件/停机申请 → **人工审批拦截** |
| 可部署性 | 一键 `docker compose up -d` 启动全部服务，无需 systemd |

### 1.3 设备选型
**以风力发电机齿轮箱为目标设备**（具备代表性：典型旋转机械 + 可获得公开退化机制文献 + 故障特征明确）。

---

## 二、系统整体架构

### 2.1 架构图（Docker Compose 微服务）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户浏览器 / API 调用方                              │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │ HTTP (8080)
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌──────────────────┐                                                       │
│  │   Nginx 反向代理  │ ── → 前端静态资源 (3000)                                │
│  │   (gateway)      │ ── → 后端 API (8000)                                    │
│  │                  │ ── → 智能体 API (8100)                                  │
│  └────────┬─────────┘                                                       │
└───────────┼─────────────────────────────────────────────────────────────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
┌──────────┐  ┌──────────────────┐
│ Frontend │  │   Backend API     │
│ (Vue 3)  │  │   (FastAPI 8000)  │
│ 3000     │  │                   │
└──────────┘  └──┬───┬───┬─────────┘
                 │   │   │
        ┌────────┘   │   └────────┐
        ▼            ▼            ▼
┌──────────────┐ ┌───────────┐ ┌──────────────┐
│ PdM Agent    │ │  MySQL 8.0│ │ MinIO 对象存储│
│ (8100)       │ │  (3306)   │ │  (9000)      │
│              │ │           │ │              │
│ ┌──────────┐ │ └───────────┘ └──────────────┘
│ │特征提取器│ │      ▲                  ▲
│ └──────────┘ │      │                  │
│ ┌──────────┐ │ ┌───────────┐ ┌──────────────┐
│ │RAG 检索  │ │ │ Redis     │ │ 手动录入/上传  │
│ └──────────┘ │ │ (6379)    │ │ PDF维修手册    │
│ ┌──────────┐ │ └───────────┘ └──────────────┘
│ │LLM 调用  │ │
│ └──────────┘ │ ┌──────────────────┐
│ ┌──────────┐ │ │  Sensor Simulator │
│ │审批拦截器│ │ │  (数据生产者)     │
│ └──────────┘ │ └──────────────────┘
└──────────────┘
```

### 2.2 服务清单

| 服务名 | 技术栈 | 端口 | 职责 |
|--------|--------|------|------|
| `frontend` | Vue 3 + Element Plus + ECharts | 3000 | 监控大屏、告警面板、审批工作台 |
| `backend` | FastAPI (Python 3.12) | 8000 | REST API、业务逻辑、权限控制 |
| `agent` | FastAPI + LangChain + 自定义推理链 | 8100 | PdM 智能体核心（特征→RCA→RUL→审批） |
| `sensor-sim` | Python + asyncio | - | 数据生产者，模拟传感器数据流 |
| `mysql` | MySQL 8.0 | 3306 | 主数据库（设备/工单/告警/审批） |
| `redis` | Redis 7 | 6379 | 实时时序数据缓存、会话 |
| `minio` | MinIO | 9000 | 维修手册 PDF 存储 |
| `nginx` | Nginx | 8080 | 统一入口、静态资源、负载均衡 |

### 2.3 数据流总览

```
[Sensor Simulator] ──MQTT/内部HTTP──▶ [Redis 时序缓存] ──▶ [MySQL 持久化]
                                            │                    │
                                            ▼                    ▼
                                     [PdM Agent] ◀─── RAG 检索 ◀── [MinIO 手册]
                                     │     │
                                     ▼     ▼
                              [异常检测] [根因推演(RCA)]
                                     │     │
                                     ▼     ▼
                              [RUL/风险等级] ──▶ [告警记录] ──▶ [前端展示]
                                     │
                                     ▼
                              [工具调用：检修/备件/停机]
                                     │
                                     ▼
                              ┌─────────────────────┐
                              │  ⚠️ 人工审批拦截器    │
                              │  等待用户审批/拒绝/编辑 │
                              └─────────┬───────────┘
                                        │ ✅ 批准
                                        ▼
                                  [工单/停机执行]
```

---

## 三、数据库设计（MySQL 8.0）

### 3.1 核心表结构

```sql
-- ========== 设备资产 ==========
CREATE TABLE equipment (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    equipment_code  VARCHAR(64) UNIQUE NOT NULL COMMENT '设备编码如 WT-GEAR-001',
    name            VARCHAR(255) NOT NULL,
    model           VARCHAR(128),
    manufacturer    VARCHAR(128),
    install_date    DATE,
    location        VARCHAR(255),
    equipment_type  ENUM('CNC_SPINDLE','COMPRESSOR','WIND_GEARBOX') NOT NULL,
    health_score    DECIMAL(5,2) DEFAULT 100.00 COMMENT '0-100',
    status          ENUM('RUNNING','STOPPED','MAINTENANCE','CRITICAL'),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (equipment_type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 传感器 ==========
CREATE TABLE sensor (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    equipment_id    BIGINT NOT NULL,
    sensor_code     VARCHAR(64) NOT NULL COMMENT '如 VIB_X_001, TEMP_BEARING_01',
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
    FOREIGN KEY (equipment_id) REFERENCES equipment(id),
    UNIQUE KEY uk_equip_sensor (equipment_id, sensor_code),
    INDEX idx_type (sensor_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 时序数据（每分钟聚合） ==========
CREATE TABLE sensor_data_agg (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    sensor_id       BIGINT NOT NULL,
    ts              DATETIME NOT NULL COMMENT '时间戳 分钟粒度',
    val_min         DECIMAL(10,4),
    val_max         DECIMAL(10,4),
    val_avg         DECIMAL(10,4),
    val_std         DECIMAL(10,4),
    anomaly_flag    TINYINT DEFAULT 0 COMMENT '0正常 1可疑 2异常',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sensor_ts (sensor_id, ts),
    INDEX idx_ts (ts),
    INDEX idx_sensor (sensor_id, ts),
    FOREIGN KEY (sensor_id) REFERENCES sensor(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 告警 ==========
CREATE TABLE alert (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    equipment_id    BIGINT NOT NULL,
    alert_type      ENUM('ANOMALY','RUL_WARNING','CRITICAL','SENSOR_FAILURE','MANUAL') NOT NULL,
    severity        ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    feature_snapshot JSON COMMENT '触发告警的特征值快照',
    rul_hours       INT COMMENT '预估剩余寿命小时数',
    risk_score      DECIMAL(5,2),
    status          ENUM('OPEN','ACKNOWLEDGED','ESCALATED','RESOLVED','IGNORED') DEFAULT 'OPEN',
    agent_diagnosis TEXT COMMENT '智能体给出的诊断',
    agent_ RCA      TEXT COMMENT '根因分析链',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at DATETIME,
    resolved_at     DATETIME,
    created_by      VARCHAR(64),
    FOREIGN KEY (equipment_id) REFERENCES equipment(id),
    INDEX idx_equip_status (equipment_id, status),
    INDEX idx_severity (severity),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 维修工单 ==========
CREATE TABLE work_order (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_no        VARCHAR(64) UNIQUE NOT NULL,
    alert_id        BIGINT,
    equipment_id    BIGINT NOT NULL,
    order_type      ENUM('PREVENTIVE','CORRECTIVE','EMERGENCY','SHUTDOWN_REQUEST') NOT NULL,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    diagnosis       TEXT,
    actions_taken   TEXT,
    spare_parts     JSON COMMENT '备件清单 [{name, qty, part_no}]',
    status          ENUM('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','IN_PROGRESS','COMPLETED','CANCELLED') DEFAULT 'DRAFT',
    priority        ENUM('LOW','MEDIUM','HIGH','CRITICAL'),
    planned_start   DATETIME,
    planned_end     DATETIME,
    actual_start    DATETIME,
    actual_end      DATETIME,
    created_by      VARCHAR(64),
    approved_by     VARCHAR(64),
    approved_at     DATETIME,
    rejected_reason TEXT,
    -- HITL 审批相关
    requires_human_approval TINYINT DEFAULT 1,
    approval_policy VARCHAR(32) COMMENT '审批策略: AUTO/LEVEL1/LEVEL2/ESCALATE',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alert(id),
    FOREIGN KEY (equipment_id) REFERENCES equipment(id),
    INDEX idx_status (status),
    INDEX idx_equip (equipment_id),
    INDEX idx_approval (requires_human_approval, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 审批记录 ==========
CREATE TABLE approval_record (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    work_order_id   BIGINT NOT NULL,
    action          ENUM('APPROVE','REJECT','EDIT','ESCALATE') NOT NULL,
    comment         TEXT,
    edited_payload  JSON COMMENT '编辑后的工单字段',
    approver        VARCHAR(64) NOT NULL,
    approver_role   VARCHAR(32),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (work_order_id) REFERENCES work_order(id),
    INDEX idx_wo (work_order_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 维修手册 ==========
CREATE TABLE maintenance_manual (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    equipment_type  VARCHAR(64) NOT NULL,
    title           VARCHAR(255) NOT NULL,
    vendor          VARCHAR(128),
    version         VARCHAR(32),
    minio_path      VARCHAR(512) COMMENT 'MinIO 对象路径',
    chunk_count     INT COMMENT '切分块数',
    uploaded_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type (equipment_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== LLM 对话历史（用于溯源） ==========
CREATE TABLE agent_conversation (
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
    FOREIGN KEY (alert_id) REFERENCES alert(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3.2 时序数据存储策略
- **实时层**：Redis Hash + TTL 存原始高频数据（最近 24 小时）
- **聚合层**：`sensor_data_agg` 表按分钟聚合（min/max/avg/std），保留 1 年
- **冷数据**：超过 1 年的聚合数据归档到文件（可选）

---

## 四、各服务详细设计

### 4.1 Sensor Simulator（传感器模拟器）

**文件位置**：`services/sensor-sim/`

**核心模块**：
```
sensor-sim/
├── main.py              # asyncio 事件循环入口
├── config.py            # 设备/传感器配置
├── models.py            # 物理退化模型
├── noise.py              # 断连/噪点生成器
├── producer.py           # HTTP 推送 Redis
├── sequences/
│   ├── normal.py         # 正常工况波动
│   ├── degradation.py    # 渐进式故障（轴承点蚀/齿轮磨损）
│   └── fault_events.py   # 突发故障事件
└── seed_data.py          # 数据库初始化脚本
```

**模拟参数（风力发电机齿轮箱示例）**：

| 传感器 | 类型 | 正常范围 | 退化趋势 | 故障特征 |
|--------|------|----------|----------|----------|
| 低速轴振动 X/Y/Z | VIBRATION | 0.5-2.5 mm/s | +0.3 mm/s / 月 | 20Hz 边频带调制 |
| 高速轴振动 | VIBRATION | 0.3-2.0 mm/s | +0.2 mm/s / 月 | 啮合频率 GMF 谐波 |
| 轴承温度 | TEMPERATURE | 45-65℃ | +2℃ / 月 | 温升速率 > 5℃/h |
| 润滑油压力 | OIL_PRESSURE | 2.5-4.0 bar | 缓慢下降 | < 2.0 bar 持续 10min |
| 电机电流 RMS | CURRENT | 25-45A | 波动增大 | 3x 转频分量 |

**数据注入场景**：
1. **正常场景**：纯随机波动 + 日/周周期（风机昼夜温差导致温度周期变化）
2. **退化场景**：渐进式叠加退化信号 + 间歇性异常冲击
3. **故障场景**：突发异常 + 传感器断连噪点（模拟真实工业环境）
4. **测试模式**：REST API 触发特定故障注入（便于演示）

### 4.2 Backend API（FastAPI）

**文件位置**：`services/backend/`

**API 路由规划**：

| 模块 | 端点前缀 | 关键接口 |
|------|----------|----------|
| 设备管理 | `/api/v1/equipment` | CRUD + 健康分数计算 |
| 传感器数据 | `/api/v1/sensors/{id}/data` | 实时流 + 历史查询 |
| 告警管理 | `/api/v1/alerts` | 查询/确认/升级/智能体诊断触发 |
| 工单管理 | `/api/v1/work-orders` | CRUD + 状态流转 |
| 审批 | `/api/v1/approvals` | 待审批列表 + APPROVE/REJECT/EDIT |
| 智能体 | `/api/v1/agent` | 触发诊断 / 对话历史 |
| 手册管理 | `/api/v1/manuals` | 上传 PDF + 切块索引 |

**工单状态机**：
```
DRAFT → PENDING_APPROVAL → APPROVED → IN_PROGRESS → COMPLETED
  │          │                    │
  │          └──→ REJECTED        └──→ CANCELLED
  │
  └──→ (智能体自动创建时跳过 DRAFT，直接 PENDING_APPROVAL)
```

### 4.3 PdM Agent（核心智能体）

**文件位置**：`services/agent/`

这是系统最关键的部分，解决 **「高频时序数据无法直接塞入 LLM 上下文」** 的工程难题。

#### 4.3.1 架构设计

```
┌──────────────────────────────────────────────────────────────┐
│                    PdM Agent Pipeline                        │
│                                                              │
│  [原始时序数据] ──→ [特征提取器] ──→ [特征摘要]              │
│     (Redis)      (独立进程)         (≤ 2000 tokens)          │
│                                         │                    │
│                                         ▼                    │
│  [特征摘要] + [历史告警] + [维修手册片段]                     │
│         │         │              │                           │
│         └─────────┴──────────────┘                           │
│                          │                                   │
│                          ▼                                   │
│                  [RAG 组装 Prompt]                            │
│                          │                                   │
│                          ▼                                   │
│                   [LLM 推理]                                  │
│                          │                                   │
│              ┌───────────┼───────────┐                       │
│              ▼           ▼           ▼                       │
│          [异常检测]  [根因推演RCA]  [RUL/风险评估]           │
│              │           │           │                       │
│              └───────────┼───────────┘                       │
│                          │                                   │
│                          ▼                                   │
│               [行动决策引擎]                                   │
│                          │                                   │
│            ┌─────────────┼─────────────┐                    │
│            ▼             ▼             ▼                    │
│       [检修计划]    [备件申领]    [停机申请]                  │
│            │             │             │                    │
│            └─────────────┼─────────────┘                    │
│                          │                                   │
│                          ▼                                   │
│               ⚠️ [HITL 审批拦截器]                           │
│              (基于策略 + 人工审批)                             │
└──────────────────────────────────────────────────────────────┘
```

#### 4.3.2 解决高频时序数据工程难题

**问题**：风机齿轮箱有 20+ 个传感器，每秒采样 1-100Hz，原始数据远超 LLM 上下文窗口。

**解决方案**：**特征提取器（Feature Extractor）独立进程**

```python
# 输入：某传感器最近 1 小时原始数据（3600-360000 个点）
# 输出：紧凑特征摘要（≤ 2000 tokens）

def extract_features(raw_series):
    features = {
        # 基础统计
        "mean": np.mean(raw_series),
        "std": np.std(raw_series),
        "min": np.min(raw_series),
        "max": np.max(raw_series),
        "range": np.max - np.min,
        
        # 趋势（线性回归斜率）
        "slope_per_hour": linear_regression_slope(raw_series),
        
        # 波动率 / 峰峰值
        "peak_to_peak": peak_to_peak(raw_series),
        "rms": rms(raw_series),
        
        # 频谱特征（振动专用）
        "dominant_freq": fft_dominant(raw_series),
        "harmonic_energy_ratio": harmonic_energy(raw_series),
        "sideband_energy_ratio": sideband_energy(raw_series),
        
        # 突变检测
        "change_points": detect_change_points(raw_series),
        "anomaly_score": isolation_forest_score(raw_series),
        
        # 长期退化对比（与基线的偏离）
        "degradation_index": compare_to_baseline(raw_series),
        
        # 断连检测
        "missing_data_ratio": count_nans(raw_series) / len(raw_series),
        "outlier_ratio": count_outliers(raw_series) / len(raw_series),
    }
    return features
```

**设计原则**：
1. 特征提取在 **LLM 之外** 完成，Python/numpy 高性能计算
2. 每个传感器输出 ≤ 500 tokens 的结构化特征摘要
3. 10 个传感器 × 500 tokens + 手册片段 ≈ 8000 tokens，留足空间给 LLM 推理
4. 关键异常点附上 **原始数据片段（前 5 个 + 后 5 个值）** 供 LLM 交叉验证

#### 4.3.3 RAG 检索设计

```python
# 维修手册切块 → 存入本地向量库 / MinIO 直接读取
def rag_retrieve(equipment_type, current_features, top_k=3):
    query = f"设备类型: {equipment_type} | " \
            f"振动异常: {current_features['vibration']} | " \
            f"温度升高: {current_features['temp_slope']} | " \
            f"油压下降: {current_features['oil_pressure']}"
    
    # 从手册中检索相关章节（Chunk）
    chunks = vector_db.search(query, top_k=top_k)
    
    # 从历史工单中检索相似案例
    similar_cases = work_order_service.find_similar(
        features_hash=hash(current_features),
        equipment_type=equipment_type,
        limit=3
    )
    return {"manual_chunks": chunks, "historical_cases": similar_cases}
```

#### 4.3.4 LLM 推理链提示词设计

**System Prompt（根因推演 RCA）**：
```
你是工业设备故障诊断专家，专注于 {equipment_type} 齿轮箱故障分析。

分析流程：
1. 检查特征摘要中的异常指标
2. 结合维修手册片段匹配故障模式
3. 对比历史工单相似案例
4. 按可能性从高到低列出根因假设
5. 给出 RUL（剩余使用寿命）估算和风险等级

输出格式要求：
{
  "anomaly_detected": true/false,
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "rul_hours": 估算小时数,
  "root_causes": [
    {
      "cause": "具体故障原因",
      "probability": 0.0-1.0,
      "evidence": ["证据1", "证据2"],
      "manual_reference": "手册章节号"
    }
  ],
  "recommended_action": "具体建议",
  "confidence": 0.0-1.0
}
```

#### 4.3.5 HITL 审批拦截机制（核心安全）

**设计原则**：AI 建议 ≠ AI 执行，所有危险操作必须人工确认

```python
# 审批策略引擎
class ApprovalPolicy:
    AUTO_APPROVE_ACTIONS = {"generate_report", "suggest_maintenance_date"}
    LEVEL1_ACTIONS = {"create_work_order_preventive", "order_spare_part_low_value"}
    LEVEL2_ACTIONS = {"create_work_order_emergency", "order_spare_part_high_value"}
    CRITICAL_ACTIONS = {"shutdown_request", "override_safety_limit"}
    
    def evaluate(self, action, context):
        # 1. 动作类型分级
        action_level = self._action_level(action)
        
        # 2. 风险等级叠加
        risk_multiplier = {
            "LOW": 0.5, "MEDIUM": 1.0,
            "HIGH": 1.5, "CRITICAL": 2.0
        }[context.risk_level]
        
        # 3. 审批策略
        if action == "shutdown_request":
            return ApprovalDecision(
                requires_approval=True,
                approver_role="SUPERVISOR",
                escalation="24h_no_response_escalate_to_MANAGER",
                reason="停机操作影响生产，必须人工确认"
            )
        elif context.risk_level == "CRITICAL" and action_level in ("LEVEL2", "CRITICAL"):
            return ApprovalDecision(
                requires_approval=True,
                approver_role="MANAGER",
                reason="CRITICAL 风险下执行高风险动作"
            )
        elif action in self.AUTO_APPROVE_ACTIONS:
            return ApprovalDecision(requires_approval=False)
        
        return ApprovalDecision(
            requires_approval=True,
            approver_role="TECHNICIAN_LEAD",
            reason=f"需要技术主管审批: {action}"
        )
```

**拦截机制流程**：
```
AI Agent 生成工具调用
         │
         ▼
   ApprovalPolicy.evaluate()
         │
    ┌────┴────┐
    ▼         ▼
  自动通过   需要审批
    │         │
    ▼         ▼
  执行工具  创建 PENDING_APPROVAL 工单
             │
             ▼
          前端审批工作台展示
             │
        ┌────┼────┐
        ▼    ▼    ▼
    APPROVE REJECT EDIT
        │    │    │
        ▼    ▼    ▼
     执行  终止  修改后重新审批
```

### 4.4 Frontend（Vue 3 + Element Plus + ECharts）

**文件位置**：`services/frontend/`

**页面规划**：

| 页面 | 路由 | 核心功能 |
|------|------|----------|
| 监控大屏 | `/dashboard` | 设备健康分数矩阵、实时时序曲线、告警滚动 |
| 设备详情 | `/equipment/:id` | 单设备 4 通道传感器曲线、健康退化趋势、RUL 图 |
| 告警中心 | `/alerts` | 告警列表、智能体诊断详情、RCA 链展示 |
| 工单管理 | `/work-orders` | 工单 CRUD、状态流转、执行记录 |
| 审批工作台 | `/approvals` | 待审批列表、APPROVE/REJECT/EDIT、审批历史 |
| 手册管理 | `/manuals` | PDF 上传、切块预览 |
| 智能体对话 | `/agent-chat` | 与智能体交互、对话历史、溯源 |

**关键可视化**：
- ECharts 时序图（多传感器叠加 + 告警标记 + 断连噪点高亮）
- 健康分数雷达图
- RUL 退化曲线（带置信区间）
- RCA 根因链流程图（DAG 可视化）

---

## 五、Docker Compose 部署方案

### 5.1 文件结构

```
d:\A3\
├── docker-compose.yml              # 主 Compose 文件
├── .env                            # 环境变量模板
├── README_DEPLOY.md                # 部署说明（人工操作指南）
│
├── services/
│   ├── frontend/
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   └── src/
│   │
│   ├── backend/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── database.py
│   │       ├── models.py
│   │       ├── schemas.py
│   │       ├── routers/
│   │       └── services/
│   │
│   ├── agent/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── pipeline/
│   │       │   ├── feature_extractor.py
│   │       │   ├── anomaly_detector.py
│   │       │   ├── rca_engine.py
│   │       │   ├── rul_predictor.py
│   │       │   └── approval_gate.py
│   │       ├── prompts/
│   │       │   ├── system_prompts.py
│   │       │   ├── rca_prompt.txt
│   │       │   └── approval_prompt.txt
│   │       └── rag/
│   │           ├── retriever.py
│   │           └── manual_chunker.py
│   │
│   ├── sensor-sim/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── producer.py
│   │       ├── models/
│   │       ├── noise.py
│   │       └── sequences/
│   │
│   └── nginx/
│       └── nginx.conf
│
├── scripts/
│   ├── init-db.sql                 # MySQL 初始化 DDL + 种子数据
│   ├── seed-manuals.py             # 维修手册片段种子数据
│   ├── seed-equipment.py           # 设备/传感器种子数据
│   └── test-fault-injection.py     # 故障注入 API 测试脚本
│
└── data/                           # 持久化数据目录（Docker volume 映射）
    ├── mysql/
    ├── minio/
    └── redis/
```

### 5.2 docker-compose.yml 骨架

```yaml
version: "3.8"

services:
  # ====== 基础设施 ======
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports:
      - "3306:3306"
    volumes:
      - ./data/mysql:/var/lib/mysql
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/01-init.sql
    command: >
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_unicode_ci
      --innodb-buffer-pool-size=512M
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 3
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: ${MINIO_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - ./data/minio:/data
    command: server /data --console-address ":9001"
    restart: unless-stopped

  # ====== 应用服务 ======
  backend:
    build: ./services/backend
    environment:
      - DATABASE_URL=mysql+pymysql://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/${MYSQL_DATABASE}
      - REDIS_URL=redis://redis:6379/0
      - MINIO_URL=http://minio:9000
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=${LLM_MODEL}
    ports:
      - "8000:8000"
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_started
    restart: unless-stopped

  agent:
    build: ./services/agent
    environment:
      - DATABASE_URL=mysql+pymysql://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/${MYSQL_DATABASE}
      - REDIS_URL=redis://redis:6379/0
      - MINIO_URL=http://minio:9000
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=${LLM_MODEL}
      - FEATURE_EXTRACT_INTERVAL=60
      - AGENT_AUTO_ANALYZE=true
    ports:
      - "8100:8100"
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  sensor-sim:
    build: ./services/sensor-sim
    environment:
      - REDIS_URL=redis://redis:6379/0
      - BACKEND_URL=http://backend:8000
      - SIM_MODE=realistic      # normal / degradation / fault / test
      - SIM_SPEED=1.0           # 模拟速度倍率
    depends_on:
      redis:
        condition: service_healthy
      backend:
        condition: service_started
    restart: unless-stopped

  frontend:
    build: ./services/frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./services/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      # 也可以将前端静态文件复制到 nginx
    depends_on:
      - frontend
      - backend
      - agent
    restart: unless-stopped
```

---

## 六、预埋数据脚本设计

### 6.1 维修手册片段种子数据

将创建 `scripts/seed-manuals.py`，生成风力发电机齿轮箱维修手册的模拟 PDF + 结构化片段：

```python
# 预埋的手册章节（用于 RAG 检索）
MANUAL_CHUNKS = [
    # 章节 3.2 轴承故障
    {
        "chapter": "3.2",
        "title": "轴承退化与更换指南",
        "content": """
        当轴承外圈振动频谱中出现特征频率 BPFO（约 3.5×转频）的谐波分量，
        且边频带能量比超过 0.15 时，判定为早期点蚀。
        此时建议将齿轮箱润滑油更换周期缩短 50%，并增加振动监测频率。
        若振动 RMS 值超过 4.5 mm/s，应计划在下一个维护窗口更换轴承。
        轴承更换操作步骤见附录 A.12。
        """,
        "equipment_type": "WIND_GEARBOX"
    },
    # 章节 4.1 齿轮磨损
    {
        "chapter": "4.1",
        "title": "齿轮啮合异常诊断",
        "content": """
        齿轮点蚀、剥落和断齿会产生冲击调制响应。
        啮合频率 GMF 的 2 次谐波能量比超过 0.3 时，
        说明轮齿已发生明显磨损。
        同时伴随电机电流中出现 2×GMF 分量。
        建议对齿轮箱进行内窥镜检查（参考 5.3 节），
        若确认断齿，应立即申请停机更换。
        """,
        "equipment_type": "WIND_GEARBOX"
    },
    # 章节 6.5 润滑油系统
    {
        "chapter": "6.5",
        "title": "润滑油压力异常处理",
        "content": """
        正常运行油压范围 2.5-4.0 bar。
        若油压持续低于 2.0 bar 超过 10 分钟，
        或油压波动幅度超过 ±0.8 bar，
        应检查：①滤油器是否堵塞 ②油泵密封件磨损 ③油路泄漏。
        可在不停机状态下先检查滤油器压差，
        若滤油器堵塞，可通过旁路阀临时切换，尽快安排更换。
        """,
        "equipment_type": "WIND_GEARBOX"
    },
]
```

### 6.2 历史工单种子数据

```python
# 预埋的历史维修工单（用于 RAG 相似案例检索）
HISTORICAL_WORK_ORDERS = [
    {
        "equipment": "WT-GEAR-003",
        "date": "2024-08-15",
        "diagnosis": "低速轴轴承外圈点蚀",
        "findings": "振动 BPFO 谐波能量比 0.18，温度从 52℃ 升至 61℃",
        "action": "更换 NSK 230/560 轴承 2 套",
        "result": "振动下降 60%，温度恢复正常",
        "duration_hours": 4.5,
        "spare_parts_value": 38000
    },
    {
        "equipment": "WT-GEAR-007",
        "date": "2024-11-02",
        "diagnosis": "润滑油滤油器堵塞",
        "findings": "油压从 3.2 bar 降至 1.8 bar，温差不明显",
        "action": "旁路切换后更换滤油器滤芯",
        "result": "油压恢复到 3.1 bar，未造成停机",
        "duration_hours": 0.5,
        "spare_parts_value": 2500
    },
]
```

---

## 七、部署步骤（人工执行）

### 7.1 前置条件

| 组件 | 最低版本 | 说明 |
|------|----------|------|
| Docker | 24.0+ | 需开启 BuildKit |
| Docker Compose | v2.20+ | Plugin 模式 |
| 操作系统 | Ubuntu 22.04 LTS / Debian 12 | 推荐 Linux |
| CPU | 4 核+ | 智能体推理需要 |
| 内存 | 8 GB+ | MySQL + Redis + LLM 客户端 |
| 磁盘 | 50 GB+ | 数据持久化 |

### 7.2 部署流程

```bash
# ===== Step 1: 克隆/上传项目 =====
cd /opt
# (上传整个 A3 目录到服务器)

# ===== Step 2: 配置环境变量 =====
cd /opt/A3
cp .env.example .env
nano .env    # 编辑密码和 LLM API Key

# ===== Step 3: 创建持久化目录 =====
mkdir -p data/mysql data/minio data/redis
chmod -R 777 data/

# ===== Step 4: 启动基础设施（MySQL/Redis/MinIO） =====
docker compose up -d mysql redis minio
sleep 30    # 等待 MySQL 初始化

# ===== Step 5: 验证 MySQL 初始化 =====
docker compose logs mysql | grep -i "ready for connections"

# ===== Step 6: 启动应用服务 =====
docker compose up -d --build

# ===== Step 7: 检查所有服务状态 =====
docker compose ps
# 预期：所有服务状态为 UP

# ===== Step 8: 执行预埋数据脚本 =====
docker compose exec backend python -m scripts.seed-equipment
docker compose exec backend python -m scripts.seed-manuals

# ===== Step 9: 访问系统 =====
# 前端: http://<服务器IP>:8080
# 后端 API 文档: http://<服务器IP>:8000/docs
# MinIO 控制台: http://<服务器IP>:9001

# ===== Step 10: 故障注入测试 =====
# 通过前端或 API 触发测试模式
curl -X POST http://localhost:8100/api/v1/test/inject-fault \
     -H "Content-Type: application/json" \
     -d '{"equipment_id": 1, "fault_type": "bearing_pitting"}'
```

### 7.3 运维命令速查

```bash
# 查看日志
docker compose logs -f backend
docker compose logs -f agent
docker compose logs -f sensor-sim

# 重启单个服务
docker compose restart agent

# 清理并重建
docker compose down -v
docker compose up -d --build

# 数据库备份
docker compose exec mysql mysqldump -u root -p pdm_system > backup_$(date +%Y%m%d).sql
```

---

## 八、实施任务清单（依赖顺序）

### Phase 1：基础设施
1. ✅ `docker-compose.yml` 编写
2. ✅ MySQL 初始化脚本 + DDL
3. ✅ Redis / MinIO 配置
4. ✅ `.env.example` 环境变量模板

### Phase 2：Sensor Simulator
5. 设备/传感器配置模型
6. 正常工况数据生成器
7. 退化/故障特征模型
8. 断连噪点注入器
9. Redis 数据推送 Producer
10. REST API 测试接口（触发故障注入）

### Phase 3：Backend API
11. FastAPI 项目骨架 + 连接池配置
12. SQLAlchemy ORM 模型映射
13. 设备/传感器 CRUD 路由
14. 告警管理路由
15. 工单管理路由 + 状态机
16. 审批路由（APPROVE/REJECT/EDIT）
17. 维修手册上传接口

### Phase 4：PdM Agent
18. 特征提取器（feature_extractor.py）
19. 异常检测器（Isolation Forest + 统计阈值）
20. RAG 检索模块 + 手册切块器
21. LLM 客户端封装（支持多模型切换）
22. RCA 根因推演链
23. RUL 剩余寿命预估
24. 审批拦截器 + ApprovalPolicy
25. Prompt 模板工程化
26. 对话历史持久化 + 溯源

### Phase 5：Frontend
27. Vue 3 项目骨架 + Element Plus 主题
28. 监控大屏 Dashboard
29. 设备详情页（多通道时序曲线）
30. 告警中心（RCA 链可视化）
31. 工单管理页
32. 审批工作台（核心交互）
33. 手册管理页
34. 智能体对话页

### Phase 6：整合 & 部署
35. Nginx 反向代理配置
36. 所有 Dockerfile 编写
37. 种子数据脚本（equipment + manuals + work-orders）
38. 端到端联调测试
39. README_DEPLOY.md 部署文档

---

## 九、风险与处理

| 风险 | 概率 | 影响 | 处理方案 |
|------|------|------|----------|
| LLM 推理速度慢（实时性不够） | 中 | 高 | 1) 特征预计算缓存 2) 分级触发（LOW 告警不立即推理） 3) 流式输出 |
| 特征提取器漏掉关键异常 | 低 | 高 | 保留原始数据片段供 LLM 交叉验证；设置保底阈值直接告警 |
| 审批拦截被绕过 | 低 | 极高 | 后端双重检查（Agent 和 Backend 都验证审批状态）；关键操作硬编码审批逻辑 |
| Docker 资源不足（LLM 客户端吃内存） | 中 | 中 | 限制 LLM 客户端并发数；可选纯 CPU 推理路径；预留 swap |
| 维修手册 PDF 非结构化 | 中 | 中 | 先使用预埋结构化片段；后续接入 LangChain PDF Loader |
| MySQL 8.0 字符集问题 | 低 | 低 | init.sql 里显式设置 utf8mb4 + collation |

---

## 十、验收标准

- [ ] `docker compose up -d` 一键启动全部 8 个服务，无 Systemd 依赖
- [ ] Sensor Simulator 成功向 Redis 推送 4 通道传感器数据
- [ ] Backend API `/docs` 可访问，CRUD 正常
- [ ] PdM Agent 成功完成「特征提取 → RAG 检索 → LLM RCA → 工单生成」全链路
- [ ] 前端审批工作台可执行 APPROVE/REJECT/EDIT 操作，阻断未审批的停机请求
- [ ] 预埋故障注入脚本触发后，告警中心可看到异常告警和 RCA 诊断
- [ ] RUL 预估输出合理数值（结合历史退化数据）

---

*—— 计划结束，待审批后执行 ——*
