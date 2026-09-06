from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import os
import sys
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUTPUT_DIR = ROOT / "docs" / "user-guide"
IMAGES_DIR = OUTPUT_DIR / "images"
PDF_PATH = OUTPUT_DIR / "HRIS_Step_by_Step_Guide.pdf"
MARKDOWN_PATH = OUTPUT_DIR / "HRIS_Step_by_Step_Guide.md"

BASE_URL = "http://127.0.0.1:5000"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

DOC_ADMIN_USERNAME = "docs_admin"
DOC_ADMIN_PASSWORD = "DocsAdmin123!"
DOC_EMPLOYEE_USERNAME = "docs_employee"
DOC_EMPLOYEE_PASSWORD = "DocsEmployee123!"


ADMIN_STEPS = [
    {
        "slug": "01-login-page",
        "title": "Open the HRIS sign-in page",
        "url": f"{BASE_URL}/auth/login",
        "body": "Start at the login page. Enter your HRIS username and password, then click Sign in to open the platform.",
    },
    {
        "slug": "02-admin-dashboard",
        "title": "Review the dashboard command center",
        "url": f"{BASE_URL}/",
        "body": "The dashboard summarizes employee activity, pending tasks, leave SLA, company updates, and quick actions so HR can work from one place.",
    },
    {
        "slug": "03-employee-directory",
        "title": "Open the employee directory",
        "url": f"{BASE_URL}/employees/list",
        "body": "Use Employees to review the master list, open employee records, and manage HR profile data from one organized table.",
    },
    {
        "slug": "04-attendance-monitoring",
        "title": "Monitor attendance records",
        "url": f"{BASE_URL}/attendance/",
        "body": "Attendance shows processed daily logs for review. HR can spot missing records, late arrivals, and incomplete time-ins or time-outs.",
    },
    {
        "slug": "05-leave-workspace",
        "title": "Manage leave requests",
        "url": f"{BASE_URL}/leave/",
        "body": "The leave workspace tracks balances and requests so managers and HR can review, approve, or reject submissions with full context.",
    },
    {
        "slug": "06-reports-overview",
        "title": "Analyze HR reports",
        "url": f"{BASE_URL}/reports/",
        "body": "Reports combines employee, attendance, leave, and payroll summaries. Filters at the top help narrow the data before exporting or reviewing trends.",
    },
    {
        "slug": "07-user-access",
        "title": "Manage user accounts",
        "url": f"{BASE_URL}/users",
        "body": "User Access is where admins create accounts, reset passwords, toggle active status, and open per-user menu assignment controls.",
    },
    {
        "slug": "08-access-governance",
        "title": "Review governance and approval queues",
        "url": f"{BASE_URL}/users/access-governance",
        "body": "Access Governance centralizes access templates, menu requests, profile update approvals, dormant access checks, and audit history.",
    },
    {
        "slug": "09-notifications",
        "title": "Check the notification center",
        "url": f"{BASE_URL}/notifications",
        "body": "Notifications collects leave alerts, access reviews, payroll events, and profile update decisions so actions are easy to track.",
    },
]

EMPLOYEE_STEPS = [
    {
        "slug": "10-employee-attendance",
        "title": "Employee view of attendance logs",
        "url": f"{BASE_URL}/attendance/my-logs",
        "body": "Employees can open My Attendance to review their own time-in and time-out history without seeing other staff records.",
    },
    {
        "slug": "11-employee-leave-request",
        "title": "Employee leave request form",
        "url": f"{BASE_URL}/leave/requests/create",
        "body": "Employees can file leave requests by choosing a leave type, date range, and reason. The request then enters the approval flow.",
    },
    {
        "slug": "12-employee-profile-update",
        "title": "Employee self-service profile update",
        "url": f"{BASE_URL}/auth/profile",
        "body": "Employees can request updates for safe personal fields such as birthdate, civil status, address, and emergency contact. The changes stay pending until HR verifies them.",
    },
]


def ensure_seed_data() -> None:
    script = textwrap.dedent(
        f"""
        import json
        from datetime import date

        from hris.app import create_app
        from hris.app.extensions import db
        from hris.app.models import AttendanceRecord, Department, Employee, EmployeeProfileUpdateRequest, LeaveRequest, LeaveType, MenuAccessRequest, Position, Role, User
        from hris.app.utils.menu_access import seed_user_menu_access

        app = create_app()
        with app.app_context():
            department = Department.query.order_by(Department.id.asc()).first()
            position = Position.query.order_by(Position.id.asc()).first()
            if department is None:
                department = Department(name="Human Resources", code="HR")
                db.session.add(department)
                db.session.flush()
            if position is None:
                position = Position(name="HR Administrator", department=department)
                db.session.add(position)
                db.session.flush()

            super_admin_role = Role.query.filter_by(name="Super Admin").first()
            employee_role = Role.query.filter_by(name="Employee").first()
            leave_type = LeaveType.query.filter_by(name="Vacation Leave").first()

            docs_admin = User.query.filter_by(username="{DOC_ADMIN_USERNAME}").first()
            if docs_admin is None:
                admin_employee = Employee(
                    employee_code="EMP-DOC-ADM",
                    first_name="Documentation",
                    last_name="Admin",
                    date_hired=date(2025, 1, 1),
                    employment_status="active",
                    department=department,
                    position=position,
                )
                db.session.add(admin_employee)
                db.session.flush()
                docs_admin = User(
                    username="{DOC_ADMIN_USERNAME}",
                    email="docs_admin@example.com",
                    role=super_admin_role,
                    employee=admin_employee,
                    is_active=True,
                    force_password_change=False,
                )
                docs_admin.set_password("{DOC_ADMIN_PASSWORD}")
                db.session.add(docs_admin)
                db.session.flush()
                seed_user_menu_access(docs_admin, force=True)
            else:
                docs_admin.set_password("{DOC_ADMIN_PASSWORD}")
                docs_admin.force_password_change = False
                docs_admin.is_active = True

            docs_employee = User.query.filter_by(username="{DOC_EMPLOYEE_USERNAME}").first()
            if docs_employee is None:
                employee_record = Employee(
                    employee_code="EMP-DOC-EMP",
                    first_name="Documentation",
                    last_name="Employee",
                    birthdate=date(1998, 6, 15),
                    gender="female",
                    civil_status="single",
                    address="123 Demo Street, Manila",
                    emergency_contact_name="Demo Contact",
                    date_hired=date(2025, 2, 1),
                    employment_status="active",
                    department=department,
                    position=position,
                )
                db.session.add(employee_record)
                db.session.flush()
                docs_employee = User(
                    username="{DOC_EMPLOYEE_USERNAME}",
                    email="docs_employee@example.com",
                    role=employee_role,
                    employee=employee_record,
                    is_active=True,
                    force_password_change=False,
                )
                docs_employee.set_password("{DOC_EMPLOYEE_PASSWORD}")
                db.session.add(docs_employee)
                db.session.flush()
                seed_user_menu_access(docs_employee, force=True)
            else:
                docs_employee.set_password("{DOC_EMPLOYEE_PASSWORD}")
                docs_employee.force_password_change = False
                docs_employee.is_active = True

            if docs_employee.employee and not AttendanceRecord.query.filter_by(employee_id=docs_employee.employee.id).first():
                db.session.add(
                    AttendanceRecord(
                        employee_id=docs_employee.employee.id,
                        date=date.today(),
                        status="present",
                        remarks="Documentation sample attendance",
                    )
                )

            if leave_type and docs_employee.employee and not LeaveRequest.query.filter_by(employee_id=docs_employee.employee.id).first():
                db.session.add(
                    LeaveRequest(
                        employee_id=docs_employee.employee.id,
                        leave_type_id=leave_type.id,
                        start_date=date.today(),
                        end_date=date.today(),
                        days=1,
                        reason="Documentation sample leave request",
                        status="pending",
                    )
                )

            if docs_employee.employee and not EmployeeProfileUpdateRequest.query.filter_by(user_id=docs_employee.id).first():
                db.session.add(
                    EmployeeProfileUpdateRequest(
                        user_id=docs_employee.id,
                        employee_id=docs_employee.employee.id,
                        requested_data_json=json.dumps({{
                            "birthdate": "1998-06-20",
                            "gender": "female",
                            "civil_status": "married",
                            "address": "456 Updated Demo Avenue, Quezon City",
                            "emergency_contact_name": "Updated Demo Contact",
                        }}),
                        reason="Documentation sample profile update request",
                        status="pending",
                    )
                )

            if not MenuAccessRequest.query.filter_by(user_id=docs_employee.id).first():
                db.session.add(
                    MenuAccessRequest(
                        user_id=docs_employee.id,
                        requested_menu_keys_json=json.dumps(["dashboard", "profile", "reports"]),
                        reason="Documentation sample access request",
                        status="pending",
                    )
                )

            db.session.commit()
        print("Documentation seed data ready.")
        """
    )
    subprocess.run(
        ["docker", "exec", "hris-web", "python", "-c", script],
        cwd=ROOT,
        check=True,
    )


def login(page, username: str, password: str) -> None:
    page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
    page.get_by_placeholder("Username").fill(username)
    page.get_by_placeholder("Password").fill(password)
    page.get_by_label("Remember me").check()
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle")


def capture_pages() -> list[dict]:
    steps = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=EDGE_PATH,
            args=["--disable-web-security"],
        )

        admin_context = browser.new_context(viewport={"width": 1600, "height": 1100}, device_scale_factor=1)
        admin_page = admin_context.new_page()
        admin_page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
        admin_page.screenshot(path=str(IMAGES_DIR / "01-login-page.png"), full_page=True)
        steps.append({**ADMIN_STEPS[0], "image": str(IMAGES_DIR / "01-login-page.png")})

        login(admin_page, DOC_ADMIN_USERNAME, DOC_ADMIN_PASSWORD)
        for step in ADMIN_STEPS[1:]:
            admin_page.goto(step["url"], wait_until="networkidle")
            admin_page.screenshot(path=str(IMAGES_DIR / f"{step['slug']}.png"), full_page=True)
            steps.append({**step, "image": str(IMAGES_DIR / f"{step['slug']}.png")})
        admin_context.close()

        employee_context = browser.new_context(viewport={"width": 1600, "height": 1100}, device_scale_factor=1)
        employee_page = employee_context.new_page()
        login(employee_page, DOC_EMPLOYEE_USERNAME, DOC_EMPLOYEE_PASSWORD)
        for step in EMPLOYEE_STEPS:
            employee_page.goto(step["url"], wait_until="networkidle")
            employee_page.screenshot(path=str(IMAGES_DIR / f"{step['slug']}.png"), full_page=True)
            steps.append({**step, "image": str(IMAGES_DIR / f"{step['slug']}.png")})
        employee_context.close()
        browser.close()
    return steps


def write_markdown(steps: list[dict]) -> None:
    lines = [
        "# HRIS Step-by-Step Guide",
        "",
        "This guide explains the main HRIS workflows for administrators and employees using the live Docker environment.",
        "",
    ]
    for index, step in enumerate(steps, start=1):
        image_name = Path(step["image"]).name
        lines.extend(
            [
                f"## Step {index}: {step['title']}",
                "",
                step["body"],
                "",
                f"![Step {index}]({Path('images') / image_name})",
                "",
            ]
        )
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")


def build_pdf(steps: list[dict]) -> None:
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]
    body_style.leading = 16
    note_style = ParagraphStyle(
        "DocNote",
        parent=body_style,
        textColor=colors.HexColor("#51607a"),
        fontSize=10,
    )

    story = [
        Paragraph("HRIS Step-by-Step Guide", title_style),
        Spacer(1, 0.2 * inch),
        Paragraph(
            "This PDF walks through the main HRIS workflows using screenshots captured from the running Docker application.",
            body_style,
        ),
        Spacer(1, 0.3 * inch),
    ]

    max_image_width = 6.5 * inch
    max_image_height = 5.8 * inch

    for index, step in enumerate(steps, start=1):
        story.append(Paragraph(f"Step {index}: {step['title']}", heading_style))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(step["body"], body_style))
        story.append(Spacer(1, 0.15 * inch))

        image = Image(step["image"])
        image.drawWidth = max_image_width
        image.drawHeight = min(max_image_height, image.imageHeight * (max_image_width / image.imageWidth))
        if image.drawHeight > max_image_height:
            scale = max_image_height / image.drawHeight
            image.drawHeight *= scale
            image.drawWidth *= scale
        story.append(image)
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(f"Screen captured from: {step['url']}", note_style))
        if index != len(steps):
            story.append(PageBreak())

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="HRIS Step-by-Step Guide",
    )
    doc.build(story)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ensure_seed_data()
    steps = capture_pages()
    write_markdown(steps)
    build_pdf(steps)
    print(f"Generated PDF: {PDF_PATH}")
    print(f"Generated Markdown: {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
