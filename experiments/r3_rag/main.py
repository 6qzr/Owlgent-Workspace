
from fake_llm import generate_answer


def main() -> None:
    question = input("Ask the clinic assistant: ")

    result = generate_answer(question)

    print("\nAnswer:")
    print(result["answer"])

    if result["sources"]:
        print("\nSource documents:")
        for source in result["sources"]:
            print(f"- {source}")

        print(f"\nRelevance score: {result['score']:.4f}")


if __name__ == "__main__":
    main()
