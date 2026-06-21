# FinRAG Production Repository Layout & Engineering Standards
## Software Architecture Specification

---

## 1. Directory Structure Tree

The structure below represents a modular, scalable, and highly testable repository design for an institutional-grade financial RAG platform.

```text
fin-rag/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Run lint, typecheck, pytest on PR
│       └── cd.yml                 # Build Docker image & deploy to ECR/VPC
├── .env.example                   # Environment configuration template
├── pyproject.toml                 # Poetry dependencies and build config
├── poetry.lock                    # Locked exact dependency versions
├── ruff.toml                      # Linting and formatting rules (replaces black/flake8)
├── alembic.ini                    # Database migration configuration
├── docker-compose.yml             # Local multi-container deployment (Postgres, Redis, Qdrant)
├── Dockerfile                     # Multi-stage production Docker build
├── docs/
│   ├── api.md                     # API endpoints documentation
│   ├── deployment.md              # VPC / Cloud deployment runbooks
│   └── architecture/              # High-level architecture details
│
├── config/                        # Static JSON/YAML configs (non-sensitive)
│   ├── parser_config.json
│   └── logging_config.json
│
├── migrations/                    # SQL Database migrations (Alembic)
│   ├── env.py
│   └── versions/
│
├── scripts/                       # DevOps, db seeding, and manual runners
│   ├── seed_db.py
│   └── run_local_worker.sh
│
├── src/                           # Main Application Package Source
│   └── finrag/
│       ├── __init__.py
│       ├── main.py                # FastAPI ASGI application entrypoint
│       │
│       ├── api/                   # API Routing and Controller Layer
│       │   ├── __init__.py
│       │   ├── dependencies.py    # Common dependencies (DB, Auth, Rate-limiter)
│       │   ├── v1/
│       │   │   ├── router.py      # Entry point for version 1 routes
│       │   │   ├── ingest.py      # Document uploading & ingestion control
│       │   │   └── query.py       # QA queries & report execution
│       │   └── middleware/
│       │       └── exception_handler.py
│       │
│       ├── core/                  # Core Systems and Configurations
│       │   ├── __init__.py
│       │   ├── config.py          # Dynamic configuration parser (Pydantic Settings)
│       │   ├── exceptions.py      # Global custom Exception classes
│       │   ├── logging.py         # Structured JSON logging initialization
│       │   └── security.py        # Encryption, token verification
│       │
│       ├── parser/                # Document Ingestion & Structural OCR Service
│       │   ├── __init__.py
│       │   ├── base.py            # Base abstract class interface
│       │   ├── layoutlm.py        # LayoutLMv3-based OCR parser
│       │   ├── textract.py        # AWS Textract integration module
│       │   └── utils.py           # Table cleaning and coordinate helpers
│       │
│       ├── chunker/               # Semantic & Layout-Aware Segmenting
│       │   ├── __init__.py
│       │   ├── base.py            # Base Chunker interface
│       │   ├── financial.py       # Custom header/table segmenter
│       │   └── tokenizer.py       # Token-count enforcement utilities
│       │
│       ├── indexer/               # Embedding generation and database loading
│       │   ├── __init__.py
│       │   ├── dense.py           # Vector embedding client integration
│       │   └── loader.py          # Pipeline manager (Chunk -> Embed -> Load DB)
│       │
│       ├── retriever/             # Dense & Sparse Search Engine
│       │   ├── __init__.py
│       │   ├── base.py            # Base Retriever interface
│       │   ├── hybrid.py          # Hybrid sparse/dense search router
│       │   └── reranker.py        # Cross-encoder score refiner
│       │
│       ├── agent/                 # Agentic Synthesis & Math Verification
│       │   ├── __init__.py
│       │   ├── orchestrator.py    # Main QA controller
│       │   ├── verification.py    # Python arithmetic execution sandbox
│       │   └── tools/             # Agent tools (Calculators, DB queries)
│       │
│       ├── db/                    # Relational Database Models & Store clients
│       │   ├── __init__.py
│       │   ├── session.py         # SQLAlchemy engine & session factory
│       │   ├── models/            # SQL Alchemy Table Schemas
│       │   │   ├── document.py
│       │   │   └── user.py
│       │   └── vector/            # Qdrant / Pinecone Client wrapper
│       │       └── client.py
│       │
│       └── utils/                 # General Utility helper functions
│           ├── __init__.py
│           ├── excel.py           # Excel exporter (openpyxl wrapper)
│           └── pdf.py             # PDF highlighting coordinates mapper
│
└── tests/                         # Test Suite
    ├── __init__.py
    ├── conftest.py                # Pytest setups (fixtures, mock clients)
    ├── unit/                      # Core algorithms test folder
    │   ├── test_chunker.py
    │   └── test_verification.py
    ├── integration/               # Multi-service flows test folder
    │   ├── test_ingest_pipeline.py
    │   └── test_retrieval.py
    └── performance/               # Latency & throughput test runs
        └── locustfile.py
```

---

## 2. Directory Explanations & Extensibility

### `src/finrag/core/` (Systems Core)
*   **Why it exists:** House the shared configuration schemas, secure utilities, custom exceptions, and structured logger. It is the absolute foundation that all other modules import from.
*   **How future modules integrate:** If a developer adds a new third-party client (e.g., Azure Document Intelligence), its API keys and connection parameters must be defined as fields in `core/config.py` to inherit validation.

### `src/finrag/parser/` (Parsing Layer)
*   **Why it exists:** Encapsulates the logic of converting visual documents to raw structured files.
*   **How future modules integrate:** Every parser must inherit from the abstract class defined in `parser/base.py`. To plug in a new parser (e.g., `surya_parser`), create `surya.py` implementing the `parse()` interface method, then register it in the parser factory.

### `src/finrag/chunker/` (Context Segmenter)
*   **Why it exists:** Handles the logical boundaries of how text and tables are split prior to vector database loading.
*   **How future modules integrate:** A new chunking model (e.g., semantic drift detector) must implement the `chunk_document()` interface in `chunker/base.py`.

### `src/finrag/indexer/` & `src/finrag/retriever/` (Index and Search)
*   **Why it exists:** Decouples embedding uploads (indexing) from run-time search execution (retrieval).
*   **How future modules integrate:** To swap vector database providers (e.g., migrating from Pinecone to Qdrant), write a new driver implementation in `db/vector/` and update the dependency injection configuration in `api/dependencies.py`.

### `src/finrag/agent/` (Cognition & Verification)
*   **Why it exists:** Houses the prompt templates, LLM client connections, and tool definitions. Critically, it maintains the mathematical python verification sandbox.
*   **How future modules integrate:** Adding a new tool (e.g., query external financial APIs) requires creating a tool class in `agent/tools/` and appending it to the reasoning agent's execution inventory.

---

## 3. Configuration & Environment Management

We enforce strict validation of environment configurations using **Pydantic Settings** to ensure that missing keys crash the application immediately during deployment.

### Example Configuration Schema (`src/finrag/core/config.py`):
```python
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    ENV: Literal["development", "staging", "production"] = "development"
    PROJECT_NAME: str = "FinRAG-Platform"
    LOG_LEVEL: str = "INFO"
    
    # DB Connections
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")
    VECTOR_DB_URL: str = Field(..., description="Pinecone/Qdrant connection endpoint")
    VECTOR_DB_API_KEY: SecretStr
    
    # LLM Settings (Strict Zero Data Retention)
    OPENAI_API_KEY: SecretStr
    ANTHROPIC_API_KEY: SecretStr
    
    # Security Secrets
    SECRET_KEY: SecretStr = Field(..., description="Used for cryptographic functions")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

# Instantiate settings singleton
settings = Settings()
```

---

## 4. Logging & Observability Strategy

*   **Format:** All log lines must be output in structured JSON to standard out. This matches specifications of modern log aggregators (e.g., Datadog, ELK, AWS CloudWatch).
*   **Context:** Log records must include transaction IDs (`correlation_id`) linked to HTTP requests to trace errors across the asynchronous pipeline.
*   **Library:** Standard Python `logging` customized with a custom formatter or `structlog`.

### Example Log Output Format:
```json
{
  "timestamp": "2026-06-21T21:40:41Z",
  "level": "ERROR",
  "correlation_id": "req-9c8a-72bf42",
  "module": "finrag.agent.verification",
  "message": "Mathematical verification mismatch for document AAPL-Q3-2026",
  "details": {
    "extracted_value": 0.42,
    "calculated_value": 0.39,
    "mismatch_delta": 0.03
  },
  "exception": "MathVerificationError: Calculation delta exceeds threshold of 0.01"
}
```

---

## 5. Error Handling & Exception Hierarchy

We avoid raw python exceptions. We implement a structured exception hierarchy inheriting from a root model.

```
                  ┌──────────────────────┐
                  │   FinRAGException    │ (Root Exception)
                  └──────────┬───────────┘
            ┌────────────────┴────────────────┐
  ┌─────────▼─────────┐             ┌─────────▼─────────┐
  │ PipelineException │             │   ApiException    │
  └─────────┬─────────┘             └─────────┬─────────┘
      ┌─────┴─────┐                     ┌─────┴─────┐
┌─────▼─────┐┌────▼──────┐        ┌─────▼─────┐┌────▼──────┐
│ParserError││MathErrError│        │ AuthError ││QueryError │
└───────────┘└───────────┘        └───────────┘└───────────┘
```

*   **FastAPI Integration:** Global Exception Middleware catches sub-exceptions of `ApiException` and maps them to HTTP status codes (e.g., `ParserError` translates to HTTP 502 Bad Gateway).

---

## 6. Testing Strategy & Hierarchy

The pipeline enforces three testing layers with target **85%+ code coverage**:

1. **Unit Tests (`tests/unit/`):** Mock out all HTTP and database connections. Test mathematical utilities, parser logic, chunk boundaries, and string serializations.
2. **Integration Tests (`tests/integration/`):** Use Docker Compose resources locally to test end-to-end functionality: document parsing -> indexing -> retrieval -> LLM generation.
3. **Performance Tests (`tests/performance/`):** Simulate multiple users uploading filings and queries concurrently using **Locust** to identify database locks and GPU parsing queue latency bottlenecks.

---

## 7. Coding Standards & Naming Conventions

*   **Style Rules:** Code formatting rules are declared in `ruff.toml` matching Ruff defaults (equivalent to strict Black + Flake8 + isort rules).
*   **Type Hinting:** Mandatory type annotations for all function parameters and return structures. Enforced by `mypy`.
*   **Naming Conventions:**
    *   **Classes:** `CamelCase` (e.g., `FinancialStatementParser`).
    *   **Functions & Methods:** `snake_case` (e.g., `extract_segment_tables`).
    *   **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_TOKEN_LIMIT`).
    *   **Abstract Interfaces:** Prefixed with base or class structure name (e.g., `class BaseEmbedder(ABC)`).
*   **File naming:** Module files named to match contents (e.g., `textract.py`, `layoutlm.py` under `parser/`).
