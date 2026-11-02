# ADR 0003: Clinic answers via PostgreSQL full-text search with sources

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** @NoorAlbusaidi, team
- **Related:** Spike R3 #4, [R3 note](../research/R3-rag.md), #13

## Context
Clinic questions must be answered only from the clinic's documents. Each answer must name its source, and the assistant must say honestly "I don't know" when nothing matches (FR-3). PostgreSQL is the only database allowed.

## Options considered
1. **PostgreSQL full-text search** (`tsvector`, `websearch_to_tsquery`, `ts_rank`): needs no extra infrastructure and worked on the R3 tests. It misses paraphrased questions.
2. **Embeddings with pgvector**: handles paraphrases, but needs the extension and an embedding model. The extension isn't available in our image.

## Decision
- Split the documents into paragraphs and store them in `doc_chunks`, with a generated `tsvector` column and a GIN index.
- Retrieve the top-k paragraphs that score above a configurable threshold.
- The LLM answers only from those passages and names the source document.
- Below the threshold, the reply is "I don't know".

## Consequences
- No new services, and PostgreSQL stays the only database.
- A reworded question can miss. An optional mitigation is to have the LLM rewrite the question into keywords before searching. This stays testable with the FakeLLM.
- The threshold (0.03 in R3) is provisional and is set in config.
- pgvector remains a future option if the document set grows.
