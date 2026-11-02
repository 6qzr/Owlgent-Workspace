
from retrieval import search_documents


def generate_answer(question: str) -> dict:
    """Generate a grounded answer using retrieved clinic documents."""

    results = search_documents(question)

    if not results:
        return {
            "answer": "I don't know. The clinic documents do not contain relevant information.",
            "sources": [],
        }

    # Use the highest-ranked retrieved paragraph.
    best_result = results[0]

    return {
        "answer": best_result["content"],
        "sources": [best_result["source"]],
        "score": best_result["score"],
    }
