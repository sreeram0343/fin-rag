import pytest
from unittest.mock import AsyncMock, MagicMock

from finrag.agent.orchestrator import AgentOrchestrator
from finrag.agent.verification import MathValidationSandbox
from finrag.db.models.document import DocumentChunk


def test_sandbox_safety_and_math() -> None:
    """Verify math validation sandbox accepts safe code and blocks imports/unsafe nodes."""
    sandbox = MathValidationSandbox()

    # Safe math script
    code = (
        "revenue = 1000\n"
        "margin = 0.40\n"
        "result = revenue * margin\n"
        "print('calculated:', result)"
    )

    res = sandbox.execute(code)
    assert res["success"] is True
    assert res["variables"]["result"] == 400.0
    assert "calculated: 400.0" in res["stdout"]

    # Blocked imports
    code_unsafe = "import os\nos.system('echo unsafe')"
    res_unsafe = sandbox.execute(code_unsafe)
    assert res_unsafe["success"] is False
    assert "SecurityError" in res_unsafe["error"]

    # Blocked write operations
    code_write = "open('test.txt', 'w').write('spam')"
    res_write = sandbox.execute(code_write)
    assert res_write["success"] is False
    assert "SecurityError" in res_write["error"]


@pytest.mark.asyncio
async def test_orchestrator_self_correction_math_flow() -> None:
    """Verify orchestrator triggers LLM self-correction loop on math mismatches."""
    llm = MagicMock()
    retriever = MagicMock()

    # Candidates list
    candidates = [
        {
            "id": "c1",
            "document_id": "d1",
            "page_number": 12,
            "bounding_box": [10, 20, 30, 40],
            "chunk_text": "Q3 revenues were 300 million and operating income was 120 million.",
            "chunk_type": "TEXT",
            "parent_header": "Income Statement Summary",
        }
    ]
    retriever.retrieve = AsyncMock(return_value=candidates)

    # 1. First prompt call returns incorrect margin metric (45% instead of 40%)
    resp_1 = {
        "text": (
            "The operating margin is 45.0%.\n"
            "```python\n"
            "result = 120 / 300\n"
            "```\n"
            "Citation: [Chunk 1]"
        ),
        "prompt_tokens": 100,
        "completion_tokens": 50,
    }

    # 2. Second prompt call corrects itself after feedback
    resp_2 = {
        "text": (
            "The operating margin is 40.0%.\n"
            "```python\n"
            "result = 120 / 300\n"
            "```\n"
            "Citation: [Chunk 1]"
        ),
        "prompt_tokens": 150,
        "completion_tokens": 50,
    }

    llm.generate = AsyncMock(side_effect=[resp_1, resp_2])

    orchestrator = AgentOrchestrator(llm=llm, retriever=retriever)

    result = await orchestrator.ask(
        query="what is the operating margin?",
        ticker="AAPL",
        max_attempts=2,
    )

    # Validate results are corrected
    assert "40.0%" in result["answer"]
    assert len(result["citations"]) == 1
    assert result["citations"][0]["page"] == 12
    assert result["citations"][0]["document_id"] == "d1"
    # The generator should be called exactly twice (first try, then self-correction try)
    assert llm.generate.call_count == 2


@pytest.mark.asyncio
async def test_orchestrator_comparison_flow() -> None:
    """Verify document comparison returns correct semantic changes."""
    llm = MagicMock()
    retriever = MagicMock()

    # Setup orchestrator with dummy chunk repos
    chunk_repo = MagicMock()
    orchestrator = AgentOrchestrator(llm=llm, retriever=retriever)
    orchestrator.chunk_repo = chunk_repo

    chunk1 = DocumentChunk(id="c1", chunk_text="Revenues rose.", parent_header="MD&A")
    chunk2 = DocumentChunk(id="c2", chunk_text="Revenues fell.", parent_header="MD&A")

    chunk_repo.get_by_document_id = AsyncMock(side_effect=[[chunk1], [chunk2]])

    llm.generate = AsyncMock(
        return_value={
            "text": '{"semantic_changes": [{"type": "MODIFIED", "summary": "Trend changed from rising to falling."}]}',
            "prompt_tokens": 50,
            "completion_tokens": 20,
        }
    )

    compare_res = await orchestrator.compare(
        ticker="AAPL",
        source_document_id="src-uuid-1111-2222-3333-444444444444",
        target_document_id="tgt-uuid-1111-2222-3333-444444444444",
        sections=["MD&A"],
    )

    assert len(compare_res["semantic_changes"]) == 1
    assert compare_res["semantic_changes"][0]["type"] == "MODIFIED"
    assert "falling" in compare_res["semantic_changes"][0]["summary"]
