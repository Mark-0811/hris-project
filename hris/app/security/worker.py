from __future__ import annotations

import time

from flask import current_app

from .services import process_frame

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency guard
    cv2 = None


def run_security_worker() -> None:
    if cv2 is None:
        raise RuntimeError("OpenCV is required to run the security worker.")

    camera_index = int(current_app.config.get("SECURITY_CAMERA_INDEX", 0))
    capture_interval = float(current_app.config.get("SECURITY_CAPTURE_INTERVAL_SECONDS", 2.0))
    source_camera = str(current_app.config.get("SECURITY_CAMERA_NAME", f"usb_cam_{camera_index}"))

    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        raise RuntimeError(f"Unable to open camera index {camera_index}.")

    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                current_app.logger.warning("Security worker could not read frame from camera index %s", camera_index)
                time.sleep(capture_interval)
                continue

            try:
                process_frame(frame, source_camera=source_camera)
            except Exception:
                current_app.logger.exception("Security worker failed to process frame")
            time.sleep(capture_interval)
    finally:
        camera.release()


def stream_generator():
    if cv2 is None:
        raise RuntimeError("OpenCV is required to stream security camera.")

    camera_index = int(current_app.config.get("SECURITY_CAMERA_INDEX", 0))
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        raise RuntimeError(f"Unable to open camera index {camera_index}.")

    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                time.sleep(0.2)
                continue
            ok, jpeg = cv2.imencode(".jpg", frame)
            if not ok:
                continue
            frame_bytes = jpeg.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
    finally:
        camera.release()
