from flask_mail import Message
from flask import current_app, url_for

from ..extensions import mail
from ..models import Employee, User


def employee_email(employee: Employee) -> str | None:
    return employee.company_email or employee.personal_email


def send_cutoff_announcement(cutoff) -> int:
    recipients = [
        employee_email(employee)
        for employee in Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all()
        if employee_email(employee)
    ]
    sent_count = 0
    for recipient in recipients:
        message = Message(
            subject=f"HRIS Payroll Cutoff: {cutoff.cutoff_name}",
            recipients=[recipient],
            body=(
                f"A payroll cutoff has been prepared in HRIS.\n\n"
                f"Cutoff: {cutoff.cutoff_name}\n"
                f"Period: {cutoff.start_date} to {cutoff.end_date}\n"
                f"Status: {cutoff.status}\n\n"
                f"This is an automated message from HRIS."
            ),
        )
        try:
            mail.send(message)
            sent_count += 1
        except Exception:
            continue
    return sent_count


def send_generated_payroll_notifications(entries, cutoff) -> int:
    sent_count = 0
    for entry in entries:
        employee = entry.employee
        recipient = employee_email(employee) if employee else None
        if not recipient:
            continue
        message = Message(
            subject=f"HRIS Payroll Ready: {cutoff.cutoff_name}",
            recipients=[recipient],
            body=(
                f"Your payroll entry has been generated in HRIS.\n\n"
                f"Employee: {employee.full_name}\n"
                f"Cutoff: {cutoff.cutoff_name}\n"
                f"Basic Pay: {entry.basic_pay}\n"
                f"Overtime Pay: {entry.overtime_pay}\n"
                f"Late Deduction: {entry.late_deduction}\n"
                f"Undertime Deduction: {entry.undertime_deduction}\n"
                f"Allowance Total: {entry.allowance_total}\n"
                f"Deduction Total: {entry.deduction_total}\n"
                f"Net Pay: {entry.net_pay}\n\n"
                f"This is an automated message from HRIS."
            ),
        )
        try:
            mail.send(message)
            sent_count += 1
        except Exception:
            continue
    return sent_count


def send_password_reset_email(user: User) -> bool:
    from ..auth.services import generate_password_reset_token

    token = generate_password_reset_token(user)
    reset_link = url_for("auth.reset_password_with_token", token=token, _external=True)
    message = Message(
        subject="HRIS Password Reset Request",
        recipients=[user.email],
        body=(
            f"Hello {user.display_name},\n\n"
            f"We received a request to reset your HRIS password.\n"
            f"Open this link to set a new password:\n\n"
            f"{reset_link}\n\n"
            f"This link will expire in 1 hour.\n"
            f"If you did not request this, you can ignore this email."
        ),
    )
    try:
        mail.send(message)
        return True
    except Exception:
        current_app.logger.exception("Failed to send password reset email to %s", user.email)
        return False
