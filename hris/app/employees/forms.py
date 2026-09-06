from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DateField, IntegerField, SelectField, StringField, SubmitField, TextAreaField, TimeField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


class DepartmentForm(FlaskForm):
    name = StringField("Department name", validators=[DataRequired(), Length(max=120)])
    code = StringField("Department code", validators=[DataRequired(), Length(max=30)])
    manager_id = SelectField("Manager", coerce=int, validators=[Optional()])
    branch = StringField("Branch", validators=[Optional(), Length(max=120)])
    cost_center = StringField("Cost center", validators=[Optional(), Length(max=50)])
    submit = SubmitField("Save department")


class PositionForm(FlaskForm):
    name = StringField("Position name", validators=[DataRequired(), Length(max=120)])
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional()])
    submit = SubmitField("Save position")


class ShiftForm(FlaskForm):
    shift_name = StringField("Schedule name", validators=[DataRequired(), Length(max=120)])
    start_time = TimeField("Start time", validators=[DataRequired()])
    end_time = TimeField("End time", validators=[DataRequired()])
    grace_period_minutes = IntegerField("Grace period (minutes)", validators=[Optional(), NumberRange(min=0)])
    break_start = TimeField("Break start", validators=[Optional()])
    break_end = TimeField("Break end", validators=[Optional()])
    is_flexible = BooleanField("Flexible schedule")
    submit = SubmitField("Save schedule")


class EmployeeForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=100)])
    middle_name = StringField("Middle name", validators=[Optional(), Length(max=100)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=100)])
    suffix = StringField("Suffix", validators=[Optional(), Length(max=20)])
    birthdate = DateField("Birthdate", validators=[Optional()])
    gender = SelectField(
        "Gender",
        choices=[("", "Select gender"), ("male", "Male"), ("female", "Female"), ("other", "Other")],
        validators=[Optional()],
    )
    civil_status = SelectField(
        "Civil status",
        choices=[
            ("", "Select status"),
            ("single", "Single"),
            ("married", "Married"),
            ("widowed", "Widowed"),
            ("separated", "Separated"),
        ],
        validators=[Optional()],
    )
    address = TextAreaField("Address", validators=[Optional()])
    contact_number = StringField("Contact number", validators=[Optional(), Length(max=30)])
    personal_email = StringField("Personal email", validators=[Optional(), Email(), Length(max=255)])
    company_email = StringField("Company email", validators=[Optional(), Email(), Length(max=255)])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    position_id = SelectField("Position", coerce=int, validators=[Optional()])
    manager_id = SelectField("Line manager", coerce=int, validators=[Optional()])
    employment_type = SelectField(
        "Employment type",
        choices=[
            ("", "Select type"),
            ("regular", "Regular"),
            ("probationary", "Probationary"),
            ("contractual", "Contractual"),
            ("project", "Project"),
        ],
        validators=[Optional()],
    )
    date_hired = DateField("Date hired", validators=[DataRequired()])
    date_regularized = DateField("Date regularized", validators=[Optional()])
    employment_status = SelectField(
        "Employment status",
        choices=[
            ("active", "Active"),
            ("probationary", "Probationary"),
            ("inactive", "Inactive"),
            ("resigned", "Resigned"),
        ],
        validators=[DataRequired()],
    )
    sss_no = StringField("SSS number", validators=[Optional(), Length(max=40)])
    tin_no = StringField("TIN number", validators=[Optional(), Length(max=40)])
    philhealth_no = StringField("PhilHealth number", validators=[Optional(), Length(max=40)])
    pagibig_no = StringField("Pag-IBIG number", validators=[Optional(), Length(max=40)])
    profile_image = StringField("Profile image path", validators=[Optional(), Length(max=255)])
    emergency_contact_name = StringField(
        "Emergency contact name", validators=[Optional(), Length(max=150)]
    )
    emergency_contact_number = StringField(
        "Emergency contact number", validators=[Optional(), Length(max=30)]
    )
    badge_id = StringField("Badge ID", validators=[Optional(), Length(max=50)])
    nfc_uid = StringField("NFC UID", validators=[Optional(), Length(max=120)])
    shift_id = SelectField("Schedule", coerce=int, validators=[Optional()])
    submit = SubmitField("Save employee")


class EmployeeBulkImportForm(FlaskForm):
    workbook = FileField(
        "Excel workbook",
        validators=[DataRequired(), FileAllowed(["xlsx"], "Excel .xlsx files only.")],
    )
    submit = SubmitField("Import employees")
