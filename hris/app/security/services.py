from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
import secrets
from typing import Any

from flask import current_app
from flask_mail import Message
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..extensions import db, mail
from ..models import AlertEvent, DetectionEvent, IntruderProfile, Notification, PersonProfile, User
from ..utils.constants import ADMIN_ROLES

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency runtime guard
    cv2 = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency runtime guard
    np = None

try:
    from twilio.rest import Client as TwilioClient
except Exception:  # pragma: no cover - optional dependency runtime guard
    TwilioClient = None


FACE_THRESHOLD_DEFAULT = 0.84
BODY_THRESHOLD_DEFAULT = 0.80


SECURITY_REQUIRED_TABLES = (
    "person_profiles",
    "intruder_profiles",
    "detection_events",
    "alert_events",
)


@dataclass
class MatchDecision:
    result_class: str
    confidence: float
    rule_trace: str
    matched_profile: PersonProfile | None
    face_confidence: float
    body_confidence: float


def _ensure_cv_runtime() -> None:
    if cv2 is None or np is None:
        raise RuntimeError("OpenCV and NumPy are required for security detection runtime.")


def security_schema_ready() -> bool:
    try:
        inspector = inspect(db.engine)
        return all(inspector.has_table(table_name) for table_name in SECURITY_REQUIRED_TABLES)
    except Exception:
        return False


def _safe_query_all(callback, default):
    try:
        return callback()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return default


def _security_upload_dir(kind: str) -> Path:
    root = Path(current_app.static_folder) / "uploads" / "security" / kind
    root.mkdir(parents=True, exist_ok=True)
    return root


def _random_name(original_name: str | None, extension: str = ".jpg") -> str:
    source = (original_name or "image").strip()
    suffix = Path(source).suffix or extension
    return f"{secrets.token_hex(12)}{suffix.lower()}"


def save_profile_upload(file_storage) -> str:
    filename = _random_name(getattr(file_storage, "filename", None), extension=".jpg")
    output_path = _security_upload_dir("profiles") / filename
    file_storage.save(output_path)
    return filename


def save_event_frame(frame: Any) -> str:
    _ensure_cv_runtime()
    filename = _random_name("event.jpg", extension=".jpg")
    output_path = _security_upload_dir("events") / filename
    cv2.imwrite(str(output_path), frame)
    return filename


def _serialize_embedding(vector: Any) -> str | None:
    if vector is None:
        return None
    return json.dumps([float(x) for x in vector])


def _deserialize_embedding(payload: str | None):
    if not payload:
        return None
    if np is None:
        return None
    return np.array(json.loads(payload), dtype="float32")


def _normalize_vector(vector):
    if np is None:
        return vector
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def cosine_similarity(vector_a, vector_b) -> float:
    if np is None:
        return 0.0
    if vector_a is None or vector_b is None:
        return 0.0
    a = _normalize_vector(vector_a)
    b = _normalize_vector(vector_b)
    if a.shape != b.shape:
        return 0.0
    return float(np.dot(a, b))


def _build_face_embedding(frame):
    _ensure_cv_runtime()
    if frame is None or frame.size == 0:
        return None, 0.0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(48, 48))
    if len(faces) == 0:
        return None, 0.0

    x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
    face_roi = gray[y : y + h, x : x + w]
    if face_roi.size == 0:
        return None, 0.0

    resized = cv2.resize(face_roi, (32, 32)).astype("float32") / 255.0
    embedding = resized.flatten()
    confidence = min(1.0, (w * h) / float(gray.shape[0] * gray.shape[1]) * 8)
    return _normalize_vector(embedding), float(confidence)


def _build_body_embedding(frame):
    _ensure_cv_runtime()
    if frame is None or frame.size == 0:
        return None, 0.0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (64, 128))
    hog = cv2.HOGDescriptor()
    descriptor = hog.compute(resized)
    if descriptor is None:
        return None, 0.0
    vector = descriptor.flatten().astype("float32")
    texture_std = float(np.std(resized) / 255.0)
    confidence = max(0.35, min(1.0, texture_std * 3.0))
    return _normalize_vector(vector), confidence


def decode_image_bytes(image_bytes: bytes):
    _ensure_cv_runtime()
    if not image_bytes:
        return None
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _profile_is_blacklisted(profile: PersonProfile | None) -> bool:
    if profile is None:
        return False
    if profile.status == "intruder":
        return True
    intruder_profile = profile.intruder_profile
    return bool(intruder_profile and intruder_profile.is_active)


def match_person(frame) -> MatchDecision:
    face_threshold = float(current_app.config.get("SECURITY_FACE_MATCH_THRESHOLD", FACE_THRESHOLD_DEFAULT))
    body_threshold = float(current_app.config.get("SECURITY_BODY_MATCH_THRESHOLD", BODY_THRESHOLD_DEFAULT))

    face_embedding, face_confidence = _build_face_embedding(frame)
    body_embedding, body_confidence = _build_body_embedding(frame)

    profiles = PersonProfile.query.filter_by(is_active=True).all()
    best_face_profile = None
    best_face_similarity = 0.0
    best_body_profile = None
    best_body_similarity = 0.0

    for profile in profiles:
        stored_face = _deserialize_embedding(profile.face_embedding)
        stored_body = _deserialize_embedding(profile.body_embedding)

        face_similarity = cosine_similarity(face_embedding, stored_face)
        body_similarity = cosine_similarity(body_embedding, stored_body)

        if face_similarity > best_face_similarity:
            best_face_similarity = face_similarity
            best_face_profile = profile

        if body_similarity > best_body_similarity:
            best_body_similarity = body_similarity
            best_body_profile = profile

    if best_face_profile and best_face_similarity >= face_threshold:
        result = "blacklisted_person" if _profile_is_blacklisted(best_face_profile) else "known_person"
        return MatchDecision(
            result_class=result,
            confidence=best_face_similarity,
            rule_trace="face_primary",
            matched_profile=best_face_profile,
            face_confidence=face_confidence,
            body_confidence=body_confidence,
        )

    if best_body_profile and best_body_similarity >= body_threshold:
        result = "blacklisted_person" if _profile_is_blacklisted(best_body_profile) else "known_person"
        return MatchDecision(
            result_class=result,
            confidence=best_body_similarity,
            rule_trace="body_fallback",
            matched_profile=best_body_profile,
            face_confidence=face_confidence,
            body_confidence=body_confidence,
        )

    return MatchDecision(
        result_class="unknown_person",
        confidence=max(best_face_similarity, best_body_similarity),
        rule_trace="unknown_after_face_and_body",
        matched_profile=None,
        face_confidence=face_confidence,
        body_confidence=body_confidence,
    )


def create_or_update_profile_from_frame(name: str, frame, notes: str = "", status: str = "allowed") -> PersonProfile:
    face_embedding, _ = _build_face_embedding(frame)
    body_embedding, _ = _build_body_embedding(frame)

    profile = PersonProfile.query.filter_by(name=name).first()
    if profile is None:
        profile = PersonProfile(name=name)
        db.session.add(profile)

    profile.status = status
    profile.notes = notes
    profile.face_embedding = _serialize_embedding(face_embedding)
    profile.body_embedding = _serialize_embedding(body_embedding)
    return profile


def create_or_update_profile_from_upload(name: str, file_storage, notes: str = "", status: str = "allowed") -> PersonProfile:
    image_bytes = file_storage.read()
    file_storage.stream.seek(0)
    frame = decode_image_bytes(image_bytes)
    if frame is None:
        raise ValueError("Uploaded image could not be decoded.")

    profile = create_or_update_profile_from_frame(name=name, frame=frame, notes=notes, status=status)
    profile.image_filename = save_profile_upload(file_storage)
    db.session.commit()
    return profile


def _default_alert_recipients() -> tuple[list[str], list[str]]:
    email_config = current_app.config.get("SECURITY_ALERT_EMAILS", "")
    sms_config = current_app.config.get("SECURITY_ALERT_SMS", "")

    emails = [item.strip() for item in str(email_config).split(",") if item.strip()]
    sms_numbers = [item.strip() for item in str(sms_config).split(",") if item.strip()]

    if not emails:
        admin_users = User.query.join(User.role).filter(User.is_active.is_(True)).all()
        emails = [user.email for user in admin_users if user.role and user.role.name in ADMIN_ROLES and user.email]

    return emails, sms_numbers


def _send_email_alert(event: DetectionEvent) -> list[AlertEvent]:
    recipients, _ = _default_alert_recipients()
    alerts: list[AlertEvent] = []
    if not recipients:
        return alerts

    image_ref = f"/static/uploads/security/events/{event.image_filename}"
    for recipient in recipients:
        alert = AlertEvent(detection_event_id=event.id, channel="email", recipient=recipient, send_status="queued")
        db.session.add(alert)
        try:
            message = Message(
                subject=f"Security Alert: {event.result_class.replace('_', ' ').title()}",
                recipients=[recipient],
                body=(
                    f"Detection time: {event.detected_at.isoformat()}\n"
                    f"Camera: {event.source_camera}\n"
                    f"Result: {event.result_class}\n"
                    f"Confidence: {event.confidence:.3f}\n"
                    f"Rule: {event.rule_trace}\n"
                    f"Image: {image_ref}\n"
                ),
            )
            mail.send(message)
            alert.send_status = "sent"
        except Exception as exc:  # pragma: no cover - external I/O
            alert.send_status = "failed"
            alert.error_message = str(exc)
        alerts.append(alert)
    return alerts


def _send_sms_alert(event: DetectionEvent) -> list[AlertEvent]:
    _, recipients = _default_alert_recipients()
    alerts: list[AlertEvent] = []
    if not recipients:
        return alerts

    sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    token = current_app.config.get("TWILIO_AUTH_TOKEN")
    sender = current_app.config.get("TWILIO_FROM_NUMBER")
    if not sid or not token or not sender or TwilioClient is None:
        for recipient in recipients:
            alert = AlertEvent(
                detection_event_id=event.id,
                channel="sms",
                recipient=recipient,
                send_status="failed",
                error_message="Twilio is not configured.",
            )
            db.session.add(alert)
            alerts.append(alert)
        return alerts

    client = TwilioClient(sid, token)
    for recipient in recipients:
        alert = AlertEvent(detection_event_id=event.id, channel="sms", recipient=recipient, send_status="queued")
        db.session.add(alert)
        try:
            message = client.messages.create(
                body=(
                    f"[HRIS Security] {event.result_class.replace('_', ' ').title()} "
                    f"on {event.source_camera} ({event.confidence:.2f})."
                ),
                from_=sender,
                to=recipient,
            )
            alert.send_status = "sent"
            alert.provider_response_id = message.sid
        except Exception as exc:  # pragma: no cover - external I/O
            alert.send_status = "failed"
            alert.error_message = str(exc)
        alerts.append(alert)
    return alerts


def _create_in_app_alerts(event: DetectionEvent) -> None:
    message = (
        f"{event.result_class.replace('_', ' ').title()} detected on {event.source_camera} "
        f"with confidence {event.confidence:.2f}."
    )
    admins = User.query.join(User.role).filter(User.is_active.is_(True)).all()
    for user in admins:
        if not user.role or user.role.name not in ADMIN_ROLES:
            continue
        db.session.add(
            Notification(
                user_id=user.id,
                title="Security Detection Alert",
                message=message,
                type="security_alert",
                is_read=False,
            )
        )


def _is_duplicate_alert(event: DetectionEvent) -> bool:
    cooldown = int(current_app.config.get("SECURITY_ALERT_COOLDOWN_SECONDS", 120))
    cutoff = event.detected_at - timedelta(seconds=cooldown)
    query = DetectionEvent.query.filter(
        DetectionEvent.id != event.id,
        DetectionEvent.detected_at >= cutoff,
        DetectionEvent.result_class == event.result_class,
        DetectionEvent.source_camera == event.source_camera,
    )

    if event.matched_profile_id:
        query = query.filter(DetectionEvent.matched_profile_id == event.matched_profile_id)
    else:
        query = query.filter(DetectionEvent.matched_profile_id.is_(None))

    return db.session.query(query.exists()).scalar()


def should_alert(decision: MatchDecision) -> bool:
    return decision.result_class in {"unknown_person", "blacklisted_person"}


def process_frame(frame, source_camera: str = "usb_cam_0") -> DetectionEvent:
    decision = match_person(frame)
    image_filename = save_event_frame(frame)
    event = DetectionEvent(
        detected_at=datetime.utcnow(),
        result_class=decision.result_class,
        confidence=decision.confidence,
        source_camera=source_camera,
        image_filename=image_filename,
        rule_trace=decision.rule_trace,
        face_confidence=decision.face_confidence,
        body_confidence=decision.body_confidence,
        matched_profile_id=decision.matched_profile.id if decision.matched_profile else None,
    )
    db.session.add(event)
    db.session.flush()

    if should_alert(decision) and not _is_duplicate_alert(event):
        _create_in_app_alerts(event)
        _send_email_alert(event)
        _send_sms_alert(event)

    db.session.commit()
    return event


def mark_event_as_intruder(event_id: int, label: str | None = None, notes: str = "") -> DetectionEvent:
    event = DetectionEvent.query.get_or_404(event_id)

    profile = event.matched_profile
    if profile is None:
        generated_name = label or f"Intruder-{event.id}"
        profile = PersonProfile(
            name=generated_name,
            status="intruder",
            notes=notes,
            is_active=True,
        )
        db.session.add(profile)
        db.session.flush()
        event.matched_profile_id = profile.id
    else:
        profile.status = "intruder"
        if notes:
            profile.notes = notes

    intruder = profile.intruder_profile
    if intruder is None:
        intruder = IntruderProfile(
            person_profile_id=profile.id,
            label=label or profile.name,
            notes=notes,
            is_active=True,
        )
        db.session.add(intruder)
    else:
        intruder.is_active = True
        if label:
            intruder.label = label
        if notes:
            intruder.notes = notes

    event.result_class = "blacklisted_person"
    event.rule_trace = "manual_intruder_mark"
    db.session.commit()
    return event


def unmark_event_intruder(event_id: int) -> DetectionEvent:
    event = DetectionEvent.query.get_or_404(event_id)
    profile = event.matched_profile
    if profile:
        profile.status = "allowed"
        if profile.intruder_profile:
            profile.intruder_profile.is_active = False

    if event.result_class == "blacklisted_person":
        event.result_class = "known_person" if profile else "unknown_person"
        event.rule_trace = "manual_intruder_unmark"

    db.session.commit()
    return event


def list_security_events(limit: int = 100, result_class: str | None = None):
    if not security_schema_ready():
        return []

    def _query():
        query = DetectionEvent.query.order_by(DetectionEvent.detected_at.desc())
        if result_class:
            query = query.filter(DetectionEvent.result_class == result_class)
        return query.limit(limit).all()

    return _safe_query_all(_query, [])


def list_intruder_profiles():
    if not security_schema_ready():
        return []
    return _safe_query_all(
        lambda: IntruderProfile.query.filter_by(is_active=True).order_by(IntruderProfile.updated_at.desc()).all(),
        [],
    )


def list_person_profiles(limit: int = 100):
    if not security_schema_ready():
        return []
    return _safe_query_all(
        lambda: PersonProfile.query.order_by(PersonProfile.updated_at.desc()).limit(limit).all(),
        [],
    )


def event_to_dict(event: DetectionEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "detected_at": event.detected_at.isoformat(),
        "result_class": event.result_class,
        "confidence": round(float(event.confidence or 0.0), 4),
        "source_camera": event.source_camera,
        "image_url": event.image_url,
        "rule_trace": event.rule_trace,
        "matched_profile": event.matched_profile.name if event.matched_profile else None,
    }


def intruder_to_dict(profile: IntruderProfile) -> dict[str, Any]:
    person = profile.person_profile
    return {
        "id": profile.id,
        "label": profile.label,
        "notes": profile.notes,
        "person_profile_id": profile.person_profile_id,
        "person_name": person.name if person else None,
        "person_image_url": person.image_url if person else None,
        "updated_at": profile.updated_at.isoformat(),
    }
