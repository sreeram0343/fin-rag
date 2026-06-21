# FinRAG: Principal Backend Architecture Design
## AI Infrastructure & Software Architecture Specification

---

## 1. Architectural Overview

The backend uses a **decoupled microservices/modular-monolith architecture** built on top of **FastAPI** (for high-performance async API routing) and **Celery** (for asynchronous event task distribution). 

```
                                  ┌──────────────┐
                                  │ Redis Cache  │
                                  └──────▲───────┘
                                         │
[Client API] ──► [FastAPI Gateway] ──────┼──────► [PostgreSQL & Vector DB]
                       │                 │
                       ▼ (Publish Job)   │
                [Celery Workers] ────────┘
```

---

## 2. Component Design & System Services

### 2.1 Core Services
*   **API Gateway & Document Service (FastAPI):** Exposes REST endpoints to users, parses file streams, authenticates requests, stores files in object storage, and initiates database records.
*   **Document Processing Worker (Celery):** Subscribes to document ingestion tasks. It handles OCR, visual parsing, table extraction, and layout coordinate compilation.
*   **Vector Indexing Worker (Celery):** Generates dense vector embeddings for text chunks and inserts index records into the Vector DB (Pinecone/Qdrant).
*   **Retrieval & Query Processor (FastAPI Service):** Orchestrates multi-vector hybrid search, queries the relational database for segment metadata, and calls the reranking model.
*   **Agentic Synthesis Orchestrator (FastAPI Service):** Controls the LLM loop, manages the mathematical validation sandbox, and formats output reports.

---

## 3. API Design & Endpoints

All APIs use standard REST conventions, accept JSON payloads, return appropriate HTTP statuses, and support JWT authorization.

### Ingestion API
*   **`POST /api/v1/documents/upload`**
    *   **Payload:** `multipart/form-data` containing `file` (PDF/HTML), `ticker` (str), `period` (str), `year` (int).
    *   **Response (202 Accepted):**
        ```json
        {
          "job_id": "job_01h2a8cd90f...",
          "status": "QUEUED",
          "document_id": "doc_01h2a8ce22...",
          "created_at": "2026-06-21T21:42:04Z"
        }
        ```
*   **`GET /api/v1/documents/jobs/{job_id}`**
    *   **Response (200 OK):**
        ```json
        {
          "job_id": "job_01h2a8cd90f...",
          "status": "PROCESSING",
          "current_step": "OCR_PARSING",
          "progress_percentage": 45
        }
        ```

### Query & QA API
*   **`POST /api/v1/queries/ask`**
    *   **Payload:**
        ```json
        {
          "query": "Compare Q2 gross margin against Q1 guidance notes.",
          "ticker": "AAPL",
          "filters": {
            "years": [2025, 2026],
            "document_types": ["10-Q", "transcript"]
          }
        }
        ```
    *   **Response (200 OK):** Contains the compiled markdown answer mapped side-by-side with coordinates:
        ```json
        {
          "answer": "Gross margin for Q2 was 46.2%, matching prior guidance...",
          "citations": [
            {
              "id": "cit_001",
              "text": "gross margin was 46.2%",
              "document_id": "doc_01h2a8ce22...",
              "page": 14,
              "bounding_box": [120, 450, 250, 500]
            }
          ]
        }
        ```

---

## 4. Background Workers & Task Queues

We use **Celery** with a **Redis** message broker backend to partition compute-heavy modules (OCR, embedding calculations).

### Processing Pipeline Lifecycle:
```
[Queued] ──► [Parsing/OCR] ──► [Chunking] ──► [Embedding] ──► [Indexing] ──► [Completed]
```

*   **Concurrency Routing:** Workers are partitioned into dedicated queues based on resource profiles:
    *   `ocr-queue`: GPU-bound workers running LayoutLM/Tesseract models.
    *   `indexing-queue`: CPU-bound workers calling external API embedders.
*   **Idempotency & Deduplication:** When a file is received, its SHA-256 hash is checked against the database. If a match is found, the file indexing step is skipped, and references are cloned.

---

## 5. Database Interactions & Schema Design

We deploy a **dual-database schema** using **PostgreSQL** for relational metadata and **Qdrant/Pinecone** for high-dimensional vector partitions.

### 5.1 Relational Schema (PostgreSQL):
*   **`documents` Table:** Tracks file storage URI, ticker, period, upload date, and SHA-256 file signature.
*   **`document_chunks` Table:** Holds the raw text chunks, parent headers, structural metadata, and coordinate coordinate arrays (`page`, `bbox`).
*   **`audit_logs` Table:** Records user query history, prompt token consumption, execution times, and LLM model flags for financial audit compliance.

### 5.2 Database Layer Extensibility (SQLAlchemy):
*   Database calls utilize async engines (`AsyncSession` from SQLAlchemy) to prevent blocking the FastAPI event loops.
*   Connection pooling configured using: `pool_size=20, max_overflow=10, pool_timeout=30`.

---

## 6. Model Interfaces & Dependency Injection

To support multiple models (e.g., swapping Claude for a local Llama model) and parsing engines, we use abstract base classes (ABCs) coupled with FastAPI's **Dependency Injection** system.

### Base LLM Provider Interface (`src/finrag/agent/base.py`):
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseLLM(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str, temperature: float = 0.0) -> Dict[str, Any]:
        """Generate response given a text prompt."""
        pass
```

### FastAPI Dependency Injection (`src/finrag/api/dependencies.py`):
```python
from fastapi import Depends
from finrag.core.config import settings
from finrag.agent.base import BaseLLM
from finrag.agent.openai_client import OpenAIProvider
from finrag.agent.anthropic_client import AnthropicProvider

def get_llm_provider() -> BaseLLM:
    if settings.ENV == "production":
        # Institutional deployment leverages strict Claude ZDR endpoints
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
    # Local development falls back to OpenAI models
    return OpenAIProvider(api_key=settings.OPENAI_API_KEY)
```

---

## 7. Caching Strategy

We use a high-performance **Redis** cache instance to decrease downstream API latencies and minimize recurring LLM token consumption costs.

1.  **Semantic Retrieval Cache:** User queries are hashed and checked in Redis (TTL: 1 hour). If the query is an exact match and target filings haven't changed, cached results are returned.
2.  **Metadata Cache:** High-frequency relational metadata lookup fields (e.g. list of documents uploaded for ticker TSLA) are cached (TTL: 10 minutes) to avoid redundant PostgreSQL queries.
3.  **LLM Context Caching:** When using Anthropic API routes, we declare system prompts and retrieved contexts with context caching headers, saving up to 90% in token pricing.

---

## 8. Authentication & Authorization

Institutional security mandates strict boundaries around data access:
*   **Authentication (AuthN):** Enforced via OAuth2 with JWT tokens containing signature encryption. Integration with corporate Identity Providers (IdP) via SAML 2.0 or OpenID Connect (OIDC) is supported.
*   **Authorization (AuthZ):** Implemented using Role-Based Access Control (RBAC). Scopes are validated at the route controller layer:
    *   `read:reports`: Can execute queries and view data.
    *   `write:documents`: Can upload financial filings to parser pipelines.
    *   `admin:system`: Access to audit log statistics and pipeline scaling.
*   **Tenant Isolation:** Row-Level Security (RLS) is configured in PostgreSQL to isolate client document access.

---

## 9. Monitoring & Observability

We use the **Prometheus** and **OpenTelemetry** standards for logging, metrics, and tracing:
*   **Log Spans:** OpenTelemetry middleware injects `trace_id` headers into request payloads, enabling trace visualization across parsing workers, database transactions, and model APIs.
*   **Core Metrics Tracked:**
    *   *System Metrics:* API request count (by HTTP code), request latencies (P95/P99), queue backlogs.
    *   *AI Metrics:* LLM prompt/completion token count, model call latency, verification math failure rates.
    *   *Infrastructure:* GPU temperature/utilization (for local OCR nodes), DB connection pool size.
