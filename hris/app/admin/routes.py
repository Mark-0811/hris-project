from flask import abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from . import bp
from .forms import AnnouncementForm, ResetPasswordForm, UserBulkImportForm, UserForm
from .services import (
    get_bulk_action_panel,
    get_api_endpoint_catalog,
    get_dashboard_context,
    get_dashboard_cards,
    get_leave_sla_summary,
    get_task_inbox,
    list_announcements,
    list_employee_choices,
    list_user_notifications,
    mark_notifications_read,
    list_roles,
    list_users,
    list_user_notifications,
    reset_user_password,
    save_announcement,
    save_user,
    serialize_notification,
    toggle_user_active,
    unread_notification_count,
)
from ..auth.services import list_profile_update_requests, profile_request_changes, review_profile_update_request
from ..extensions import db
from ..models import Announcement, EmployeeProfileUpdateRequest, MenuAccessRequest, MenuAccessTemplate, Notification, User
from ..utils.constants import ROLE_SUPER_ADMIN, USER_ADMIN_ROLES
from ..utils.decorators import role_required
from ..utils.menu_access import (
    access_request_menu_keys,
    apply_template_to_user,
    build_manageable_menu_sections,
    bulk_apply_template,
    create_access_request,
    create_menu_access_template,
    emergency_lock_user,
    get_user_menu_keys,
    list_access_requests,
    list_menu_access_templates,
    recent_menu_audit_logs,
    recommended_menu_keys_for_user,
    review_access_request,
    save_user_menu_access,
    template_menu_keys,
    dormant_access_rows,
)
from ..utils.excel_bulk import build_user_import_template, parse_user_import


def populate_user_form_choices(form):
    form.role_id.choices = [(role.id, role.name) for role in list_roles()]
    form.employee_id.choices = [(0, "Not linked")] + [
        (employee.id, f"{employee.employee_code} - {employee.full_name}")
        for employee in list_employee_choices()
    ]


def can_manage_api_access() -> bool:
    return bool(current_user.role and current_user.role.name == ROLE_SUPER_ADMIN)


@bp.route("/")
@login_required
def dashboard():
    dashboard_context = get_dashboard_context(current_user)
    return render_template(
        "dashboard/index.html",
        dashboard_context=dashboard_context,
        cards=dashboard_context["cards"],
        announcements=list_announcements(limit=5),
    )


@bp.route("/tasks")
@login_required
def tasks():
    status_filter = (request.args.get("status") or "all").strip()
    if status_filter not in {"all", "needs_action", "waiting", "done_today"}:
        status_filter = "all"
    items = get_task_inbox(current_user, status_filter=status_filter)
    return render_template(
        "admin/tasks/index.html",
        tasks=items,
        status_filter=status_filter,
        sla_summary=get_leave_sla_summary(),
    )


@bp.route("/bulk-actions")
@login_required
@role_required(*USER_ADMIN_ROLES)
def bulk_actions():
    return render_template(
        "admin/bulk_actions/index.html",
        actions=get_bulk_action_panel(current_user),
    )


@bp.route("/users")
@login_required
@role_required(*USER_ADMIN_ROLES)
def users():
    return render_template("admin/users/index.html", users=list_users())


@bp.route("/users/import/template")
@login_required
@role_required(*USER_ADMIN_ROLES)
def download_user_import_template():
    return send_file(
        build_user_import_template(),
        as_attachment=True,
        download_name="hris_user_import_template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/users/import", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def import_users():
    form = UserBulkImportForm()
    result = None
    if form.validate_on_submit():
        result = parse_user_import(form.workbook.data, actor_user_id=current_user.id)
        flash(
            f"User import completed. Created {result.created} user(s), {len(result.errors)} issue(s).",
            "success" if not result.errors else "warning",
        )
    return render_template(
        "admin/users/bulk_import.html",
        form=form,
        result=result,
        page_title="Import User Access",
        modal_intro="Upload an Excel file to bulk-create user accounts and access assignments.",
        template_url=url_for("admin.download_user_import_template"),
        cancel_url=url_for("admin.users"),
    )


@bp.route("/users/create", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def create_user():
    form = UserForm()
    populate_user_form_choices(form)
    if not can_manage_api_access():
        form.can_access_api.data = False
    if form.validate_on_submit():
        if not form.password.data:
            form.password.errors.append("Temporary password is required.")
        elif User.query.filter_by(username=form.username.data.strip()).first():
            form.username.errors.append("Username is already in use.")
        elif User.query.filter_by(email=form.email.data.strip().lower()).first():
            form.email.errors.append("Email is already in use.")
        elif form.employee_id.data and User.query.filter_by(employee_id=form.employee_id.data).first():
            form.employee_id.errors.append("This employee is already linked to another user.")
        else:
            save_user(form, allow_manage_api_access=can_manage_api_access())
            flash("User account created successfully.", "success")
            return redirect(url_for("admin.users"))
    return render_template(
        "admin/users/form.html",
        form=form,
        page_title="Create User",
        can_manage_api_access=can_manage_api_access(),
    )


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def edit_user(user_id: int):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    populate_user_form_choices(form)
    if not form.is_submitted():
        form.role_id.data = user.role_id
        form.employee_id.data = user.employee_id or 0
        form.can_access_api.data = user.can_access_api
    elif not can_manage_api_access():
        form.can_access_api.data = user.can_access_api

    if form.validate_on_submit():
        existing_username = User.query.filter(
            User.username == form.username.data.strip(), User.id != user.id
        ).first()
        existing_email = User.query.filter(
            User.email == form.email.data.strip().lower(), User.id != user.id
        ).first()
        if existing_username:
            form.username.errors.append("Username is already in use.")
        elif existing_email:
            form.email.errors.append("Email is already in use.")
        elif form.employee_id.data and User.query.filter(
            User.employee_id == form.employee_id.data, User.id != user.id
        ).first():
            form.employee_id.errors.append("This employee is already linked to another user.")
        else:
            save_user(form, user=user, allow_manage_api_access=can_manage_api_access())
            flash("User account updated successfully.", "success")
            return redirect(url_for("admin.users"))

    return render_template(
        "admin/users/form.html",
        form=form,
        page_title="Edit User",
        user=user,
        can_manage_api_access=can_manage_api_access(),
    )


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def toggle_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account while you are logged in.", "warning")
        return redirect(url_for("admin.users"))
    new_state = toggle_user_active(user)
    flash(f"User {'activated' if new_state else 'deactivated'} successfully.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def reset_password(user_id: int):
    user = User.query.get_or_404(user_id)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        reset_user_password(user, form.password.data, form.force_password_change.data)
        flash("Password reset successfully.", "success")
        return redirect(url_for("admin.users"))

    return render_template(
        "admin/users/reset_password.html",
        form=form,
        user=user,
        page_title="Reset Password",
    )


@bp.route("/users/<int:user_id>/menus", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def manage_user_menus(user_id: int):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        action = (request.form.get("menu_action") or "save").strip()
        if action == "reset_recommended":
            save_user_menu_access(user, recommended_menu_keys_for_user(user))
            flash("Menu access reset to the recommended set for this role.", "success")
        elif action == "clear_all":
            save_user_menu_access(user, [])
            flash("All menu access has been cleared for this user.", "success")
        elif action == "request_access":
            create_access_request(user, request.form.getlist("menu_keys"), request.form.get("request_reason") or "")
            flash("Access request submitted for review.", "success")
        elif action == "emergency_lock":
            emergency_lock_user(user, current_user.id)
            flash("Emergency lock applied. This user now has profile-only access.", "warning")
        else:
            save_user_menu_access(user, request.form.getlist("menu_keys"))
            flash("Menu access updated successfully.", "success")
        return redirect(url_for("admin.users"))

    return render_template(
        "admin/users/menus.html",
        user=user,
        menu_sections=build_manageable_menu_sections(),
        selected_menu_keys=get_user_menu_keys(user),
        recommended_menu_keys=set(recommended_menu_keys_for_user(user)),
        page_title="Manage Menu Access",
    )


@bp.route("/users/access-governance", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def access_governance():
    if request.method == "POST":
        action = (request.form.get("access_action") or "").strip()
        if action == "create_template":
            create_menu_access_template(
                (request.form.get("template_name") or "").strip(),
                (request.form.get("template_description") or "").strip(),
                (request.form.get("template_role_name") or "").strip(),
                request.form.getlist("template_menu_keys"),
                current_user.id,
            )
            flash("Access template saved.", "success")
            return redirect(url_for("admin.access_governance"))
        if action == "apply_template":
            template_id_raw = (request.form.get("template_id") or "").strip()
            target_user_id_raw = (request.form.get("target_user_id") or "").strip()
            expires_in_days_raw = (request.form.get("expires_in_days") or "").strip()
            expires_in_days = int(expires_in_days_raw) if expires_in_days_raw.isdigit() else None
            if target_user_id_raw.isdigit() and template_id_raw.isdigit():
                target_user = db.session.get(User, int(target_user_id_raw))
                template = db.session.get(MenuAccessTemplate, int(template_id_raw))
                if target_user and template:
                    apply_template_to_user(target_user, template, current_user.id, expires_in_days=expires_in_days)
                    flash("Template applied to user.", "success")
            return redirect(url_for("admin.access_governance"))
        if action == "bulk_apply":
            template_id_raw = (request.form.get("bulk_template_id") or "").strip()
            role_name = (request.form.get("bulk_role_name") or "").strip() or None
            source_user_id_raw = (request.form.get("source_user_id") or "").strip()
            updated = bulk_apply_template(
                int(template_id_raw) if template_id_raw.isdigit() else 0,
                actor_user_id=current_user.id,
                role_name=role_name,
                source_user_id=int(source_user_id_raw) if source_user_id_raw.isdigit() else None,
            )
            flash(f"Bulk access update applied to {updated} user(s).", "success")
            return redirect(url_for("admin.access_governance"))

    return render_template(
        "admin/users/access_governance.html",
        page_title="Access Governance",
        templates=list_menu_access_templates(),
        menu_sections=build_manageable_menu_sections(),
        users=list_users(),
        access_requests=list_access_requests(),
        profile_update_requests=list_profile_update_requests(),
        audit_logs=recent_menu_audit_logs(),
        dormant_rows=dormant_access_rows(),
        roles=list_roles(),
        template_menu_keys=template_menu_keys,
        request_menu_keys=access_request_menu_keys,
        profile_request_changes=profile_request_changes,
    )


@bp.route("/users/access-requests/<int:request_id>/review", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def approve_access_request(request_id: int):
    request_obj = db.session.get(MenuAccessRequest, request_id)
    if request_obj is None:
        abort(404)
    if request.method == "GET":
        decision = (request.args.get("decision") or "approve").strip().lower()
        if decision not in {"approve", "reject"}:
            decision = "approve"
        return render_template(
            "confirm_action.html",
            page_title="Confirm Access Request Review",
            modal_intro="Review this access request before applying the final decision.",
            confirm_heading=f"{'Approve' if decision == 'approve' else 'Reject'} access request",
            confirm_message=f"You are about to {decision} this access request. Continue?",
            confirm_button_label=f"{'Approve' if decision == 'approve' else 'Reject'} Request",
            form_action=url_for("admin.approve_access_request", request_id=request_id),
            hidden_fields={"decision": decision},
            cancel_url=url_for("admin.access_governance"),
        )
    approved = (request.form.get("decision") or "").strip() == "approve"
    review_access_request(
        request_obj,
        current_user.id,
        approved=approved,
        decision_notes=(request.form.get("decision_notes") or "").strip(),
    )
    flash(f"Access request {'approved' if approved else 'rejected'}.", "success")
    return redirect(url_for("admin.access_governance"))


@bp.route("/users/profile-update-requests/<int:request_id>/review", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def review_profile_request(request_id: int):
    request_obj = db.session.get(EmployeeProfileUpdateRequest, request_id)
    if request_obj is None:
        abort(404)
    if request.method == "GET":
        decision = (request.args.get("decision") or "approve").strip().lower()
        if decision not in {"approve", "reject"}:
            decision = "approve"
        return render_template(
            "confirm_action.html",
            page_title="Confirm Profile Update Review",
            modal_intro="Review the employee profile update request before saving the decision.",
            confirm_heading=f"{'Approve' if decision == 'approve' else 'Reject'} profile update request",
            confirm_message=f"You are about to {decision} this profile update request. Continue?",
            confirm_button_label=f"{'Approve' if decision == 'approve' else 'Reject'} Request",
            form_action=url_for("admin.review_profile_request", request_id=request_id),
            hidden_fields={"decision": decision},
            cancel_url=url_for("admin.access_governance"),
        )
    approved = (request.form.get("decision") or "").strip() == "approve"
    review_profile_update_request(
        request_obj,
        current_user,
        approved=approved,
        decision_notes=(request.form.get("decision_notes") or "").strip(),
    )
    flash(f"Profile update request {'approved' if approved else 'rejected'}.", "success")
    return redirect(url_for("admin.access_governance"))


@bp.route("/news")
@login_required
@role_required(*USER_ADMIN_ROLES)
def news():
    return render_template("admin/news/index.html", announcements=list_announcements())


@bp.route("/news/create", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def create_news():
    form = AnnouncementForm()
    if form.validate_on_submit():
        save_announcement(form, current_user.id)
        flash("News published successfully.", "success")
        return redirect(url_for("admin.news"))
    return render_template("admin/news/form.html", form=form, page_title="Post News")


@bp.route("/news/<int:announcement_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def edit_news(announcement_id: int):
    announcement = Announcement.query.get_or_404(announcement_id)
    form = AnnouncementForm(obj=announcement)
    if form.validate_on_submit():
        save_announcement(form, current_user.id, announcement=announcement)
        flash("News updated successfully.", "success")
        return redirect(url_for("admin.news"))
    return render_template(
        "admin/news/form.html",
        form=form,
        page_title="Edit News",
        announcement=announcement,
    )


@bp.route("/notifications")
@login_required
def notifications():
    mark_notifications_read(current_user)
    items = list_user_notifications(current_user)
    return render_template("admin/notifications/index.html", notifications=items)


@bp.route("/notifications/live")
@login_required
def notifications_live():
    from ..chat.services import unread_chat_count_for_user

    items = list_user_notifications(current_user, limit=5, unread_only=True)
    return jsonify(
        {
            "count": unread_notification_count(current_user),
            "items": [serialize_notification(item) for item in items],
            "chat_count": unread_chat_count_for_user(current_user),
        }
    )


@bp.route("/api-requests")
@login_required
@role_required(ROLE_SUPER_ADMIN)
def api_requests():
    return render_template(
        "admin/api_requests/index.html",
        endpoint_groups=get_api_endpoint_catalog(),
    )
