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

## Try layout discovery

```bash
uv run python -m phonebook.cli samples/   # reads 2-4 pages, shows the layout, asks you to accept
```
It calls the API once (my estimate: about $0.01-0.05); running it again on the same pages is free (disk cache).

## Try one page

```bash
uv run python -m phonebook.cli_page samples/page_05.jpg              # read one page (Haiku)
uv run python -m phonebook.cli_page samples/page_05.jpg --tier best  # same page with Opus
```
Free check first (no LLM): `uv run python -m phonebook.cli_rows samples/page_05.jpg` saves
`output/page_05.rows.jpg` with the row lines and numbers the agent will see.

The page reader is an agent: it can zoom into hard rows (max 4 tool calls per page).

Add `--debug` to see the steps as a tree: each node of the graph, and indented under
`read_page` the agent's steps (model, middleware, tools), with tokens and cost per LLM
call. All details (full prompts and answers) go to `output/<page>.<tier>.debug.txt`.

`--tier` is `cheap` (Haiku), `strong` (Sonnet) or `best` (Opus). `phonebook.cli` has it too.
The result is saved to `output/page_05.best.json` (gitignored, it has real numbers).
Run layout discovery first: it saves the layout to `.cache/profile.json`.

Phone book photos are private: keep them in `samples/` (ignored by git).
