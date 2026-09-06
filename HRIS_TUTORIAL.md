# HRIS Full Tutorial

This guide explains how to use the current HRIS in this project.

## 1. Overview

HRIS currently includes:

- Role-based login
- User administration
- Employee records
- Departments and positions
- Schedules and shifts
- Attendance and kiosk punching
- Leave filing, granting, adjustment, and approval
- Payroll cutoff, generation, posting, and PDF payslips
- Reports
- Notifications
- News and announcements
- Realtime chat with file and image attachments
- Profile page
- API request catalog for Super Admin

## 2. Roles

The system supports:

- `Super Admin`
- `HR Admin`
- `Payroll Admin`
- `Manager`
- `Employee`
- `Biometrics API User`

## 3. First Login

Default seeded super admin:

- Username: `superadmin`
- Password: `ChangeMe123!`

After login:

1. Open the profile dropdown.
2. Review your profile.
3. Change or reset passwords as needed.

## 4. Navigation

The sidebar is now user-centered.

### Common Sections

- `Home`
- `My Work`
- `Profile`

### Employee Menu

- `Home`
- `My Attendance`
- `Leave`
- `Profile`

### Manager Menu

- `Home`
- `My Work`
- `Team`
- `Profile`

### HR Admin Menu

- `Home`
- `My Work`
- `HR Admin`
- `Payroll`
- `Profile`

### Super Admin Extras

- `Kiosk Terminal`
- `API Requests`

## 5. Dashboard

The dashboard changes depending on who is logged in.

### Employee Dashboard

Shows:

- Leave balance
- Pending leave count
- Unread alerts
- Today status
- Quick actions like `File Leave` and `Open Profile`

### Manager Dashboard

Shows:

- Team members
- Pending approvals
- Team attendance
- Team action shortcuts

### Admin Dashboard

Shows:

- Employees
- Active users
- Departments
- Pending leave requests
- Attendance today
- News and company updates

## 6. User Management

For `Super Admin` and `HR Admin`.

Open:

- `HR Workspace > User Access`

### Create or Edit User

You can set:

- Username
- Email
- Role
- Linked employee
- Password
- Active or inactive
- Force password change
- User photo

### API Access

`Can access API`:

- only `Super Admin` can set it
- enables a personal API token when applicable

### Important Rules

- a logged-in user cannot deactivate themself
- forgot-password is supported by email
- biometric API users can receive API tokens

## 7. Employee Management

Open:

- `HR Admin > People > Employees`

### Employee Record Includes

- Basic information
- Contact details
- Company and personal email
- Government IDs
- Emergency contact
- Badge ID
- NFC UID
- Shift assignment
- Line manager

### Duplicate Protection

The system prevents duplicates on:

- Personal email
- Company email
- SSS number
- TIN number
- PhilHealth number
- Pag-IBIG number
- Badge ID
- NFC UID

### Enable or Disable Employee

Admins can:

- `Enable`
- `Disable`

The logged-in user cannot disable their own employee record.

### Line Manager

You can assign `Line manager` in the employee form.

Only employees with a position name containing `Manager` are selectable.

Examples:

- `HR Manager`
- `Operations Manager`
- `Team Manager`

## 8. Departments and Positions

Open:

- `HR Admin > People > Departments`
- `HR Admin > People > Positions`

### Departments

Can include:

- Name
- Code
- Branch
- Cost center
- Manager

### Positions

Belong to departments.

If a position name includes `Manager`, employees using that position can be selected as line managers.

## 9. Schedules and Shifts

Open:

- `HR Admin > People > Schedules`

### Default Schedule

The default office schedule is:

- `8:30 AM to 5:30 PM`

### Shift Setup

Each shift can define:

- Shift name
- Start time
- End time
- Grace period
- Break start
- Break end
- Flexible schedule flag

### Flexible Shift Rules

For flexible shifts:

- no late tagging
- required work is 8 hours
- 1-hour break is excluded
- leaving before required work time becomes undertime

## 10. Attendance

Open:

- `My Work > Attendance`

### Today’s Timekeeping

The attendance board shows:

- Employee
- Date
- Time in
- Time out
- Late
- Undertime
- Today status

Possible statuses:

- `Present`
- `Late`
- `Undertime`
- `Incomplete`
- `Absent`
- `Awaiting Time In`

### Attendance Rules

For fixed schedules:

- late is based on start time plus grace period
- undertime is based on early timeout before allowed shift end
- if no time in after the allowed window, status becomes `Absent`
- if only time in exists, status becomes `Incomplete`

For flexible schedules:

- no late count
- work must reach 8 hours excluding break
- otherwise undertime is applied

### Manual Record and Adjustments

Admins and managers can:

- `Add Record`
- submit `Adjustment Request`
- approve attendance adjustments

## 11. Kiosk Terminal

Visible only to `Super Admin`.

Open:

- `Platform > Kiosk Terminal`

### Kiosk Supports

- Employee code
- Badge ID
- NFC UID

### Punch Options

- `Auto detect`
- `Time in`
- `Time out`

### Kiosk Behavior

- valid identifiers create or update attendance
- employee logs update live
- kiosk is kept separate from the main HR navigation

## 12. Leave Management

Open:

- `My Work > Leave`

### Standard Leave Types

Seeded types include:

- Birthday Leave
- Sick Leave
- Emergency Leave
- Vacation Leave
- Maternity Leave
- Single Parent Leave

### Employee Leave View

Employees now see:

- only their own leave requests
- only their own granted balances
- every leave type, even if no credits were granted yet

If no credits were granted for a leave type:

- it shows as `0`

### Leave Credits

Admins can:

- `Grant Leave`
- `Adjust Leave`

`Adjust Leave` supports:

- adding credits
- reducing credits

This is available to:

- `Super Admin`
- `HR Admin`

### Filing Leave

The leave request form supports:

- Leave type
- Duration
- Start date
- End date
- Reason

### Duration Options

- `Whole day`
- `Half day`

For half-day:

- start and end date must be the same
- the leave counts as `0.5`

### Paid and Unpaid Leave

If credits are enough:

- leave stays `Paid`

If no credits or insufficient credits:

- leave can still be filed
- it becomes `Unpaid`

### Leave Approval

Leave can be approved or disapproved by:

- `Super Admin`
- `HR Admin`
- assigned `Manager`

Managers can only approve their own direct reports.

### Leave Notifications

When leave is filed:

- line manager is notified
- HR Admin is notified
- Super Admin is notified

## 13. Payroll

Open:

- `Payroll`

### Payroll Workflow

The recommended flow is:

1. `New Cutoff`
2. `Salary Setup`
3. `Generate Payroll`
4. `Post Payroll`

### Payroll Features

Current payroll includes:

- Cutoff setup
- Salary setup
- Allowances
- Deductions
- Payroll generation
- Payroll posting
- PDF payslip download

### Cutoff

Cutoff requires:

- Cutoff name
- Start date
- End date
- Status

If end date is earlier than start date:

- the form will reject it

### Salary Setup

Before payroll can generate, employees must have salary setup.

### Generate Payroll

Generation creates payroll entries from:

- salary setup
- attendance within cutoff dates
- allowances
- deductions

Late and undertime attendance are still included as payable days, with deductions applied.

### Post Payroll

`Post Payroll` does this:

- changes generated entries to `posted`
- closes the cutoff
- sends employee notifications

### Payroll Notifications and Email

When payroll is created or posted:

- employees receive in-app notifications
- if email is configured and valid, they also receive email

If email sending fails:

- payroll still appears in their account through notifications and reports

### PDF Payslips

Employees and admins can download PDF payroll slips from:

- Payroll module
- Reports module

## 14. Reports

Open:

- `Reports`

### Role-Based Scope

If logged in as:

- `Employee`: only personal reports are shown
- `Admin` or elevated role: full report data is shown

### Report Areas

Includes:

- Employee master list
- Attendance snapshot
- Leave snapshot
- Payroll snapshot

Payroll rows include:

- PDF download button

## 15. Notifications

Open:

- `Notifications`

### Notification Sources

Notifications can come from:

- News
- Leave filing
- Chat reports
- Payroll
- Other HR workflows

### Behavior

Unread notifications increase the navbar count.

Once read:

- they no longer count toward the unread badge

### Actionable Notifications

Notification cards can lead directly to:

- Leave review
- Chat
- Payroll report
- Dashboard

## 16. News and Announcements

Available to admin roles.

Open:

- `HR Workspace > News`

### News Supports

- Title
- Rich HTML body
- Optional image
- Active or inactive state

Published news appears on:

- dashboard
- notifications

## 17. Chat

Open:

- `Messages`

### Chat Supports

- employee to admin conversation
- admin to employee replies
- realtime updates
- image attachments
- file attachments

### Attachments

Users can now:

- send images
- send files
- preview image attachments inside chat
- open non-image files as download links

### Foul Language Handling

If foul language is detected:

- sender gets a warning prompt
- manager receives a report notification when applicable

## 18. Profile Page

Open from the user dropdown:

- `Profile`

Shows:

- account information
- role
- email
- linked employee info
- profile photo if uploaded

## 19. API Requests

Visible only to `Super Admin`.

Open:

- `Platform > API Requests`

This page lists available API endpoints such as:

- biometric health
- biometric punch
- employee validation
- attendance API
- leave API
- payroll API
- reports API

## 20. Forgot Password

From login page:

- click `Forgot password?`

Process:

1. Enter email
2. Submit request
3. Open reset link from email
4. Set new password

This requires SMTP to be configured properly.

## 21. Email Setup

Example environment settings:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=HRIS Bot
```

Used for:

- password reset
- payroll notifications
- cutoff announcements

## 22. Running the App Locally

```powershell
cd "C:\Users\JohnRaymarkLlavanes\OneDrive - Dexterton Corporation\Desktop\John Raymark"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FLASK_APP="run.py"
python run.py
```

Open:

- [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 23. Apply Database Migrations

```powershell
$env:FLASK_APP="run.py"
.\.venv\Scripts\python.exe -m flask db upgrade
```

## 24. Docker

Files included:

- `Dockerfile`
- `docker-compose.yml`
- `.env.docker`
- `.env.docker.example`

Run:

```powershell
docker compose up --build
```

If Docker fails:

- open Docker Desktop
- make sure Docker Engine is running

## 25. Quick Admin Setup Checklist

Recommended setup order:

1. Log in as `superadmin`
2. Create departments
3. Create positions
4. Create manager positions
5. Create employees
6. Assign line managers
7. Create users and link employees
8. Create schedules
9. Grant leave credits
10. Adjust leave if needed
11. Test kiosk
12. Create cutoff
13. Add salary setup
14. Generate payroll
15. Post payroll
16. Test reports and PDF downloads

## 26. Troubleshooting

### Leave Credit Looks Missing

If no leave was granted:

- the employee now sees `0` instead of a missing row

### Cannot Generate Payroll

Check:

- cutoff exists
- salary setup exists
- attendance records fall inside the cutoff period

### Cannot Post Payroll

You must generate payroll first.

### Payslip Not Sent by Email

Even if email fails:

- payroll notification still goes to the account
- PDF remains downloadable from HRIS

### Employee Not Visible as Line Manager

Check whether the employee’s position includes the word `Manager`.

### Chat Attachment Upload Fails

Refresh the page first so the latest chat upload form loads with the CSRF token.

## 27. Recommended Next Improvements

Possible next upgrades:

- drag and drop chat uploads
- max file size and file type rules for chat attachments
- direct notification links to exact payroll PDF
- export more reports to PDF and Excel
- stronger audit logs
- richer dashboard charts

---

Notice: it was create by JOHN RAYMARK LLAVANES with LOVE
