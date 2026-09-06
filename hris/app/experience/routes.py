from pathlib import Path

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from . import bp
from .forms import (
    AttendanceCorrectionWizardForm,
    DocumentRequestForm,
    ExitRequestForm,
    MobilePunchForm,
    PrivacyRequestForm,
    SuggestionForm,
    SupportTicketForm,
    SurveyResponseForm,
)
from .services import (
    acknowledge_document,
    cancel_leave_request_for_employee,
    create_support_ticket,
    current_employee,
    document_download_path,
    documents_context,
    exit_context,
    help_center_context,
    learning_context,
    onboarding_context,
    requests_context,
    schedule_context,
    submit_attendance_correction,
    submit_document_request,
    submit_exit_request,
    submit_leave_modification_request,
    submit_mobile_punch,
    submit_privacy_request_for_employee,
    submit_suggestion,
    submit_survey_response,
    surveys_context,
    timeline_context,
    workspace_context,
)
from ..attendance.services import list_employee_attendance_records
from ..leave.forms import LeaveRequestForm
from ..leave.routes import populate_request_form
from ..leave.services import save_leave_request


def _ensure_employee():
    if not current_employee(current_user):
        abort(403)


def _populate_correction_choices(form):
    employee = current_employee(current_user)
    records = list_employee_attendance_records(employee.id) if employee else []
    form.attendance_record_id.choices = [(item.id, f"{item.date} · {item.status.replace('_', ' ').title()}") for item in records]


@bp.route("/")
@login_required
def workspace():
    _ensure_employee()
    return render_template("experience/workspace.html", workspace=workspace_context(current_user))


@bp.route("/schedule", methods=["GET", "POST"])
@login_required
def schedule():
    _ensure_employee()
    punch_form = MobilePunchForm(prefix="punch")
    correction_form = AttendanceCorrectionWizardForm(prefix="correction")
    _populate_correction_choices(correction_form)

    if punch_form.submit.data and punch_form.validate_on_submit():
        try:
            _record, message = submit_mobile_punch(current_user, punch_form)
            flash(message, "success")
            return redirect(url_for("experience.schedule"))
        except ValueError as exc:
            flash(str(exc), "warning")
    elif correction_form.submit.data and correction_form.validate_on_submit():
        try:
            submit_attendance_correction(current_user, correction_form)
            flash("Attendance correction request submitted.", "success")
            return redirect(url_for("experience.schedule"))
        except ValueError as exc:
            flash(str(exc), "warning")

    return render_template(
        "experience/schedule.html",
        schedule=schedule_context(current_user),
        punch_form=punch_form,
        correction_form=correction_form,
    )


@bp.route("/requests", methods=["GET", "POST"])
@login_required
def requests_home():
    _ensure_employee()
    leave_form = LeaveRequestForm(prefix="leave")
    populate_request_form(leave_form)
    if not leave_form.is_submitted() and current_user.employee_id:
        leave_form.employee_id.data = current_user.employee_id
    ticket_form = SupportTicketForm(prefix="ticket")
    privacy_form = PrivacyRequestForm(prefix="privacy")
    document_form = DocumentRequestForm(prefix="document")

    if leave_form.submit.data and leave_form.validate_on_submit():
        try:
            save_leave_request(leave_form)
            flash("Leave request submitted successfully.", "success")
            return redirect(url_for("experience.requests_home"))
        except ValueError as exc:
            flash(str(exc), "warning")
    elif ticket_form.submit.data and ticket_form.validate_on_submit():
        try:
            create_support_ticket(current_user, ticket_form)
            flash("HR request submitted.", "success")
            return redirect(url_for("experience.requests_home"))
        except ValueError as exc:
            flash(str(exc), "warning")
    elif privacy_form.submit.data and privacy_form.validate_on_submit():
        try:
            submit_privacy_request_for_employee(current_user, privacy_form)
            flash("Privacy request submitted.", "success")
            return redirect(url_for("experience.requests_home"))
        except ValueError as exc:
            flash(str(exc), "warning")
    elif document_form.submit.data and document_form.validate_on_submit():
        try:
            submit_document_request(current_user, document_form)
            flash("Document request submitted.", "success")
            return redirect(url_for("experience.requests_home"))
        except ValueError as exc:
            flash(str(exc), "warning")
    elif request.method == "POST" and request.form.get("modification_request_id") and request.form.get("modification_details"):
        try:
            submit_leave_modification_request(
                current_user,
                int(request.form["modification_request_id"]),
                request.form["modification_details"],
            )
            flash("Leave modification request submitted.", "success")
            return redirect(url_for("experience.requests_home"))
        except ValueError as exc:
            flash(str(exc), "warning")

    return render_template(
        "experience/requests.html",
        requests_data=requests_context(current_user),
        leave_form=leave_form,
        ticket_form=ticket_form,
        privacy_form=privacy_form,
        document_form=document_form,
    )


@bp.route("/requests/leave/<int:request_id>/cancel", methods=["POST"])
@login_required
def cancel_leave_request(request_id: int):
    _ensure_employee()
    try:
        cancel_leave_request_for_employee(current_user, request_id)
        flash("Leave request cancelled.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("experience.requests_home"))


@bp.route("/documents", methods=["GET", "POST"])
@login_required
def documents():
    _ensure_employee()
    if request.method == "POST":
        document_id = int(request.form.get("document_id") or 0)
        try:
            acknowledge_document(current_user, document_id)
            flash("Document acknowledged.", "success")
        except ValueError as exc:
            flash(str(exc), "warning")
        return redirect(url_for("experience.documents"))
    return render_template("experience/documents.html", docs=documents_context(current_user))


@bp.route("/documents/<int:document_id>/download")
@login_required
def download_document(document_id: int):
    _ensure_employee()
    ctx = documents_context(current_user)
    item = next((entry["record"] for entry in ctx["documents"] if entry["record"].id == document_id), None)
    if item is None:
        abort(404)
    file_path = document_download_path(item)
    if file_path is None:
        abort(404)
    return send_file(file_path, as_attachment=True, download_name=Path(file_path).name)


@bp.route("/help-center")
@login_required
def help_center():
    _ensure_employee()
    return render_template("experience/help_center.html", help_center=help_center_context(current_user))


@bp.route("/learning")
@login_required
def learning():
    _ensure_employee()
    return render_template("experience/learning.html", learning=learning_context(current_user))


@bp.route("/surveys", methods=["GET", "POST"])
@login_required
def surveys():
    _ensure_employee()
    suggestion_form = SuggestionForm(prefix="suggestion")
    if suggestion_form.submit.data and suggestion_form.validate_on_submit():
        try:
            submit_suggestion(current_user, suggestion_form)
            flash("Suggestion sent to HR.", "success")
            return redirect(url_for("experience.surveys"))
        except ValueError as exc:
            flash(str(exc), "warning")
    response_form = SurveyResponseForm(prefix="survey")
    return render_template(
        "experience/surveys.html",
        surveys_data=surveys_context(current_user),
        response_form=response_form,
        suggestion_form=suggestion_form,
    )


@bp.route("/surveys/<int:survey_id>/respond", methods=["POST"])
@login_required
def respond_survey(survey_id: int):
    _ensure_employee()
    form = SurveyResponseForm(prefix="survey")
    if form.validate_on_submit():
        try:
            submit_survey_response(current_user, survey_id, form)
            flash("Survey response submitted.", "success")
        except ValueError as exc:
            flash(str(exc), "warning")
    else:
        flash("Please complete the survey feedback fields.", "warning")
    return redirect(url_for("experience.surveys"))


@bp.route("/timeline")
@login_required
def timeline():
    _ensure_employee()
    return render_template("experience/timeline.html", timeline=timeline_context(current_user))


@bp.route("/onboarding")
@login_required
def onboarding():
    _ensure_employee()
    return render_template("experience/onboarding.html", onboarding=onboarding_context(current_user))


@bp.route("/exit", methods=["GET", "POST"])
@login_required
def exit_center():
    _ensure_employee()
    form = ExitRequestForm()
    if form.validate_on_submit():
        try:
            submit_exit_request(current_user, form)
            flash("Exit request submitted.", "success")
            return redirect(url_for("experience.exit_center"))
        except ValueError as exc:
            flash(str(exc), "warning")
    return render_template("experience/exit.html", exit_data=exit_context(current_user), form=form)
