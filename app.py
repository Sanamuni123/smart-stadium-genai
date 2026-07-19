import os
from datetime import datetime
from typing import Literal

import anthropic
import streamlit as st
from pydantic import BaseModel

from stadium_kb import SYSTEM_PROMPT

MODEL = "claude-sonnet-5"

st.set_page_config(
    page_title="Smart Stadium Copilot — FIFA World Cup 2026",
    page_icon="🏟️",
    layout="wide",
)


def get_client() -> anthropic.Anthropic:
    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error(
            "No ANTHROPIC_API_KEY configured. Add it under this app's Settings → Secrets "
            "on Streamlit Community Cloud, or set the ANTHROPIC_API_KEY environment "
            "variable when running locally."
        )
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


class IncidentTriage(BaseModel):
    category: Literal[
        "crowd_management", "medical", "accessibility", "security",
        "facilities", "transportation", "sustainability", "other",
    ]
    urgency: Literal["low", "medium", "high", "critical"]
    recommended_action: str
    requires_immediate_dispatch: bool


def triage_incident(client: anthropic.Anthropic, description: str) -> IncidentTriage:
    response = client.messages.parse(
        model=MODEL,
        max_tokens=512,
        system=(
            "You triage incident reports called in by volunteers and staff at a FIFA World Cup "
            "2026 stadium. Classify each report and recommend one concrete next action for the "
            "control room. Set requires_immediate_dispatch=true only for medical emergencies, "
            "security threats, or crowd-crush risk — not for routine facilities issues."
        ),
        messages=[{"role": "user", "content": description}],
        output_format=IncidentTriage,
    )
    parsed = next(
        (block.parsed_output for block in response.content if block.type == "text"),
        None,
    )
    if parsed is None:
        raise ValueError("Claude returned no parsed structured output for this incident")
    return parsed


def generate_ops_digest(client: anthropic.Anthropic, incidents: list[dict]) -> str:
    incident_lines = "\n".join(
        f"- [{i['urgency'].upper()}] {i['category']}: {i['text']} "
        f"(suggested: {i['recommended_action']})"
        for i in incidents
    )
    prompt = (
        "Here are all currently open incidents reported at the stadium tonight:\n\n"
        f"{incident_lines}\n\n"
        "Produce a short prioritized action list (at most 5 items) for the control room "
        "commander, ordered by urgency and operational impact. Be direct and operational — "
        "this is read under time pressure during a live event."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return next((block.text for block in response.content if block.type == "text"), "")


def ask_fan_assistant(client: anthropic.Anthropic, question: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    return next((block.text for block in response.content if block.type == "text"), "")


def render_sidebar():
    with st.sidebar:
        st.title("🏟️ Smart Stadium Copilot")
        st.caption("Challenge 4 — Smart Stadiums & Tournament Operations")
        st.markdown(
            """
**How this uses GenAI:**
- **Multilingual navigation & accessibility** — Fan Assistant answers in whatever
  language a fan asks in, grounded in venue facts (no hallucinated gate numbers).
- **Operational intelligence** — free-text incident reports are classified into
  category/urgency/action via Claude's structured outputs.
- **Real-time decision support** — the Ops Digest turns a pile of raw incident
  reports into a prioritized action list for the control room, on demand.

Model: `claude-sonnet-5`
            """
        )
        st.divider()
        st.caption("Demo venue and incidents are simulated for this submission.")


def render_fan_assistant(client: anthropic.Anthropic):
    st.header("🗣️ Fan Assistant")
    st.caption("Ask about navigation, accessibility, transport, or sustainability — in any language.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("e.g. Where's the nearest wheelchair-accessible restroom to Gate B?")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Checking stadium info..."):
                answer = ask_fan_assistant(client, question)
            st.markdown(answer)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})


def render_ops_control_room(client: anthropic.Anthropic):
    st.header("🛠️ Ops Control Room")
    st.caption("Simulates volunteers/staff phoning in incidents during the tournament.")

    if "incidents" not in st.session_state:
        st.session_state.incidents = []

    with st.form("incident_form", clear_on_submit=True):
        incident_text = st.text_area(
            "Log an incident report",
            placeholder="e.g. Queue backing up badly at Gate A, wait is 20+ minutes and growing",
        )
        submitted = st.form_submit_button("Submit & triage")

    if submitted and incident_text.strip():
        with st.spinner("Triaging incident..."):
            triage = triage_incident(client, incident_text)
        st.session_state.incidents.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "text": incident_text,
            "category": triage.category,
            "urgency": triage.urgency,
            "recommended_action": triage.recommended_action,
            "dispatch": triage.requires_immediate_dispatch,
        })

    urgency_color = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

    if st.session_state.incidents:
        st.subheader(f"Open incidents ({len(st.session_state.incidents)})")
        for incident in st.session_state.incidents:
            badge = urgency_color.get(incident["urgency"], "⚪")
            dispatch_flag = " · **IMMEDIATE DISPATCH**" if incident["dispatch"] else ""
            with st.container(border=True):
                st.markdown(
                    f"{badge} `{incident['time']}` **{incident['category']}** "
                    f"— {incident['urgency']}{dispatch_flag}"
                )
                st.write(incident["text"])
                st.caption(f"Suggested action: {incident['recommended_action']}")

        st.divider()
        if st.button("📋 Generate Live Ops Digest", type="primary"):
            with st.spinner("Summarizing for the control room..."):
                digest = generate_ops_digest(client, st.session_state.incidents)
            st.subheader("Live Ops Digest")
            st.info(digest)
    else:
        st.info("No incidents logged yet — submit one above to see triage in action.")


def main():
    client = get_client()
    render_sidebar()
    fan_tab, ops_tab = st.tabs(["🗣️ Fan Assistant", "🛠️ Ops Control Room"])
    with fan_tab:
        render_fan_assistant(client)
    with ops_tab:
        render_ops_control_room(client)


if __name__ == "__main__":
    main()
