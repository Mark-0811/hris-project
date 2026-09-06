from ..extensions import db
from .base import TimestampMixin


class ChatThread(TimestampMixin, db.Model):
    __tablename__ = "chat_threads"

    id = db.Column(db.Integer, primary_key=True)
    employee_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    employee_user = db.relationship("User", foreign_keys=[employee_user_id], back_populates="chat_thread")
    messages = db.relationship(
        "ChatMessage",
        back_populates="thread",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
    )


class ChatMessage(TimestampMixin, db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("chat_threads.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    attachment_filename = db.Column(db.String(255))
    attachment_original_name = db.Column(db.String(255))
    attachment_mime_type = db.Column(db.String(255))
    is_read_by_employee = db.Column(db.Boolean, default=False, nullable=False)
    is_read_by_admin = db.Column(db.Boolean, default=False, nullable=False)

    thread = db.relationship("ChatThread", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="chat_messages")
