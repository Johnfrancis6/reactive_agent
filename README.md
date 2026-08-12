# React Agent — LangGraph + FastAPI + PostgreSQL

Production-ready AI agent with persistent memory, guardrails, and human-in-the-loop approval.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLAlchemy async |
| Agent | LangGraph (StateGraph) |
| LLM | Groq — llama-3.3-70b / llama-3.1-8b |
| Memory | PostgreSQL — JSONB (LTM) + AsyncPostgresSaver (STM) |
| Tools | DuckDuckGo · smtplib · AST calculator |
| Frontend | Next.js 15 + TypeScript |

---

## Setup

```bash
git clone https://github.com/Johnfrancis6/reactive_agent.git
cd reactive_agent

uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

cp .env.example .env   # fill in GROQ_API_KEY

make dev               # starts PostgreSQL + backend
```

---

## Environment Variables

| Variable | Required | Default |
|---|---|---|
| `DATABASE_URL` | Yes | — |
| `GROQ_API_KEY` | Yes | — |
| `LLM_GENERATOR` | No | `llama-3.3-70b-versatile` |
| `LLM_CLARIFIER` | No | `llama-3.1-8b-instant` |
| `SMTP_HOST/PORT/USER/PASSWORD/FROM_EMAIL` | No | email tool disabled if missing |

---

## Architecture

```
POST /agent/chat
     │
     ├─► input_validation      → blocks injections, scores risk
     ├─► planner           → JSON plan + tool selection
     ├─► agent_llm    ◄────────────────────────┐
     │       │                                  │
     │       ├─ tool calls + approval ──► human_loop
     │       ├─ tool calls ──────────► tool_executor ─┘
     │       └─ no tool calls ──────► output_guard
     │
     └─► LTM extract + save
```

---

## API

| Endpoint | Description |
|---|---|
| `POST /agent/chat` | Start or continue a conversation |
| `GET /agent/stream/{session_id}` | SSE — stream graph events in real time |
| `POST /agent/approve` | Resume graph after human approval |

---

## Make Commands

```bash
make dev        # start PostgreSQL + backend
make stop       # stop PostgreSQL
make logs       # PostgreSQL logs
make db-reset   # reset database (deletes all data)
make db-shell   # psql shell
make db-memory  # show long-term memory
make lint       # ruff check + format
make test       # pytest
make build      # Docker prod image
```

---

## Known Bugs Fixed

| File | Bug | Fix |
|---|---|---|
| `long_term.py` | `json.loads()` on asyncpg JSONB dict | `isinstance` check |
| `long_term.py` | `::jsonb` rejected by asyncpg | `CAST(:param AS jsonb)` |
| `email_sender.py` | `get_event_loop()` deprecated 3.10+ | `get_running_loop()` |
| `web_search.py` | same | same |
| `agent_llm.py` | `requires_human_approval` not propagated | added to return dict |
| `output_guard.py` | checks last message regardless of type | filter for `AIMessage` |
| `routes/agent.py` | `_get_ltm_llm()` missing return | fixed |
