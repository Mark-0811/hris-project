from datetime import date, datetime, time, timedelta

import click

from .extensions import db
from .models import (
    ApprovalInstance,
    AttendanceAnomaly,
    AttendanceRecord,
    Department,
    Employee,
    EmployeeShift,
    HelpArticle,
    LeaveType,
    NotificationPreference,
    PayrollCutoff,
    PayrollEntry,
    PayslipDispute,
    Permission,
    Position,
    PulseSurvey,
    Role,
    RolePermission,
    Shift,
    TaskInboxItem,
    TrainingCourse,
    User,
)
from .utils.constants import DEFAULT_ROLES, PERMISSION_MATRIX, ROLE_HR_ADMIN, ROLE_SUPER_ADMIN
from .utils.menu_access import backfill_all_user_menu_access, backfill_default_templates

DEFAULT_SHIFT_NAME = "Default Office Shift"
STANDARD_LEAVE_TYPES = [
    {"name": "Birthday Leave", "default_credits": 1, "is_paid": True},
    {"name": "Sick Leave", "default_credits": 15, "is_paid": True},
    {"name": "Emergency Leave", "default_credits": 3, "is_paid": True},
    {"name": "Vacation Leave", "default_credits": 15, "is_paid": True},
    {"name": "Maternity Leave", "default_credits": 105, "is_paid": True},
    {"name": "Single Parent Leave", "default_credits": 7, "is_paid": True},
]


def seed_roles_and_permissions() -> None:
    roles = {}
    for role_name in DEFAULT_ROLES:
        role = Role.query.filter_by(name=role_name).first()
        if role is None:
            role = Role(name=role_name, description=f"{role_name} role")
            db.session.add(role)
        roles[role_name] = role

    db.session.flush()

    permissions = {}
    for grants in PERMISSION_MATRIX.values():
        for module, action in grants:
            permission_name = f"{module}.{action}"
            permission = Permission.query.filter_by(name=permission_name).first()
            if permission is None:
                permission = Permission(name=permission_name, module=module, action=action)
                db.session.add(permission)
            permissions[permission_name] = permission

    db.session.flush()

    for role_name, grants in PERMISSION_MATRIX.items():
        role = roles[role_name]
        for module, action in grants:
            permission = permissions[f"{module}.{action}"]
            existing = RolePermission.query.filter_by(
                role_id=role.id, permission_id=permission.id
            ).first()
            if existing is None:
                db.session.add(RolePermission(role=role, permission=permission))


def seed_reference_data() -> None:
    hr_department = Department.query.filter_by(code="HR").first()
    if hr_department is None:
        hr_department = Department(
            name="Human Resources",
            code="HR",
            branch="Head Office",
            cost_center="CORP-HR",
        )
        db.session.add(hr_department)
        db.session.flush()

    admin_position = Position.query.filter_by(name="HR Administrator", department_id=hr_department.id).first()
    if admin_position is None:
        db.session.add(
            Position(
                name="HR Administrator",
                department=hr_department,
                description="Seeded default HR administrator position.",
            )
        )

    default_shift = Shift.query.filter_by(shift_name=DEFAULT_SHIFT_NAME).first()
    if default_shift is None:
        default_shift = Shift(
            shift_name=DEFAULT_SHIFT_NAME,
            start_time=time(8, 30),
            end_time=time(17, 30),
            grace_period_minutes=15,
            is_flexible=False,
        )
        db.session.add(default_shift)
        db.session.flush()

    for item in STANDARD_LEAVE_TYPES:
        leave_type = LeaveType.query.filter_by(name=item["name"]).first()
        if leave_type is None:
            leave_type = LeaveType(
                name=item["name"],
                default_credits=item["default_credits"],
                is_paid=item["is_paid"],
                requires_attachment=False,
            )
            db.session.add(leave_type)

    if HelpArticle.query.filter_by(title="How to use My Workspace").first() is None:
        db.session.add(
            HelpArticle(
                module="general",
                title="How to use My Workspace",
                content="Use My Workspace to check attendance, leave, requests, documents, learning, and company updates from one place.",
                is_active=True,
            )
        )

    if TrainingCourse.query.filter_by(code="HRIS-START").first() is None:
        db.session.add(
            TrainingCourse(
                code="HRIS-START",
                title="Getting Started with HRIS",
                required_for_role=None,
                renewal_months=None,
                is_active=True,
            )
        )

    if PulseSurvey.query.filter_by(title="Weekly Employee Pulse").first() is None:
        db.session.add(
            PulseSurvey(
                title="Weekly Employee Pulse",
                question_set_json='["How supported did you feel this week?","What should HR improve next?"]',
                status="open",
            )
        )

    employees_without_shift = (
        Employee.query.outerjoin(EmployeeShift, EmployeeShift.employee_id == Employee.id)
        .filter(EmployeeShift.id.is_(None))
        .all()
    )
    for employee in employees_without_shift:
        db.session.add(
            EmployeeShift(
                employee_id=employee.id,
                shift_id=default_shift.id,
                effective_date=employee.date_hired,
            )
        )


def seed_super_admin(username: str, email: str, password: str) -> None:
    super_admin_role = Role.query.filter_by(name=ROLE_SUPER_ADMIN).first()
    if super_admin_role is None:
        raise RuntimeError("Seed roles before creating the super admin.")

    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(
            username=username,
            email=email,
            role=super_admin_role,
            is_active=True,
            force_password_change=True,
        )
        user.set_password(password)
        db.session.add(user)
    else:
        user.email = email
        user.role = super_admin_role
        user.is_active = True
        user.force_password_change = True

    user.set_password(password)


def run_seed(app) -> None:
    with app.app_context():
        seed_roles_and_permissions()
        seed_reference_data()
        seed_super_admin(
            app.config["FIRST_SUPERADMIN_USERNAME"],
            app.config["FIRST_SUPERADMIN_EMAIL"],
            app.config["FIRST_SUPERADMIN_PASSWORD"],
        )
        db.session.commit()
        backfill_all_user_menu_access()
        backfill_default_templates()


def seed_demo_records(app) -> None:
    super_admin = User.query.filter_by(username=app.config["FIRST_SUPERADMIN_USERNAME"]).first()
    if not super_admin:
        return

    hr_department = Department.query.filter_by(code="HR").first()
    if hr_department is None:
        hr_department = Department(
            name="Human Resources",
            code="HR",
            branch="Head Office",
            cost_center="CORP-HR",
        )
        db.session.add(hr_department)
        db.session.flush()

    admin_position = Position.query.filter_by(name="HR Administrator", department_id=hr_department.id).first()
    if admin_position is None:
        admin_position = Position(
            name="HR Administrator",
            department_id=hr_department.id,
            description="Default admin position for Docker demo data.",
        )
        db.session.add(admin_position)
        db.session.flush()

    if super_admin.employee is None:
        employee = Employee.query.filter_by(employee_code="EMP-90001").first()
        if employee is None:
            employee = Employee(
                employee_code="EMP-90001",
                first_name="System",
                last_name="Admin",
                date_hired=date.today(),
                employment_status="active",
                department_id=hr_department.id,
                position_id=admin_position.id,
                badge_id="BADGE-90001",
                nfc_uid="NFC-90001",
                personal_email="sysadmin@example.com",
                company_email="sysadmin@company.local",
            )
            db.session.add(employee)
            db.session.flush()
        super_admin.employee_id = employee.id
        super_admin.force_password_change = False
    else:
        employee = super_admin.employee

    hr_admin_role = Role.query.filter_by(name=ROLE_HR_ADMIN).first()
    if hr_admin_role and User.query.filter_by(username="hradmin").first() is None:
        hr_admin = User(
            username="hradmin",
            email="hradmin@example.com",
            role=hr_admin_role,
            employee_id=super_admin.employee_id,
            is_active=True,
            force_password_change=False,
        )
        hr_admin.set_password("Password123!")
        db.session.add(hr_admin)

    today = date.today()
    record = AttendanceRecord.query.filter_by(employee_id=employee.id, date=today).first()
    if record is None:
        record = AttendanceRecord(employee_id=employee.id, date=today, status="incomplete")
        db.session.add(record)
        db.session.flush()

    anomaly = AttendanceAnomaly.query.filter_by(attendance_record_id=record.id, anomaly_type="missing_time_out").first()
    if anomaly is None:
        db.session.add(
            AttendanceAnomaly(
                attendance_record_id=record.id,
                employee_id=employee.id,
                date=today,
                anomaly_type="missing_time_out",
                severity="high",
                score=0.91,
                status="open",
                details="Sample exception: missing time out.",
            )
        )

    task = TaskInboxItem.query.filter_by(user_id=super_admin.id, title="Review pending attendance correction").first()
    if task is None:
        db.session.add(
            TaskInboxItem(
                user_id=super_admin.id,
                task_type="approval",
                title="Review pending attendance correction",
                description="Sample manager/admin task item.",
                status="open",
                due_at=datetime.utcnow() + timedelta(days=1),
                reference_module="attendance",
                reference_id=record.id,
                metadata_json='{"source":"docker-seed"}',
            )
        )

    if ApprovalInstance.query.filter_by(module="leave", record_id=999001).first() is None:
        db.session.add(
            ApprovalInstance(module="leave", record_id=999001, current_step=1, total_steps=2, status="submitted")
        )

    pref = NotificationPreference.query.filter_by(user_id=super_admin.id, event_type="leave_updates").first()
    if pref is None:
        pref = NotificationPreference(user_id=super_admin.id, event_type="leave_updates")
        db.session.add(pref)
    pref.in_app_enabled = True
    pref.email_enabled = True
    pref.sms_enabled = False

    cutoff = PayrollCutoff.query.filter_by(cutoff_name="Sample Cutoff").first()
    if cutoff is None:
        cutoff = PayrollCutoff(
            cutoff_name="Sample Cutoff",
            start_date=today.replace(day=1),
            end_date=today,
            status="open",
        )
        db.session.add(cutoff)
        db.session.flush()

    entry = PayrollEntry.query.filter_by(cutoff_id=cutoff.id, employee_id=employee.id).first()
    if entry is None:
        entry = PayrollEntry(
            employee_id=employee.id,
            cutoff_id=cutoff.id,
            basic_pay=20000,
            overtime_pay=1200,
            late_deduction=100,
            undertime_deduction=50,
            allowance_total=500,
            deduction_total=300,
            net_pay=21250,
            status="released",
        )
        db.session.add(entry)
        db.session.flush()

    dispute = PayslipDispute.query.filter_by(payroll_entry_id=entry.id, subject="Sample payslip dispute").first()
    if dispute is None:
        db.session.add(
            PayslipDispute(
                employee_id=employee.id,
                payroll_entry_id=entry.id,
                subject="Sample payslip dispute",
                details="Please verify overtime computation.",
                status="open",
            )
        )

    db.session.commit()


def register_seed_commands(app) -> None:
    @app.cli.command("seed")
    @click.option("--username", default=None, help="Username for the first super admin.")
    @click.option("--email", default=None, help="Email for the first super admin.")
    @click.option("--password", default=None, help="Password for the first super admin.")
    def seed_command(username: str | None, email: str | None, password: str | None) -> None:
        """Seed base roles, permissions, and the first super admin."""

        seed_roles_and_permissions()
        seed_reference_data()
        seed_super_admin(
            username or app.config["FIRST_SUPERADMIN_USERNAME"],
            email or app.config["FIRST_SUPERADMIN_EMAIL"],
            password or app.config["FIRST_SUPERADMIN_PASSWORD"],
        )
        db.session.commit()
        backfill_all_user_menu_access()
        backfill_default_templates()
        click.echo("Seed data applied successfully.")

    @app.cli.command("seed-demo")
    def seed_demo_command() -> None:
        """Seed demo records for Docker environments (idempotent)."""
        seed_demo_records(app)
        click.echo("Demo records applied successfully.")
