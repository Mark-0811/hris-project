def validate_device_request(headers: dict) -> bool:
    return "X-Device-Key" in headers
