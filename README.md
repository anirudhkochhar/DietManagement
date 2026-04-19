# Diet Management Bot

A Telegram bot for tracking meals and nutrition, powered by LLMs. Log food by typing, taking a photo, scanning a barcode, or sending a voice message. The bot estimates calories and macros, tracks your daily targets, and shows weekly progress.

---

## Features

- **Text logging** — describe a meal in plain language
- **Photo logging** — photograph your food; Claude Vision identifies it and estimates nutrition
- **Barcode scanning** — photograph any product barcode; the bot looks it up in Open Food Facts (3M+ products, no API key needed)
- **Voice logging** — send a voice message; Whisper transcribes it and logs the meal
- **Daily summary** — calories and macros vs your personal targets, with visual progress bars
- **Weekly overview** — 7-day calorie and protein history
- **Profile setup** — guided onboarding sets your goal, body stats, and dietary restrictions; daily targets are calculated automatically using the Mifflin-St Jeor formula

---

## Tech stack

| Layer | Choice |
|---|---|
| Bot framework | `python-telegram-bot` v21+ (async) |
| LLM (text/image) | DeepSeek by default; Claude Sonnet for vision; swappable via env |
| Audio transcription | OpenAI Whisper |
| Barcode database | Open Food Facts (free, open, no key required) |
| Data models | Pydantic v2 |
| Storage | SQLAlchemy async — SQLite locally, Postgres-ready for prod |
| Logging | structlog (JSON in prod, console in dev) |
| Language | Python 3.11+ |

---

## Quickstart

### 1. Get a Telegram bot token

Talk to [@BotFather](https://t.me/botfather) on Telegram:

```
/newbot
```

Copy the token it gives you.

### 2. Clone and configure

```bash
git clone <repo-url>
cd DietManagement
cp .env.example .env
```

Open `.env` and fill in the values:

```env
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# At least one LLM key (DeepSeek is cheapest for text)
DEEPSEEK_API_KEY=your_deepseek_key

# Needed for photo/barcode analysis (Claude Vision)
ANTHROPIC_API_KEY=your_anthropic_key

# Needed for voice message transcription (Whisper)
OPENAI_API_KEY=your_openai_key
```

> You can run without `OPENAI_API_KEY` — voice messages will just be unsupported.  
> You can run without `ANTHROPIC_API_KEY` — photo analysis will be unsupported.  
> Text logging works with DeepSeek alone.

### 3. Install dependencies and run

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync

# Run the bot
uv run python -m bot.main
```

The database (`diet.db`) is created automatically on first run.

---

## Commands

| Command | Description |
|---|---|
| `/start` | Register and get a welcome message |
| `/setup` | 5-step guided setup: goal, height, weight, age, restrictions |
| `/log <food>` | Log a meal by description |
| `/summary` | Today's nutrition summary with progress bars |
| `/weekly` | 7-day calorie and protein overview |
| `/profile` | View your current profile and targets |
| `/help` | Show all commands |
| `/cancel` | Cancel an in-progress setup |

### Non-command inputs

| What you send | What happens |
|---|---|
| A meal description (no `/log`) | Logged as a meal automatically |
| A photo of food | Vision model identifies food and estimates nutrition |
| A photo of a barcode | Barcode is read → Open Food Facts lookup |
| A voice message | Whisper transcribes → logged as a meal |

---

## Usage examples

**Log a meal by text:**
```
/log 2 scrambled eggs, 1 slice sourdough toast with butter, 200ml orange juice
```

**Free-text logging (no slash command needed):**
```
had a chicken caesar salad for lunch, medium sized
```

**Log by barcode:**
Photograph the barcode on any packaged product. The bot reads it and looks up the exact nutrition information.

**Log by voice:**
Hold the microphone button in Telegram and describe what you ate. The bot transcribes and logs it.

**Daily summary:**
```
/summary
```
```
📊 Sunday, April 19

Calories: 1420kcal / 1800kcal ███████░░░ 79%
Protein : 98g / 135g ███████░░░ 73%
Carbs   : 160g / 200g ████████░░ 80%
Fat     : 52g / 60g ████████░░ 87%
Fiber   : 18g

Meals logged: 3
  • Breakfast: 420 kcal
  • Lunch: 580 kcal
  • Dinner: 420 kcal
```

---

## Configuration

All settings are controlled via `.env` or environment variables.

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Required. From BotFather. |
| `ANTHROPIC_API_KEY` | — | Claude API key (vision + reasoning tasks) |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key (default for text tasks) |
| `OPENAI_API_KEY` | — | OpenAI key (Whisper voice transcription only) |
| `LLM_MODEL_TRIVIAL` | `deepseek-chat` | Model for classification/routing tasks |
| `LLM_MODEL_STANDARD` | `deepseek-chat` | Model for meal parsing and replies |
| `LLM_MODEL_REASONING` | `claude-sonnet-4-6` | Model for complex reasoning tasks |
| `LLM_MODEL_VISION` | `claude-sonnet-4-6` | Model for image/barcode analysis |
| `BUDGET_PER_USER_DAILY_USD` | `0.10` | Max LLM spend per user per day |
| `BUDGET_GLOBAL_HOURLY_USD` | `1.00` | Max total LLM spend per hour |
| `DATABASE_URL` | `sqlite+aiosqlite:///./diet.db` | SQLite locally; use Postgres URL for prod |
| `ENV` | `dev` | `dev` = console logs; `prod` = JSON logs |

### Swapping LLM providers

To use Claude for everything:
```env
LLM_MODEL_TRIVIAL=claude-haiku-4-5-20251001
LLM_MODEL_STANDARD=claude-sonnet-4-6
```

To use DeepSeek for everything (no Anthropic key needed):
```env
LLM_MODEL_VISION=deepseek-chat
```
Note: DeepSeek's vision support is more limited than Claude's for food recognition.

---

## How multimodal input works

### Food photos
1. Telegram sends the photo to the bot
2. The photo is base64-encoded and sent to the vision model (Claude Sonnet by default)
3. The model returns structured JSON: food items with quantities and estimated nutrition
4. Results are saved and a summary is returned

### Barcode photos
1. Same photo pipeline as above
2. If the model detects a barcode, it returns `result_type: "barcode"` with the barcode string
3. The barcode is queried against the [Open Food Facts API](https://world.openfoodfacts.org) — free, no key required, 3M+ products
4. Exact product nutrition is returned and logged

### Voice messages
1. Telegram sends the voice message as an OGG file
2. The audio is sent to OpenAI Whisper (`whisper-1`) for transcription
3. The transcription is treated as a text meal description and parsed by the standard meal model
4. Requires `OPENAI_API_KEY`

---

## Cost estimates

| Action | Model | Approx cost |
|---|---|---|
| Log a meal (text) | `deepseek-chat` | ~$0.0001 |
| Analyse a food photo | `claude-sonnet-4-6` | ~$0.003 |
| Transcribe voice (1 min) | `whisper-1` | ~$0.006 |
| `/summary`, `/weekly` | DB only — no LLM | $0 |

With the default $0.10/day user budget:
- ~1000 text meal logs, or
- ~30 photo analyses, or
- ~15 minutes of voice logging

---

## Project structure

```
bot/           # Telegram handlers, conversation flows (thin layer only)
  deps.py      # Per-request service factories (session management)
  formatters.py
  keyboards.py
  handlers/
llm/           # Provider-agnostic LLM interface and router
  interface.py # LLMClient protocol, TaskSpec, Message types
  router.py    # Router (model selection) + BudgetGuard
  pricing.py   # Cost calculation
  providers/   # anthropic.py, deepseek.py, whisper.py
diet/          # Domain logic — no Telegram or LLM SDK imports
  models.py    # Pydantic domain models
  meal_service.py
  profile_service.py
  nutrition.py
  barcode.py   # Open Food Facts integration
  image.py     # Vision-based food recognition
  audio.py     # Whisper transcription
storage/       # SQLAlchemy ORM models and repositories
config/        # pydantic-settings config
tests/         # pytest + async + FakeLLMClient
```

---

## Development

```bash
# Run tests
uv run pytest

# Type check
uv run mypy --strict .

# Lint and format
uv run ruff check .
uv run ruff format .
```

All four must pass before committing (enforced by the `commit-review` workflow).

### Adding a new LLM provider

1. Implement `Provider` protocol in `llm/providers/your_provider.py`
2. Register it in `llm/providers/__init__.py`
3. Wire it in `bot/main.py` `_build_llm()`
4. Set `LLM_MODEL_<CLASS>=your-model-name` in `.env`

No other code changes required.

---

## Deploying to production

1. Set `ENV=prod` for JSON structured logs
2. Switch `DATABASE_URL` to a Postgres connection string:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:pass@host/diet
   ```
3. Run behind a process manager (systemd, Docker, etc.)
4. Set `BUDGET_PER_USER_DAILY_USD` and `BUDGET_GLOBAL_HOURLY_USD` to safe limits
5. Keep `.env` out of version control (it's in `.gitignore`)

---

## Known limitations

- **Conversation persistence**: the `/setup` onboarding flow state is in-memory. A bot restart during setup will lose progress. Full persistence requires configuring `python-telegram-bot`'s `Persistence` class.
- **Nutrition estimates**: LLM-estimated nutrition for unpackaged foods is approximate. Barcode lookups from Open Food Facts are exact.
- **Voice**: requires an OpenAI API key even though the rest of the bot can run on DeepSeek alone.
- **Prices in `llm/pricing.py`**: hard-coded and should be verified against current provider pricing before production use.
