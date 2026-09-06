from ..extensions import db
from .base import TimestampMixin


class Employee(TimestampMixin, db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100), nullable=False)
    suffix = db.Column(db.String(20))
    birthdate = db.Column(db.Date)
    gender = db.Column(db.String(20))
    civil_status = db.Column(db.String(20))
    address = db.Column(db.Text)
    contact_number = db.Column(db.String(30))
    personal_email = db.Column(db.String(255))
    company_email = db.Column(db.String(255))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    position_id = db.Column(db.Integer, db.ForeignKey("positions.id"))
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    employment_type = db.Column(db.String(50))
    date_hired = db.Column(db.Date, nullable=False)
    date_regularized = db.Column(db.Date)
    employment_status = db.Column(db.String(50), default="active", nullable=False)
    sss_no = db.Column(db.String(40))
    tin_no = db.Column(db.String(40))
    philhealth_no = db.Column(db.String(40))
    pagibig_no = db.Column(db.String(40))
    profile_image = db.Column(db.String(255))
    emergency_contact_name = db.Column(db.String(150))
    emergency_contact_number = db.Column(db.String(30))
    badge_id = db.Column(db.String(50), unique=True)
    nfc_uid = db.Column(db.String(120), unique=True)

    department = db.relationship(
        "Department", back_populates="employees", foreign_keys=[department_id]
    )
    position = db.relationship("Position", back_populates="employees")
    manager = db.relationship("Employee", remote_side=[id], foreign_keys=[manager_id], backref="direct_reports")
    user = db.relationship("User", back_populates="employee", uselist=False)
    salaries = db.relationship("EmployeeSalary", back_populates="employee", lazy="dynamic")
    leave_balances = db.relationship("LeaveBalance", back_populates="employee", lazy="dynamic")
    leave_requests = db.relationship("LeaveRequest", back_populates="employee", lazy="dynamic")
    biometric_logs = db.relationship("BiometricLog", back_populates="employee", lazy="dynamic")
    attendance_records = db.relationship(
        "AttendanceRecord", back_populates="employee", lazy="dynamic"
    )
    shift_assignments = db.relationship(
        "EmployeeShift",
        back_populates="employee",
        lazy="dynamic",
        order_by="desc(EmployeeShift.effective_date)",
    )

    @property
    def full_name(self) -> str:
        return " ".join(
            filter(None, [self.first_name, self.middle_name, self.last_name, self.suffix])
        )

    @property
    def status_label(self) -> str:
        return self.employment_status.replace("_", " ").title()
