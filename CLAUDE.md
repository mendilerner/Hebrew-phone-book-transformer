# Hebrew Phone Book Transformer

A learning project: a LangGraph (Python) pipeline that reads photos of
handwritten Hebrew phone books and turns them into structured contacts
(Excel + `.vcf`). The design must stay **generic**: it should work for other
Hebrew phone books too, not only the first one.

## Where the design lives

- `docs/ARCHITECTURE.md`: the **current** architecture (flow, decision points, state, graph).
- `docs/decisions/`: one short file per decision (ADR style), numbered `NNNN-title.md`.
- `docs/design/`: design drafts (for example the state schema).

These files are the single source of truth. The design is also discussed in a
claude.ai project, which reads this repo to stay up to date.

## Rule: keep the docs in sync

When you change the architecture (nodes, edges, routers, state keys, sub-graphs,
tools, the output format, or the MVP scope):

1. Update `docs/ARCHITECTURE.md` in the same commit, so it describes the code as it is now.
2. Add a new file in `docs/decisions/` that says what changed and why.
   Never edit an old decision: write a new one and mark the old one as "Superseded by NNNN".
3. If code and docs disagree, tell the user before you continue.

Small code changes that don't change the design do not need a decision file.

## About the user

An intermediate Python/TypeScript developer and not a native English speaker:
use simple words and short sentences. Add a short explanation to every
terminal command. This is a learning project: don't hide or skip the LangGraph
concepts.
