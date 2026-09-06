from datetime import datetime
import secrets

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from flask import url_for

from ..extensions import db, login_manager
from .base import TimestampMixin


class Role(TimestampMixin, db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))

    users = db.relationship("User", back_populates="role", lazy="dynamic")
    permissions = db.relationship("RolePermission", back_populates="role", lazy="dynamic")


class Permission(TimestampMixin, db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    module = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(80), nullable=False)

    roles = db.relationship("RolePermission", back_populates="permission", lazy="dynamic")


class RolePermission(db.Model):
    __tablename__ = "role_permissions"
    __table_args__ = (
        db.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), nullable=False)

    role = db.relationship("Role", back_populates="permissions")
    permission = db.relationship("Permission", back_populates="roles")


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    photo_filename = db.Column(db.String(255))
    api_token = db.Column(db.String(255), unique=True)
    can_access_api = db.Column(db.Boolean, default=False, nullable=False)
    menu_access_initialized = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    force_password_change = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime)

    role = db.relationship("Role", back_populates="users")
    employee = db.relationship("Employee", back_populates="user")
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic")
    chat_thread = db.relationship("ChatThread", back_populates="employee_user", uselist=False)
    chat_messages = db.relationship("ChatMessage", back_populates="sender", lazy="dynamic")
    menu_accesses = db.relationship(
        "UserMenuAccess",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="UserMenuAccess.user_id",
    )

    @property
    def display_name(self) -> str:
        if self.employee:
            return self.employee.full_name
        return self.username

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def mark_login(self) -> None:
        self.last_login = datetime.utcnow()

    @property
    def is_super_admin(self) -> bool:
        return bool(self.role and self.role.name == "Super Admin")

    def ensure_api_token(self) -> str:
        if not self.api_token:
            self.api_token = secrets.token_urlsafe(32)
        return self.api_token

    def revoke_api_token(self) -> None:
        self.api_token = None

    @property
    def photo_url(self) -> str | None:
        if not self.photo_filename:
            return None
        return url_for("static", filename=f"uploads/users/{self.photo_filename}")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class UserMenuAccess(TimestampMixin, db.Model):
    __tablename__ = "user_menu_access"
    __table_args__ = (
        db.UniqueConstraint("user_id", "menu_key", name="uq_user_menu_access_user_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    menu_key = db.Column(db.String(120), nullable=False, index=True)
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    expires_at = db.Column(db.DateTime, index=True)
    last_seen_at = db.Column(db.DateTime, index=True)

    user = db.relationship("User", back_populates="menu_accesses", foreign_keys=[user_id])


class MenuAccessTemplate(TimestampMixin, db.Model):
    __tablename__ = "menu_access_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(255))
    role_name = db.Column(db.String(80))
    menu_keys_json = db.Column(db.Text, nullable=False, default="[]")
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))


class MenuAccessRequest(TimestampMixin, db.Model):
    __tablename__ = "menu_access_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    requested_menu_keys_json = db.Column(db.Text, nullable=False, default="[]")
    reason = db.Column(db.Text)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    decision_notes = db.Column(db.Text)


class EmployeeProfileUpdateRequest(TimestampMixin, db.Model):
    __tablename__ = "employee_profile_update_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    requested_data_json = db.Column(db.Text, nullable=False, default="{}")
    reason = db.Column(db.Text)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    decision_notes = db.Column(db.Text)

    user = db.relationship("User", foreign_keys=[user_id])
    employee = db.relationship("Employee", foreign_keys=[employee_id])
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
