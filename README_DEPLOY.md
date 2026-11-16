# PdM Agent 部署指南

> **关键工业设备可预测性维护（PdM）与排障智能体**  
> 架构：Docker Compose 微服务（零 Systemd 依赖）  
> 数据库：MySQL 8.0  
> LLM：支持 DeepSeek / OpenAI / 任何 OpenAI 兼容 API

---

## 一、前置条件

| 组件 | 最低版本 | 说明 |
|------|----------|------|
| Docker Engine | 24.0+ | 需开启 BuildKit (`DOCKER_BUILDKIT=1`) |
| Docker Compose | v2.20+ | Plugin 模式（`docker compose` 不带横杠） |
| 操作系统 | Ubuntu 22.04 LTS / Debian 12 / CentOS 8+ | 推荐 Linux |
| CPU | 4 核+ | 智能体推理需要 |
| 内存 | 8 GB+ | MySQL + Redis + LLM 客户端 |
| 磁盘 | 50 GB+ | 数据持久化空间 |

### Docker 快速安装（Ubuntu 22.04）

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 验证
docker --version
docker compose version
```

---

## 二、部署流程

### Step 1：上传项目

```bash
# 在你的开发机上打包
cd d:\A3
# 在 Git Bash 或 Linux 上：tar -czf pdm-agent.tar.gz A3/

# 上传到服务器（假设服务器 IP 为 192.168.1.100）
scp pdm-agent.tar.gz user@192.168.1.100:/opt/

# 在服务器上解压
ssh user@192.168.1.100
cd /opt
tar -xzf pdm-agent.tar.gz
mv A3 pdm-agent
cd pdm-agent
```

### Step 2：配置环境变量

```bash
cp .env.example .env
nano .env
```

**必填项：**

```ini
# ===== MySQL 密码（请修改）=====
MYSQL_ROOT_PASSWORD=change_this_to_a_strong_password
MYSQL_PASSWORD=change_this_to_a_strong_password

# ===== LLM API Key =====
# DeepSeek（推荐）：https://platform.deepseek.com/
# 如果留空，Agent 将进入「模拟模式」（返回规则引擎分析结果，不调 LLM）
LLM_API_KEY=sk-your-llm-api-key-here

# 如果用其他模型（OpenAI / 本地 vLLM / Ollama 等）
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-mini
```

### Step 3：创建持久化目录

```bash
mkdir -p data/mysql data/minio data/redis
chmod -R 777 data/
```

### Step 4：启动基础设施

```bash
# 先起数据层（MySQL 初始化需要时间）
docker compose up -d mysql redis minio

# 等待 MySQL 就绪（首次启动约 30-60 秒）
echo "等待 MySQL 初始化..."
while ! docker compose exec -T mysql mysqladmin ping -h localhost -u root -p${MYSQL_ROOT_PASSWORD:-pdm_root_2026} --silent 2>/dev/null; do
  sleep 3
  echo -n "."
done
echo ""
echo "✅ MySQL 就绪"
```

### Step 5：启动全部应用

```bash
docker compose up -d --build
```

首次构建需要 5-15 分钟（编译 Python 依赖 + npm install）。

### Step 6：验证部署

```bash
# 所有服务应该都是 Up 状态
docker compose ps

# 预期输出：
# NAME              STATUS
# pdm_mysql         Up (healthy)
# pdm_redis         Up (healthy)
# pdm_minio         Up
# pdm_backend       Up
# pdm_agent         Up
# pdm_sensor_sim    Up
# pdm_frontend      Up
# pdm_nginx         Up
```

### Step 7：访问系统

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端界面** | `http://<服务器IP>:8080` | 主入口（监控大屏、审批工作台等） |
| **后端 API 文档** | `http://<服务器IP>:8000/docs` | FastAPI Swagger |
| **智能体 API 文档** | `http://<服务器IP>:8100/docs` | Agent FastAPI |
| **MinIO 控制台** | `http://<服务器IP>:9001` | 对象存储管理（默认账号 minioadmin） |

---

## 三、系统架构一览

```
用户浏览器
    │
    ▼
:8080 Nginx ──┬──▶ :3000 Frontend (Vue3)
              ├──▶ :8000 Backend API (FastAPI)
              └──▶ :8100 Agent (FastAPI + LLM)
                        │
                        ▼
                   ╔═══════════════════╗
                   ║   PdM Agent 核心   ║
                   ║ ┌─────────────────┐║
                   ║ │ 特征提取器(独立) │║ ← 解决高频时序数据无法塞入 LLM 的工程难题
                   ║ └────────┬────────┘║
                   ║          ▼          ║
                   ║ ┌─────────────────┐║
                   ║ │ RAG 手册检索    │║ ← 从 MinIO + MySQL 取维修手册
                   ║ └────────┬────────┘║
                   ║          ▼          ║
                   ║ ┌─────────────────┐║
                   ║ │ LLM 推理(RCA)   │║ ← 输出 JSON 格式根因分析
                   ║ └────────┬────────┘║
                   ║          ▼          ║
                   ║ ┌─────────────────┐║
                   ║ │ ⚠️ HITL 审批拦截 │║ ← 所有工单必须人工审批
                   ║ └─────────────────┘║
                   ╚═══════════════════╝
                        │
                        ▼
                   MySQL 8.0 + Redis 7
                   MinIO (维修手册 PDF)
```

---

## 四、预埋数据说明

系统初始化时会自动创建以下种子数据（在 `scripts/init-db.sql` 中）：

### 4.1 设备（4 台风力发电机齿轮箱）

| 编码 | 状态 | 健康分 | 说明 |
|------|------|--------|------|
| WT-GEAR-001 | RUNNING | 95 | 健康，作为正常基线 |
| WT-GEAR-002 | RUNNING | 78.5 | 有轻微退化 |
| WT-GEAR-003 | RUNNING | 62.3 | **较旧设备，默认退化模拟目标** |
| WT-GEAR-004 | RUNNING | 98 | 新安装 |

### 4.2 每台设备配置 8 个传感器

- 低速轴振动 X/Y/Z
- 高速轴振动 X
- 轴承温度
- 润滑油温度
- 润滑油压力
- 电机电流

### 4.3 维修手册（6 个章节）

- 3.2 轴承退化与更换指南
- 4.1 齿轮啮合异常诊断
- 5.3 内窥镜检查流程
- 2.1 轴承特征频率计算
- 3.4 早期故障预警指标
- 6.5 润滑油压力异常处理

### 4.4 历史工单（2 条）

- 2024-08-15 WT-GEAR-003 轴承更换（已完成）
- 2024-09-01 WT-GEAR-003 润滑油更换周期调整（已完成）

### 4.5 历史告警（3 条，已解决）

---

## 五、模拟模式与故障注入

### 5.1 传感器模拟模式

修改 `.env` 中的 `SIM_MODE`：

| 模式 | 说明 |
|------|------|
| `normal` | 纯正常工况，无退化 |
| `degradation`（默认） | WT-GEAR-003 有渐进式退化（适合演示） |
| `fault` | 加速退化 + 故障特征注入 |

修改后重启 Sensor Simulator：
```bash
docker compose restart sensor-sim
```

### 5.2 故障注入 API

```bash
# 通过 API 触发完整分析
curl -X POST http://localhost:8100/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"equipment_code": "WT-GEAR-003", "force_llm": true}'
```

### 5.3 前端演示流程

1. 打开 `http://<服务器IP>:8080`
2. 点击 Dashboard → 找到「手动触发智能体分析」区域
3. 选择 WT-GEAR-003 → 点击「触发完整分析」
4. 等待 30-120 秒（LLM 推理）
5. 切换到「告警中心」→ 看到新生成的告警
6. 点击告警详情 → 查看 Agent 诊断 + RCA 根因链
7. 如果 Agent 生成了工单 → 「审批工作台」会显示待审批
8. 审批通过 → 工单进入「工单管理」可执行状态

---

## 六、运维命令速查

```bash
# ===== 日志 =====
docker compose logs -f backend          # 后端日志
docker compose logs -f agent           # 智能体日志（最重要）
docker compose logs -f sensor-sim      # 模拟器数据输出
docker compose logs -f mysql            # 数据库日志

# ===== 重启 =====
docker compose restart agent            # 重启单个服务
docker compose restart sensor-sim      # 重启模拟器（改 SIM_MODE 后）

# ===== 重建 =====
docker compose up -d --build agent     # 只重建 Agent（改代码后）

# ===== 数据库 =====
docker compose exec -it mysql mysql -u root -p pdm_system

# 备份
docker compose exec mysql mysqldump -u root -p pdm_system > backup_$(date +%Y%m%d_%H%M%S).sql

# ===== 清理 =====
docker compose down                    # 停止容器（保留数据卷）
docker compose down -v                 # 停止并删除所有数据（慎用！）
docker system prune -a                 # 清理无用镜像（回收磁盘）

# ===== 健康检查 =====
curl http://localhost:8000/health      # Backend
curl http://localhost:8100/health      # Agent
curl http://localhost:8080/backend-health  # Nginx 代理
```

---

## 七、常见问题

### Q1: Agent 返回「模拟 LLM 响应」
**A**: `.env` 中的 `LLM_API_KEY` 未设置或为空。填入你的 API Key 后重启：
```bash
docker compose restart agent backend
```

### Q2: Sensor Simulator 日志全是 NaN
**A**: MySQL 初始化可能还没完成。等 MySQL healthcheck 通过后再启动 Simulator：
```bash
docker compose restart sensor-sim
```

### Q3: 前端页面空白
**A**: 检查 Nginx 日志：`docker compose logs nginx`。通常是前端构建出错：
```bash
docker compose up -d --build frontend
```

### Q4: MySQL 启动失败（utf8mb4 错误）
**A**: init-db.sql 在 MySQL 8.0 下应该没问题。检查 MySQL 版本：
```bash
docker compose exec mysql mysql -V
```

### Q5: 停机申请审批被拒绝
**A**: 这是正常行为。停机申请必须由 SUPERVISOR 或 MANAGER 角色审批。在审批对话框中选择正确的 approver_role。

### Q6: LLM 推理很慢
**A**: 正常——特征提取 + RAG + LLM 完整链路约 30-120 秒。可以：
- 在 `.env` 中换更快的模型（如 `gpt-4o-mini`）
- 只对 HIGH/CRITICAL 告警触发 LLM（修改 Agent `AGENT_AUTO_ANALYZE=false`）

### Q7: 想清理演示数据重新开始
```bash
docker compose down -v
docker compose up -d mysql redis minio
# 等 MySQL 初始化
docker compose up -d --build
```

---

## 八、项目结构

```
pdm-agent/
├── docker-compose.yml              # 主 Compose 文件（8 服务编排）
├── .env.example                    # 环境变量模板
├── README_DEPLOY.md                # 本文档
│
├── services/
│   ├── backend/                    # FastAPI REST API
│   │   ├── app/
│   │   │   ├── main.py             # 入口（含 Dashboard stats）
│   │   │   ├── models.py           # SQLAlchemy ORM
│   │   │   ├── schemas.py          # Pydantic 请求/响应
│   │   │   ├── config.py           # 配置
│   │   │   ├── database.py         # 数据库连接
│   │   │   ├── routers/            # 7 个路由模块
│   │   │   └── services/           # Redis 客户端
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── agent/                      # PdM Agent 核心
│   │   ├── app/
│   │   │   ├── main.py             # Agent FastAPI 入口（完整分析流水线）
│   │   │   ├── llm_client.py       # OpenAI 兼容 API 封装
│   │   │   ├── models.py           # ORM 模型
│   │   │   ├── config.py
│   │   │   ├── pipeline/           # ⭐ 核心推理链
│   │   │   │   ├── feature_extractor.py   # 特征提取器（解决 LLM 时序数据问题）
│   │   │   │   ├── anomaly_detector.py    # 异常检测（多策略）
│   │   │   │   ├── rca_engine.py          # 根因分析规则引擎
│   │   │   │   ├── rul_predictor.py       # RUL 剩余寿命预估
│   │   │   │   └── approval_gate.py       # ⚠️ HITL 审批拦截器
│   │   │   ├── rag/                # RAG 模块
│   │   │   │   └── retriever.py    # 手册 + 历史案例检索
│   │   │   └── prompts/            # Prompt 模板
│   │   │       └── templates.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── sensor-sim/                 # 传感器模拟器
│   │   ├── src/
│   │   │   ├── main.py             # asyncio 事件循环入口
│   │   │   ├── config.py           # 设备/传感器配置
│   │   │   ├── producer.py         # Redis 推送 Producer
│   │   │   ├── sequences/          # 正常/退化序列生成
│   │   │   └── noise.py            # 断连/噪点注入
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── frontend/                   # Vue 3 + Element Plus
│   │   ├── src/
│   │   │   ├── App.vue             # 主框架（侧边栏 + Header）
│   │   │   ├── router.js           # 路由
│   │   │   ├── api/client.js       # Axios 客户端
│   │   │   └── views/              # 7 个页面
│   │   │       ├── Dashboard.vue          # 监控大屏
│   │   │       ├── Equipment.vue          # 设备列表
│   │   │       ├── EquipmentDetail.vue    # 设备详情 + ECharts 曲线
│   │   │       ├── Alerts.vue             # 告警中心 + 智能体详情
│   │   │       ├── WorkOrders.vue         # 工单管理
│   │   │       ├── Approvals.vue          # ⭐ 审批工作台核心
│   │   │       ├── Manuals.vue            # 维修手册浏览器
│   │   │       └── AgentChat.vue          # 智能体对话
│   │   ├── Dockerfile（多阶段构建）
│   │   ├── nginx.conf
│   │   ├── vite.config.js
│   │   └── package.json
│   │
│   └── nginx/
│       └── nginx.conf              # 统一入口反向代理
│
├── scripts/
│   └── init-db.sql                 # MySQL DDL + 种子数据（4 设备 + 64 传感器 + 6 手册章节 + 历史工单）
│
└── data/                           # Docker volume 持久化目录
    ├── mysql/
    ├── minio/
    └── redis/
```

---

## 九、验收检查清单

部署完成后，请逐项验证：

- [ ] `docker compose ps` 显示全部 8 个容器为 Up 状态
- [ ] `http://<IP>:8080` 前端可访问
- [ ] Dashboard 能看到 4 台设备的健康分数
- [ ] Sensor Simulator 日志持续输出传感器读数
- [ ] Redis 中有实时数据（`docker compose exec redis redis-cli keys 'latest:*'`）
- [ ] Backend `/docs` 可访问
- [ ] Agent `/health` 返回正常状态
- [ ] Dashboard 触发分析 → Agent 返回完整结果（含 RUL、RCA、工单建议）
- [ ] 告警中心出现新告警
- [ ] 审批工作台显示 Agent 创建的 PENDING_APPROVAL 工单
- [ ] 审批对话框拒绝时需要填写理由
- [ ] 停机申请批准时弹出 SUPERVISOR 角色检查

---

*部署成功后，系统即进入运行状态。传感器模拟器持续注入数据，PdM Agent 待命，所有 AI 生成的工单都被 HITL 拦截器保护。*
