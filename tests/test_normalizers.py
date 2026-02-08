"""Tests for yattmcp.normalizers — pure functions, no I/O."""

import pytest

from yattmcp.normalizers import (
    date_from_api,
    date_to_api,
    normalize_project,
    normalize_task,
    priority_from_api,
    priority_to_api,
    subtask_from_api,
    subtask_to_api,
)


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------


class TestPriorityToApi:
    @pytest.mark.parametrize(
        "label, expected",
        [("none", 0), ("low", 1), ("medium", 3), ("high", 5)],
    )
    def test_valid_values(self, label: str, expected: int) -> None:
        assert priority_to_api(label) == expected

    def test_case_insensitive(self) -> None:
        assert priority_to_api("HIGH") == 5
        assert priority_to_api("Low") == 1

    def test_strips_whitespace(self) -> None:
        assert priority_to_api("  medium  ") == 3

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid priority"):
            priority_to_api("urgent")


class TestPriorityFromApi:
    @pytest.mark.parametrize(
        "numeric, expected",
        [(0, "none"), (1, "low"), (3, "medium"), (5, "high")],
    )
    def test_known_values(self, numeric: int, expected: str) -> None:
        assert priority_from_api(numeric) == expected

    def test_unknown_defaults_to_none(self) -> None:
        assert priority_from_api(99) == "none"


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


class TestDateToApi:
    def test_date_only(self) -> None:
        api_str, is_all_day = date_to_api("2025-03-15")
        assert is_all_day is True
        assert api_str.startswith("2025-03-15T00:00:00")
        assert "+0000" in api_str

    def test_datetime_no_seconds(self) -> None:
        api_str, is_all_day = date_to_api("2025-03-15T14:00")
        assert is_all_day is False
        assert "14:00:00" in api_str

    def test_datetime_with_seconds(self) -> None:
        api_str, is_all_day = date_to_api("2025-03-15T14:30:45")
        assert is_all_day is False
        assert "14:30:45" in api_str

    def test_datetime_with_offset(self) -> None:
        api_str, is_all_day = date_to_api("2025-03-15T14:00:00+05:00")
        assert is_all_day is False
        assert "+0500" in api_str

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            date_to_api("not-a-date")


class TestDateFromApi:
    def test_none_returns_none(self) -> None:
        assert date_from_api(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert date_from_api("") is None

    def test_ticktick_format(self) -> None:
        result = date_from_api("2025-03-15T00:00:00+0000")
        assert result is not None
        assert "2025-03-15" in result

    def test_already_iso(self) -> None:
        result = date_from_api("2025-03-15T14:00:00+00:00")
        assert result is not None
        assert "2025-03-15T14:00:00" in result


# ---------------------------------------------------------------------------
# Subtasks
# ---------------------------------------------------------------------------


class TestSubtaskToApi:
    def test_incomplete(self) -> None:
        result = subtask_to_api({"title": "Buy milk"})
        assert result == {"title": "Buy milk", "status": 0}

    def test_completed(self) -> None:
        result = subtask_to_api({"title": "Buy milk", "isCompleted": True})
        assert result == {"title": "Buy milk", "status": 1}

    def test_explicitly_incomplete(self) -> None:
        result = subtask_to_api({"title": "Buy milk", "isCompleted": False})
        assert result == {"title": "Buy milk", "status": 0}


class TestSubtaskFromApi:
    def test_complete(self) -> None:
        result = subtask_from_api({"id": "s1", "title": "Buy milk", "status": 1})
        assert result == {"id": "s1", "title": "Buy milk", "isCompleted": True}

    def test_incomplete(self) -> None:
        result = subtask_from_api({"id": "s2", "title": "Buy eggs", "status": 0})
        assert result == {"id": "s2", "title": "Buy eggs", "isCompleted": False}

    def test_missing_fields_default(self) -> None:
        result = subtask_from_api({})
        assert result == {"id": None, "title": "", "isCompleted": False}


# ---------------------------------------------------------------------------
# Task normalization
# ---------------------------------------------------------------------------


class TestNormalizeTask:
    def test_minimal_task(self) -> None:
        raw = {"id": "t1", "projectId": "p1", "title": "Do thing"}
        result = normalize_task(raw)
        assert result["id"] == "t1"
        assert result["projectId"] == "p1"
        assert result["title"] == "Do thing"
        assert result["priority"] == "none"
        assert result["isCompleted"] is False
        assert result["dueDate"] is None
        assert result["startDate"] is None
        assert result["subtasks"] == []

    def test_high_priority(self) -> None:
        raw = {"id": "t1", "priority": 5}
        result = normalize_task(raw)
        assert result["priority"] == "high"

    def test_completed_status(self) -> None:
        raw = {"id": "t1", "status": 2}
        result = normalize_task(raw)
        assert result["isCompleted"] is True

    def test_with_subtasks(self) -> None:
        raw = {
            "id": "t1",
            "items": [
                {"id": "s1", "title": "Sub A", "status": 0},
                {"id": "s2", "title": "Sub B", "status": 1},
            ],
        }
        result = normalize_task(raw)
        assert len(result["subtasks"]) == 2
        assert result["subtasks"][0]["isCompleted"] is False
        assert result["subtasks"][1]["isCompleted"] is True

    def test_with_dates(self) -> None:
        raw = {
            "id": "t1",
            "dueDate": "2025-03-15T00:00:00+0000",
            "startDate": "2025-03-14T00:00:00+0000",
        }
        result = normalize_task(raw)
        assert result["dueDate"] is not None
        assert "2025-03-15" in result["dueDate"]
        assert result["startDate"] is not None
        assert "2025-03-14" in result["startDate"]


# ---------------------------------------------------------------------------
# Project normalization
# ---------------------------------------------------------------------------


class TestNormalizeProject:
    def test_basic(self) -> None:
        raw = {"id": "p1", "name": "Work", "color": "#F18181", "viewMode": "list"}
        result = normalize_project(raw)
        assert result == {
            "id": "p1",
            "name": "Work",
            "color": "#F18181",
            "viewMode": "list",
            "isClosed": False,
        }

    def test_closed_project(self) -> None:
        raw = {"id": "p2", "name": "Old", "closed": True}
        result = normalize_project(raw)
        assert result["isClosed"] is True

    def test_minimal_project(self) -> None:
        raw = {"id": "p3"}
        result = normalize_project(raw)
        assert result["name"] == ""
        assert result["color"] is None
        assert result["viewMode"] is None
        assert result["isClosed"] is False
