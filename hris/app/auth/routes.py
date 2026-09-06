from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import bp
from .forms import ChangePasswordForm, ForgotPasswordForm, LoginForm, ProfileUpdateRequestForm, ResetPasswordForm
from .services import (
    authenticate_user,
    change_user_password,
    create_profile_update_request,
    list_profile_update_requests,
    pending_profile_update_request_for_user,
    profile_request_field_labels,
    verify_password_reset_token,
)
from ..models import EmployeeShift
from ..models import User
from ..utils.menu_access import access_summary_for_user, first_accessible_endpoint, list_access_requests, user_has_menu_access
from ..utils.mailer import send_password_reset_email


def post_login_redirect(user, next_url=None):
    if next_url:
        return next_url
    if user.role and user.role.name == "Employee" and user.employee_id:
        if user_has_menu_access(user, "my_workspace"):
            return url_for("experience.workspace")
        if user_has_menu_access(user, "attendance"):
            return url_for("attendance.my_logs")
    first_endpoint = first_accessible_endpoint(user)
    if first_endpoint:
        return url_for(first_endpoint)
    return url_for("admin.dashboard")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate_user(form.username.data, form.password.data)
        if user:
            login_user(user, remember=form.remember_me.data)
            if user.force_password_change:
                flash("Please update your password before continuing.", "warning")
                return redirect(url_for("auth.change_password"))
            next_url = request.args.get("next")
            flash("Welcome back.", "success")
            return redirect(post_login_redirect(user, next_url))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html", form=form)


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(post_login_redirect(current_user))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower(), is_active=True).first()
        if user:
            send_password_reset_email(user)
        flash("If that email exists in HRIS, a password reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password_with_token(token: str):
    if current_user.is_authenticated:
        return redirect(post_login_redirect(current_user))

    user = verify_password_reset_token(token)
    if not user:
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        change_user_password(user, form.new_password.data, require_change=False)
        flash("Your password has been reset successfully. You can sign in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            change_user_password(current_user, form.new_password.data, require_change=False)
            flash("Password updated successfully.", "success")
            return redirect(post_login_redirect(current_user))

    return render_template("auth/change_password.html", form=form)


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    active_shift = None
    if current_user.employee_id:
        active_shift = (
            EmployeeShift.query.filter_by(employee_id=current_user.employee_id, end_date=None)
            .order_by(EmployeeShift.effective_date.desc())
            .first()
        )

    user_requests = [item for item in list_access_requests() if item.user_id == current_user.id][:5]
    profile_update_form = ProfileUpdateRequestForm()
    pending_profile_request = pending_profile_update_request_for_user(current_user)

    if request.method == "GET" and current_user.employee:
        profile_update_form.birthdate.data = current_user.employee.birthdate
        profile_update_form.gender.data = current_user.employee.gender or ""
        profile_update_form.civil_status.data = current_user.employee.civil_status or ""
        profile_update_form.address.data = current_user.employee.address or ""
        profile_update_form.emergency_contact_name.data = current_user.employee.emergency_contact_name or ""

    if profile_update_form.validate_on_submit():
        try:
            create_profile_update_request(current_user, profile_update_form)
            flash("Your profile update request was submitted for verification.", "success")
            return redirect(url_for("auth.profile"))
        except ValueError as exc:
            flash(str(exc), "warning")

    return render_template(
        "auth/profile.html",
        active_shift=active_shift,
        access_summary=access_summary_for_user(current_user),
        access_requests=user_requests,
        profile_update_form=profile_update_form,
        profile_update_requests=list_profile_update_requests(user_id=current_user.id, limit=5),
        pending_profile_request=pending_profile_request,
        profile_request_field_labels=profile_request_field_labels(),
    )
