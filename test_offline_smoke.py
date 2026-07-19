"""Offline smoke test: verifies triage_incident's response-parsing logic against a
mocked Gemini client, without making a real network call. Not part of the Streamlit
app; run manually with `python test_offline_smoke.py`."""

from unittest.mock import MagicMock

from app import IncidentTriage, triage_incident


def main():
    expected = IncidentTriage(
        category="crowd_management",
        urgency="high",
        recommended_action="Open overflow lane and dispatch two additional stewards to Gate A.",
        requires_immediate_dispatch=True,
    )

    fake_response = MagicMock()
    fake_response.parsed = expected

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    result = triage_incident(fake_client, "Queue backing up badly at Gate A, wait is 20+ minutes")

    assert result == expected, f"Mismatch: {result}"
    call_kwargs = fake_client.models.generate_content.call_args.kwargs
    assert call_kwargs["config"].response_schema is IncidentTriage
    print("OK: triage_incident correctly reads .parsed from the Gemini response")

    fallback_response = MagicMock()
    fallback_response.parsed = None
    fallback_response.text = expected.model_dump_json()
    fake_client.models.generate_content.return_value = fallback_response

    result_fallback = triage_incident(fake_client, "Same incident again")
    assert result_fallback == expected, f"Fallback mismatch: {result_fallback}"
    print("OK: triage_incident falls back to parsing .text when .parsed is None")


if __name__ == "__main__":
    main()
