from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class PayrollCutoffForm(FlaskForm):
    cutoff_name = StringField("Cutoff name", validators=[DataRequired(), Length(max=120)])
    start_date = DateField("Start date", validators=[DataRequired()])
    end_date = DateField("End date", validators=[DataRequired()])
    status = SelectField(
        "Status",
        choices=[("open", "Open"), ("processing", "Processing"), ("closed", "Closed")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Save cutoff")


class EmployeeSalaryForm(FlaskForm):
    employee_id = SelectField("Employee", coerce=int, validators=[DataRequired()])
    basic_salary = DecimalField("Basic salary", validators=[DataRequired(), NumberRange(min=0)], places=2)
    daily_rate = DecimalField("Daily rate", validators=[Optional(), NumberRange(min=0)], places=2)
    hourly_rate = DecimalField("Hourly rate", validators=[Optional(), NumberRange(min=0)], places=2)
    effective_date = DateField("Effective date", validators=[DataRequired()])
    submit = SubmitField("Save salary")


class AllowanceForm(FlaskForm):
    employee_id = SelectField("Employee", coerce=int, validators=[DataRequired()])
    allowance_type = StringField("Allowance type", validators=[DataRequired(), Length(max=120)])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)], places=2)
    taxable = BooleanField("Taxable")
    effective_date = DateField("Effective date", validators=[DataRequired()])
    submit = SubmitField("Save allowance")


class DeductionForm(FlaskForm):
    employee_id = SelectField("Employee", coerce=int, validators=[DataRequired()])
    deduction_type = StringField("Deduction type", validators=[DataRequired(), Length(max=120)])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)], places=2)
    effective_date = DateField("Effective date", validators=[DataRequired()])
    submit = SubmitField("Save deduction")


class PayrollGenerateForm(FlaskForm):
    cutoff_id = SelectField("Cutoff", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Generate payroll")
