"""Replies carry a kind marker that survives the checkpoint and never reaches the model."""

from langchain_core.messages import AIMessage, HumanMessage, convert_to_openai_messages
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from clinic_assistant.agent.nodes import CLARIFYING, reply_kind, reply_update


def test_ordinary_reply_has_no_kind() -> None:
    message = reply_update("8 to 4.")["messages"][0]

    assert reply_kind(message) is None


def test_marked_reply_carries_its_kind() -> None:
    message = reply_update("Which day?", kind=CLARIFYING)["messages"][0]

    assert reply_kind(message) == CLARIFYING


def test_kind_survives_the_checkpoint_serializer() -> None:
    serializer = JsonPlusSerializer()
    message = reply_update("Which day?", kind=CLARIFYING)["messages"][0]

    restored = serializer.loads_typed(serializer.dumps_typed(message))

    assert reply_kind(restored) == CLARIFYING


def test_kind_is_never_sent_to_the_model() -> None:
    message = reply_update("Which day?", kind=CLARIFYING)["messages"][0]

    assert convert_to_openai_messages([message]) == [{"role": "assistant", "content": "Which day?"}]


def test_messages_without_metadata_have_no_kind() -> None:
    assert reply_kind(HumanMessage("hi")) is None
    assert reply_kind(AIMessage("hi", response_metadata={"reply_kind": 3})) is None
