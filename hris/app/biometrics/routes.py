from flask import current_app, jsonify, request

from . import bp
from ..models import Employee, User


def validate_api_token():
    supplied_token = request.headers.get("X-API-Token")
    if not supplied_token:
        return None

    if supplied_token == current_app.config["BIOMETRIC_API_TOKEN"]:
        return {"auth_type": "config"}

    user = User.query.filter_by(api_token=supplied_token, is_active=True).first()
    if user and user.can_access_api:
        return {
            "auth_type": "user",
            "username": user.username,
            "role": user.role.name if user.role else None,
        }

    return None


@bp.route("/health")
def health_check():
    return jsonify({"module": "biometrics", "status": "ready"})


@bp.route("/punch", methods=["POST"])
def punch():
    auth_context = validate_api_token()
    if not auth_context:
        return jsonify({"message": "Invalid biometric API token."}), 401
    payload = request.get_json(silent=True) or {}
    return (
        jsonify(
            {
                "received": True,
                "status": "accepted_placeholder",
                "message": "Punch payload accepted for the MVP placeholder contract.",
                "payload": payload,
                "authorized_as": auth_context,
            }
        ),
        202,
    )


@bp.route("/validate-employee", methods=["POST"])
def validate_employee():
    auth_context = validate_api_token()
    if not auth_context:
        return jsonify({"message": "Invalid biometric API token."}), 401

    payload = request.get_json(silent=True) or {}
    employee_code = payload.get("employee_code")
    employee = Employee.query.filter_by(employee_code=employee_code).first() if employee_code else None
    return jsonify(
        {
            "valid": employee is not None,
            "employee_code": employee_code,
            "employee_name": employee.full_name if employee else None,
            "authorized_as": auth_context,
        }
    )


@bp.route("/device-sync", methods=["POST"])
def device_sync():
    auth_context = validate_api_token()
    if not auth_context:
        return jsonify({"message": "Invalid biometric API token."}), 401

    payload = request.get_json(silent=True) or {}
    return jsonify({"status": "accepted_placeholder", "payload": payload, "authorized_as": auth_context}), 202
