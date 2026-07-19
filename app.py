import os
from datetime import datetime
from typing import Literal

import streamlit as st
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from stadium_kb import SYSTEM_PROMPT

MODEL = "gemini-3.5-flash"

st.set_page_config(
    page_title="Smart Stadium Copilot — FIFA World Cup 2026",
    page_icon="🏟️",
    layout="wide",
)


@st.cache_resource
def get_client() -> genai.Client:
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error(
            "No GEMINI_API_KEY configured. Add it under this app's Settings → Secrets "
            "on Streamlit Community Cloud, or set the GEMINI_API_KEY environment "
            "variable when running locally. Get a free key at aistudio.google.com."
        )
        st.stop()
    return genai.Client(api_key=api_key)


class IncidentTriage(BaseModel):
    category: Literal[
        "crowd_management", "medical", "accessibility", "security",
        "facilities", "transportation", "sustainability", "other",
    ]
    urgency: Literal["low", "medium", "high", "critical"]
    recommended_action: str
    requires_immediate_dispatch: bool


def triage_incident(client: genai.Client, description: str) -> IncidentTriage:
    response = client.models.generate_content(
        model=MODEL,
        contents=description,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You triage incident reports called in by volunteers and staff at a FIFA World "
                "Cup 2026 stadium. Classify each report and recommend one concrete next action "
                "for the control room. Set requires_immediate_dispatch=true only for medical "
                "emergencies, security threats, or crowd-crush risk — not for routine facilities "
                "issues."
            ),
            response_mime_type="application/json",
            response_schema=IncidentTriage,
        ),
    )
    if response.parsed is not None:
        return response.parsed
    return IncidentTriage.model_validate_json(response.text)


def generate_ops_digest(client: genai.Client, incidents: list[dict]) -> str:
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
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text


def ask_fan_assistant(client: genai.Client, question: str) -> str:
    response = client.models.generate_content(
        model=MODEL,
        contents=question,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text


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
  category/urgency/action via structured outputs.
- **Real-time decision support** — the Ops Digest turns a pile of raw incident
  reports into a prioritized action list for the control room, on demand.

Model: `gemini-3.5-flash` (Google AI Studio, free tier)
            """
        )
        st.divider()
        st.caption("Demo venue and incidents are simulated for this submission.")


def render_fan_assistant(client: genai.Client):
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
            answer = None
            with st.spinner("Checking stadium info..."):
                try:
                    answer = ask_fan_assistant(client, question)
                except genai_errors.APIError as e:
                    st.error(f"Gemini API error: {e}")
            if answer:
                st.markdown(answer)
        if answer:
            st.session_state.chat_history.append({"role": "assistant", "content": answer})


def render_ops_control_room(client: genai.Client):
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
            try:
                triage = triage_incident(client, incident_text)
            except genai_errors.APIError as e:
                triage = None
                st.error(f"Gemini API error: {e}")
        if triage:
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
            digest = None
            with st.spinner("Summarizing for the control room..."):
                try:
                    digest = generate_ops_digest(client, st.session_state.incidents)
                except genai_errors.APIError as e:
                    st.error(f"Gemini API error: {e}")
            if digest:
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
