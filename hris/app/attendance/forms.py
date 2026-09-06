from flask_wtf import FlaskForm
from wtforms import DateField, DateTimeLocalField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class AttendanceRecordForm(FlaskForm):
    employee_id = SelectField("Employee", coerce=int, validators=[DataRequired()])
    date = DateField("Attendance date", validators=[DataRequired()])
    time_in = DateTimeLocalField("Time in", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    time_out = DateTimeLocalField("Time out", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    break_in = DateTimeLocalField("Break in", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    break_out = DateTimeLocalField("Break out", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    late_minutes = IntegerField("Late minutes", validators=[Optional(), NumberRange(min=0)])
    undertime_minutes = IntegerField("Undertime minutes", validators=[Optional(), NumberRange(min=0)])
    overtime_minutes = IntegerField("Overtime minutes", validators=[Optional(), NumberRange(min=0)])
    status = SelectField(
        "Status",
        choices=[
            ("present", "Present"),
            ("late", "Late"),
            ("pending", "Pending"),
            ("absent", "Absent"),
            ("incomplete", "Incomplete"),
            ("approved", "Approved"),
        ],
        validators=[DataRequired()],
    )
    remarks = TextAreaField("Remarks", validators=[Optional()])
    submit = SubmitField("Save attendance")


class AttendanceAdjustmentForm(FlaskForm):
    attendance_record_id = SelectField("Attendance record", coerce=int, validators=[DataRequired()])
    reason = TextAreaField("Reason", validators=[DataRequired()])
    new_time_in = DateTimeLocalField("Adjusted time in", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    new_time_out = DateTimeLocalField("Adjusted time out", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    submit = SubmitField("Submit adjustment")


class KioskPunchForm(FlaskForm):
    identifier = StringField(
        "Employee ID / Badge / NFC UID", validators=[DataRequired(), Length(max=120)]
    )
    action = SelectField(
        "Punch action",
        choices=[
            ("auto", "Auto detect"),
            ("time_in", "Time in"),
            ("time_out", "Time out"),
        ],
        validators=[DataRequired()],
    )
    source = SelectField(
        "Input source",
        choices=[("manual", "Manual input"), ("nfc", "NFC / Tap"), ("badge", "Badge ID")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Submit punch")
