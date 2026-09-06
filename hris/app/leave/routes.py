from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from .forms import LeaveBalanceAdjustmentForm, LeaveBalanceForm, LeaveRequestForm, LeaveTypeForm
from .services import (
    adjust_leave_balance,
    approve_leave_request,
    can_manage_leave_request,
    disapprove_leave_request,
    leave_summary_for_user,
    list_leave_balances_for_user,
    list_leave_requests_for_user,
    list_leave_type_balances_for_user,
    list_leave_types,
    save_leave_balance,
    save_leave_request,
    save_leave_type,
    serialize_leave_request,
)
from ..models import Employee, LeaveRequest, LeaveType
from ..utils.decorators import role_required

LEAVE_ADMIN_ROLES = ("Super Admin", "HR Admin", "Manager")


def populate_leave_type_form(_form):
    return None


def populate_balance_form(form):
    employees = Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all()
    leave_types = list_leave_types()
    form.employee_id.choices = [(employee.id, employee.full_name) for employee in employees]
    form.leave_type_id.choices = [(leave_type.id, leave_type.name) for leave_type in leave_types]
    current_year = datetime.utcnow().year
    form.year.choices = [(year, str(year)) for year in range(current_year - 1, current_year + 4)]


def populate_balance_adjustment_form(form):
    populate_balance_form(form)


def populate_request_form(form):
    if current_user.role and current_user.role.name == "Employee" and current_user.employee:
        employees = [current_user.employee]
    else:
        employees = Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all()
    leave_types = list_leave_types()
    form.employee_id.choices = [(employee.id, employee.full_name) for employee in employees]
    form.leave_type_id.choices = [(leave_type.id, leave_type.name) for leave_type in leave_types]


@bp.route("/")
@login_required
def index():
    return render_template(
        "leave/index.html",
        summary=leave_summary_for_user(current_user),
        leave_types=list_leave_types(),
        balances=list_leave_balances_for_user(current_user),
        leave_type_balances=list_leave_type_balances_for_user(current_user),
        requests=list_leave_requests_for_user(current_user),
        can_manage_leave_request=can_manage_leave_request,
    )


@bp.route("/types/create", methods=["GET", "POST"])
@login_required
@role_required("Super Admin", "HR Admin")
def create_type():
    form = LeaveTypeForm()
    if form.validate_on_submit():
        existing = LeaveType.query.filter_by(name=form.name.data.strip()).first()
        if existing:
            form.name.errors.append("Leave type already exists.")
        else:
            save_leave_type(form)
            flash("Leave type saved successfully.", "success")
            return redirect(url_for("leave.index"))
    return render_template("leave/type_form.html", form=form)


@bp.route("/balances/create", methods=["GET", "POST"])
@login_required
@role_required("Super Admin", "HR Admin")
def create_balance():
    form = LeaveBalanceForm()
    populate_balance_form(form)
    if form.validate_on_submit():
        save_leave_balance(form)
        flash("Leave granted successfully.", "success")
        return redirect(url_for("leave.index"))
    return render_template("leave/balance_form.html", form=form)


@bp.route("/balances/adjust", methods=["GET", "POST"])
@login_required
@role_required("Super Admin", "HR Admin")
def adjust_balance():
    form = LeaveBalanceAdjustmentForm()
    populate_balance_adjustment_form(form)
    if form.validate_on_submit():
        try:
            adjust_leave_balance(form)
        except ValueError as exc:
            form.adjustment_credits.errors.append(str(exc))
        else:
            flash("Leave balance adjusted successfully.", "success")
            return redirect(url_for("leave.index"))
    return render_template("leave/adjust_balance_form.html", form=form)


@bp.route("/requests/create", methods=["GET", "POST"])
@login_required
def create_request():
    form = LeaveRequestForm()
    populate_request_form(form)
    if not form.is_submitted() and current_user.role and current_user.role.name == "Employee" and current_user.employee_id:
        form.employee_id.data = current_user.employee_id
    if form.validate_on_submit():
        if current_user.role and current_user.role.name == "Employee" and form.employee_id.data != current_user.employee_id:
            form.employee_id.errors.append("You can only file leave for your own employee profile.")
            return render_template("leave/request_form.html", form=form)
        try:
            save_leave_request(form)
        except ValueError as exc:
            form.start_date.errors.append(str(exc))
        else:
            flash("Leave request submitted successfully.", "success")
            return redirect(url_for("leave.index"))
    return render_template("leave/request_form.html", form=form)


@bp.route("/requests/<int:request_id>/approve", methods=["GET", "POST"])
@login_required
@role_required(*LEAVE_ADMIN_ROLES)
def approve_request(request_id: int):
    request_obj = LeaveRequest.query.get_or_404(request_id)
    if not can_manage_leave_request(current_user, request_obj):
        flash("You are not allowed to approve this leave request.", "danger")
        return redirect(url_for("leave.index"))
    if request.method == "GET":
        return render_template(
            "confirm_action.html",
            page_title="Confirm Leave Approval",
            modal_intro="Approve this leave request after confirming the employee, dates, and type.",
            confirm_heading="Approve leave request",
            confirm_message="This will mark the leave request as approved.",
            confirm_button_label="Approve Leave",
            form_action=url_for("leave.approve_request", request_id=request_id),
            hidden_fields={},
            cancel_url=url_for("leave.index"),
        )
    approve_leave_request(request_id, current_user.id)
    flash("Leave request approved.", "success")
    return redirect(url_for("leave.index"))


@bp.route("/requests/<int:request_id>/disapprove", methods=["GET", "POST"])
@login_required
@role_required(*LEAVE_ADMIN_ROLES)
def disapprove_request(request_id: int):
    request_obj = LeaveRequest.query.get_or_404(request_id)
    if not can_manage_leave_request(current_user, request_obj):
        flash("You are not allowed to disapprove this leave request.", "danger")
        return redirect(url_for("leave.index"))
    if request.method == "GET":
        return render_template(
            "confirm_action.html",
            page_title="Confirm Leave Disapproval",
            modal_intro="Reject this leave request if it should not proceed.",
            confirm_heading="Disapprove leave request",
            confirm_message="This will mark the leave request as disapproved.",
            confirm_button_label="Disapprove Leave",
            form_action=url_for("leave.disapprove_request", request_id=request_id),
            hidden_fields={},
            cancel_url=url_for("leave.index"),
        )
    disapprove_leave_request(request_id, current_user.id)
    flash("Leave request disapproved.", "warning")
    return redirect(url_for("leave.index"))


@bp.route("/api/summary")
@login_required
def api_summary():
    return jsonify(leave_summary_for_user(current_user))


@bp.route("/api/requests", methods=["GET", "POST"])
@login_required
def api_requests():
    if request.method == "GET":
        return jsonify([serialize_leave_request(item) for item in list_leave_requests_for_user(current_user)])

    payload = request.get_json(silent=True) or {}
    request_obj = LeaveRequest(
        employee_id=payload["employee_id"],
        leave_type_id=payload["leave_type_id"],
        start_date=datetime.fromisoformat(payload["start_date"]).date(),
        end_date=datetime.fromisoformat(payload["end_date"]).date(),
        days=payload.get("days", 1),
        reason=payload["reason"],
        status=payload.get("status", "pending"),
    )
    from ..extensions import db

    db.session.add(request_obj)
    db.session.commit()
    return jsonify(serialize_leave_request(request_obj)), 201
