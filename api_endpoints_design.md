# FinRAG: REST API Specification
## Senior API Architect Design Document

---

## 1. Global API Standards

*   **API Versioning:** All endpoints are versioned and prefixed with `/api/v1`.
*   **Base URL Structure:** `https://api.finrag.institutional.internal`
*   **Request & Response Formats:** JSON (UTF-8 encoding). Document uploads use standard `multipart/form-data`.
*   **Correlation ID Header:** Every request must either include or will be assigned a `X-Correlation-ID` UUID header to propagate transaction tracing across asynchronous background operations.

---

## 2. Global Rate Limiting & Authentication

### Rate Limiting Policy:
*   **Standard Tier:** 60 requests/minute per client IP (excluding file uploads).
*   **Premium Tier:** 300 requests/minute.
*   **Institutional Tier:** 1000 requests/minute.
*   *Rate limit metadata is returned in headers:*
    *   `X-RateLimit-Limit`: Maximum requests allowed in cycle.
    *   `X-RateLimit-Remaining`: Requests remaining in current minute cycle.
    *   `X-RateLimit-Reset`: Epoch timestamp when limits reset.

### Global Error Payload Layout:
If an API error occurs, the server returns a structured body matching this JSON format:
```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "The request body failed to validate against the schema.",
    "correlation_id": "req-9c8a-72bf42",
    "details": [
      {
        "field": "ticker",
        "issue": "Ticker must contain 1-5 capital alphanumeric characters (e.g. AAPL)."
      }
    ]
  }
}
```

---

## 3. Detailed Endpoint Designs

### 3.1 `POST /api/v1/auth/token`
*   **Purpose:** Authenticate institutional user credentials and issue a JSON Web Token (JWT) containing access scopes.
*   **Request:**
    *   **Method:** `POST`
    *   **Content-Type:** `application/x-www-form-urlencoded`
    *   **Body Schema:**
        *   `grant_type` (str): Must be `"password"` or `"client_credentials"`.
        *   `client_id` (str): Institutional client ID.
        *   `client_secret` (str): Confidential client password.
*   **Response (200 OK):**
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 3600,
      "scope": "read:documents write:documents read:queries"
    }
    ```
*   **Validation:**
    *   `client_id` and `client_secret` must be non-empty strings.
*   **Authentication:** Public endpoint (no token required). Secure HTTPS transport required.
*   **Error Handling & Status Codes:**
    *   `401 Unauthorized` for invalid credentials (`INVALID_CREDENTIALS`).
    *   `400 Bad Request` for unsupported grant types (`INVALID_GRANT_TYPE`).
*   **Rate Limiting:** Capped at 5 requests/minute per IP to prevent brute-force attacks.
*   **Future Extensions:** Support OAuth 2.1 authorization code flow with PKCE for client browser sessions.

---

### 3.2 `POST /api/v1/documents`
*   **Purpose:** Upload a new financial PDF or text report and schedule the asynchronous parsing and indexing pipeline.
*   **Request:**
    *   **Method:** `POST`
    *   **Content-Type:** `multipart/form-data`
    *   **Body Parameters:**
        *   `file` (binary): PDF, HTML, or raw TXT file (Max 150MB).
        *   `ticker` (str): Capitalized ticker symbol (e.g. `"AAPL"`).
        *   `period` (str): Filing period context (e.g. `"Q3"`, `"FY"`).
        *   `year` (int): Fiscal year associated with report (e.g. `2026`).
*   **Response (202 Accepted):**
    ```json
    {
      "job_id": "job_01h2a8cd90f77ab1...",
      "document_id": "doc_01h2a8ce22ef88ca...",
      "status": "QUEUED",
      "ticker": "AAPL",
      "period": "Q3",
      "year": 2026,
      "created_at": "2026-06-21T21:43:18Z"
    }
    ```
*   **Validation:**
    *   `file` extension must be `.pdf`, `.html`, or `.txt`.
    *   `ticker` must match regex pattern: `^[A-Z0-9]{1,5}$`.
    *   `year` must fall in range `[1990, 2100]`.
    *   `period` must match: `^(Q[1-4]|FY|H[1-2])$`.
*   **Authentication:** Bearer token required. Required Scope: `write:documents`.
*   **Error Handling & Status Codes:**
    *   `400 Bad Request` if file type is invalid or fields fail regex parameters (`VALIDATION_FAILED`).
    *   `413 Payload Too Large` if file exceeds 150MB (`PAYLOAD_TOO_LARGE`).
*   **Rate Limiting:** Capped at 10 file uploads/minute per client tenant.
*   **Future Extensions:** Support Batch ingestion API mappings (`POST /api/v1/documents/batch`) processing lists of URIs.

---

### 3.3 `GET /api/v1/documents/jobs/{job_id}`
*   **Purpose:** Query the current state and progress status of an active document ingestion task.
*   **Request:**
    *   **Method:** `GET`
    *   **Path Parameters:**
        *   `job_id` (str): UUID of the background task returned during upload.
*   **Response (200 OK):**
    ```json
    {
      "job_id": "job_01h2a8cd90f77ab1...",
      "status": "PROCESSING",
      "current_step": "TABLE_STRUCTURE_PARSING",
      "progress_percentage": 65,
      "error": null
    }
    ```
*   **Validation:**
    *   `job_id` must be a valid 36-character UUID pattern.
*   **Authentication:** Bearer token required. Required Scope: `read:documents`.
*   **Error Handling & Status Codes:**
    *   `404 Not Found` if job identifier does not exist (`JOB_NOT_FOUND`).
*   **Rate Limiting:** Capped at 120 polling requests/minute.
*   **Future Extensions:** Support WebSockets streams for real-time task progress notifications.

---

### 3.4 `POST /api/v1/queries/ask`
*   **Purpose:** Query the RAG engine to retrieve verified quantitative facts or qualitative statements from indexed reports.
*   **Request:**
    *   **Method:** `POST`
    *   **Body Schema:**
        ```json
        {
          "query": "What is the lease liability for 2026?",
          "ticker": "AAPL",
          "filters": {
            "years": [2025, 2026],
            "document_types": ["10-K", "10-Q"]
          }
        }
        ```
*   **Response (200 OK):**
    ```json
    {
      "answer": "The lease liability for 2026 is $120 million...",
      "citations": [
        {
          "text": "$120 million",
          "document_id": "doc_01h2a8ce22ef88ca...",
          "page": 14,
          "bounding_box": [120, 450, 250, 500]
        }
      ]
    }
    ```
*   **Validation:**
    *   `query` length must fall in range `[5, 500]` characters.
    *   `ticker` must match regex pattern: `^[A-Z0-9]{1,5}$`.
*   **Authentication:** Bearer token required. Required Scope: `read:queries`.
*   **Error Handling & Status Codes:**
    *   `422 Unprocessable Entity` if query constraints fail (`VALIDATION_FAILED`).
    *   `502 Bad Gateway` if external LLM provider APIs timeout (`LLM_PROVIDER_TIMEOUT`).
*   **Rate Limiting:** Standard: 30 requests/minute. Institutional: 200 requests/minute.
*   **Future Extensions:** Add dynamic streaming response headers (`text/event-stream`) to render responses token-by-token.

---

### 3.5 `POST /api/v1/queries/compare`
*   **Purpose:** Perform a visual and semantic comparison of risk factors or MD&A disclosures across sequential periods.
*   **Request:**
    *   **Method:** `POST`
    *   **Body Schema:**
        ```json
        {
          "ticker": "AAPL",
          "source_document_id": "doc_01h2a8ce22ef88ca...",
          "target_document_id": "doc_01h2a8cf99ab99ce...",
          "sections": ["risk_factors"]
        }
        ```
*   **Response (200 OK):**
    ```json
    {
      "source_document_id": "doc_01h2a8ce22ef88ca...",
      "target_document_id": "doc_01h2a8cf99ab99ce...",
      "semantic_changes": [
        {
          "type": "ADDED",
          "summary": "Introduced language regarding cyber liabilities of autonomous vehicles."
        }
      ],
      "lexical_diff": "<p>Risk factors now include: <ins>cyber liability risks</ins>...</p>"
    }
    ```
*   **Validation:**
    *   `source_document_id` and `target_document_id` must match 36-character UUID limits.
*   **Authentication:** Bearer token required. Required Scope: `read:queries`.
*   **Error Handling & Status Codes:**
    *   `404 Not Found` if one or both document IDs are missing (`DOCUMENT_NOT_FOUND`).
*   **Rate Limiting:** Capped at 15 document comparisons/minute per user.
*   **Future Extensions:** Add auto-generation of comparative charts for numeric statement balance shifts.
