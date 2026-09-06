# HRIS Project Blueprint

This repository now contains a Phase 1 Flask foundation for a modular Human Resource Information System (HRIS) covering authentication, employee data, attendance, biometrics, leave, payroll support, reports, notifications, and audit logging.

## Current Scope

- App factory with environment-based configuration
- SQLAlchemy, Migrate, Login, and CSRF extensions
- Modular blueprints for `auth`, `admin`, `employees`, `biometrics`, `attendance`, `leave`, `payroll`, and `reports`
- Core database models for the backbone entities in your project plan
- Starter templates for login and dashboard
- Utility helpers for role checks and employee code generation

## Project Structure

```text
├── hris/
│   └── app/
│       ├── admin/
│       ├── attendance/
│       ├── auth/
│       ├── biometrics/
│       ├── employees/
│       ├── leave/
│       ├── models/
│       ├── payroll/
│       ├── reports/
│       ├── static/
│       ├── templates/
│       ├── utils/
│       ├── __init__.py
│       ├── config.py
│       └── extensions.py
├── tests/
├── README.md
├── requirements.txt
└── run.py
```

## Backbone Models Included

- Access control: `users`, `roles`, `permissions`, `role_permissions`
- HR master data: `employees`, `departments`, `positions`
- Attendance: `biometric_devices`, `biometric_logs`, `attendance_records`, `attendance_adjustments`
- Scheduling: `shifts`, `employee_shifts`, `holidays`
- Leave: `leave_types`, `leave_balances`, `leave_requests`
- Payroll support: `payroll_cutoffs`, `employee_salary`, `allowances`, `deductions`, `payroll_entries`
- Platform: `notifications`, `audit_logs`

## Suggested Build Order

1. Add `.env` values for `SECRET_KEY` and `DATABASE_URL`.
2. Create the virtual environment and install `requirements.txt`.
3. Initialize migrations with `flask db init`, `flask db migrate`, and `flask db upgrade`.
4. Seed default roles and a first super admin account.
5. Build employee CRUD screens and admin user management.
6. Implement biometric ingestion and attendance processing services.
7. Add leave workflow, approval routing, and notification delivery.
8. Extend payroll support and reporting exports.

## Recommended MVP

- Authentication and role-based access
- Employee CRUD
- Department and position setup
- Biometrics log ingestion
- Attendance records view
- Leave request and approval flow
- Notifications
- Admin dashboard and core reports

## Notes For Next Iteration

- The current biometric endpoint is a safe placeholder and still needs API-key validation, device registration, and attendance processing.
- The current dashboard is static and should be wired to service-layer metrics.
- SQLite is configured as the local fallback so the app can bootstrap easily, but production should use PostgreSQL or MySQL.
- Recruitment, onboarding, performance, and document management are intentionally deferred until the core HRIS spine is stable.

## Security CV Monitoring MVP

- New `security` module adds a web viewer (`/security/viewer`) with:
1. live USB camera stream
2. detection event feed
3. intruder mark/unmark actions
4. profile enrollment via image upload
- New APIs:
1. `POST /api/security/enroll`
2. `GET /api/security/events`
3. `POST /api/security/events/<id>/mark-intruder`
4. `POST /api/security/events/<id>/unmark-intruder`
- Run the always-on worker independently from the web app:
1. `python run.py`
2. `python run_security_worker.py`
- Required `.env` values for alerts:
1. `SECURITY_ALERT_EMAILS`
2. `SECURITY_ALERT_SMS`
3. `TWILIO_ACCOUNT_SID`
4. `TWILIO_AUTH_TOKEN`
5. `TWILIO_FROM_NUMBER`
