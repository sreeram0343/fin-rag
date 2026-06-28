import json
import re
from typing import Any, Dict, List, Optional

import structlog

from finrag.agent.base import BaseLLM
from finrag.agent.verification import MathValidationSandbox
from finrag.retriever.base import BaseRetriever

logger = structlog.get_logger(__name__)


class AgentOrchestrator:
    """The central coordinator for QA synthesis, self-correction, math verification, and period-over-period comparisons."""

    def __init__(
        self,
        llm: BaseLLM,
        retriever: BaseRetriever,
        sandbox: Optional[MathValidationSandbox] = None,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.sandbox = sandbox or MathValidationSandbox()

    async def ask(
        self,
        query: str,
        ticker: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        """Execute the full RAG pipeline: retrieval, LLM reasoning, math verification, and self-correction."""
        logger.info("Executing orchestrator query ask", query=query, ticker=ticker)

        # 1. Retrieve candidates
        candidates = await self.retriever.retrieve(query, ticker, filters, top_k)
        if not candidates:
            return {
                "answer": "No relevant financial disclosures were found in the indexed documents for this ticker and period.",
                "citations": [],
            }

        # 2. Format retrieval context for LLM
        context_lines = []
        for idx, c in enumerate(candidates):
            bbox = c.get("bounding_box") or [0, 0, 0, 0]
            if isinstance(bbox, dict):
                x1, y1, x2, y2 = bbox.get("x1", 0), bbox.get("y1", 0), bbox.get("x2", 0), bbox.get("y2", 0)
            elif isinstance(bbox, list) and len(bbox) >= 4:
                x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
            else:
                x1, y1, x2, y2 = 0, 0, 0, 0

            context_lines.append(
                f"[Chunk {idx + 1}]\n"
                f"Ticker:\n{c.get('ticker') or ticker}\n"
                f"Page:\n{c['page_number']}\n"
                f"Section:\n{c['parent_header'] or 'MD&A'}\n"
                f"Bounding Box:\n({int(x1)},{int(y1)})-({int(x2)},{int(y2)})\n"
                f"Content:\n{c['chunk_text']}\n"
            )
        context_str = "\n---\n".join(context_lines)

        # 3. System prompt with strict instructions on citations and calculations
        system_prompt = (
            "You are an institutional-grade financial analyst agent. Your goal is to synthesize reports with mathematical precision.\n"
            "Here is the retrieved context from financial disclosures:\n\n"
            f"{context_str}\n\n"
            "Instructions:\n"
            "1. Answer the query strictly based on the retrieved context chunks. If the information is not present, state so.\n"
            "2. For every assertion or metric you reference, cite the source chunk using the format [Chunk X] at the end of the sentence.\n"
            "3. If you perform any calculations (e.g. growth rates, operating margins, ratios), you MUST write a python code block containing the calculation, assigning the final value to the variable `result`.\n"
            "Example calculation:\n"
            "```python\n"
            "# Operating income / Revenue\n"
            "result = 120.0 / 300.0\n"
            "```\n"
            "4. Enforce strict factuality. Do not estimate or guess numbers."
        )

        attempts = 0
        prompt = f"User Query: {query}\nProvide your synthesis:"
        feedback = ""

        last_response_text = ""

        # Generation & self-correction loop
        while attempts < max_attempts:
            attempts += 1
            current_prompt = prompt
            if feedback:
                current_prompt = f"{prompt}\n\n[SYSTEM FEEDBACK]\n{feedback}\nPlease revise your answer and correct any calculations or facts."

            response = await self.llm.generate(current_prompt, system_prompt, temperature=0.0)
            response_text = response["text"]
            last_response_text = response_text

            logger.info("Generated raw response from LLM", attempt=attempts)

            # Extract python blocks
            py_blocks = re.findall(r"```python\s*(.*?)\s*```", response_text, re.DOTALL)
            if not py_blocks:
                # No calculations to verify. Break loop.
                logger.info("No math blocks found in LLM response. Verification skipped.")
                break

            # Execute code blocks in sandbox
            validation_errors = []
            for block in py_blocks:
                res = self.sandbox.execute(block)
                if not res["success"]:
                    validation_errors.append(f"Calculation script execution error: {res['error']}")
                else:
                    # Check if 'result' is present and matches the response text claims
                    variables = res["variables"]
                    if "result" in variables:
                        val = variables["result"]
                        # Verify that the value of result is represented in text
                        if isinstance(val, (int, float)):
                            # Format value as float, percentage, and check
                            val_str = f"{val:.4f}"
                            val_pct = f"{val * 100:.1f}%"
                            val_pct_alt = f"{val * 100:.0f}%"
                            val_short = f"{val:.2f}"

                            # Build clean regexes or substring matches
                            in_text = (
                                str(val) in response_text
                                or val_str in response_text
                                or val_pct in response_text
                                or val_pct_alt in response_text
                                or val_short in response_text
                            )

                            if not in_text:
                                validation_errors.append(
                                    f"Mathematical validation mismatch: The code block evaluated `result = {val}`, but this value is not mentioned in your text summary."
                                )

            if not validation_errors:
                logger.info("All mathematical calculations verified successfully!")
                break
            else:
                feedback = "\n".join(validation_errors)
                logger.warning("Math validation failed", feedback=feedback, attempt=attempts)

        # 4. Resolve citations from the final text response
        from finrag.citation_engine.mapper import resolve_citations

        # Extract variables from successful sandbox executions if present in loop scope
        verified_vars = None
        if "res" in locals() and isinstance(locals()["res"], dict) and locals()["res"].get("success"):
            verified_vars = locals()["res"].get("variables")

        citations = resolve_citations(
            response_text=last_response_text,
            candidates=candidates,
            verified_math_vars=verified_vars,
        )

        # Clean the output text by removing [Chunk X] strings
        clean_answer = re.sub(r"\s*\[Chunk \d+\]", "", last_response_text)

        return {
            "answer": clean_answer,
            "citations": citations,
        }

    async def compare(
        self,
        ticker: str,
        source_document_id: str,
        target_document_id: str,
        sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compare disclosures across sequential filing periods (e.g. Risk Factors, MD&A)."""
        logger.info(
            "Comparing document disclosures",
            ticker=ticker,
            source=source_document_id,
            target=target_document_id,
            sections=sections,
        )

        # 1. Fetch chunks for both documents
        src_chunks = await self.chunk_repo.get_by_document_id(source_document_id)
        tgt_chunks = await self.chunk_repo.get_by_document_id(target_document_id)

        if not src_chunks or not tgt_chunks:
            return {
                "source_document_id": source_document_id,
                "target_document_id": target_document_id,
                "semantic_changes": [],
                "lexical_diff": "<p>Unable to retrieve document text for comparison.</p>",
            }

        # Filter by section tags if provided (heuristic based on parent headers)
        def filter_chunks(chunks: List[Any]) -> str:
            text_lines = []
            for chunk in chunks:
                if sections:
                    match_section = False
                    for sec in sections:
                        sec_clean = sec.replace("_", " ").lower()
                        header_clean = (chunk.parent_header or "").lower()
                        if sec_clean in header_clean or header_clean in sec_clean:
                            match_section = True
                            break
                    if not match_section:
                        continue
                text_lines.append(chunk.chunk_text)
            return "\n".join(text_lines)

        src_text = filter_chunks(src_chunks)
        tgt_text = filter_chunks(tgt_chunks)

        if not src_text or not tgt_text:
            # Fall back to comparing first 20 chunks if section filters returned nothing
            src_text = "\n".join([c.chunk_text for c in src_chunks[:20]])
            tgt_text = "\n".join([c.chunk_text for c in tgt_chunks[:20]])

        # 2. Call LLM to perform semantic diffing
        system_prompt = (
            "You are a financial risk and accounting difference engine.\n"
            "Compare the two texts below. The source text represents the previous period, and the target text represents the current period.\n"
            "Identify what was ADDED, MODIFIED, or DELETED.\n"
            "Return a clean JSON payload mapping semantic shifts under the key 'semantic_changes' containing objects with 'type' (ADDED, MODIFIED, DELETED) and 'summary' keys."
        )

        prompt = (
            f"Source Text:\n{src_text[:6000]}\n\n"
            f"Target Text:\n{tgt_text[:6000]}\n\n"
            "Provide semantic comparison JSON:"
        )

        response = await self.llm.generate(prompt, system_prompt, temperature=0.0)
        response_text = response["text"]

        # Parse JSON from response
        try:
            # Look for JSON structure in text
            json_match = re.search(r"({.*})|(\[.*\])", response_text, re.DOTALL)
            if json_match:
                parsed_data = json.loads(json_match.group(0))
                # Ensure it has 'semantic_changes' key
                if isinstance(parsed_data, dict) and "semantic_changes" in parsed_data:
                    changes = parsed_data["semantic_changes"]
                elif isinstance(parsed_data, list):
                    changes = parsed_data
                else:
                    changes = [{"type": "MODIFIED", "summary": "Disclosures updated across periods."}]
            else:
                changes = [{"type": "MODIFIED", "summary": "Disclosures updated across periods."}]
        except Exception:
            # Basic fallback
            changes = [
                {"type": "MODIFIED", "summary": "Document disclosures were modified. Detailed text diff shows shifts."}
            ]

        # Generate a simple lexical HTML diff
        lexical_diff = f"<p>Disclosures compared for section. Target document contains {len(tgt_text)} characters, source contained {len(src_text)} characters.</p>"

        return {
            "source_document_id": source_document_id,
            "target_document_id": target_document_id,
            "semantic_changes": changes,
            "lexical_diff": lexical_diff,
        }
