import re

from diet.models import DailySummary, MealLog, UserProfile


def escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special)}])", r"\\\1", text)


def _bar(current: float, target: float, width: int = 10) -> str:
    if target <= 0:
        return "░" * width
    ratio = min(current / target, 1.0)
    filled = round(ratio * width)
    return "█" * filled + "░" * (width - filled)


def format_nutrition_row(label: str, current: float, target: float | None, unit: str = "g") -> str:
    cur = round(current)
    if target:
        tgt = round(target)
        bar = _bar(current, target)
        pct = min(round(current / target * 100), 999)
        return f"{label}: {cur}{unit} / {tgt}{unit} {bar} {pct}%"
    return f"{label}: {cur}{unit}"


def format_meal_log(meal: MealLog) -> str:
    n = meal.total_nutrition
    lines = [
        f"✅ Logged {meal.meal_type.value.title()} ({meal.source.value})",
        "",
    ]
    for entry in meal.entries:
        f = entry.food
        lines.append(f"  • {f.name} — {f.quantity} {f.unit} ({round(f.nutrition.calories)} kcal)")
    lines += [
        "",
        f"Total: {round(n.calories)} kcal  |  P {round(n.protein_g)}g  "
        f"|  C {round(n.carbs_g)}g  |  F {round(n.fat_g)}g",
    ]
    return "\n".join(lines)


def format_daily_summary(summary: DailySummary) -> str:
    n = summary.total_nutrition
    t = summary.targets
    date_str = summary.date.strftime("%A, %B %-d")
    lines = [f"📊 {date_str}", ""]

    lines.append(format_nutrition_row("Calories", n.calories, t.calories if t else None, "kcal"))
    lines.append(format_nutrition_row("Protein ", n.protein_g, t.protein_g if t else None))
    lines.append(format_nutrition_row("Carbs   ", n.carbs_g, t.carbs_g if t else None))
    lines.append(format_nutrition_row("Fat     ", n.fat_g, t.fat_g if t else None))
    lines.append(format_nutrition_row("Fiber   ", n.fiber_g, None))
    lines.append("")

    if summary.meals:
        lines.append(f"Meals logged: {len(summary.meals)}")
        for meal in summary.meals:
            lines.append(
                f"  • {meal.meal_type.value.title()}: {round(meal.total_nutrition.calories)} kcal"
            )
    else:
        lines.append("No meals logged yet.")

    return "\n".join(lines)


def format_weekly_summary(summaries: list[DailySummary]) -> str:
    lines = ["📈 Weekly Overview", ""]
    for s in summaries:
        day = s.date.strftime("%a %-d %b")
        cal = round(s.total_nutrition.calories)
        prot = round(s.total_nutrition.protein_g)
        target_str = ""
        if s.targets:
            pct = round(cal / s.targets.calories * 100) if s.targets.calories else 0
            target_str = f" ({pct}%)"
        lines.append(f"{day}: {cal} kcal{target_str}  |  P {prot}g")
    return "\n".join(lines)


def format_profile(profile: UserProfile) -> str:
    lines = ["👤 Your Profile", ""]
    lines.append(f"Goal: {profile.goal.value.replace('_', ' ').title()}")
    if profile.height_cm:
        lines.append(f"Height: {profile.height_cm} cm")
    if profile.weight_kg:
        lines.append(f"Weight: {profile.weight_kg} kg")
    if profile.age:
        lines.append(f"Age: {profile.age}")
    if profile.dietary_restrictions:
        lines.append(f"Restrictions: {', '.join(profile.dietary_restrictions)}")
    if profile.targets:
        t = profile.targets
        lines += [
            "",
            "Daily Targets:",
            f"  Calories: {round(t.calories)} kcal",
            f"  Protein:  {round(t.protein_g)} g",
            f"  Carbs:    {round(t.carbs_g)} g",
            f"  Fat:      {round(t.fat_g)} g",
        ]
    return "\n".join(lines)


HELP_TEXT = """🥗 *Diet Bot — Commands*

*Logging meals:*
/log \\<food description\\> — log a meal by text
Send a photo — log from food image or barcode scan
Send a voice message — log by speaking

*Tracking:*
/summary — today's nutrition summary
/weekly — 7\\-day overview

*Profile:*
/profile — view your profile
/setup — set up goals and targets

*Other:*
/help — show this message

*Tips:*
• Be specific: "2 scrambled eggs, 1 slice whole wheat toast, 200ml OJ"
• Send a product barcode photo to log packaged food
• Voice messages work great for logging on the go
"""
