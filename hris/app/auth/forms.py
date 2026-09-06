from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Update password")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField("New password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset password")


class ProfileUpdateRequestForm(FlaskForm):
    birthdate = DateField("Birthdate", validators=[Optional()], format="%Y-%m-%d")
    gender = SelectField(
        "Gender",
        choices=[
            ("", "Prefer not to say"),
            ("male", "Male"),
            ("female", "Female"),
            ("non_binary", "Non-binary"),
        ],
        validators=[Optional()],
    )
    civil_status = SelectField(
        "Civil Status",
        choices=[
            ("", "Not set"),
            ("single", "Single"),
            ("married", "Married"),
            ("separated", "Separated"),
            ("widowed", "Widowed"),
        ],
        validators=[Optional()],
    )
    address = TextAreaField("Address", validators=[Optional(), Length(max=1000)])
    emergency_contact_name = StringField("Emergency Contact Name", validators=[Optional(), Length(max=150)])
    reason = TextAreaField("Reason For Update", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Submit for verification")
