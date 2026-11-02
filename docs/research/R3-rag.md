# R3 – RAG (Retrieval-Augmented Generation) Experiment

## 1. Question

How can we split clinic documents into paragraphs, retrieve relevant passages, ground answers in those passages, and identify their source? Should we use PostgreSQL keyword search or embeddings? What happens when no relevant information is found?

## 2. Options compared

### Option A: PostgreSQL Full-Text Search

- Split documents into paragraphs (chunks).
- Store each paragraph and its source filename in PostgreSQL.
- Use `to_tsvector()` to create searchable text.
- Use `plainto_tsquery()` / `websearch_to_tsquery()` to process questions.
- Use `ts_rank()` to rank matching paragraphs.
- Apply a relevance threshold to reject weak matches.

### Option B: Embedding Search (pgvector)

- Convert document paragraphs into numerical vectors using an embedding model.
- Store vectors alongside the original paragraphs in PostgreSQL.
- Convert user questions into vectors.
- Retrieve semantically similar paragraphs using vector distance.

pgvector was investigated as an option, but the current PostgreSQL Docker image does not have the `vector` extension available. Therefore, this comparison is based on technical capabilities rather than an empirical embedding benchmark.

## 3. Experiment setup

Three fictional clinic documents were created:

- `opening_hours.md`
- `blood_test_preparation.md`
- `insurance.md`

The documents were split into paragraphs and stored in the `r3_rag_chunks` PostgreSQL table.

Each record contains:
- Unique ID
- Source filename
- Paragraph index
- Paragraph content
- Automatically generated `tsvector`

A GIN index was created to support full-text search.

The prototype uses a deterministic fake LLM and does not require an API key.

## 4. Experimental results

| Question | Result |
|---       |---|
| What time does the clinic open? | Correct passage retrieved; score approximately 0.0405 |
| How long should I fast before a blood test? | Correct passage retrieved; score approximately 0.0494 |
| What is the best restaurant in Muscat? | No matching passage; assistant returned "I don't know" |
| When does the medical center start operating? | No matching passage; keyword search failed to recognize the paraphrase |

The initial relevance threshold was 0.01. After observing irrelevant results, it was increased to 0.03. This filtered the observed low-scoring results while retaining the tested relevant passages.

## 5. What the experiment showed

**Strengths of keyword search:**
- Simple implementation.
- No embedding model required.
- No additional PostgreSQL extension required.
- Effective for questions containing matching terminology.
- Supports source attribution and relevance ranking.

**Limitations:**
- May fail when users use synonyms or different wording.
- OR-based matching can retrieve irrelevant passages.
- The relevance threshold requires calibration.
- A high ranking score does not guarantee that a passage answers the question.

**Embedding search advantages:**
- Can identify semantic similarity between differently worded sentences.
- Better suited to synonym and paraphrase retrieval.
- Requires an embedding model and pgvector support in PostgreSQL.

## 6. Recommendation

Recommend PostgreSQL Full-Text Search for the current clinic assistant prototype.

Reasons:
- The document collection is small.
- Keyword retrieval worked for the tested questions.
- Source attribution and rejection of unmatched questions were demonstrated.
- It avoids additional infrastructure and embedding dependencies.

Consider pgvector and embedding-based retrieval if the document collection grows or users frequently ask questions using different wording.

PostgreSQL remains the only database in either approach.

## 7. Risks and limitations

- The sample documents are fictional and do not represent official clinic policies.
- The experiment contains only three documents and 16 paragraphs.
- The 0.03 threshold is provisional and needs further evaluation.
- Embedding search was not implemented or benchmarked because pgvector was unavailable.
- The fake LLM returns retrieved text rather than generating a natural-language answer.
- Retrieval quality does not guarantee factual correctness; source passages should always be checked.

## 8. Sources

1. PostgreSQL Official Documentation – Text Search Functions and Operators: https://www.postgresql.org/docs/current/functions-textsearch.html
2. PostgreSQL Official Documentation – Text Search Tables and Indexes: https://www.postgresql.org/docs/current/textsearch-tables.html
3. PostgreSQL Official Documentation – Controlling Text Search: https://www.postgresql.org/docs/current/textsearch-controls.html
4. pgvector Official Repository: https://github.com/pgvector/pgvector

## 9. Outcome

A working PostgreSQL-based RAG prototype was demonstrated. It retrieves relevant clinic paragraphs, identifies their source documents, and returns an honest "I don't know" when no matching information is found.

**Decision proposed:** Use PostgreSQL Full-Text Search for the current prototype and consider pgvector for future semantic retrieval requirements.