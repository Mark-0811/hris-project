import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
ENV_FILE = BASE_DIR.parent / ".env"

load_dotenv(ENV_FILE)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-env")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'hris.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    BIOMETRIC_API_TOKEN = os.getenv("BIOMETRIC_API_TOKEN", "change-biometric-token")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "HRIS Bot")
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "false").lower() == "true"
    UPLOAD_FOLDER = str(INSTANCE_DIR / "uploads")
    FIRST_SUPERADMIN_USERNAME = os.getenv("FIRST_SUPERADMIN_USERNAME", "superadmin")
    FIRST_SUPERADMIN_EMAIL = os.getenv("FIRST_SUPERADMIN_EMAIL", "admin@example.com")
    FIRST_SUPERADMIN_PASSWORD = os.getenv("FIRST_SUPERADMIN_PASSWORD", "ChangeMe123!")
    SECURITY_CAMERA_INDEX = int(os.getenv("SECURITY_CAMERA_INDEX", "0"))
    SECURITY_CAMERA_NAME = os.getenv("SECURITY_CAMERA_NAME", "usb_cam_0")
    SECURITY_CAPTURE_INTERVAL_SECONDS = float(os.getenv("SECURITY_CAPTURE_INTERVAL_SECONDS", "2.0"))
    SECURITY_FACE_MATCH_THRESHOLD = float(os.getenv("SECURITY_FACE_MATCH_THRESHOLD", "0.84"))
    SECURITY_BODY_MATCH_THRESHOLD = float(os.getenv("SECURITY_BODY_MATCH_THRESHOLD", "0.80"))
    SECURITY_ALERT_COOLDOWN_SECONDS = int(os.getenv("SECURITY_ALERT_COOLDOWN_SECONDS", "120"))
    SECURITY_ALERT_EMAILS = os.getenv("SECURITY_ALERT_EMAILS", "")
    SECURITY_ALERT_SMS = os.getenv("SECURITY_ALERT_SMS", "")
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
    MOBILE_ACCESS_TOKEN_HOURS = int(os.getenv("MOBILE_ACCESS_TOKEN_HOURS", "8"))
    MOBILE_REFRESH_TOKEN_DAYS = int(os.getenv("MOBILE_REFRESH_TOKEN_DAYS", "30"))
    MOBILE_WEBVIEW_BRIDGE_MINUTES = int(os.getenv("MOBILE_WEBVIEW_BRIDGE_MINUTES", "10"))
    MOBILE_FCM_ENABLED = os.getenv("MOBILE_FCM_ENABLED", "false").lower() == "true"
    AI_ASSISTANT_ENABLED = os.getenv("AI_ASSISTANT_ENABLED", "true").lower() == "true"
    AI_ASSISTANT_API_KEY = os.getenv("AI_ASSISTANT_API_KEY", "")
    AI_ASSISTANT_MODEL = os.getenv("AI_ASSISTANT_MODEL", "gpt-4o-mini")
    AI_ASSISTANT_EMAIL = os.getenv("AI_ASSISTANT_EMAIL", "ai-assistant@hris.local")
    AI_ASSISTANT_AUTOMATION_ENABLED = os.getenv("AI_ASSISTANT_AUTOMATION_ENABLED", "true").lower() == "true"
    AI_ASSISTANT_SYSTEM_PROMPT = os.getenv(
        "AI_ASSISTANT_SYSTEM_PROMPT",
        "You are an internal HR assistant for employees. Keep responses concise, accurate, and policy-friendly.",
    )


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
