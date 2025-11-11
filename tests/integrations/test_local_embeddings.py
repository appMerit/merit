import pytest

from merit_analyzer.core.local_models.embeddings import (
    MODEL_ID,
    LocalEmbeddingsEngine,
)


@pytest.mark.asyncio
async def test_local_engine_generates_embeddings_from_granite_weights() -> None:
    engine = LocalEmbeddingsEngine()
    inputs = [
        "User service timed out during login attempts.",
        "Login request failed because the user service took too much time.",
        "Payment gateway rejected the transaction with code 502.",
        "Charge attempt hit an error from the Stripe gateway.",
        "Formatting mismatch for CSV export columns.",
    ]

    vectors = await engine.generate_embeddings(inputs, model=MODEL_ID)

    assert len(vectors) == len(inputs)
    assert len(vectors[0]) == 384
    assert vectors[0] != vectors[1]
