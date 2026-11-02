
from database import get_connection

MIN_RELEVANCE_SCORE = 0.03


def search_documents(
    question: str,
    limit: int = 3,
) -> list[dict]:
    """Retrieve relevant clinic paragraphs using PostgreSQL full-text search."""

    if not question.strip():
        return []

    sql = """
        WITH search_query AS (
            SELECT websearch_to_tsquery(
                'english',
                replace(%s, ' ', ' OR ')
            ) AS query
        )
        SELECT
            chunks.content,
            chunks.source,
            chunks.chunk_index,
            ts_rank(chunks.search_vector, search_query.query) AS score
        FROM r3_rag_chunks AS chunks
        CROSS JOIN search_query
        WHERE chunks.search_vector @@ search_query.query
        ORDER BY score DESC
        LIMIT %s;
    """

    with get_connection() as conn:
        rows = conn.execute(sql, (question, limit)).fetchall()

    return [
        {
            "content": row[0],
            "source": row[1],
            "chunk_index": row[2],
            "score": float(row[3]),
        }
        for row in rows
        if float(row[3]) >= MIN_RELEVANCE_SCORE
    ]


if __name__ == "__main__":
    questions = [
        "What time does the clinic open?",
        "What is the best restaurant in Muscat?",
    ]

    for question in questions:
        print(f"\nQuestion: {question}")
        results = search_documents(question)

        for result in results:
            print(result)
