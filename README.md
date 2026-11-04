# Hebrew-phone-book-transformer

A LangGraph learning project: photos of a handwritten Hebrew phone book → Excel + `.vcf`.
The design is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Setup

```bash
uv sync                        # create .venv and install the project + dev tools
```

Put the API keys in a file `.env` in the project folder (it is gitignored; tests don't need it):
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```
Don't set `ANTHROPIC_API_KEY` as a system or user variable: Claude Code reads it too, and
then it uses the paid key instead of your Claude subscription (and Remote Control won't start).

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
uv run python -m phonebook.cli_page samples/page_05.jpg                # Claude (Opus) + GPT read the page
uv run python -m phonebook.cli_page samples/page_05.jpg --tier strong  # Claude side with Sonnet (cheaper)
```
Names both models read the same are trusted. For the others Claude picks between the two
readings, and GPT checks each answer Claude is sure about. The rest is listed "To review"
with every reading.
Add `--debug` to see every message sent to the LLM, its answer, and every graph step
(printed to stderr; save it with `2> debug.txt`).

### Score a run (free)

```bash
uv run python -m phonebook.cli_score --make-truth output/page_05.best.json truth/page_05.json  # copy a run, then fix it by hand
uv run python -m phonebook.cli_score truth/page_05.json output/page_05.*.json                 # compare runs with it
```
It shows names right, letters right, phones right, missing and extra entries, and cost.

`--tier` is `cheap` (Haiku), `strong` (Sonnet) or `best` (Opus) for the Claude nodes.
`phonebook.cli` has it too. The result is saved to `output/page_05.default.json`
(gitignored, it has real numbers).
Run layout discovery first: it saves the layout to `.cache/profile.json`.

Phone book photos are private: keep them in `samples/` (ignored by git).
