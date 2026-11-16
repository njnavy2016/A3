# HITL 审批拦截器 —— 核心安全机制
from dataclasses import dataclass
from typing import Optional


@dataclass
class ApprovalDecision:
    requires_approval: bool
    approver_role: str = "TECHNICIAN_LEAD"
    reason: str = ""
    policy_tag: str = "LEVEL1"
    can_be_auto_approved: bool = False


class ApprovalGate:
    """
    审批策略引擎。
    设计原则：
    1. AI 建议 ≠ AI 执行
    2. 不同动作对应不同审批等级
    3. 风险等级叠加提升审批要求
    4. 停机 / 紧急操作强制高等级审批
    """
    
    # 动作分级定义
    ACTION_LEVELS = {
        # 自动放行（只读、建议型）
        "generate_report": "AUTO",
        "suggest_maintenance_date": "AUTO",
        "estimate_rul": "AUTO",
        # 常规维护
        "create_work_order_preventive": "LEVEL1",
        "order_spare_part_low_value": "LEVEL1",
        # 中高风险维护
        "create_work_order_corrective": "LEVEL2",
        "order_spare_part_high_value": "LEVEL2",
        # 紧急 / 停机
        "create_work_order_emergency": "CRITICAL",
        "create_work_order_shutdown": "CRITICAL",
        "override_safety_limit": "CRITICAL",
    }
    
    # 角色层级
    ROLE_HIERARCHY = {
        "TECHNICIAN": 1,
        "TECHNICIAN_LEAD": 2,
        "SUPERVISOR": 3,
        "MANAGER": 4,
        "DIRECTOR": 5,
    }
    
    def evaluate(
        self,
        action: str,
        context: dict,
    ) -> ApprovalDecision:
        """
        评估一次工具调用是否需要审批。
        
        参数:
            action: 动作名称（如 create_work_order_shutdown）
            context: 上下文 {
                "risk_level": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL",
                "equipment_type": str,
                "value": float（备件金额）,
                "severity": str,
            }
        """
        risk_level = context.get("risk_level", "MEDIUM")
        value = context.get("value", 0)
        
        # 1. 确定动作基础等级
        action_level = self.ACTION_LEVELS.get(action, "LEVEL1")
        
        # 2. 风险叠加
        risk_multiplier = {
            "LOW": 1.0,
            "MEDIUM": 1.2,
            "HIGH": 1.5,
            "CRITICAL": 2.0,
        }.get(risk_level, 1.0)
        
        # 3. 核心规则
        # === 强制拦截场景 ===
        
        # 场景 A: 停机申请 → 必须 SUPERVISOR+
        if "shutdown" in action.lower() or "SHUTDOWN" in action.upper():
            return ApprovalDecision(
                requires_approval=True,
                approver_role="SUPERVISOR",
                reason="⚠️ 停机操作影响生产，必须由 SUPERVISOR 或 MANAGER 级别人工审批",
                policy_tag="CRITICAL_SHUTDOWN",
            )
        
        # 场景 B: CRITICAL 风险 + CRITICAL 动作
        if risk_level == "CRITICAL" and action_level in ("CRITICAL",):
            return ApprovalDecision(
                requires_approval=True,
                approver_role="MANAGER",
                reason="⚠️ CRITICAL 风险下执行紧急动作，升级至 MANAGER 审批",
                policy_tag="CRITICAL_ESCALATE",
            )
        
        # 场景 C: 紧急工单 + HIGH 以上风险
        if "emergency" in action.lower() and risk_level in ("HIGH", "CRITICAL"):
            return ApprovalDecision(
                requires_approval=True,
                approver_role="SUPERVISOR",
                reason="紧急工单 + 高风险，需 SUPERVISOR 即时审批",
                policy_tag="HIGH_EMERGENCY",
            )
        
        # 场景 D: 高金额备件
        if action.startswith("order_spare_part") and value > 50000:
            return ApprovalDecision(
                requires_approval=True,
                approver_role="MANAGER",
                reason=f"备件金额 ¥{value:,.0f} 超过 5 万阈值，需 MANAGER 审批",
                policy_tag="HIGH_VALUE",
            )
        
        # 4. 常规规则
        if action_level == "AUTO":
            return ApprovalDecision(
                requires_approval=False,
                reason="只读/建议型操作，自动放行",
                policy_tag="AUTO",
                can_be_auto_approved=True,
            )
        
        if action_level == "LEVEL1":
            return ApprovalDecision(
                requires_approval=True,
                approver_role="TECHNICIAN_LEAD",
                reason="常规维护工单，需 TECHNICIAN_LEAD 审批",
                policy_tag="LEVEL1",
            )
        
        if action_level == "LEVEL2":
            return ApprovalDecision(
                requires_approval=True,
                approver_role="TECHNICIAN_LEAD" if risk_level in ("LOW", "MEDIUM") else "SUPERVISOR",
                reason=" corrective 工单，需 TECHNICIAN_LEAD 或以上审批",
                policy_tag="LEVEL2",
            )
        
        if action_level == "CRITICAL":
            return ApprovalDecision(
                requires_approval=True,
                approver_role="SUPERVISOR",
                reason="紧急操作，需 SUPERVISOR 审批",
                policy_tag="CRITICAL",
            )
        
        # 兜底
        return ApprovalDecision(
            requires_approval=True,
            approver_role="TECHNICIAN_LEAD",
            reason="默认需要 TECHNICIAN_LEAD 审批",
            policy_tag="DEFAULT",
        )
    
    def check_bypass_attempt(
        self,
        work_order_status: str,
        required_policy: str,
        caller_role: str,
    ) -> tuple:
        """
        后端二次校验：防止绕过审批。
        返回 (是否允许, 原因)
        """
        # 必须是 PENDING_APPROVAL 状态才能审批
        if work_order_status != "PENDING_APPROVAL":
            return False, f"工单状态 {work_order_status} 不允许审批操作"
        
        # 检查角色权限
        required_role = {
            "AUTO": "TECHNICIAN",
            "LEVEL1": "TECHNICIAN_LEAD",
            "LEVEL2": "TECHNICIAN_LEAD",
            "CRITICAL": "SUPERVISOR",
            "CRITICAL_SHUTDOWN": "SUPERVISOR",
            "CRITICAL_ESCALATE": "MANAGER",
            "HIGH_EMERGENCY": "SUPERVISOR",
        }.get(required_policy, "TECHNICIAN_LEAD")
        
        caller_level = self.ROLE_HIERARCHY.get(caller_role, 0)
        required_level = self.ROLE_HIERARCHY.get(required_role, 2)
        
        if caller_level < required_level:
            return False, f"审批角色 {caller_role} 权限不足，需要 {required_role}"
        
        return True, "OK"
