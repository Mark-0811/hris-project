from ..extensions import db
from .base import TimestampMixin


class PayrollCutoff(TimestampMixin, db.Model):
    __tablename__ = "payroll_cutoffs"

    id = db.Column(db.Integer, primary_key=True)
    cutoff_name = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(40), default="open", nullable=False)

    entries = db.relationship("PayrollEntry", back_populates="cutoff", lazy="dynamic")


class EmployeeSalary(TimestampMixin, db.Model):
    __tablename__ = "employee_salary"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    basic_salary = db.Column(db.Numeric(12, 2), nullable=False)
    daily_rate = db.Column(db.Numeric(12, 2))
    hourly_rate = db.Column(db.Numeric(12, 2))
    effective_date = db.Column(db.Date, nullable=False)

    employee = db.relationship("Employee", back_populates="salaries")


class Allowance(TimestampMixin, db.Model):
    __tablename__ = "allowances"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    allowance_type = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    taxable = db.Column(db.Boolean, default=False, nullable=False)
    effective_date = db.Column(db.Date, nullable=False)

    employee = db.relationship("Employee")


class Deduction(TimestampMixin, db.Model):
    __tablename__ = "deductions"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    deduction_type = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    effective_date = db.Column(db.Date, nullable=False)

    employee = db.relationship("Employee")


class PayrollEntry(TimestampMixin, db.Model):
    __tablename__ = "payroll_entries"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    cutoff_id = db.Column(db.Integer, db.ForeignKey("payroll_cutoffs.id"), nullable=False)
    basic_pay = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    overtime_pay = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    late_deduction = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    undertime_deduction = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    allowance_total = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    deduction_total = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    net_pay = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    status = db.Column(db.String(40), default="draft", nullable=False)

    employee = db.relationship("Employee")
    cutoff = db.relationship("PayrollCutoff", back_populates="entries")
