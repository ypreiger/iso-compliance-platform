# ISO standard upload format

Upload full standards via **Admin → Knowledge → ISO standards corpus**.

## Supported files

| Format | Use |
|--------|-----|
| `.md` / `.txt` | Clause headers like `4.1 Title` or `## 4.1 Title`, body until next clause |
| `.pdf` | Text-based PDF only. The parser reflows wrapped lines and assigns paragraphs to the nearest clause heading. Re-upload with **Replace** after parser updates. |
| `.docx` | Uses Word heading styles when present; otherwise same clause-line parser as PDF. |
| `.json` (single language) | Array of `{clause_id, title, body, sort_order}` |
| `.json` (bilingual bundle) | `{standard, clauses: [{clause_id, en: {title, body}, he: {title, body}}]}` — set language to **English + Hebrew** |

Upload **one language per file** (`en` or `he`), or one **bilingual JSON** to replace both at once.

## Example markdown (`ISO9001-2015-en.md`)

```markdown
4.1 Understanding the organization and its context

The organization shall determine external and internal issues...

4.2 Understanding the needs and expectations of interested parties

The organization shall determine the interested parties...
```

## Workflow

1. **English** — upload with language `en`, edition e.g. `2015`.
2. **Hebrew** — upload with language `he`, use **English + Hebrew (JSON bundle)**, or click **Translate EN → HE** (requires LLM configured).
3. **Replace vs merge** — check **Replace existing clauses and RAG** to delete all prior rows for that standard+language and load the file fresh (recommended for full standards). Uncheck to merge/update only matching clause IDs.
4. **Duplicate clause IDs in one file** — if the parser finds the same clause number twice (common in PDFs), the last occurrence is kept and a warning is returned.

## Viewer

- **ISO Standards** page reads `iso_clause_text` (not RAG placeholders).
- Hebrew mode uses Hebrew rows when present; otherwise shows English with an **EN** badge until translated.
