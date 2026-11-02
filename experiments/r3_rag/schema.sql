
-- R3 RAG experiment: clinic document chunks

CREATE TABLE IF NOT EXISTS r3_rag_chunks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    source TEXT NOT NULL,

    chunk_index INTEGER NOT NULL,

    content TEXT NOT NULL,

    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', content)
    ) STORED,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (source, chunk_index)
);

-- Index to make full-text searches faster
CREATE INDEX IF NOT EXISTS idx_r3_rag_search
ON r3_rag_chunks
USING GIN (search_vector);
