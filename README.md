# 🎙️ Voice AI Finance Agent

A **production-oriented, modular, multi-agent voice AI system** for finance automation.

This project enables users to interact with financial data using **voice or text**, powered by a structured agent architecture, tool execution, retrieval (RAG), and persistent storage.

---

## 🚀 Overview

**Pipeline:**

```
Voice/Text → Orchestrator → Finance / Research / Action Agents 
→ Tools / DB / RAG → Response → Voice Output
```

The system is designed to be:

* Modular
* Extensible
* Locally runnable
* Production-aware (auth, logging, rate limiting included)

---

## ✨ Capabilities

### 🎤 Interaction

* Voice and text chat from browser UI
* Browser STT fallback for local voice input
* Backend Whisper STT (when `ffmpeg` is installed)
* Spoken responses via backend TTS

---

### 💼 Finance Operations

* Invoice:

  * Create, list, summarize, mark as paid
* Transactions:

  * Create, list, balance, spending summary
* Reminders:

  * Create, list, mark done

---

### 🧠 Intelligence Layer

* Multi-agent architecture:

  * Orchestrator (routing)
  * Finance agent
  * Research agent
  * Action agent
* RAG (Retrieval-Augmented Generation):

  * FAISS-based retrieval
  * Local embedding fallback (works offline)
* Research responses:

  * Works even without OpenAI/network

---

### 🗄️ Persistence

* SQLite (default)
* Optional PostgreSQL via `DATABASE_URL`
* Stores:

  * Invoices
  * Transactions
  * Reminders
  * Conversation memory

---

### ⚙️ Production Features

* Authentication support
* Rate limiting
* Request IDs
* Structured logging
* Modular architecture (clean separation of concerns)

---

## 🧠 System Architecture

```
User Input (Voice/Text)
        ↓
Speech-to-Text (Browser / Whisper)
        ↓
Orchestrator Agent
        ↓
┌───────────────┬───────────────┬───────────────┐
│ Finance Agent │ Research Agent│ Action Agent  │
└───────────────┴───────────────┴───────────────┘
        ↓
Tools / Database / RAG
        ↓
LLM Response
        ↓
Text-to-Speech
        ↓
Voice Output
```

---

## 📁 Project Structure

```
voice-ai-finance-agent/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── routes.py
│   │   └── websocket.py
│   │
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── research_agent.py
│   │   ├── finance_agent.py
│   │   └── action_agent.py
│   │
│   ├── llm/
│   │   ├── llm_provider.py
│   │   ├── prompts/
│   │   └── memory.py
│   │
│   ├── rag/
│   │   ├── vector_store.py
│   │   ├── retriever.py
│   │   └── embeddings.py
│   │
│   ├── voice/
│   │   ├── stt.py
│   │   ├── tts.py
│   │   └── streaming.py
│   │
│   ├── tools/
│   │   ├── invoice_tools.py
│   │   ├── reminder_tools.py
│   │   └── transaction_tools.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── crud.py
│   │
│   └── utils/
│
├── data/
├── tests/
├── frontend/
├── scripts/
├── docker/
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## 📌 Important Files

* `app/main.py`
  Initializes FastAPI, database, routes, and frontend

* `app/api/routes.py`
  REST endpoints: chat, finance actions, reminders, memory

* `app/api/websocket.py`
  Handles audio streaming for Whisper and TTS

* `app/agents/`
  Orchestrator + domain-specific agents

* `app/tools/`
  Structured backend execution functions

* `app/db/`
  SQLAlchemy models, database config, CRUD

* `app/llm/memory.py`
  Conversation memory storage

* `app/rag/`
  Embeddings, FAISS index, retrieval

* `frontend/`
  Voice + text UI

---

## ⚙️ Installation & Setup

### 1. Clone repository

```
git clone https://github.com/PunyaSethi/voice-ai-finance-agent.git
cd voice-ai-finance-agent
```

---

### 2. Setup environment

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

### 3. Initialize database

```
python scripts/setup_db.py
```

---

### 4. Ingest data (optional)

```
python scripts/ingest_data.py
```

---

### 5. Run server

```
uvicorn app.main:app --reload
```

---

## 🌐 Access Points

* Health:
  `http://localhost:8000/api/health`

* Capabilities:
  `http://localhost:8000/api/capabilities`

* Chat API:
  `POST http://localhost:8000/api/chat`

* WebSocket:
  `ws://localhost:8000/ws`

* Frontend UI:
  `http://127.0.0.1:8000/frontend/index.html`

---

## 🧪 Example Commands

```
show invoices
create invoice for 5000 for Rahul
invoice summary
add expense 250 for food
how much did I spend last week
what is my balance
remind me to send invoice tomorrow at 10am
show reminders
explain GST for freelancers
```

---

## 🎤 Backend Voice STT (Whisper)

To enable backend transcription:

```
winget install Gyan.FFmpeg
ffmpeg -version
```

Once installed:

* Audio is streamed to backend
* Whisper handles transcription
* TTS responses are returned

---

## 🔐 Environment Variables

Create `.env` from `.env.example`:

```
OPENAI_API_KEY=your_key_here
DATABASE_URL=sqlite:///./finance.db
```

Notes:

* OpenAI key is optional for basic operations
* Required for advanced research queries

---

## 🧪 Testing

```
pytest
```

---

## 🧠 Key Concepts

### Multi-Agent Architecture

* Orchestrator decides routing
* Agents specialize in tasks
* Tools execute actions

---

### RAG (Retrieval-Augmented Generation)

* Enhances responses with context
* Works offline with fallback embeddings

---

### Voice Pipeline

* Supports browser + backend STT
* End-to-end voice interaction

---

## 🚀 Future Improvements

* Real-time streaming STT
* Improved agent reasoning (LLM-based orchestration)
* Better database scaling (PostgreSQL + migrations)
* Advanced analytics (spending insights)
* Cloud deployment (AWS/GCP)

---

## 🤝 Contributing

Feel free to fork and submit PRs.

---

## 🎬 Demo

*https://drive.google.com/file/d/1-kIr39xbTel9LwX5exHIrwuuMKMF2xbQ/view?usp=sharing*

---

## 👨‍💻 Author

**Punya**
AI Systems & Engineering Enthusiast
