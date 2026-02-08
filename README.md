# WhatsApp + Google Conversational Agents Integration

A FastAPI webhook server that connects WhatsApp to Google Conversational Agents (Dialogflow CX) and Gemini AI. Incoming WhatsApp messages are enqueued to a Redis-backed ARQ worker for async processing, so the webhook returns `200 OK` immediately without risking Meta timeout/retries.

## Architecture

```
WhatsApp User
     │
     ▼
Meta Cloud API ──POST /webhook──▶ FastAPI
                                    │
                                    ├─ verify signature
                                    ├─ parse payload
                                    ├─ mark message as read
                                    └─ enqueue to Redis ──▶ ARQ Worker
                                                              │
                                          ┌───────────────────┼───────────────────┐
                                          ▼                   ▼                   ▼
                                   Text messages       Media messages       Other types
                                          │                   │            (location, contacts)
                                          ▼                   ▼
                                  Dialogflow CX          Gemini AI
                                  (intent detection)     (image/doc/audio analysis)
                                          │                   │
                                          └─────────┬─────────┘
                                                    ▼
                                            WhatsApp reply
```

## Supported Message Types

| Type | Processing |
|---|---|
| Text | Dialogflow CX intent detection and response |
| Image | Gemini AI image analysis |
| Document | Gemini AI document summarization |
| Audio/Voice | Gemini AI transcription |
| Video | Logged (processing TBD) |
| Location | Logged (processing TBD) |
| Contacts | Logged (processing TBD) |

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- Redis server
- Meta WhatsApp Business API app (App Secret, Access Token, Phone ID)
- Google Cloud project with Dialogflow CX agent
- Gemini API key

## Setup

1. **Clone and install dependencies**

   ```bash
   git clone <repo-url>
   cd google-conversational-agents-whatsapp
   uv sync
   ```

2. **Configure environment variables**

   ```bash
   cp .env.example .env
   ```

   Fill in your `.env`:

   | Variable | Description |
   |---|---|
   | `PORT` | Server port (default: `8080`) |
   | `APP_SECRET` | Meta app secret for webhook signature verification |
   | `ACCESS_TOKEN` | WhatsApp Cloud API access token |
   | `PHONE_ID` | WhatsApp phone number ID |
   | `WEBHOOK_VERIFICATION_TOKEN` | Token you set when subscribing the webhook in Meta dashboard |
   | `GCP_SERVICE_ACCOUNT_JSON` | GCP service account credentials (JSON string or file path) |
   | `CA_PROJECT_ID` | Google Cloud project ID |
   | `CA_AGENT_ID` | Dialogflow CX agent ID |
   | `CA_LOCATION` | Dialogflow CX agent location (e.g. `us-central1`) |
   | `GEMINI_API_KEY` | Google Gemini API key |
   | `REDIS_URL` | Redis connection URL (default: `redis://localhost:6379/0`) |

3. **Start Redis**

   ```bash
   docker run -d --name redis -p 6379:6379 redis:7-alpine
   ```

## Running

You need three processes running:

```bash
# Terminal 1 — FastAPI server
uv run python run.py

# Terminal 2 — ARQ worker
uv run python run_worker.py
```

The FastAPI server starts on `http://127.0.0.1:8080` by default.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `GET` | `/webhook` | Meta webhook verification (hub challenge) |
| `POST` | `/webhook` | Receive and enqueue WhatsApp messages |

## Project Structure

```
├── run.py              # FastAPI server entrypoint
├── run_worker.py       # ARQ worker entrypoint
├── pyproject.toml
├── .env.example
└── src/
    ├── __init__.py     # Logging setup
    ├── config.py       # Environment variable loading
    ├── main.py         # FastAPI app, webhook routes, lifespan
    ├── models.py       # Pydantic models for WhatsApp payloads
    ├── security.py     # Webhook signature verification
    ├── queue.py        # Redis pool management + enqueue helper
    ├── worker.py       # ARQ worker tasks + WorkerSettings
    ├── ca_client.py    # Dialogflow CX client
    ├── gemini_client.py# Gemini AI client
    └── whatsapp_client.py # WhatsApp Cloud API client
```

## How It Works

1. Meta sends a `POST /webhook` with the message payload
2. FastAPI verifies the `X-Hub-Signature-256` header against `APP_SECRET`
3. The payload is parsed and each message is marked as read immediately
4. Message content is serialized and pushed to Redis via ARQ
5. The webhook returns `200 OK` — total latency is just signature check + Redis enqueue
6. The ARQ worker picks up the job and routes it by message type:
   - **Text** goes to Dialogflow CX for intent detection
   - **Image/Document/Audio** is downloaded from WhatsApp then processed by Gemini AI
7. The response is sent back to the user via WhatsApp Cloud API
