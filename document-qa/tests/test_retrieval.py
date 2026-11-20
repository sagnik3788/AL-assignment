from app.retrieval import contextual_query, cosine_similarity


def test_cosine_similarity_handles_scale_and_mismatch():
    assert cosine_similarity([1, 0], [4, 0]) == 1
    assert cosine_similarity([1, 0], [0, 1]) == 0
    assert cosine_similarity([1], [1, 0]) == 0
    assert cosine_similarity([0, 0], [1, 0]) == 0


def test_follow_up_query_uses_previous_user_question():
    history = [{"role": "user", "content": "Summarize the field report"}, {"role": "assistant", "content": "It compares three sites."}]
    assert "Earlier question: Summarize the field report" in contextual_query("What about its limits?", history)


def test_standalone_query_stays_unchanged():
    assert contextual_query("What is the field report deadline?", []) == "What is the field report deadline?"
