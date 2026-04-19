import base64

import structlog

from diet.barcode import lookup_barcode
from diet.models import (
    FoodItem,
    ImageAnalysisResponse,
    InputSource,
    MealEntry,
    MealType,
    NutritionInfo,
)
from llm.interface import ImageContent, LLMClient, Message, TaskClass, TaskSpec, TextContent

logger = structlog.get_logger()

_TASK = TaskSpec(name="analyze_food_image", task_class=TaskClass.STANDARD, requires_vision=True)

_SYSTEM_PROMPT = """You are a nutrition expert analyzing food images.
Identify either:
1. Food items visible in the image with estimated portions and nutrition
2. A barcode visible in the image (return the barcode number)

Be concise and accurate. Estimate portions based on visual cues.
For nutrition, use standard database values. Confidence 0–1."""


async def analyze_image(
    llm: LLMClient,
    image_bytes: bytes,
    media_type: str,
    user_id: int,
) -> tuple[list[MealEntry], InputSource, MealType | None]:
    """Analyze a food photo or barcode image. Returns (entries, source, meal_type)."""
    b64 = base64.b64encode(image_bytes).decode()

    messages = [
        Message(role="system", content=_SYSTEM_PROMPT),
        Message(
            role="user",
            content=[
                ImageContent(base64_data=b64, media_type=media_type),
                TextContent(
                    text=(
                        "Analyze this image. If you see a barcode, return result_type='barcode' "
                        "and the barcode string. If you see food, return result_type='food' with "
                        "a list of entries. If neither, return result_type='unknown'."
                    )
                ),
            ],
        ),
    ]

    result = await llm.complete(_TASK, messages, response_model=ImageAnalysisResponse)
    if result.parsed is None:
        logger.warning("image.parse_failed", user_id=user_id)
        return [], InputSource.IMAGE, None

    parsed: ImageAnalysisResponse = result.parsed

    if parsed.result_type == "barcode" and parsed.barcode:
        logger.info("image.barcode_detected", barcode=parsed.barcode, user_id=user_id)
        food = await lookup_barcode(parsed.barcode)
        if food:
            return [MealEntry(food=food)], InputSource.BARCODE, None
        # barcode not in database — fall through to empty
        return [], InputSource.BARCODE, None

    if parsed.result_type == "food" and parsed.entries:
        entries = [
            MealEntry(
                food=FoodItem(
                    name=e.name,
                    quantity=e.quantity,
                    unit=e.unit,
                    nutrition=NutritionInfo(
                        calories=e.calories,
                        protein_g=e.protein_g,
                        carbs_g=e.carbs_g,
                        fat_g=e.fat_g,
                        fiber_g=e.fiber_g,
                    ),
                    confidence=e.confidence,
                )
            )
            for e in parsed.entries
        ]
        return entries, InputSource.IMAGE, None

    return [], InputSource.IMAGE, None
