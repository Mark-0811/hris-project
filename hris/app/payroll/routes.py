from io import BytesIO

from flask import abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from . import bp
from .forms import (
    AllowanceForm,
    DeductionForm,
    EmployeeSalaryForm,
    PayrollCutoffForm,
    PayrollGenerateForm,
)
from .services import (
    can_access_payroll_entry,
    generate_payroll_for_cutoff,
    list_allowances,
    list_cutoffs,
    list_deductions,
    list_payroll_entries,
    list_salaries,
    post_payroll_for_cutoff,
    save_allowance,
    save_cutoff,
    save_deduction,
    save_salary,
    serialize_entry,
    summarize_cutoff,
)
from ..models import Employee, PayrollCutoff, PayrollEntry
from ..utils.decorators import role_required

PAYROLL_ROLES = ("Super Admin", "HR Admin", "Payroll Admin")


def populate_employee_form(form):
    form.employee_id.choices = [
        (employee.id, f"{employee.employee_code} - {employee.full_name}")
        for employee in Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all()
    ]


def populate_generate_form(form):
    form.cutoff_id.choices = [(cutoff.id, cutoff.cutoff_name) for cutoff in list_cutoffs()]


@bp.route("/")
@login_required
@role_required(*PAYROLL_ROLES)
def index():
    return render_template(
        "payroll/index.html",
        summary=summarize_cutoff(),
        cutoffs=list_cutoffs(),
        salaries=list_salaries(),
        allowances=list_allowances(),
        deductions=list_deductions(),
        entries=list_payroll_entries(),
    )


@bp.route("/cutoffs/create", methods=["GET", "POST"])
@login_required
@role_required(*PAYROLL_ROLES)
def create_cutoff():
    form = PayrollCutoffForm()
    if form.validate_on_submit():
        try:
            _, sent_count = save_cutoff(form)
        except ValueError as exc:
            form.end_date.errors.append(str(exc))
        else:
            flash(f"Payroll cutoff saved successfully. Email sent to {sent_count} employee(s).", "success")
            return redirect(url_for("payroll.index"))
    return render_template("payroll/cutoff_form.html", form=form)


@bp.route("/salary/create", methods=["GET", "POST"])
@login_required
@role_required(*PAYROLL_ROLES)
def create_salary():
    form = EmployeeSalaryForm()
    populate_employee_form(form)
    if form.validate_on_submit():
        save_salary(form)
        flash("Salary setup saved successfully.", "success")
        return redirect(url_for("payroll.index"))
    return render_template("payroll/salary_form.html", form=form)


@bp.route("/allowances/create", methods=["GET", "POST"])
@login_required
@role_required(*PAYROLL_ROLES)
def create_allowance():
    form = AllowanceForm()
    populate_employee_form(form)
    if form.validate_on_submit():
        save_allowance(form)
        flash("Allowance saved successfully.", "success")
        return redirect(url_for("payroll.index"))
    return render_template("payroll/allowance_form.html", form=form)


@bp.route("/deductions/create", methods=["GET", "POST"])
@login_required
@role_required(*PAYROLL_ROLES)
def create_deduction():
    form = DeductionForm()
    populate_employee_form(form)
    if form.validate_on_submit():
        save_deduction(form)
        flash("Deduction saved successfully.", "success")
        return redirect(url_for("payroll.index"))
    return render_template("payroll/deduction_form.html", form=form)


@bp.route("/generate", methods=["GET", "POST"])
@login_required
@role_required(*PAYROLL_ROLES)
def generate():
    form = PayrollGenerateForm()
    populate_generate_form(form)
    if form.validate_on_submit():
        entries, sent_count = generate_payroll_for_cutoff(form.cutoff_id.data)
        if not entries:
            flash("No payroll entries were generated. Check salary setup and cutoff dates.", "warning")
            return redirect(url_for("payroll.index"))
        flash(f"Generated {len(entries)} payroll entries and emailed {sent_count} employee(s).", "success")
        return redirect(url_for("payroll.index"))
    return render_template("payroll/generate_form.html", form=form)


@bp.route("/post", methods=["GET", "POST"])
@login_required
@role_required(*PAYROLL_ROLES)
def post_payroll():
    form = PayrollGenerateForm()
    populate_generate_form(form)
    if form.validate_on_submit():
        entries, notified_count = post_payroll_for_cutoff(form.cutoff_id.data)
        if not entries:
            flash("No generated payroll entries were found for the selected cutoff.", "warning")
            return redirect(url_for("payroll.index"))
        flash(f"Posted {len(entries)} payroll entries and notified {notified_count} employee(s).", "success")
        return redirect(url_for("payroll.index"))
    return render_template("payroll/post_form.html", form=form)


@bp.route("/api/summary")
@login_required
@role_required(*PAYROLL_ROLES)
def api_summary():
    return jsonify(summarize_cutoff())


@bp.route("/api/entries")
@login_required
@role_required(*PAYROLL_ROLES)
def api_entries():
    return jsonify([serialize_entry(entry) for entry in list_payroll_entries()])


@bp.route("/entries/<int:entry_id>/pdf")
@login_required
def download_entry_pdf(entry_id: int):
    entry = PayrollEntry.query.get_or_404(entry_id)
    if not can_access_payroll_entry(current_user, entry):
        abort(403)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 60

    pdf.setTitle(f"Payroll Slip - {entry.employee.full_name if entry.employee else 'Employee'}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "HRIS Payroll Slip")
    y -= 30

    pdf.setFont("Helvetica", 11)
    lines = [
        f"Employee: {entry.employee.full_name if entry.employee else 'Unknown'}",
        f"Employee Code: {entry.employee.employee_code if entry.employee else 'N/A'}",
        f"Cutoff: {entry.cutoff.cutoff_name if entry.cutoff else 'N/A'}",
        f"Status: {entry.status.title()}",
        "",
        f"Basic Pay: {entry.basic_pay}",
        f"Overtime Pay: {entry.overtime_pay}",
        f"Late Deduction: {entry.late_deduction}",
        f"Undertime Deduction: {entry.undertime_deduction}",
        f"Allowance Total: {entry.allowance_total}",
        f"Deduction Total: {entry.deduction_total}",
        "",
        f"Net Pay: {entry.net_pay}",
    ]
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 20

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    filename = f"payroll_{entry.employee.employee_code if entry.employee else entry.id}_{entry.cutoff_id}.pdf"
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)
