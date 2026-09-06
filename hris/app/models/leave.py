from ..extensions import db
from .base import TimestampMixin


class LeaveType(TimestampMixin, db.Model):
    __tablename__ = "leave_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    default_credits = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    is_paid = db.Column(db.Boolean, default=True, nullable=False)
    requires_attachment = db.Column(db.Boolean, default=False, nullable=False)


class LeaveBalance(TimestampMixin, db.Model):
    __tablename__ = "leave_balances"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("leave_types.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    total_credits = db.Column(db.Numeric(10, 2), nullable=False)
    used_credits = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    remaining_credits = db.Column(db.Numeric(10, 2), nullable=False)

    employee = db.relationship("Employee", back_populates="leave_balances")
    leave_type = db.relationship("LeaveType")


class LeaveRequest(TimestampMixin, db.Model):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("leave_types.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    duration_type = db.Column(db.String(20), default="whole_day", nullable=False)
    days = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    attachment = db.Column(db.String(255))
    is_paid = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(db.String(40), default="pending", nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)

    employee = db.relationship("Employee", back_populates="leave_requests")
    leave_type = db.relationship("LeaveType")
    approver = db.relationship("User", foreign_keys=[approved_by])
