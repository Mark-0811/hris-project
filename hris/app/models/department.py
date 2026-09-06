from ..extensions import db
from .base import TimestampMixin


class Department(TimestampMixin, db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(30), unique=True, nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    cost_center = db.Column(db.String(50))
    branch = db.Column(db.String(120))

    manager = db.relationship("Employee", foreign_keys=[manager_id], post_update=True)
    positions = db.relationship("Position", back_populates="department", lazy="dynamic")
    employees = db.relationship(
        "Employee",
        back_populates="department",
        lazy="dynamic",
        foreign_keys="Employee.department_id",
    )


class Position(TimestampMixin, db.Model):
    __tablename__ = "positions"
    __table_args__ = (
        db.UniqueConstraint("department_id", "name", name="uq_position_department_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    description = db.Column(db.Text)

    department = db.relationship("Department", back_populates="positions")
    employees = db.relationship("Employee", back_populates="position", lazy="dynamic")
