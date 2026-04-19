import httpx
import structlog

from diet.models import FoodItem, NutritionInfo

logger = structlog.get_logger()

_BASE_URL = "https://world.openfoodfacts.org/api/v2/product"


async def lookup_barcode(barcode: str) -> FoodItem | None:
    """Query Open Food Facts for product nutrition by barcode."""
    url = f"{_BASE_URL}/{barcode}.json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
    except httpx.RequestError:
        logger.warning("barcode.request_failed", barcode=barcode)
        return None

    if resp.status_code != 200:
        logger.warning("barcode.lookup_failed", barcode=barcode, status=resp.status_code)
        return None

    data = resp.json()
    if data.get("status") != 1:
        logger.info("barcode.not_found", barcode=barcode)
        return None

    product = data.get("product", {})
    nutriments = product.get("nutriments", {})

    name = (
        product.get("product_name")
        or product.get("product_name_en")
        or product.get("generic_name")
        or "Unknown Product"
    )

    # prefer per-serving values, fall back to per-100g
    def _get(key: str) -> float:
        return float(nutriments.get(f"{key}_serving") or nutriments.get(f"{key}_100g") or 0.0)

    nutrition = NutritionInfo(
        calories=_get("energy-kcal"),
        protein_g=_get("proteins"),
        carbs_g=_get("carbohydrates"),
        fat_g=_get("fat"),
        fiber_g=_get("fiber"),
    )

    return FoodItem(
        name=name,
        quantity=1,
        unit="serving",
        nutrition=nutrition,
        barcode=barcode,
        confidence=0.95,
    )
