from typing import Final

from pydantic import BaseModel, ConfigDict


class ModelPrice(BaseModel):
    model_config = ConfigDict(frozen=True)
    input: float  # $ per million tokens
    output: float  # $ per million tokens
    cached: float = 0.0  # $ per million cached tokens


# Prices are approximate — verify against current provider docs before prod deployment.
PRICES: Final[dict[str, ModelPrice]] = {
    "deepseek-chat": ModelPrice(input=0.14, output=0.28, cached=0.014),
    "claude-haiku-4-5-20251001": ModelPrice(input=0.80, output=4.00, cached=0.08),
    "claude-sonnet-4-6": ModelPrice(input=3.00, output=15.00, cached=0.30),
    "claude-opus-4-7": ModelPrice(input=15.00, output=75.00, cached=1.50),
}

_FALLBACK: Final[ModelPrice] = ModelPrice(input=1.00, output=3.00)


def get_price(model: str) -> ModelPrice:
    return PRICES.get(model, _FALLBACK)


def calculate_cost(
    model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0
) -> float:
    price = get_price(model)
    billed_input = max(0, input_tokens - cached_tokens)
    return (
        billed_input * price.input / 1_000_000
        + output_tokens * price.output / 1_000_000
        + cached_tokens * price.cached / 1_000_000
    )
