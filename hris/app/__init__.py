from pathlib import Path

from flask import Flask, g, render_template, request
from flask_login import current_user

from .admin import bp as admin_bp
from .attendance import bp as attendance_bp
from .chat import bp as chat_bp
from .auth import bp as auth_bp
from .biometrics import bp as biometrics_bp
from .config import config_by_name
from .employees import bp as employees_bp
from .enterprise import bp as enterprise_bp
from .experience import bp as experience_bp
from .extensions import csrf, db, login_manager, mail, migrate, socketio
from .leave import bp as leave_bp
from .mobile import bp as mobile_bp
from .payroll import bp as payroll_bp
from .reports import bp as reports_bp
from .security import bp as security_bp
from .seed import register_seed_commands
from .chat.socket_events import register_chat_socket_handlers
from .attendance.socket_events import register_socket_handlers


def create_app(config_name: str = "development") -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[config_name])
    app.config["CONFIG_NAME"] = config_name
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"], "users").mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"], "chat").mkdir(parents=True, exist_ok=True)
    Path(app.static_folder, "uploads", "security", "events").mkdir(parents=True, exist_ok=True)
    Path(app.static_folder, "uploads", "security", "profiles").mkdir(parents=True, exist_ok=True)

    register_extensions(app)
    register_blueprints(app)
    register_error_handlers(app)
    register_shell_context(app)
    register_cli_commands(app)

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)
    register_socket_handlers(socketio)
    register_chat_socket_handlers(socketio)


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(biometrics_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(mobile_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(enterprise_bp)
    app.register_blueprint(experience_bp)
    app.register_blueprint(security_bp)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404


def register_shell_context(app: Flask) -> None:
    from . import models
    from .admin.services import list_announcements, list_user_notifications, unread_notification_count
    from .chat.services import unread_chat_count_for_user
    from .utils.menu_access import (
        MENU_BY_KEY,
        PROTECTED_ENDPOINTS,
        access_summary_for_user,
        build_sidebar_sections,
        can_access_endpoint,
        record_menu_access,
        user_has_menu_access,
    )

    @app.shell_context_processor
    def shell_context():
        return {"db": db, "models": models}

    @app.context_processor
    def inject_navigation_context():
        return {
            "nav_notifications": list_user_notifications(current_user, limit=5, unread_only=True),
            "nav_notification_count": unread_notification_count(current_user),
            "nav_announcements": list_announcements(limit=5),
            "nav_chat_count": unread_chat_count_for_user(current_user),
            "nav_has_chat_access": user_has_menu_access(current_user, "messages"),
            "sidebar_sections": build_sidebar_sections(current_user, request.endpoint),
            "can_access_endpoint": lambda endpoint: can_access_endpoint(current_user, endpoint),
            "profile_access_summary": access_summary_for_user(current_user) if getattr(current_user, "is_authenticated", False) else {},
        }

    @app.before_request
    def enforce_navigation_access():
        if request.blueprint == "mobile":
            return None
        if not getattr(current_user, "is_authenticated", False):
            return None
        if not can_access_endpoint(current_user, request.endpoint):
            required_menu_keys = PROTECTED_ENDPOINTS.get(request.endpoint, ())
            g.access_denied_context = {
                "endpoint": request.endpoint,
                "required_labels": [MENU_BY_KEY[key]["label"] for key in required_menu_keys if key in MENU_BY_KEY],
            }
            return render_template("403.html"), 403
        record_menu_access(request.endpoint, current_user)
        return None


def register_cli_commands(app: Flask) -> None:
    register_seed_commands(app)
    register_data_sync_commands(app)


def register_data_sync_commands(app: Flask) -> None:
    import click
    from sqlalchemy import MetaData, create_engine, text

    @app.cli.command("sync-sqlite-to-postgres")
    @click.option("--sqlite-path", default=str(Path(app.instance_path) / "hris.db"), help="Path to the source SQLite database.")
    @click.option("--postgres-url", default=None, help="Target PostgreSQL URL. Defaults to DATABASE_URL.")
    def sync_sqlite_to_postgres(sqlite_path: str, postgres_url: str | None) -> None:
        """Copy the current SQLite data set into PostgreSQL using SQLAlchemy."""

        target_url = postgres_url or app.config["SQLALCHEMY_DATABASE_URI"]
        if not target_url.startswith("postgresql"):
            raise click.ClickException("Target database must be a PostgreSQL URL.")

        source_engine = create_engine(f"sqlite:///{sqlite_path}")
        target_engine = create_engine(target_url)

        source_metadata = MetaData()
        target_metadata = MetaData()
        source_metadata.reflect(bind=source_engine)
        target_metadata.reflect(bind=target_engine)

        preferred_order = [
            "biometric_devices",
            "permissions",
            "roles",
            "shifts",
            "holidays",
            "leave_types",
            "payroll_cutoffs",
            "departments",
            "positions",
            "employees",
            "role_permissions",
            "users",
            "announcements",
            "notifications",
            "person_profiles",
            "intruder_profiles",
            "detection_events",
            "alert_events",
            "audit_logs",
            "allowances",
            "deductions",
            "employee_salary",
            "employee_shifts",
            "attendance_records",
            "biometric_logs",
            "attendance_adjustments",
            "leave_balances",
            "leave_requests",
            "payroll_entries",
        ]
        available_shared_tables = [
            table_name
            for table_name in source_metadata.tables.keys()
            if table_name in target_metadata.tables and table_name != "alembic_version"
        ]
        shared_table_names = [table_name for table_name in preferred_order if table_name in available_shared_tables]
        shared_table_names.extend(
            table_name for table_name in available_shared_tables if table_name not in shared_table_names
        )
        if not shared_table_names:
            raise click.ClickException("No shared tables found between SQLite and PostgreSQL.")

        with target_engine.begin() as target_conn, source_engine.connect() as source_conn:
            target_conn.execute(text("SET session_replication_role = replica"))
            try:
                for table_name in reversed(shared_table_names):
                    target_conn.execute(target_metadata.tables[table_name].delete())

                for table_name in shared_table_names:
                    rows = [dict(row._mapping) for row in source_conn.execute(source_metadata.tables[table_name].select())]
                    if rows:
                        target_conn.execute(target_metadata.tables[table_name].insert(), rows)

                for table_name in shared_table_names:
                    table = target_metadata.tables[table_name]
                    if "id" not in table.c:
                        continue
                    target_conn.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                            f"COALESCE((SELECT MAX(id) FROM {table_name}), 1), "
                            f"(SELECT COUNT(*) > 0 FROM {table_name}))"
                        )
                    )
            finally:
                target_conn.execute(text("SET session_replication_role = origin"))

        click.echo(f"Copied {len(shared_table_names)} tables from SQLite into PostgreSQL.")
