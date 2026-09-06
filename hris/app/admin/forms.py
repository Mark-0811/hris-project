from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional


class UserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    role_id = SelectField("Role", coerce=int, validators=[DataRequired()])
    employee_id = SelectField("Linked employee", coerce=int, validators=[Optional()])
    password = PasswordField("Temporary password", validators=[Optional(), Length(min=8)])
    photo = FileField("User photo", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only.")])
    can_access_api = BooleanField("Can access API")
    is_active = BooleanField("Active account", default=True)
    force_password_change = BooleanField("Require password change on first login", default=True)
    submit = SubmitField("Save user")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New temporary password", validators=[DataRequired(), Length(min=8)])
    force_password_change = BooleanField("Require password change on next login", default=True)
    submit = SubmitField("Reset password")


class AnnouncementForm(FlaskForm):
    title = StringField("News title", validators=[DataRequired(), Length(max=255)])
    body = TextAreaField("News content", validators=[DataRequired()])
    image = FileField("News image", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp", "gif"], "Images only.")])
    is_active = BooleanField("Publish now", default=True)
    submit = SubmitField("Publish news")


class UserBulkImportForm(FlaskForm):
    workbook = FileField(
        "Excel workbook",
        validators=[DataRequired(), FileAllowed(["xlsx"], "Excel .xlsx files only.")],
    )
    submit = SubmitField("Import users")
