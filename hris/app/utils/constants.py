ROLE_SUPER_ADMIN = "Super Admin"
ROLE_HR_ADMIN = "HR Admin"
ROLE_PAYROLL_ADMIN = "Payroll Admin"
ROLE_MANAGER = "Manager"
ROLE_EMPLOYEE = "Employee"
ROLE_BIOMETRICS_API = "Biometrics API User"

DEFAULT_ROLES = (
    ROLE_SUPER_ADMIN,
    ROLE_HR_ADMIN,
    ROLE_PAYROLL_ADMIN,
    ROLE_MANAGER,
    ROLE_EMPLOYEE,
    ROLE_BIOMETRICS_API,
)

ADMIN_ROLES = (
    ROLE_SUPER_ADMIN,
    ROLE_HR_ADMIN,
)

USER_ADMIN_ROLES = (
    ROLE_SUPER_ADMIN,
    ROLE_HR_ADMIN,
)

PERMISSION_MATRIX = {
    ROLE_SUPER_ADMIN: (
        ("dashboard", "view"),
        ("users", "manage"),
        ("employees", "manage"),
        ("departments", "manage"),
        ("positions", "manage"),
        ("reports", "view"),
        ("attendance", "view"),
        ("leave", "approve"),
        ("payroll", "manage"),
        ("biometrics", "ingest"),
    ),
    ROLE_HR_ADMIN: (
        ("dashboard", "view"),
        ("users", "manage"),
        ("employees", "manage"),
        ("departments", "manage"),
        ("positions", "manage"),
        ("reports", "view"),
        ("attendance", "view"),
        ("leave", "approve"),
    ),
    ROLE_PAYROLL_ADMIN: (
        ("dashboard", "view"),
        ("payroll", "manage"),
        ("reports", "view"),
        ("employees", "view"),
    ),
    ROLE_MANAGER: (
        ("dashboard", "view"),
        ("employees", "view"),
        ("attendance", "view"),
        ("leave", "approve"),
    ),
    ROLE_EMPLOYEE: (
        ("dashboard", "view"),
        ("employees", "view"),
        ("leave", "view"),
    ),
    ROLE_BIOMETRICS_API: (
        ("biometrics", "ingest"),
    ),
}
