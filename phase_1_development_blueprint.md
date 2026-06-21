# FinRAG: Phase 1 Initial Development Blueprint
## Master Engineering Blueprint & Software Architecture Specification

---

## 1. Overall Engineering Blueprint

FinRAG implements **Clean Architecture** and **Domain-Driven Design (DDD)** principles to separate technical capabilities (such as PDF OCR parsing or vector similarity searches) from core financial analytical domains.

### 1.1 Layered Architecture Overview
The system is divided into four distinct concentric rings, ensuring code dependency flows strictly from outer implementation layers to the inner core logic domain:

```
┌─────────────────────────────────────────────────────────┐
│              1. Infrastructure Layer                    │
│   (PostgreSQL, Qdrant, MinIO, FastAPI Host, Docker)      │
│  ┌───────────────────────────────────────────────────┐  │
│  │               2. Adapter Layer                    │  │
│  │ (Repositories, Controllers, Clients for LLMs/OCR)  │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │             3. Application Layer            │  │  │
│  │  │   (Verification Services, Query Orchestrators) │  │  │
│  │  │  ┌───────────────────────────────────────┐  │  │  │
│  │  │  │          4. Domain Layer              │  │  │  │
│  │  │  │     (Document & Metrics Entities)     │  │  │  │
│  │  │  └───────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

1.  **Domain Layer (Core):** Houses core entity models (e.g., `Document`, `Table`, `FinancialMetric`) and domain rule calculations. It contains zero references to external packages or frameworks.
2.  **Application Layer:** Contains application-specific use cases, orchestrating domain logic flows (e.g., retrieval logic execution, report generation routing, math verification tasks).
3.  **Adapter Layer:** Ports implementation abstractions. Resolves interface routes (FastAPI HTTP endpoints), database repository drivers, and external API connectors (Anthropic API client, Docling PDF client).
4.  **Infrastructure Layer:** Comprises physical databases (PostgreSQL, Redis, Qdrant), message brokers (Celery workers), security mechanisms, and environment configurations.

### 1.2 Module Interactions & Component Responsibilities
*   **Ingest Subsystem:** Listens on HTTP upload endpoint, calculates hash for deduplication, writes PDF bytes to MinIO object storage, and emits task payloads to Redis message brokers.
*   **Structure-Aware Parsing Worker (Asynchronous):** Reads raw documents from MinIO, executes layout analysis to separate tables and footnotes, formats structures into segment JSON schemas, and stores metadata in PostgreSQL.
*   **Vector Database Indexer:** Transforms text chunks and tables into vector representations using Sentence Transformers, indexing payloads in Qdrant collections mapped by tenant scopes.
*   **Hybrid Query Controller:** Parses user searches, conducts dual-vector retrievals (dense semantic cosine checks paired with BM25 term scores), filters candidates by metadata, and refines top results via Cross-Encoder Rerankers.
*   **Verification Agent System:** Coordinates ReAct reasoning cycles, executes sandboxed Python code to audit mathematical formulas, and renders completed Markdown reports with visual coordinate citations.

---

## 2. Project Folder Structure

A standardized repository configuration separating the React frontend and FastAPI backend into clean, decoupled workspaces.

```text
fin-rag/
├── .github/workflows/             # GitHub Actions CI/CD workflows
├── backend/                       # Backend FastAPI Modular Monolith
│   ├── config/                    # Static configuration files
│   ├── migrations/                # Database migrations (Alembic)
│   ├── src/
│   │   └── finrag/                # Core Python package namespace
│   │       ├── api/               # API Controllers and middleware
│   │       ├── core/              # Settings, logs, exception frameworks
│   │       ├── db/                # PostgreSQL models and repository engines
│   │       ├── parser/            # Docling, PyMuPDF, OCR wrappers
│   │       ├── chunker/           # Table & header-aware chunkers
│   │       ├── indexer/           # Vector embeddings loaders
│   │       ├── retriever/         # Hybrid BM25 & Dense retrieval routers
│   │       ├── agent/             # LLM ReAct loop & Python sandbox
│   │       └── utils/             # PDF coordinates & Excel generators
│   ├── tests/                     # Pytest suite (Unit, Integration)
│   ├── pyproject.toml             # Python dependencies (Poetry)
│   └── Dockerfile                 # Multi-stage production build configuration
│
└── frontend/                      # React Frontend Package Workspace
    ├── public/                    # Static assets (favicons, logos)
    ├── src/
    │   ├── api/                   # Axios / TanStack Query client services
    │   ├── components/            # Shared UI components (Button, Modal, Input)
    │   ├── features/              # Feature-scoped views and dashboards
    │   │   ├── auth/              # JWT login logic
    │   │   ├── documents/         # Document uploads and list views
    │   │   └── queries/           # Search input and side-by-side viewer
    │   ├── hooks/                 # Reusable React hooks
    │   ├── pages/                 # Route page components
    │   ├── router/                # React Router configs
    │   ├── styles/                # Tailwind CSS configs
    │   └── utils/                 # Coordinate canvas highlights mapping
    ├── package.json               # Frontend dependencies (npm)
    └── tailwind.config.js         # Tailwind styling configs
```

### Explanations of Directories:
*   **`backend/src/finrag/parser/`**: Completely isolates visual parsing code. Adding new engines (e.g., Docling to replace PyMuPDF) requires zero edits to the API layer, only updating this folder.
*   **`backend/src/finrag/agent/`**: Keeps prompt configurations, LLM connectors, and mathematical execution runtimes grouped together.
*   **`frontend/src/features/`**: Grouping components, state management, and api hooks by features prevents cognitive clutter, making it easy to refactor the workspace later.

---

## 3. Detailed Architectural Specifications

### 3.1 Backend Service Layer & Repository Boundaries
We enforce the **Repository Pattern** to abstract database access. Controllers never issue database queries directly. Instead, they interact with Services, which retrieve data via Repositories.

#### Base Abstract Repository (`backend/src/finrag/db/base.py`):
```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    @abstractmethod
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """Fetch entity by primary key identifier."""
        pass

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Persist or update entity state."""
        pass
```

### 3.2 Dynamic Configuration Layer
Dynamic configurations are handled by **Pydantic Settings**, which enforces strict typing and fails fast if required configurations are missing.

### 3.3 Core Shared Utilities & Middleware
*   **Correlation ID Middleware:** Injects a unique `X-Correlation-ID` header into every request. This ID is appended to all structured JSON logs, tracing operations across FastAPI and asynchronous Celery workers.
*   **Global Exception Handler:** Catches custom system exceptions (e.g., `ParserException`, `VerificationException`) and translates them into uniform JSON responses.

---

## 4. Frontend Architecture & Design System

The frontend is built on **React** and **TypeScript**, using **Tailwind CSS** for layout styling and **shadcn/ui** for core UI primitives.

### 4.1 Component Layering
*   **Pages (`frontend/src/pages/`):** Represent top-level route views (e.g., Dashboard page, PDF viewer page).
*   **Feature Modules (`frontend/src/features/`):** Self-contained capabilities (e.g., `features/queries` contains `SearchInput.tsx` and `CitationCanvas.tsx`).
*   **Shared UI Elements (`frontend/src/components/`):** Stateless atomic elements (e.g. customized shadcn wrappers for buttons and tables).

### 4.2 Data Fetching & State Management
*   **Server State (TanStack Query):** Manages all external API cache states, retries, and background updates.
*   **Client State (React Context):** Tracks active document selections, query filters, and UI canvas zoom settings.

---

## 5. Database Blueprint

PostgreSQL is our primary system of record. We model document ingestion, text chunks, and audit metrics.

```
  ┌───────────────┐          1 : N          ┌─────────────────────┐
  │   documents   ├────────────────────────►│   document_chunks   │
  └───────┬───────┘                         └─────────────────────┘
          │ 1 : N
          ▼
  ┌───────────────┐
  │  audit_logs   │
  └───────────────┘
```

### 5.1 Core Database Schemas (SQL DDL)

```sql
-- Track core filing document records
CREATE TABLE documents (
    id VARCHAR(36) PRIMARY KEY,
    ticker VARCHAR(5) NOT NULL,
    period VARCHAR(5) NOT NULL,
    year INT NOT NULL,
    storage_uri VARCHAR(512) NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Track chunk segmentation & coordinates
CREATE TABLE document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) REFERENCES documents(id) ON DELETE CASCADE,
    page_number INT NOT NULL,
    bounding_box INT[] NOT NULL, -- Array size 4 [x0, y0, x1, y1]
    chunk_text TEXT NOT NULL,
    chunk_type VARCHAR(16) NOT NULL, -- 'TEXT' or 'TABLE'
    parent_header VARCHAR(256),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index metadata to accelerate searches
CREATE INDEX idx_docs_ticker_year ON documents(ticker, year);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
```

### 5.2 Vector Database Schema (Qdrant)
We utilize **Qdrant** for semantic lookup partitions:
*   **Collection Name:** `finrag_chunks`
*   **Vector Dimension:** `1024` (matches Cohere Embed / BGE-large dimensionality).
*   **Distance Metric:** Cosine similarity.
*   **Payload Schema:** Stores `document_id` (UUID), `chunk_id` (UUID), `ticker` (string), and `year` (integer) to support metadata filtering.

---

## 6. Document Ingestion & AI RAG Pipeline

```
  [Ingest API]
       │
       ▼
 [MinIO Storage]
       │
       ▼ (Emit Job)
   [Celery] ──► [Layout Parser (Docling)] ──► [Chunker & Footnote Connector]
                                                           │
                                                           ▼ (Embed & Load)
  [PostgreSQL] ◄── [Qdrant Vector DB] ◄── [Sentence Transformer Embeddings]
```

### Stage-by-Stage Processing Steps:
1.  **Document Upload:** Client uploads report PDF. API validates file type and payload headers, saving the file to MinIO.
2.  **Visual Layout Parser:** Docling parses the PDF, separating text blocks from visual tables.
3.  **Semantic Chunker:** Splits sections into cohesive text nodes, linking footnotes directly to table cell blocks.
4.  **Embedding Generation:** Generates 1024-dimensional embeddings using Sentence Transformers.
5.  **Vector Loading:** Writes vector records to Qdrant, referencing corresponding PostgreSQL rows.
6.  **Hybrid Retrieval:** Executes dense semantic searches paired with sparse BM25 token matches over target filings.
7.  **Reranking:** Cross-encoder models evaluate and re-sort retrieved context chunks.
8.  **Verification Loop:** The ReAct Agent executes Python code to recalculate and verify numbers before output compilation.
9.  **Report Generation:** Compiles output Markdown reports mapping visual bounding-box coordinates to source citations.

---

## 7. Data Flow Trace

Tracing a query: *"What was the YoY increase in Cloud revenue for 2026?"*

```
User Query ──► [FastAPI Router] ──► [Hybrid Retriever]
                                           ├─► Dense Vector Search (Qdrant)
                                           └─► Sparse Text Match (BM25)
                                                    │
[Agent Verified JSON] ◄── [LLM ReAct Loop] ◄── [Cross-Reranker]
```

---

## 8. Planned REST Endpoints (Phase 1)

| Endpoint | Method | Required Scope | Purpose |
| :--- | :--- | :--- | :--- |
| `/api/v1/auth/token` | `POST` | None (Public) | Issue JWT access tokens. |
| `/api/v1/documents` | `POST` | `write:documents` | Ingest new PDF statements. |
| `/api/v1/documents` | `GET` | `read:documents` | List uploaded documents. |
| `/api/v1/documents/{id}` | `GET` | `read:documents` | Retrieve specific document metadata. |
| `/api/v1/documents/jobs/{id}` | `GET` | `read:documents` | Check parser pipeline status. |
| `/api/v1/queries/ask` | `POST` | `read:queries` | Run verified QA searches. |
| `/api/v1/queries/compare` | `POST` | `read:queries` | Compare sections across periods. |

---

## 9. Development Milestones

### Milestone 1: Core Scaffolding & API Gateway
*   **Task 1.1:** Initialize FastAPI and Poetry. Establish database sessions.
*   **Task 1.2:** Configure Pydantic validation singleton classes.
*   **Task 1.3:** Build API upload endpoints. Verify file saving to MinIO.

### Milestone 2: Structure-Aware Visual OCR Parser
*   **Task 2.1:** Implement Docling visual parser driver.
*   **Task 2.2:** Build table cell coordinate extractors.
*   **Task 2.3:** Map footnote linking logic to target statements.

### Milestone 3: Chunker & Vector DB Pipeline
*   **Task 3.1:** Implement header-aware text splitters.
*   **Task 3.2:** Configure local Sentence Transformers.
*   **Task 3.3:** Integrate Qdrant vector database load drivers.

### Milestone 4: Hybrid Search & Math Verification Agent
*   **Task 4.1:** Build dual-vector retrieval controllers (Qdrant + BM25).
*   **Task 4.2:** Integrate Cross-Encoder reranker layers.
*   **Task 4.3:** Build python-sandboxed execution utilities for the verification agent.

---

## 10. Engineering & Coding Standards

*   **Language Standards:** TypeScript strictly enforced on frontend; Python with typing on backend (`mypy --strict`).
*   **Style Formatting:** Black + Flake8 rules executed via Ruff. Pre-commit hooks run automated linting.
*   **Error Logging:** Structured JSON format containing transaction `correlation_id` values.
*   **Test Suite Requirements:** Pytest unit tests for parsers, agents, and calculators. React Testing Library for frontend component checks.

---

## 11. Future Scalability Blueprint

*   **Multi-Agent Workflows:** Migrating to LangGraph or CrewAI to partition reasoning loads (e.g. specialized extraction, math auditing, and report writing agents).
*   **Financial Knowledge Graphs:** Storing entities (companies, divisions, products) and relations (acquisitions, liabilities) in Neo4j, enabling queries like *"What are the indirect supply chain exposures of AAPL's key partners?"*
*   **Fine-Tuned Domain SLMs:** Transitioning from generic LLM calls to local, fine-tuned 14B models (e.g. Llama-3-Finance) running on private vLLM server clusters, reducing API fees.
*   **Real-time Streaming Ingestion:** Using Apache Kafka to feed live earnings calls and news feeds, transcribing audio streams on-the-fly and generating semantic alerts.
