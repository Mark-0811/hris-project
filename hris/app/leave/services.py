from datetime import datetime
from decimal import Decimal

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..extensions import db
from ..models import (
    ApprovalDecision,
    ApprovalInstance,
    ApprovalWorkflowDefinition,
    ApprovalWorkflowStep,
    Employee,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    Notification,
    Role,
    User,
)
from ..utils.constants import ROLE_EMPLOYEE, ROLE_HR_ADMIN, ROLE_MANAGER, ROLE_SUPER_ADMIN


def compute_remaining_credits(total_credits: float, used_credits: float) -> float:
    return max(total_credits - used_credits, 0)


def _table_exists(table_name: str) -> bool:
    try:
        return inspect(db.engine).has_table(table_name)
    except Exception:
        return False


def _workflow_engine_ready() -> bool:
    return all(
        _table_exists(name)
        for name in (
            ApprovalWorkflowDefinition.__tablename__,
            ApprovalWorkflowStep.__tablename__,
            ApprovalInstance.__tablename__,
            ApprovalDecision.__tablename__,
        )
    )


def _default_leave_workflow_steps() -> list[dict]:
    return [
        {"step_order": 1, "approver_role": ROLE_MANAGER, "fallback_role": ROLE_HR_ADMIN},
        {"step_order": 2, "approver_role": ROLE_HR_ADMIN, "fallback_role": ROLE_SUPER_ADMIN},
    ]


def _get_leave_workflow_steps() -> list[dict]:
    if not _workflow_engine_ready():
        return _default_leave_workflow_steps()
    definition = (
        ApprovalWorkflowDefinition.query.filter_by(module="leave", is_active=True)
        .order_by(ApprovalWorkflowDefinition.id.desc())
        .first()
    )
    if not definition:
        return _default_leave_workflow_steps()
    steps = definition.steps.order_by(ApprovalWorkflowStep.step_order.asc()).all()
    if not steps:
        return _default_leave_workflow_steps()
    return [
        {
            "step_order": item.step_order,
            "approver_role": item.approver_role,
            "fallback_role": item.fallback_role,
        }
        for item in steps
    ]


def _get_or_create_leave_approval_instance(request_obj: LeaveRequest) -> ApprovalInstance | None:
    if not _workflow_engine_ready():
        return None
    instance = ApprovalInstance.query.filter_by(module="leave", record_id=request_obj.id).first()
    if instance:
        return instance
    steps = _get_leave_workflow_steps()
    definition = (
        ApprovalWorkflowDefinition.query.filter_by(module="leave", is_active=True)
        .order_by(ApprovalWorkflowDefinition.id.desc())
        .first()
    )
    instance = ApprovalInstance(
        module="leave",
        record_id=request_obj.id,
        definition_id=definition.id if definition else None,
        current_step=1,
        total_steps=len(steps),
        status="pending",
    )
    db.session.add(instance)
    db.session.flush()
    return instance


def _role_matches_step(user, request_obj: LeaveRequest, step: dict) -> tuple[bool, bool]:
    if not user or not user.role:
        return False, False
    user_role = user.role.name
    approver_role = step.get("approver_role")
    fallback_role = step.get("fallback_role")
    if user_role == approver_role:
        if user_role == ROLE_MANAGER:
            is_manager = bool(
                request_obj.employee
                and request_obj.employee.manager
                and request_obj.employee.manager.user
                and request_obj.employee.manager.user.id == user.id
            )
            return is_manager, False
        return True, False
    if fallback_role and user_role == fallback_role:
        return True, True
    return False, False


def list_leave_types():
    return LeaveType.query.order_by(LeaveType.name.asc()).all()


def list_leave_balances():
    return LeaveBalance.query.order_by(LeaveBalance.year.desc(), LeaveBalance.id.desc()).all()


def list_leave_requests():
    return LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all()


def list_leave_balances_for_user(user):
    query = LeaveBalance.query.order_by(LeaveBalance.year.desc(), LeaveBalance.id.desc())
    if user and getattr(user, "is_authenticated", False) and user.role and user.role.name == ROLE_EMPLOYEE:
        employee_id = getattr(user, "employee_id", None)
        if not employee_id:
            return []
        query = query.filter_by(employee_id=employee_id)
    return query.all()


def list_leave_requests_for_user(user):
    query = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all()
    if user and getattr(user, "is_authenticated", False) and user.role and user.role.name == ROLE_EMPLOYEE:
        employee_id = getattr(user, "employee_id", None)
        if not employee_id:
            return []
        return [item for item in query if item.employee_id == employee_id]
    return query


def list_leave_type_balances_for_user(user, year: int | None = None):
    target_year = year or datetime.utcnow().year
    leave_types = list_leave_types()
    if user and getattr(user, "is_authenticated", False) and user.role and user.role.name == ROLE_EMPLOYEE:
        employee_id = getattr(user, "employee_id", None)
        if not employee_id:
            return [
                {"leave_type": leave_type, "year": target_year, "total_credits": Decimal("0"), "used_credits": Decimal("0"), "remaining_credits": Decimal("0")}
                for leave_type in leave_types
            ]
        balances = {
            balance.leave_type_id: balance
            for balance in LeaveBalance.query.filter_by(employee_id=employee_id, year=target_year).all()
        }
        rows = []
        for leave_type in leave_types:
            balance = balances.get(leave_type.id)
            rows.append(
                {
                    "leave_type": leave_type,
                    "year": target_year,
                    "total_credits": Decimal(balance.total_credits) if balance else Decimal("0"),
                    "used_credits": Decimal(balance.used_credits) if balance else Decimal("0"),
                    "remaining_credits": Decimal(balance.remaining_credits) if balance else Decimal("0"),
                }
            )
        return rows
    return list_leave_balances_for_user(user)


def can_manage_leave_request(user, request_obj: LeaveRequest | None) -> bool:
    if not user or not getattr(user, "is_authenticated", False) or request_obj is None or not user.role:
        return False
    if not _workflow_engine_ready():
        if user.role.name in {ROLE_SUPER_ADMIN, ROLE_HR_ADMIN}:
            return True
        if user.role.name == ROLE_MANAGER:
            return bool(
                request_obj.employee
                and request_obj.employee.manager
                and request_obj.employee.manager.user
                and request_obj.employee.manager.user.id == user.id
            )
        return False

    instance = ApprovalInstance.query.filter_by(module="leave", record_id=request_obj.id).first()
    if not instance or instance.status != "pending":
        return user.role.name in {ROLE_SUPER_ADMIN, ROLE_HR_ADMIN}
    steps = _get_leave_workflow_steps()
    step = next((item for item in steps if item["step_order"] == instance.current_step), None)
    if not step:
        return user.role.name in {ROLE_SUPER_ADMIN, ROLE_HR_ADMIN}
    allowed, _is_fallback = _role_matches_step(user, request_obj, step)
    return allowed


def get_leave_balance(employee_id: int, leave_type_id: int, year: int):
    return LeaveBalance.query.filter_by(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        year=year,
    ).first()


def leave_summary():
    return {
        "leave_types": LeaveType.query.count(),
        "pending_requests": LeaveRequest.query.filter_by(status="pending").count(),
        "approved_requests": LeaveRequest.query.filter_by(status="approved").count(),
        "balances": LeaveBalance.query.count(),
    }


def leave_summary_for_user(user):
    if user and getattr(user, "is_authenticated", False) and user.role and user.role.name == ROLE_EMPLOYEE:
        employee_id = getattr(user, "employee_id", None)
        if not employee_id:
            return {
                "leave_types": LeaveType.query.count(),
                "pending_requests": 0,
                "approved_requests": 0,
                "balances": 0,
            }
        return {
            "leave_types": LeaveType.query.count(),
            "pending_requests": LeaveRequest.query.filter_by(employee_id=employee_id, status="pending").count(),
            "approved_requests": LeaveRequest.query.filter_by(employee_id=employee_id, status="approved").count(),
            "balances": LeaveBalance.query.filter_by(employee_id=employee_id).count(),
        }
    return leave_summary()


def save_leave_type(form, leave_type=None):
    if leave_type is None:
        leave_type = LeaveType()
        db.session.add(leave_type)

    leave_type.name = form.name.data.strip()
    leave_type.default_credits = form.default_credits.data
    leave_type.is_paid = form.is_paid.data
    leave_type.requires_attachment = form.requires_attachment.data
    db.session.commit()
    return leave_type


def save_leave_balance(form, balance=None):
    total = Decimal(form.total_credits.data)
    used = Decimal(form.used_credits.data or 0)
    if balance is None:
        balance = get_leave_balance(form.employee_id.data, form.leave_type_id.data, form.year.data)
    if balance is None:
        balance = LeaveBalance()
        db.session.add(balance)

    balance.employee_id = form.employee_id.data
    balance.leave_type_id = form.leave_type_id.data
    balance.year = form.year.data
    balance.total_credits = total
    balance.used_credits = used
    balance.remaining_credits = Decimal(compute_remaining_credits(float(total), float(used)))
    db.session.commit()
    return balance


def adjust_leave_balance(form):
    adjustment = Decimal(form.adjustment_credits.data)
    balance = get_leave_balance(form.employee_id.data, form.leave_type_id.data, form.year.data)
    if balance is None:
        balance = LeaveBalance(
            employee_id=form.employee_id.data,
            leave_type_id=form.leave_type_id.data,
            year=form.year.data,
            total_credits=Decimal("0"),
            used_credits=Decimal("0"),
            remaining_credits=Decimal("0"),
        )
        db.session.add(balance)

    new_total = Decimal(balance.total_credits) + adjustment
    if new_total < 0:
        raise ValueError("Total credits cannot be reduced below zero.")
    if new_total < Decimal(balance.used_credits):
        raise ValueError("Adjusted total credits cannot be lower than the credits already used.")

    balance.total_credits = new_total
    balance.remaining_credits = new_total - Decimal(balance.used_credits)
    db.session.commit()
    return balance


def save_leave_request(form, request_obj=None):
    duration_type = form.duration_type.data
    if duration_type == "half_day" and form.end_date.data != form.start_date.data:
        raise ValueError("Half-day leave must start and end on the same date.")

    days = Decimal("0.5") if duration_type == "half_day" else Decimal((form.end_date.data - form.start_date.data).days + 1)
    leave_type = db.session.get(LeaveType, form.leave_type_id.data)
    if leave_type is None:
        raise ValueError("Selected leave type does not exist.")
    if form.end_date.data < form.start_date.data:
        raise ValueError("End date must be on or after the start date.")

    request_is_paid = bool(leave_type.is_paid)
    if leave_type.is_paid:
        balance = get_leave_balance(form.employee_id.data, form.leave_type_id.data, form.start_date.data.year)
        if balance is None or Decimal(balance.remaining_credits) < days:
            request_is_paid = False

    if request_obj is None:
        request_obj = LeaveRequest()
        db.session.add(request_obj)

    request_obj.employee_id = form.employee_id.data
    request_obj.leave_type_id = form.leave_type_id.data
    request_obj.start_date = form.start_date.data
    request_obj.end_date = form.end_date.data
    request_obj.duration_type = duration_type
    request_obj.days = days
    request_obj.reason = form.reason.data.strip()
    request_obj.is_paid = request_is_paid
    request_obj.status = request_obj.status or "pending"
    db.session.flush()
    instance = _get_or_create_leave_approval_instance(request_obj)
    if instance and instance.status == "pending":
        request_obj.status = "pending_step_1"
    db.session.commit()
    notify_leave_approvers(request_obj)
    return request_obj


def approve_leave_request(request_id: int, approved_by_id: int):
    request_obj = db.session.get(LeaveRequest, request_id)
    if request_obj is None:
        return None

    approver = db.session.get(User, approved_by_id)
    if _workflow_engine_ready():
        try:
            instance = _get_or_create_leave_approval_instance(request_obj)
            steps = _get_leave_workflow_steps()
            if instance and instance.status == "pending":
                step = next((item for item in steps if item["step_order"] == instance.current_step), None)
                if step and approver:
                    allowed, is_fallback = _role_matches_step(approver, request_obj, step)
                    if not allowed:
                        return None
                    db.session.add(
                        ApprovalDecision(
                            instance_id=instance.id,
                            step_order=instance.current_step,
                            approver_id=approved_by_id,
                            approver_role=approver.role.name if approver.role else "Unknown",
                            is_fallback=is_fallback,
                            decision="approved",
                        )
                    )
                    if instance.current_step < instance.total_steps:
                        instance.current_step += 1
                        request_obj.status = f"pending_step_{instance.current_step}"
                        db.session.commit()
                        notify_leave_approvers(request_obj)
                        return request_obj
                    instance.status = "approved"
        except (ProgrammingError, OperationalError):
            db.session.rollback()

    request_obj.status = "approved"
    request_obj.approved_by = approved_by_id
    request_obj.approved_at = datetime.utcnow()

    balance = LeaveBalance.query.filter_by(
        employee_id=request_obj.employee_id,
        leave_type_id=request_obj.leave_type_id,
        year=request_obj.start_date.year,
    ).first()
    if balance and request_obj.leave_type and request_obj.leave_type.is_paid and request_obj.is_paid:
        balance.used_credits = Decimal(balance.used_credits) + Decimal(request_obj.days)
        balance.remaining_credits = Decimal(balance.total_credits) - Decimal(balance.used_credits)
    db.session.commit()
    return request_obj


def disapprove_leave_request(request_id: int, approved_by_id: int):
    request_obj = db.session.get(LeaveRequest, request_id)
    if request_obj is None:
        return None

    if _workflow_engine_ready():
        try:
            instance = _get_or_create_leave_approval_instance(request_obj)
            if instance:
                instance.status = "rejected"
                approver = db.session.get(User, approved_by_id)
                db.session.add(
                    ApprovalDecision(
                        instance_id=instance.id,
                        step_order=instance.current_step,
                        approver_id=approved_by_id,
                        approver_role=approver.role.name if approver and approver.role else "Unknown",
                        decision="rejected",
                    )
                )
        except (ProgrammingError, OperationalError):
            db.session.rollback()

    request_obj.status = "disapproved"
    request_obj.approved_by = approved_by_id
    request_obj.approved_at = datetime.utcnow()
    db.session.commit()
    return request_obj


def serialize_leave_request(request_obj):
    return {
        "id": request_obj.id,
        "employee_id": request_obj.employee_id,
        "employee_name": request_obj.employee.full_name if request_obj.employee else None,
        "leave_type": request_obj.leave_type.name if request_obj.leave_type else None,
        "start_date": request_obj.start_date.isoformat(),
        "end_date": request_obj.end_date.isoformat(),
        "duration_type": request_obj.duration_type,
        "days": float(request_obj.days),
        "is_paid": request_obj.is_paid,
        "status": request_obj.status,
        "reason": request_obj.reason,
    }


def notify_leave_approvers(request_obj: LeaveRequest) -> None:
    recipients = set()
    if request_obj.employee and request_obj.employee.manager and request_obj.employee.manager.user and request_obj.employee.manager.user.is_active:
        recipients.add(request_obj.employee.manager.user.id)

    admin_users = (
        User.query.join(Role, User.role_id == Role.id)
        .filter(User.is_active.is_(True))
        .filter(Role.name.in_([ROLE_SUPER_ADMIN, ROLE_HR_ADMIN]))
        .all()
    )
    recipients.update(user.id for user in admin_users)

    title = f"Leave filed: {request_obj.employee.full_name if request_obj.employee else 'Employee'}"
    message = (
        f"{request_obj.employee.full_name if request_obj.employee else 'An employee'} filed a "
        f"{request_obj.duration_type.replace('_', ' ')} {request_obj.leave_type.name if request_obj.leave_type else 'leave'} "
        f"from {request_obj.start_date} to {request_obj.end_date}."
    )
    for user_id in recipients:
        db.session.add(
            Notification(
                user_id=user_id,
                title=title,
                message=message,
                type="leave_request",
                is_read=False,
            )
        )
    db.session.commit()
