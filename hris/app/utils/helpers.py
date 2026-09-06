from ..models import Employee


def generate_employee_code(prefix: str, sequence: int) -> str:
    return f"{prefix}-{sequence:05d}"


def generate_next_employee_code(prefix: str = "EMP") -> str:
    latest = Employee.query.order_by(Employee.id.desc()).first()
    next_sequence = 1 if latest is None else latest.id + 1
    return generate_employee_code(prefix, next_sequence)
