# Smart Stadium Copilot — FIFA World Cup 2026

**Challenge 4: Smart Stadiums & Tournament Operations**

A GenAI-powered assistant for stadium operations during the FIFA World Cup 2026,
built around two personas that share one venue knowledge base and one incident feed:

- **Fan Assistant** — a multilingual concierge for navigation, accessibility,
  transportation, and sustainability questions.
- **Ops Control Room** — an incident-triage and real-time decision-support tool
  for volunteers, staff, and the control room commander.

Live demo: **[add your deployed Streamlit URL here]**

## How this maps to the challenge

| Challenge theme | How it's addressed |
|---|---|
| Navigation | Fan Assistant answers gate/section/route questions grounded in venue data |
| Accessibility | Dedicated accessibility facts (ramps, accessible restrooms, sensory room, hearing loops) the assistant surfaces on request |
| Transportation | Transit options and post-match exit-crowding guidance per gate |
| Sustainability | Water refill stations, recycling/compost, reusable-cup program |
| Multilingual assistance | Claude answers in whatever language the fan asks in — no separate translation step |
| Operational intelligence | Free-text incident reports are classified into category/urgency/action via structured outputs |
| Real-time decision support | "Generate Live Ops Digest" turns a pile of raw incident reports into a prioritized action list on demand |

## Why this design

**One knowledge base, two audiences.** Fans and staff are both trying to answer
"what do I do right now" — the difference is fans ask in natural language about
themselves, staff report what they're observing about the venue. Both are a
retrieval-and-reasoning problem, not a lookup-table problem, which is exactly
where an LLM adds value over a static FAQ or a hardcoded ops runbook.

**Multilingual is free, not a feature to build.** Rather than a translation
API + a separate NLU pipeline, the system prompt just instructs Claude to
respond in the fan's own language — Claude's multilingual fluency does the
work directly. This is deliberately the simplest possible way to hit the
"multilingual assistance" requirement well, instead of over-engineering a
translation layer.

**Structured outputs for triage, not free-text.** Incident reports are
classified into a fixed schema (`category`, `urgency`, `recommended_action`,
`requires_immediate_dispatch`) via Claude's structured outputs — guaranteed
parseable, so the control-room dashboard can render consistently and flag
dispatch-worthy incidents without regex-parsing free text.

**Real-time decision support, not just classification.** Classifying one
incident at a time is table stakes. The Ops Digest step takes the *entire*
current incident list and asks Claude to synthesize a prioritized action
list — the harder, more valuable step: turning many individually-triaged
reports into one coherent recommendation for whoever is actually in charge
during a live event.

## What's simulated for this demo

- The venue ("Continental Arena") and its gates/sections/services are a
  representative fixture (`stadium_kb.py`), not a live feed — a production
  version would source this from the venue's wayfinding and transit systems.
- Incidents are entered manually in the Ops Control Room tab rather than
  arriving from a real volunteer radio/dispatch system.
- No authentication — a real deployment would gate the Ops Control Room
  behind staff login, separate from the public Fan Assistant.

## Tech stack

Python + [Streamlit](https://streamlit.io/) (single-file server-rendered app —
fastest path to a live, judge-testable deployment) + the official
[`anthropic`](https://github.com/anthropics/anthropic-sdk-python) Python SDK,
model `claude-sonnet-5`.

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

## Deploying (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io/), sign in with GitHub.
3. "New app" → select this repo, branch `main`, main file `app.py`.
4. Under **Advanced settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. Deploy — the app is live at `https://<your-app-name>.streamlit.app`.
