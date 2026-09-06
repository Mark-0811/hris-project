from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class MobilePunchForm(FlaskForm):
    action = SelectField(
        "Punch action",
        choices=[("auto", "Auto detect"), ("time_in", "Time in"), ("time_out", "Time out")],
        validators=[DataRequired()],
        default="auto",
    )
    latitude = DecimalField("Latitude", validators=[Optional()], places=6)
    longitude = DecimalField("Longitude", validators=[Optional()], places=6)
    device_name = StringField("Device name", validators=[Optional(), Length(max=120)])
    anti_spoof_confirmed = BooleanField("Anti-spoof check passed", default=True)
    submit = SubmitField("Submit mobile punch")


class AttendanceCorrectionWizardForm(FlaskForm):
    attendance_record_id = SelectField("Attendance record", coerce=int, validators=[DataRequired()])
    reason_template = SelectField(
        "Reason template",
        choices=[
            ("missed_punch", "Missed punch"),
            ("biometric_error", "Biometric or device error"),
            ("field_work", "Field work / offsite work"),
            ("network_issue", "Network or power interruption"),
            ("other", "Other"),
        ],
        validators=[DataRequired()],
    )
    details = TextAreaField("Details", validators=[DataRequired(), Length(max=1000)])
    new_time_in = StringField("Adjusted time in", validators=[Optional(), Length(max=25)])
    new_time_out = StringField("Adjusted time out", validators=[Optional(), Length(max=25)])
    submit = SubmitField("Send correction request")


class SupportTicketForm(FlaskForm):
    category = SelectField(
        "Request type",
        choices=[
            ("coe", "Certificate of Employment"),
            ("id_replacement", "ID replacement"),
            ("benefits", "Benefits concern"),
            ("payroll", "Payroll concern"),
            ("it_account", "IT / account issue"),
            ("leave_modification", "Leave modification"),
            ("general", "General HR support"),
        ],
        validators=[DataRequired()],
    )
    subject = StringField("Subject", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(max=2000)])
    priority = SelectField(
        "Priority",
        choices=[("low", "Low"), ("normal", "Normal"), ("high", "High")],
        validators=[DataRequired()],
        default="normal",
    )
    submit = SubmitField("Submit request")


class PrivacyRequestForm(FlaskForm):
    request_type = SelectField(
        "Privacy request",
        choices=[
            ("data_access", "Access my personal data"),
            ("data_correction", "Correct my personal data"),
            ("retention_query", "Retention or storage concern"),
            ("consent_question", "Consent question"),
        ],
        validators=[DataRequired()],
    )
    details = TextAreaField("Details", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Send privacy request")


class DocumentRequestForm(FlaskForm):
    document_type = SelectField(
        "Missing document",
        choices=[
            ("contract", "Contract"),
            ("payslip", "Payslip"),
            ("government_form", "Government form"),
            ("certificate", "Certificate"),
            ("policy_copy", "Policy copy"),
            ("other", "Other"),
        ],
        validators=[DataRequired()],
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Request document")


class SurveyResponseForm(FlaskForm):
    survey_id = HiddenField(validators=[DataRequired()])
    sentiment_score = DecimalField("Mood score", validators=[DataRequired(), NumberRange(min=1, max=5)], places=1)
    feedback = TextAreaField("Feedback", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Send response")


class SuggestionForm(FlaskForm):
    is_anonymous = BooleanField("Hide my name in the HR queue", default=True)
    message = TextAreaField("Suggestion", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Send suggestion")


class ExitRequestForm(FlaskForm):
    resignation_date = DateField("Resignation date", validators=[DataRequired()])
    last_day = DateField("Requested last day", validators=[DataRequired()])
    reason = StringField("Primary reason", validators=[DataRequired(), Length(max=255)])
    interview_notes = TextAreaField("Notes for HR", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Submit exit request")
