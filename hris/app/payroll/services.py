from decimal import Decimal

from ..extensions import db
from ..models import (
    Allowance,
    AttendanceRecord,
    Deduction,
    Employee,
    EmployeeSalary,
    Notification,
    PayrollCutoff,
    PayrollEntry,
    User,
)
from ..utils.mailer import send_cutoff_announcement, send_generated_payroll_notifications


def summarize_cutoff():
    return {
        "cutoffs": PayrollCutoff.query.count(),
        "entries": PayrollEntry.query.count(),
        "open_cutoffs": PayrollCutoff.query.filter_by(status="open").count(),
        "employees_with_salary": EmployeeSalary.query.count(),
    }


def list_cutoffs():
    return PayrollCutoff.query.order_by(PayrollCutoff.start_date.desc()).all()


def list_salaries():
    return EmployeeSalary.query.order_by(EmployeeSalary.effective_date.desc()).all()


def list_allowances():
    return Allowance.query.order_by(Allowance.effective_date.desc()).all()


def list_deductions():
    return Deduction.query.order_by(Deduction.effective_date.desc()).all()


def list_payroll_entries():
    return PayrollEntry.query.order_by(PayrollEntry.created_at.desc()).all()


def can_access_payroll_entry(user, entry: PayrollEntry | None) -> bool:
    if not user or not getattr(user, "is_authenticated", False) or entry is None:
        return False
    if user.role and user.role.name in {"Super Admin", "HR Admin", "Payroll Admin"}:
        return True
    return bool(getattr(user, "employee_id", None) and entry.employee_id == user.employee_id)


def save_cutoff(form, cutoff=None):
    if cutoff is None:
        cutoff = PayrollCutoff()
        db.session.add(cutoff)

    if form.end_date.data < form.start_date.data:
        raise ValueError("Cutoff end date must be on or after the start date.")

    cutoff.cutoff_name = form.cutoff_name.data.strip()
    cutoff.start_date = form.start_date.data
    cutoff.end_date = form.end_date.data
    cutoff.status = form.status.data
    db.session.commit()
    sent_count = send_cutoff_announcement(cutoff)
    create_cutoff_notifications(cutoff)
    return cutoff, sent_count


def save_salary(form, salary=None):
    if salary is None:
        salary = EmployeeSalary()
        db.session.add(salary)

    salary.employee_id = form.employee_id.data
    salary.basic_salary = form.basic_salary.data
    salary.daily_rate = form.daily_rate.data
    salary.hourly_rate = form.hourly_rate.data
    salary.effective_date = form.effective_date.data
    db.session.commit()
    return salary


def save_allowance(form):
    allowance = Allowance(
        employee_id=form.employee_id.data,
        allowance_type=form.allowance_type.data.strip(),
        amount=form.amount.data,
        taxable=form.taxable.data,
        effective_date=form.effective_date.data,
    )
    db.session.add(allowance)
    db.session.commit()
    return allowance


def save_deduction(form):
    deduction = Deduction(
        employee_id=form.employee_id.data,
        deduction_type=form.deduction_type.data.strip(),
        amount=form.amount.data,
        effective_date=form.effective_date.data,
    )
    db.session.add(deduction)
    db.session.commit()
    return deduction


def generate_payroll_for_cutoff(cutoff_id: int):
    cutoff = db.session.get(PayrollCutoff, cutoff_id)
    if cutoff is None:
        return [], 0

    generated_entries = []
    salaries = (
        EmployeeSalary.query.filter(EmployeeSalary.effective_date <= cutoff.end_date)
        .order_by(EmployeeSalary.employee_id.asc(), EmployeeSalary.effective_date.desc())
        .all()
    )
    latest_by_employee = {}
    for salary in salaries:
        latest_by_employee.setdefault(salary.employee_id, salary)

    for employee_id, salary in latest_by_employee.items():
        attendance_records = AttendanceRecord.query.filter(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.date >= cutoff.start_date,
            AttendanceRecord.date <= cutoff.end_date,
        ).all()
        days_present = sum(1 for record in attendance_records if record.status in {"present", "approved", "late", "undertime"})
        total_late = sum(record.late_minutes for record in attendance_records)
        total_undertime = sum(record.undertime_minutes for record in attendance_records)
        total_overtime = sum(record.overtime_minutes for record in attendance_records)

        daily_rate = Decimal(salary.daily_rate or (Decimal(salary.basic_salary) / Decimal("22")))
        hourly_rate = Decimal(salary.hourly_rate or (daily_rate / Decimal("8")))

        allowance_total = sum(
            Decimal(item.amount)
            for item in Allowance.query.filter(
                Allowance.employee_id == employee_id,
                Allowance.effective_date <= cutoff.end_date,
            ).all()
        )
        deduction_total = sum(
            Decimal(item.amount)
            for item in Deduction.query.filter(
                Deduction.employee_id == employee_id,
                Deduction.effective_date <= cutoff.end_date,
            ).all()
        )

        basic_pay = daily_rate * Decimal(days_present)
        overtime_pay = (hourly_rate / Decimal("60")) * Decimal(total_overtime)
        late_deduction = (hourly_rate / Decimal("60")) * Decimal(total_late)
        undertime_deduction = (hourly_rate / Decimal("60")) * Decimal(total_undertime)
        net_pay = basic_pay + overtime_pay + allowance_total - deduction_total - late_deduction - undertime_deduction

        entry = PayrollEntry.query.filter_by(employee_id=employee_id, cutoff_id=cutoff.id).first()
        if entry is None:
            entry = PayrollEntry(employee_id=employee_id, cutoff_id=cutoff.id)
            db.session.add(entry)

        entry.basic_pay = basic_pay
        entry.overtime_pay = overtime_pay
        entry.late_deduction = late_deduction
        entry.undertime_deduction = undertime_deduction
        entry.allowance_total = allowance_total
        entry.deduction_total = deduction_total
        entry.net_pay = net_pay
        entry.status = "generated"
        generated_entries.append(entry)

    if generated_entries:
        cutoff.status = "processing"
    db.session.commit()
    email_count = send_generated_payroll_notifications(generated_entries, cutoff)
    create_generated_payroll_notifications(generated_entries, cutoff)
    return generated_entries, email_count


def post_payroll_for_cutoff(cutoff_id: int):
    cutoff = db.session.get(PayrollCutoff, cutoff_id)
    if cutoff is None:
        return [], 0

    entries = PayrollEntry.query.filter_by(cutoff_id=cutoff.id).all()
    if not entries:
        return [], 0

    for entry in entries:
        entry.status = "posted"
    cutoff.status = "closed"
    db.session.commit()
    notification_count = create_posted_payroll_notifications(entries, cutoff)
    return entries, notification_count


def serialize_entry(entry):
    return {
        "id": entry.id,
        "employee_id": entry.employee_id,
        "employee_name": entry.employee.full_name if entry.employee else None,
        "cutoff": entry.cutoff.cutoff_name if entry.cutoff else None,
        "basic_pay": float(entry.basic_pay),
        "overtime_pay": float(entry.overtime_pay),
        "late_deduction": float(entry.late_deduction),
        "undertime_deduction": float(entry.undertime_deduction),
        "allowance_total": float(entry.allowance_total),
        "deduction_total": float(entry.deduction_total),
        "net_pay": float(entry.net_pay),
        "status": entry.status,
    }


def create_cutoff_notifications(cutoff) -> int:
    recipients = [
        user
        for user in User.query.filter_by(is_active=True).all()
        if user.employee
    ]

    for user in recipients:
        db.session.add(
            Notification(
                user_id=user.id,
                title=f"Payroll cutoff posted: {cutoff.cutoff_name}",
                message=f"Payroll cutoff for {cutoff.start_date} to {cutoff.end_date} is now {cutoff.status}.",
                type="payroll",
                is_read=False,
            )
        )
    db.session.commit()
    return len(recipients)


def create_generated_payroll_notifications(entries, cutoff) -> int:
    count = 0
    for entry in entries:
        employee = entry.employee
        user = employee.user if employee else None
        if not user or not user.is_active:
            continue
        db.session.add(
            Notification(
                user_id=user.id,
                title=f"Payroll ready: {cutoff.cutoff_name}",
                message=(
                    f"Your payroll for {cutoff.start_date} to {cutoff.end_date} has been generated. "
                    f"Net pay: {entry.net_pay}. Open Reports to download your PDF payslip."
                ),
                type="payroll",
                is_read=False,
            )
        )
        count += 1
    db.session.commit()
    return count


def create_posted_payroll_notifications(entries, cutoff) -> int:
    count = 0
    for entry in entries:
        employee = entry.employee
        user = employee.user if employee else None
        if not user or not user.is_active:
            continue
        db.session.add(
            Notification(
                user_id=user.id,
                title=f"Payroll posted: {cutoff.cutoff_name}",
                message=(
                    f"Your payroll for {cutoff.start_date} to {cutoff.end_date} has been posted. "
                    f"Open Reports or Payroll to download your PDF payslip."
                ),
                type="payroll",
                is_read=False,
            )
        )
        count += 1
    db.session.commit()
    return count
