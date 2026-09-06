from datetime import datetime

from hris.app.extensions import db
from hris.app.models import DetectionEvent, IntruderProfile, PersonProfile
from hris.app.security import services as security_services

from .conftest import login


def _create_detection_event(result_class="unknown_person", confidence=0.77, matched_profile=None):
    event = DetectionEvent(
        detected_at=datetime.utcnow(),
        result_class=result_class,
        confidence=confidence,
        source_camera="usb_cam_0",
        image_filename="sample.jpg",
        rule_trace="unit_test",
        matched_profile_id=matched_profile.id if matched_profile else None,
    )
    db.session.add(event)
    db.session.commit()
    return event


def test_security_viewer_requires_admin_role(client, seeded_data):
    login(client, username="employee1")
    response = client.get("/security/viewer")
    assert response.status_code == 403


def test_security_viewer_renders_for_hr_admin(client, seeded_data):
    login(client)
    response = client.get("/security/viewer")
    assert response.status_code == 200
    assert b"Security Viewer" in response.data


def test_security_events_api_returns_recent_events(client, app, seeded_data):
    login(client)
    with app.app_context():
        _create_detection_event(result_class="unknown_person", confidence=0.55)
        _create_detection_event(result_class="blacklisted_person", confidence=0.99)

    response = client.get("/api/security/events?limit=10")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert len(payload) >= 2
    assert {item["result_class"] for item in payload}.issuperset({"unknown_person", "blacklisted_person"})


def test_mark_and_unmark_intruder_flow(client, app, seeded_data):
    login(client)
    with app.app_context():
        profile = PersonProfile(name="Known Person", status="allowed", is_active=True)
        db.session.add(profile)
        db.session.flush()
        event = _create_detection_event(result_class="known_person", matched_profile=profile)
        event_id = event.id

    mark_response = client.post(
        f"/api/security/events/{event_id}/mark-intruder",
        json={"label": "Blacklisted Person", "notes": "Security flagged"},
    )
    assert mark_response.status_code == 200
    assert mark_response.get_json()["result_class"] == "blacklisted_person"

    with app.app_context():
        refreshed = db.session.get(DetectionEvent, event_id)
        assert refreshed.result_class == "blacklisted_person"
        intruder = IntruderProfile.query.filter_by(person_profile_id=refreshed.matched_profile_id).first()
        assert intruder is not None
        assert intruder.is_active is True

    unmark_response = client.post(f"/api/security/events/{event_id}/unmark-intruder", json={})
    assert unmark_response.status_code == 200

    with app.app_context():
        refreshed = db.session.get(DetectionEvent, event_id)
        assert refreshed.result_class == "known_person"
        assert refreshed.matched_profile.status == "allowed"


def test_security_enroll_api_validates_required_fields(client, seeded_data):
    login(client)
    response = client.post("/api/security/enroll", data={"name": ""}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_should_alert_rule():
    unknown = security_services.MatchDecision(
        result_class="unknown_person",
        confidence=0.4,
        rule_trace="unknown",
        matched_profile=None,
        face_confidence=0.1,
        body_confidence=0.2,
    )
    blacklisted = security_services.MatchDecision(
        result_class="blacklisted_person",
        confidence=0.9,
        rule_trace="intruder",
        matched_profile=None,
        face_confidence=0.9,
        body_confidence=0.8,
    )
    known = security_services.MatchDecision(
        result_class="known_person",
        confidence=0.93,
        rule_trace="face",
        matched_profile=None,
        face_confidence=0.9,
        body_confidence=0.5,
    )

    assert security_services.should_alert(unknown) is True
    assert security_services.should_alert(blacklisted) is True
    assert security_services.should_alert(known) is False


def test_process_frame_creates_event_and_sends_alerts(monkeypatch, app, seeded_data):
    with app.app_context():
        profile = PersonProfile(name="Sample", status="allowed", is_active=True)
        db.session.add(profile)
        db.session.commit()

        def fake_match(_frame):
            return security_services.MatchDecision(
                result_class="unknown_person",
                confidence=0.78,
                rule_trace="unit",
                matched_profile=None,
                face_confidence=0.3,
                body_confidence=0.5,
            )

        monkeypatch.setattr(security_services, "match_person", fake_match)
        monkeypatch.setattr(security_services, "save_event_frame", lambda _frame: "event-test.jpg")

        calls = {"email": 0, "sms": 0, "notify": 0}

        def fake_email(_event):
            calls["email"] += 1
            return []

        def fake_sms(_event):
            calls["sms"] += 1
            return []

        def fake_notify(_event):
            calls["notify"] += 1

        monkeypatch.setattr(security_services, "_send_email_alert", fake_email)
        monkeypatch.setattr(security_services, "_send_sms_alert", fake_sms)
        monkeypatch.setattr(security_services, "_create_in_app_alerts", fake_notify)
        monkeypatch.setattr(security_services, "_is_duplicate_alert", lambda _event: False)

        event = security_services.process_frame(frame="fake-frame", source_camera="usb_cam_0")

        assert event.id is not None
        assert event.result_class == "unknown_person"
        assert calls["email"] == 1
        assert calls["sms"] == 1
        assert calls["notify"] == 1


def test_process_frame_skips_alert_on_duplicate(monkeypatch, app, seeded_data):
    with app.app_context():
        def fake_match(_frame):
            return security_services.MatchDecision(
                result_class="blacklisted_person",
                confidence=0.98,
                rule_trace="unit",
                matched_profile=None,
                face_confidence=0.8,
                body_confidence=0.8,
            )

        monkeypatch.setattr(security_services, "match_person", fake_match)
        monkeypatch.setattr(security_services, "save_event_frame", lambda _frame: "event-duplicate.jpg")

        calls = {"email": 0, "sms": 0, "notify": 0}
        monkeypatch.setattr(security_services, "_send_email_alert", lambda _event: calls.__setitem__("email", calls["email"] + 1) or [])
        monkeypatch.setattr(security_services, "_send_sms_alert", lambda _event: calls.__setitem__("sms", calls["sms"] + 1) or [])
        monkeypatch.setattr(security_services, "_create_in_app_alerts", lambda _event: calls.__setitem__("notify", calls["notify"] + 1))
        monkeypatch.setattr(security_services, "_is_duplicate_alert", lambda _event: True)

        event = security_services.process_frame(frame="fake-frame", source_camera="usb_cam_0")

        assert event.id is not None
        assert calls["email"] == 0
        assert calls["sms"] == 0
        assert calls["notify"] == 0
