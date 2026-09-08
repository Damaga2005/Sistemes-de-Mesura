"""Contratos F13: recursos académicos reales y calendario honesto."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(__file__).split("tests")[0] + "web")
import server as S  # noqa: E402


@pytest.fixture()
def bridge():
    return S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-f13-"))


def test_documents_catalog_is_real_and_filterable(bridge):
    status, data, _ = bridge.route("GET", "/api/documents")
    assert status == 200
    assert data["source"] == "COURSE_SOURCE"
    assert data["documents"]
    item = data["documents"][0]
    assert set(item) >= {"id", "title", "kind", "topic", "sections"}
    assert isinstance(item["sections"], int)

    status, filtered, _ = bridge.route(
        "GET", "/api/documents", {"topic": "2"})
    assert status == 200
    assert filtered["documents"]
    assert {item["topic"] for item in filtered["documents"]} == {2}


def test_documents_catalog_rejects_invalid_topic(bridge):
    status, data, _ = bridge.route(
        "GET", "/api/documents", {"topic": "not-a-topic"})
    assert status == 400
    assert data["code"] == "VALIDATION_ERROR"


def test_study_document_navigation_can_select_one_document(bridge):
    status, catalog, _ = bridge.route(
        "GET", "/api/documents", {"topic": "2"})
    doc_id = catalog["documents"][0]["id"]
    status, data, _ = bridge.route(
        "GET", "/api/study/documents",
        {"topic": "2", "doc_id": str(doc_id)})
    assert status == 200
    assert [doc["id"] for doc in data["documents"]] == [doc_id]


def test_calendar_is_explicitly_empty_without_academic_source(bridge):
    status, data, _ = bridge.route("GET", "/api/calendar")
    assert status == 200
    assert data == {
        "events": [],
        "configured": False,
        "source": "COURSE_SOURCE",
        "message": "No hi ha esdeveniments acadèmics configurats.",
    }


def test_calendar_loads_versioned_local_source_deterministically(tmp_path):
    source = tmp_path / "calendar.json"
    source.write_text(
        '{"version": 1, "source_path": "horari-2026.json", '
        '"source_hash": "abc123", "events": ['
        '{"id":"lab-2","title":"Laboratori 2","start":"2026-10-03T10:00:00",'
        '"end":"2026-10-03T12:00:00","kind":"laboratori"},'
        '{"id":"exam-1","title":"Examen parcial","start":"2026-09-20T09:00:00",'
        '"end":"2026-09-20T11:00:00","kind":"examen"}]}',
        encoding="utf-8")
    bridge = S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-f13-cal-"),
                      calendar_path=str(source))
    status, data, _ = bridge.route("GET", "/api/calendar")
    assert status == 200
    assert data["configured"] is True
    assert data["source"] == "COURSE_SOURCE"
    assert data["source_path"] == "horari-2026.json"
    assert [event["id"] for event in data["events"]] == ["exam-1", "lab-2"]
    assert data["events"][0]["source_hash"] == "abc123"


def test_calendar_rejects_invalid_source(tmp_path):
    source = tmp_path / "calendar.json"
    source.write_text('{"version": 1, "events": [{"id": "x"}]}',
                      encoding="utf-8")
    bridge = S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-f13-cal-"),
                      calendar_path=str(source))
    status, data, _ = bridge.route("GET", "/api/calendar")
    assert status == 400
    assert data["code"] == "VALIDATION_ERROR"


def test_f13_pages_load_real_resources():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "web"
    documents = (root / "documents.html").read_text(encoding="utf-8")
    calendar = (root / "calendar.html").read_text(encoding="utf-8")
    assert "NOT_IMPLEMENTED" not in documents
    assert "static/js/documents.js" in documents
    assert "NOT_IMPLEMENTED" not in calendar
    assert "static/js/calendar.js" in calendar
