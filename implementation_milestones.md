# FinRAG: Engineering Milestones & Implementation Roadmap
## Technical Program Manager (TPM) Specification

---

## Milestone Dependency Order

```
[Milestone 1: Foundations] ──► [Milestone 2: Parse Engine] ──► [Milestone 3: Chunker & Index]
                                                                        │
[Milestone 6: API & Export] ◄── [Milestone 5: Verification Agent] ◄── [Milestone 4: Retriever]
```

---

## Milestone 1: Repository Foundations, Configuration, & Ingestion Pipeline

*   **Objective:** Establish the development environment, package manager configs, directory trees, structured logging, global exception frameworks, and asynchronous file uploading endpoints.
*   **Features:**
    *   Poetry package setup with standard configurations (Ruff, pytest, mypy).
    *   Config validation singleton module using Pydantic Settings.
    *   Asynchronous file uploads mapped to Cloud Object Store buckets (Local MinIO in development).
    *   Basic event publishing architecture using a message queue (Celery task setup with Redis backend).
*   **Dependencies:** None (initial step).
*   **Deliverables:**
    *   Repository scaffolding config files (`pyproject.toml`, `ruff.toml`, `.env.example`).
    *   Core systems modules (`src/finrag/core/config.py`, `core/logging.py`, `core/exceptions.py`).
    *   Ingestion API controller (`src/finrag/api/v1/ingest.py`) with unit test suite.
*   **Testing Strategy:**
    *   Unit tests checking environment variable validations with mock inputs.
    *   API tests verifying raw upload limits (e.g., throwing error on payloads > 150MB).
    *   Linting and type-checking validation scripts (Ruff, mypy verification).
*   **Completion Criteria:**
    *   `poetry run pytest tests/unit/` completes with 100% pass rates.
    *   Ruff format and mypy check complete with zero violations.
    *   A document uploaded to `/api/v1/ingest` successfully saves to object storage and schedules an indexing task in Redis.
*   **Risks:** Network delays or authentication failures to cloud buckets. (Mitigation: use local file system storage in development environment governed by env flags).
*   **Future Integration Points:** Ingestion triggers downstream Document OCR and parsing worker nodes.

---

## Milestone 2: Layout-Aware OCR & Parsing Engine

*   **Objective:** Implement visual layout analysis, OCR engine fallback layers, and table cell coordinate mapping.
*   **Features:**
    *   Layout-aware visual segmenter mapping paragraphs, headers, and footers.
    *   Table extraction engine converting visual grids into structured column/row data blocks.
    *   Coordinate mapping logic assigning pixel regions (`x_min, y_min, x_max, y_max`) to every parsed node.
*   **Dependencies:** Milestone 1 (requires configuration and file ingestion API).
*   **Deliverables:**
    *   Abstract parser interfaces (`src/finrag/parser/base.py`).
    *   Visual Layout parser drivers (`src/finrag/parser/layoutlm.py`, `parser/textract.py`).
    *   Coordinates formatting helpers (`src/finrag/parser/utils.py`).
*   **Testing Strategy:**
    *   Regression tests comparing extracted visual coordinate arrays against reference ground-truth coordinate maps.
    *   Unit tests verifying multi-page table concatenation.
*   **Completion Criteria:**
    *   The parsing engine extracts a 100-page complex PDF statement, returning a structured JSON document maintaining table cells and coordinate boundaries.
    *   OCR layers accurately read scanned pages below a target character error rate (CER) limit of 2%.
*   **Risks:** High GPU costs and parsing timeouts on extremely long scanned documents. (Mitigation: Implement PDF page splitting to parse document subsets in parallel).
*   **Future Integration Points:** Output JSON serves as raw text input for the Semantic Chunker.

---

## Milestone 3: Semantic Chunking & Vector Database Indexing

*   **Objective:** Convert parsed document structures into embeddings and index them with metadata.
*   **Features:**
    *   Header-aware chunk splitters that maintain table block coherence.
    *   Footnote linking algorithms attaching parenthesized references directly to table cell blocks.
    *   Dense vector database loading wrappers (Qdrant/Pinecone).
*   **Dependencies:** Milestone 2 (requires parsed JSON schemas).
*   **Deliverables:**
    *   Chunker implementations (`src/finrag/chunker/financial.py`).
    *   Indexer and loader modules (`src/finrag/indexer/loader.py`).
    *   Vector database wrapper drivers (`src/finrag/db/vector/client.py`).
*   **Testing Strategy:**
    *   Assert that tabular blocks are not split across chunk partitions.
    *   Mock out embedding API endpoints during test runs to verify vector database insert requests.
*   **Completion Criteria:**
    *   Uploading parsed documents converts sections to embeddings and inserts them into vector namespaces with tags.
    *   Unit tests verify correct footnote mapping logic.
*   **Risks:** Embedding rate-limits causing pipeline backlogs during high concurrent loads. (Mitigation: Implement task queues with exponential retry intervals).
*   **Future Integration Points:** Stored database indexes are queried by the Retriever Engine.

---

## Milestone 4: Hybrid Multi-Vector Retrieval Engine

*   **Objective:** Implement hybrid dense-sparse search logic, metadata filtering, and post-retrieval reranking.
*   **Features:**
    *   Dual-channel query router executing sparse (BM25) and dense (vector similarity) search queries.
    *   Reciprocal Rank Fusion (RRF) algorithm to combine dense and sparse rankings.
    *   Cross-Encoder reranking model mapping top candidate subsets.
*   **Dependencies:** Milestone 3 (requires database indexes).
*   **Deliverables:**
    *   Hybrid retrieval controllers (`src/finrag/retriever/hybrid.py`).
    *   Reranking integrations (`src/finrag/retriever/reranker.py`).
*   **Testing Strategy:**
    *   Evaluation metrics tracking: Retrieval Recall@K (target >96%) and Mean Reciprocal Rank (MRR).
    *   Integration tests verifying metadata scoping rules (e.g. searching strictly inside "Risk Factors" of target filings).
*   **Completion Criteria:**
    *   Retrieval request returns correct chunks, sorted by relevance, with zero formatting loss on serialized tables.
    *   Search operations complete within latency limits (<600ms).
*   **Risks:** Vector dimension mismatches between dense and sparse spaces. (Mitigation: Strict schema enforcement inside vector database definitions).
*   **Future Integration Points:** Retrieved relevant contexts populate the LLM agent window prompt.

---

## Milestone 5: AI-Agentic Synthesis & Mathematical Verification

*   **Objective:** Build reasoning agent loops, Chain-of-Thought prompting, and a python mathematical validation sandbox.
*   **Features:**
    *   Reasoning orchestrator implementing ReAct loops.
    *   Python execution sandbox isolating arithmetic execution runs.
    *   Self-correction logic mapping validation discrepancies.
*   **Dependencies:** Milestone 4 (requires retrieval outputs).
*   **Deliverables:**
    *   Agent orchestrator (`src/finrag/agent/orchestrator.py`).
    *   Math validation sandbox utilities (`src/finrag/agent/verification.py`).
*   **Testing Strategy:**
    *   Unit tests checking sandbox execution capabilities (ensuring system calls are blocked).
    *   Mock LLM queries returning wrong math to verify self-correction prompts trigger.
*   **Completion Criteria:**
    *   Queries requesting calculations (e.g., margins, ratios) output verified values matching local python computations.
    *   Answers output citation metadata mapped to source bounding-box coordinates.
*   **Risks:** Infinite loops inside self-correction agent paths. (Mitigation: Enforce max step parameters, capping self-corrections at 2 attempts).
*   **Future Integration Points:** Output payloads compile into UI templates and file formats.

---

## Milestone 6: API Layer, Worker Integration & Final Report Compiler

*   **Objective:** Implement report export formatting, Celery task queue integration, user authorization, and the web interface.
*   **Features:**
    *   FastAPI Router mappings for querying and reporting.
    *   Export tools compiling output Markdown to PDF, and tables to Excel with formulas.
    *   Local Web UI panel built with Streamlit/Gradio.
*   **Dependencies:** Milestone 5 (requires verified output generation).
*   **Deliverables:**
    *   API routes (`src/finrag/api/v1/query.py`).
    *   Export compilers (`src/finrag/utils/excel.py`, `utils/pdf.py`).
    *   Web application app (`src/finrag/ui/app.py`).
*   **Testing Strategy:**
    *   End-to-end integration flows simulating document upload -> query execution -> Excel model export.
    *   Load testing using Locust to verify concurrent throughput thresholds.
*   **Completion Criteria:**
    *   User uploads document, schedules task, polls execution, and queries data.
    *   System exports tables to functional Excel formats and reports to PDF formats.
*   **Risks:** Client browser crashes when rendering highlighted PDF canvases with hundreds of coordinates. (Mitigation: Paginate rendering layers, loading bounding boxes dynamically).
*   **Future Integration Points:** System ready for staging/production deployment and downstream institutional client systems integrations.
