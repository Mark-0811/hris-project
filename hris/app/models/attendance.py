from ..extensions import db
from .base import TimestampMixin


class Shift(TimestampMixin, db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    shift_name = db.Column(db.String(120), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    grace_period_minutes = db.Column(db.Integer, default=0, nullable=False)
    break_start = db.Column(db.Time)
    break_end = db.Column(db.Time)
    is_flexible = db.Column(db.Boolean, default=False, nullable=False)

    employee_shifts = db.relationship("EmployeeShift", back_populates="shift", lazy="dynamic")


class EmployeeShift(TimestampMixin, db.Model):
    __tablename__ = "employee_shifts"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=False)
    effective_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)

    shift = db.relationship("Shift", back_populates="employee_shifts")
    employee = db.relationship("Employee", back_populates="shift_assignments")


class Holiday(TimestampMixin, db.Model):
    __tablename__ = "holidays"

    id = db.Column(db.Integer, primary_key=True)
    holiday_name = db.Column(db.String(120), nullable=False)
    date = db.Column(db.Date, nullable=False, unique=True)
    holiday_type = db.Column(db.String(50), nullable=False)


class AttendanceRecord(TimestampMixin, db.Model):
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    time_in = db.Column(db.DateTime)
    time_out = db.Column(db.DateTime)
    break_in = db.Column(db.DateTime)
    break_out = db.Column(db.DateTime)
    late_minutes = db.Column(db.Integer, default=0, nullable=False)
    undertime_minutes = db.Column(db.Integer, default=0, nullable=False)
    overtime_minutes = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(40), default="pending", nullable=False)
    remarks = db.Column(db.Text)

    employee = db.relationship("Employee", back_populates="attendance_records")
    adjustments = db.relationship(
        "AttendanceAdjustment", back_populates="attendance_record", lazy="dynamic"
    )


class AttendanceAdjustment(TimestampMixin, db.Model):
    __tablename__ = "attendance_adjustments"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    attendance_record_id = db.Column(
        db.Integer, db.ForeignKey("attendance_records.id"), nullable=False
    )
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reason = db.Column(db.Text, nullable=False)
    old_time_in = db.Column(db.DateTime)
    new_time_in = db.Column(db.DateTime)
    old_time_out = db.Column(db.DateTime)
    new_time_out = db.Column(db.DateTime)
    status = db.Column(db.String(40), default="pending", nullable=False)

    attendance_record = db.relationship("AttendanceRecord", back_populates="adjustments")
