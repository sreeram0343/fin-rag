# Production-Grade Financial AI Platform: System Architecture & Data Pipeline
## Staff AI Systems Architect Design Specification

---

## 1. Architectural Overview

The core architecture of the FinRAG platform is designed as an **Asynchronous, Event-Driven, Advanced RAG with Multi-Agent Verification**. 

```
[User PDF Upload] ──► [API Ingestion] ──► [Kafka Queue] ──► [Visual OCR Parser]
                                                                  │
[Verified Output] ◄── [Math Verification Agent] ◄── [Rerank] ◄── [Vector / DB Index]
```

### Key Pillars of the Design:
1. **Asynchronous Orchestration:** Document processing is decoupled from the web application using **Apache Kafka** and **Celery** workers. This isolates long-running operations (like PDF parsing and OCR) from user-facing APIs.
2. **Visual & Layout-Aware Parsing:** PDF text extraction is guided by visual layout detection. Tables are extracted as structured objects, preserving row/column relations, rather than flat text.
3. **Hybrid Multi-Vector Retrieval:** We combine dense vector search (semantic retrieval) with sparse token matching (BM25) and relational section filters to achieve high-recall accuracy.
4. **Agentic Verification Loop:** Instead of returning raw LLM outputs, the generation phase employs a **ReAct Agent** that generates and runs python code locally to verify mathematical claims, comparing calculated ratios against source metrics.
5. **Zero-Data-Retention (ZDR) & VPC Guardrails:** To satisfy institutional compliance, all models are either deployed inside a private VPC using open-source foundations (e.g., Llama-3, vLLM) or connected via enterprise API endpoints governed by strict zero-data-retention (ZDR) agreements.

---

## 2. Pipeline Stages

### Stage 1: Ingestion & Event-Driven Orchestration

| Dimension | Description |
| :--- | :--- |
| **Input** | Raw PDF document uploaded via the Web UI or Client API (e.g., 150MB 10-K filing) + Metadata (Ticker, Period, User ID). |
| **Output** | Document saved to WORM (Write-Once-Read-Many) storage. Event payload published to Apache Kafka topic `document-ingestion-jobs`. |
| **Purpose** | To securely receive, validate, sanitize, and persist raw documents while initiating the downstream processing pipeline asynchronously. |
| **Algorithms/Techniques involved** | SHA-256 deduplication hashing, ClamAV antivirus scanning, PDF format sanitation, Event-driven publish-subscribe pattern. |
| **Recommended AI/ML Models** | ClamAV (Security); no ML models in this structural layer. |
| **Technical Challenges** | Handling large payloads during peak earnings season, preventing denial-of-service (DoS) via malicious PDFs, ensuring deduplication to save storage and compute resources. |
| **Expected Latency** | **< 300ms** (Instant API response returning a unique `Job ID` for client polling). |
| **Engineering Trade-offs** | **Asynchronous processing vs. Synchronous feedback:** Users must poll or listen on WebSockets for completion rather than getting an immediate response, but this guarantees API gateway stability. |
| **Failure Cases & Fallback Strategies** | **Storage write failure:** Retry with exponential backoff. **Kafka partition failure:** Fallback to writing task directly to Redis Celery queue to bypass the broker temporarily. |

---

### Stage 2: Layout-Aware OCR & Structural Parsing

| Dimension | Description |
| :--- | :--- |
| **Input** | Raw PDF URI retrieved from secure cloud storage. |
| **Output** | Hierarchical structured JSON payload detailing text paragraphs, tables (with row/column coordinate cells), footnotes, headers, and visual bounding-box coordinates (`x_min, y_min, x_max, y_max`). |
| **Purpose** | To convert visual PDF pages into machine-readable structure, preserving the exact layout schema of financial statements and footnotes. |
| **Algorithms/Techniques involved** | Visual object detection (for layout analysis), Grid-based table structural reconstruction, OCR (for non-digitized text). |
| **Recommended AI/ML Models** | **Open Source:** LayoutLMv3, Table-Transformer, Surya. <br>**Enterprise:** Azure Document Intelligence (Layout API with ZDR agreement). |
| **Technical Challenges** | Parsing tables that span multiple page boundaries, linking superscript footnote symbols to text at page bottom, and maintaining correct column boundaries in non-ruled ledger sheets. |
| **Expected Latency** | **15s – 45s** for a 100-page document (GPU-accelerated parsing). |
| **Engineering Trade-offs** | **Visual Layout Models vs. PDF text extraction:** Visual Layout models (LayoutLMv3) require high-cost GPU workers but maintain 99%+ table structure, whereas pure text extractors (PyPDF) are fast/cheap but completely scramble tabular columns. |
| **Failure Cases & Fallback Strategies** | **OCR layout crash:** Segment PDF into 5-page batches and parse in parallel. **Stitching failure of split tables:** Fallback to table reconstruct heuristics based on column schema matching. |

---

### Stage 3: Financial-Specific Chunking & Semantic Embedding

| Dimension | Description |
| :--- | :--- |
| **Input** | Hierarchical structured JSON payload from Stage 2. |
| **Output** | Dense vector embeddings indexed in a Vector DB, and sparse indexes (BM25) saved in the Metadata Store. |
| **Purpose** | Segment the document into semantic nodes while maintaining financial context (e.g., matching table cells with headers) and convert them to numerical vectors. |
| **Algorithms/Techniques involved** | Header-aware recursive text splitting, Table serialization (Markdown or JSON-L conversion), Dense-Sparse hybrid index mapping. |
| **Recommended AI/ML Models** | **Open Source:** BAAI/bge-large-en-v1.5, Snowflake/snowflake-arctic-embed-l. <br>**Enterprise:** Cohere Embed v3 (Finance-tuned). |
| **Technical Challenges** | Representing multi-column tables in vector space without losing parent context (e.g., knowing a cell value `120` means "Gross Margin in millions for Q2 2026"). |
| **Expected Latency** | **2s – 8s** for a 100-page document. |
| **Engineering Trade-offs** | **Chunk size size:** Small chunks (e.g., 256 tokens) return highly specific matches but lose context, while large chunks (e.g., 1024 tokens) preserve context but dilute similarity search scores and waste LLM tokens. We choose hierarchy chunking with parent-child links. |
| **Failure Cases & Fallback Strategies** | **Embedding service rate-limiting:** Local failover to light container running `sentence-transformers` (e.g., `all-MiniLM-L6-v2`) to prevent data pipeline blocks. |

---

### Stage 4: Hybrid Multi-Vector Retrieval

| Dimension | Description |
| :--- | :--- |
| **Input** | Natural language user query (e.g., *"What was the YoY change in segment revenues?"*) + Metadata filters. |
| **Output** | Top-K highly relevant document nodes containing text chunks, serialized tables, coordinate bounding boxes, and parent header/footnote contexts. |
| **Purpose** | Select and rank the most factually relevant source data to answer the analyst's specific question. |
| **Algorithms/Techniques involved** | Cosine similarity vector search, Sparse BM25 keyword matching, Reciprocal Rank Fusion (RRF), Cross-Encoder Reranking. |
| **Recommended AI/ML Models** | **Open Source Reranker:** BAAI/bge-reranker-large. <br>**Enterprise Reranker:** Cohere Rerank v3. |
| **Technical Challenges** | Balancing vector scores against exact keyword matches (e.g., ensuring a query searching for section "ASC 606" strictly retrieves documents referencing that standard). |
| **Expected Latency** | **200ms – 600ms**. |
| **Engineering Trade-offs** | **Reranking latency overhead:** Reranking adds ~200-300ms of latency to the retrieval loop but raises Retrieval Mean Reciprocal Rank (MRR) by up to 25%, which directly reduces hallucination rates. |
| **Failure Cases & Fallback Strategies** | **Vector DB partition offline:** Fallback to database full-text search (BM25) over SQL database metadata tables. **Reranker service timeout:** Skip reranking and return raw top-K RRF results directly. |

---

### Stage 5: AI-Agentic Synthesis & Numerical Math Verification

| Dimension | Description |
| :--- | :--- |
| **Input** | Query + Context (top-K chunks, tables, coordinates, footnotes). |
| **Output** | Mathematically verified text answer containing markdown structures and bounding-box coordinates for citations. |
| **Purpose** | Reason over the retrieved inputs, synthesize the final textual answers, calculate any ratios, and mathematically check the results against source values. |
| **Algorithms/Techniques involved** | Chain-of-Thought (CoT), Program-Aided Language models (PAL - writing python script to compute math), Dual-pass Verification Agent loop. |
| **Recommended AI/ML Models** | **Open Source:** Llama-3-70B-Instruct (hosted on vLLM/TGI). <br>**Enterprise:** Anthropic Claude 3.5 Sonnet (preferred for complex logic/math), OpenAI GPT-4o. |
| **Technical Challenges** | Eliminating LLM arithmetic errors, handling conflicting disclosures across different documents, and generating strict JSON outputs with bounding-box citations. |
| **Expected Latency** | **3s – 8s** (Depending on multi-turn self-correction loops). |
| **Engineering Trade-offs** | **Single-pass generation vs. Agentic verification loop:** Single-pass is fast and inexpensive, but prone to math hallucinations. The multi-agent verification loop guarantees mathematical consistency at the expense of latency and API costs. |
| **Failure Cases & Fallback Strategies** | **Verification agent math mismatch:** If recalculated values mismatch LLM text assertions, trigger a self-correction prompt. If the second attempt fails, surface the raw source numbers with a warning badge instead of the computed value. |

---

### Stage 6: Report Generation & Output Compilation

| Dimension | Description |
| :--- | :--- |
| **Input** | Verified text output + Structured coordinates + Original PDF. |
| **Output** | Generated PDF report, Excel model sheet, and interactive Web UI view with side-by-side highlighted PDF canvas. |
| **Purpose** | Compile the finalized verified results into professional formats ready for downstream analyst review or export to Research Management Systems. |
| **Algorithms/Techniques involved** | HTML-to-PDF compilation, dynamic Excel generation (openpyxl), coordinate mapping onto canvas layers. |
| **Recommended AI/ML Models** | None (purely deterministic rendering layer). |
| **Technical Challenges** | Rendering visually aligned tables in exported PDF layouts, inserting Excel formulas rather than hardcoded numbers, and tracking precise pixel coordinates across multiple zoom levels in the UI. |
| **Expected Latency** | **< 400ms**. |
| **Engineering Trade-offs** | **Client-side vs. Server-side rendering:** Client-side rendering (using React/Canvas) minimizes server overhead but relies on browser performance; server-side compilation is slower but ensures consistent output formatting. We choose client-side canvas highlighting. |
| **Failure Cases & Fallback Strategies** | **PDF compiler crash:** Expose raw HTML/Markdown download download option directly to the user. **Excel export error:** Generate standard CSV output files as a fail-safe. |

---

## 3. Data Flow & Security Framework

### Data Isolation & Vaulting
1. **Multi-Tenant Partitioning:** Document assets are locked in encrypted storage buckets under user-group specific keys.
2. **KMS Key Rotation:** Customer data is encrypted in transit using TLS 1.3 and at rest with AES-256 keys managed in a key management service (KMS) with monthly rotation.
3. **Data Lifecycle Policies:** Filings and parsed tables are automatically archived or purged based on customer-defined retention schedules (e.g., 90-day automatic deletion).
