from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class LeaveTypeForm(FlaskForm):
    name = StringField("Leave type", validators=[DataRequired(), Length(max=120)])
    default_credits = DecimalField(
        "Default credits", validators=[DataRequired(), NumberRange(min=0)], places=2
    )
    is_paid = BooleanField("Paid leave", default=True)
    requires_attachment = BooleanField("Requires attachment")
    submit = SubmitField("Save leave type")


class LeaveBalanceForm(FlaskForm):
    employee_id = SelectField("Employee", coerce=int, validators=[DataRequired()])
    leave_type_id = SelectField("Leave type", coerce=int, validators=[DataRequired()])
    year = SelectField("Year", coerce=int, validators=[DataRequired()])
    total_credits = DecimalField(
        "Total credits", validators=[DataRequired(), NumberRange(min=0)], places=2
    )
    used_credits = DecimalField(
        "Used credits", validators=[Optional(), NumberRange(min=0)], places=2, default=0
    )
    submit = SubmitField("Save balance")


class LeaveBalanceAdjustmentForm(FlaskForm):
    employee_id = SelectField("Employee", coerce=int, validators=[DataRequired()])
    leave_type_id = SelectField("Leave type", coerce=int, validators=[DataRequired()])
    year = SelectField("Year", coerce=int, validators=[DataRequired()])
    adjustment_credits = DecimalField(
        "Adjustment credits",
        validators=[DataRequired()],
        places=2,
        description="Use a positive number to add credits or a negative number to reduce them.",
    )
    reason = TextAreaField("Reason", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Apply adjustment")


class LeaveRequestForm(FlaskForm):
    employee_id = SelectField("Employee", coerce=int, validators=[DataRequired()])
    leave_type_id = SelectField("Leave type", coerce=int, validators=[DataRequired()])
    duration_type = SelectField(
        "Leave duration",
        choices=[("whole_day", "Whole day"), ("half_day", "Half day")],
        validators=[DataRequired()],
    )
    start_date = DateField("Start date", validators=[DataRequired()])
    end_date = DateField("End date", validators=[DataRequired()])
    reason = TextAreaField("Reason", validators=[DataRequired()])
    submit = SubmitField("Submit request")
