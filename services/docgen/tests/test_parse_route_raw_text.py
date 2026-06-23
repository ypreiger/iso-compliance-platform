import asyncio
import base64

from app.routes import parse as parse_route


def test_general_task_preserves_raw_text_for_retrieval(monkeypatch):
    raw_text = "1 . 2 Clause heading\nLine A\n\nLine B"
    monkeypatch.setattr("app.agents.parser.extract_text", lambda _data, _filename: raw_text)

    req = parse_route.ParseRequest(
        filename="sample.pdf",
        content_b64=base64.b64encode(b"fake").decode(),
        standard="ISO9001",
        language="en",
        task="general",
    )
    result = asyncio.run(parse_route.parse_document(req))

    assert result.parse_method == "text"
    assert result.raw_text == raw_text
    assert result.raw_text_length == len(raw_text)
    assert result.sheets is not None
    assert result.sheets[0]["rows"][0]["line"] == "1 . 2 Clause heading"


def test_iso_clause_task_uses_preprocessed_text(monkeypatch):
    raw_text = "1 . 2 Clause heading\nBody"
    seen = {}

    monkeypatch.setattr("app.agents.parser.extract_text", lambda _data, _filename: raw_text)

    async def fake_extract_clauses(text, *, standard, language):
        seen["llm_text"] = text
        return ([{"clause_id": "1.2", "title": "Clause heading", "body": "Body"}], "extract-model")

    monkeypatch.setattr("app.agents.extractor.extract_clauses", fake_extract_clauses)
    monkeypatch.setattr(
        parse_route,
        "_regex_extract_clauses",
        lambda text: [{"clause_id": "1.2", "title": "Clause heading", "body": f"regex:{text}"}],
    )
    monkeypatch.setattr(
        parse_route,
        "_choose_best_clause_set",
        lambda **kwargs: (kwargs["llm_clauses"], "llm"),
    )

    req = parse_route.ParseRequest(
        filename="sample.pdf",
        content_b64=base64.b64encode(b"fake").decode(),
        standard="ISO9001",
        language="en",
        task="iso_clauses",
    )
    result = asyncio.run(parse_route.parse_document(req))

    assert result.parse_method == "llm"
    assert seen["llm_text"].startswith("1.2 Clause heading")
