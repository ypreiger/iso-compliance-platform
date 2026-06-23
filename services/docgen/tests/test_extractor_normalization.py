import asyncio

from app.agents import extractor


def test_extract_clauses_handles_nested_payload_without_crashing(monkeypatch):
    async def fake_llm_call(*_args, **_kwargs):
        return "{}"

    monkeypatch.setattr(extractor, "llm_call", fake_llm_call)
    monkeypatch.setattr(
        extractor,
        "parse_json_response",
        lambda _raw: {
            "result": {
                "clauses": [
                    {"clause_id": "4.1", "title": "Context", "body": "Body text"},
                    [{"clause_id": "4.2", "title": "Needs", "body": "Needs body"}],
                ]
            },
            "meta": {"tokens": 111},
        },
    )
    monkeypatch.setattr(
        "app.config.get_model_config",
        lambda: {"extract": {"model": "extract-test-model"}},
    )

    clauses, model_used = asyncio.run(
        extractor.extract_clauses(
            "4.1 Context\nBody text\n4.2 Needs\nNeeds body",
            standard="ISO9001",
            language="en",
        )
    )

    assert model_used == "extract-test-model"
    assert [c["clause_id"] for c in clauses] == ["4.1", "4.2"]
    assert clauses[0]["body"] == "Body text"
    assert clauses[1]["body"] == "Needs body"
