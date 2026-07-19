"""Unit tests for app.py's business logic (Gemini calls are mocked — no network,
no API key needed). Run with `pytest`."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app import IncidentTriage, ask_fan_assistant, generate_ops_digest, triage_incident


def make_response(text: str = "", parsed=None):
    response = MagicMock()
    response.text = text
    response.parsed = parsed
    return response


class TestIncidentTriageSchema:
    def test_valid_triage_constructs(self):
        triage = IncidentTriage(
            category="medical",
            urgency="critical",
            recommended_action="Dispatch medical team to Section 12 immediately.",
            requires_immediate_dispatch=True,
        )
        assert triage.category == "medical"
        assert triage.requires_immediate_dispatch is True

    def test_invalid_category_is_rejected(self):
        with pytest.raises(ValidationError):
            IncidentTriage(
                category="not_a_real_category",
                urgency="low",
                recommended_action="ignore",
                requires_immediate_dispatch=False,
            )

    def test_invalid_urgency_is_rejected(self):
        with pytest.raises(ValidationError):
            IncidentTriage(
                category="medical",
                urgency="super-urgent",
                recommended_action="ignore",
                requires_immediate_dispatch=False,
            )


class TestTriageIncident:
    def test_reads_parsed_field_when_present(self):
        expected = IncidentTriage(
            category="crowd_management",
            urgency="high",
            recommended_action="Open overflow lane at Gate A.",
            requires_immediate_dispatch=True,
        )
        client = MagicMock()
        client.models.generate_content.return_value = make_response(parsed=expected)

        result = triage_incident(client, "Queue backing up badly at Gate A")

        assert result == expected

    def test_falls_back_to_parsing_text_when_parsed_is_none(self):
        expected = IncidentTriage(
            category="facilities",
            urgency="low",
            recommended_action="Send a cleaning crew when convenient.",
            requires_immediate_dispatch=False,
        )
        client = MagicMock()
        client.models.generate_content.return_value = make_response(
            text=expected.model_dump_json(), parsed=None
        )

        result = triage_incident(client, "Spilled drink near Section B stairs")

        assert result == expected

    def test_passes_schema_and_json_mime_type_in_config(self):
        client = MagicMock()
        client.models.generate_content.return_value = make_response(
            parsed=IncidentTriage(
                category="other", urgency="low",
                recommended_action="log it", requires_immediate_dispatch=False,
            )
        )

        triage_incident(client, "Minor issue")

        call_kwargs = client.models.generate_content.call_args.kwargs
        config = call_kwargs["config"]
        assert config.response_schema is IncidentTriage
        assert config.response_mime_type == "application/json"


class TestGenerateOpsDigest:
    def test_includes_every_incident_in_the_prompt(self):
        client = MagicMock()
        client.models.generate_content.return_value = make_response(text="Priority list here.")
        incidents = [
            {"urgency": "critical", "category": "medical", "text": "Person collapsed at Gate C",
             "recommended_action": "Dispatch medical team"},
            {"urgency": "low", "category": "facilities", "text": "Bin overflowing at food court",
             "recommended_action": "Notify cleaning crew"},
        ]

        digest = generate_ops_digest(client, incidents)

        assert digest == "Priority list here."
        prompt_sent = client.models.generate_content.call_args.kwargs["contents"]
        assert "Person collapsed at Gate C" in prompt_sent
        assert "Bin overflowing at food court" in prompt_sent
        assert "CRITICAL" in prompt_sent


class TestAskFanAssistant:
    def test_returns_response_text_and_uses_system_prompt(self):
        client = MagicMock()
        client.models.generate_content.return_value = make_response(
            text="The nearest accessible restroom is next to Section 210."
        )

        answer = ask_fan_assistant(client, "Where's the nearest accessible restroom?")

        assert answer == "The nearest accessible restroom is next to Section 210."
        call_kwargs = client.models.generate_content.call_args.kwargs
        assert "accessible" in call_kwargs["config"].system_instruction.lower() or \
            "accessibility" in call_kwargs["config"].system_instruction.lower()
