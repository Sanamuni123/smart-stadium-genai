"""Offline smoke test: verifies triage_incident's response-parsing logic against a
constructed ParsedMessage, without making a real network call. Not part of the
Streamlit app; run manually with `python test_offline_smoke.py`."""

from unittest.mock import MagicMock

from anthropic.types.parsed_message import ParsedMessage, ParsedTextBlock

from app import IncidentTriage, triage_incident


def build_fake_parsed_response(triage: IncidentTriage) -> ParsedMessage:
    text_block = ParsedTextBlock.model_construct(
        type="text",
        text=triage.model_dump_json(),
        citations=None,
        parsed_output=triage,
    )
    return ParsedMessage.model_construct(
        id="msg_test",
        content=[text_block],
        model="claude-sonnet-5",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=None,
        container=None,
        stop_details=None,
    )


def main():
    expected = IncidentTriage(
        category="crowd_management",
        urgency="high",
        recommended_action="Open overflow lane and dispatch two additional stewards to Gate A.",
        requires_immediate_dispatch=True,
    )

    fake_client = MagicMock()
    fake_client.messages.parse.return_value = build_fake_parsed_response(expected)

    result = triage_incident(fake_client, "Queue backing up badly at Gate A, wait is 20+ minutes")

    assert result == expected, f"Mismatch: {result}"
    assert fake_client.messages.parse.call_args.kwargs["output_format"] is IncidentTriage
    print("OK: triage_incident correctly reads parsed_output from the text content block")


if __name__ == "__main__":
    main()
