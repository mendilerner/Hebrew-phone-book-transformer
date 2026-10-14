# Hebrew-phone-book-transformer

A LangGraph learning project: photos of a handwritten Hebrew phone book → Excel + `.vcf`.
The design is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Setup

```bash
uv sync                        # create .venv and install the project + dev tools
export ANTHROPIC_API_KEY=...   # needed only for real LLM calls (tests don't need it)
```

## Check the code

```bash
uv run pytest                  # run the unit tests (no API calls, $0)
uv run ruff check src tests    # find lint problems
uv run ruff format src tests   # fix code formatting
```

Phone book photos are private: keep them in `samples/` (ignored by git).
