<div align="center">

# LIAM — LinkedIn Intelligent Autonomous Manager

A Python agent that researches trending topics, writes LinkedIn posts in a configured personal voice, generates matching images and publishes to LinkedIn — with mandatory human approval via Telegram before every post.

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-15%2F15%20passing-brightgreen)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/SinhaRepo/LIAM/liam.yml?label=CI&logo=github)](../../actions)

Built by [Ansh Sinha](https://github.com/SinhaRepo) · Python Backend Developer

</div>

---

## Overview

LIAM runs as a stateless job on GitHub Actions twice daily. It wakes up, researches what is trending in tech, writes a post scored against a personal voice profile, sends a Telegram approval request with 5 action buttons, waits up to an hour for a decision, then posts to LinkedIn and exits. No server. No subscription. No manual work beyond tapping a button.

The interesting engineering problems in this project are the Telegram bot architecture, the ReAct agent loop and the voice scoring system — all described below.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [GitHub Actions Deployment](#github-actions-deployment)
- [Telegram Bot](#telegram-bot)
- [Voice Profile and Scoring](#voice-profile-and-scoring)
- [Safety Guardrails](#safety-guardrails)
- [Tests](#tests)
- [LinkedIn Token Renewal](#linkedin-token-renewal)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## How It Works

```
GitHub Actions (cron: 8:00 AM + 12:30 PM IST, Mon–Fri)
          |
          v
    liam.py  →  start_command_bot()  →  agent_loop()
          |
          v
    ┌─────────────────────────────────────────────────┐
    │               ReAct Loop                        │
    │                                                 │
    │  THINK   No topic given. Research needed.       │
    │    |                                            │
    │  ACT     RSS feeds + Google Search              │
    │          Filter by niche keywords               │
    │          Deduplicate against SQLite memory      │
    │    |                                            │
    │  ACT     Pick random angle + hook               │
    │          Generate post via Groq (Llama 3.3 70B) │
    │          Score 0–100 via voice scorer           │
    │          Retry if score < 70 (max 3 attempts)   │
    │    |                                            │
    │  ACT     Generate image prompt via Groq         │
    │          Generate image via Stability AI        │
    │          Fall back to HuggingFace if needed     │
    │    |                                            │
    │  ACT     Send Telegram approval message         │
    │          5 action buttons, 45-min reminder      │
    │    |                                            │
    │  OBSERVE Wait up to 1 hour for decision         │
    │    |                                            │
    │  ACT     Post to LinkedIn ugcPosts API          │
    │          Save result to SQLite                  │
    │          Exit                                   │
    └─────────────────────────────────────────────────┘
```

---

## Architecture

### Telegram Bot — Single Application, Shared State

The naive approach for this kind of agent creates two separate `Application` instances: one for command handling and one for approval callbacks. Both call `start_polling()` on the same bot token. Telegram rejects the second connection with a polling conflict error, silently crashing the approval flow on every real run.

The fix is a single shared `Application` instance initialized at startup in `bot.py` and stored as a module-level singleton. Command handlers are registered once at startup. Approval handlers are added and removed **dynamically per session** using handler groups (group 10 for inline button callbacks, group 11 for text message replies). Communication between the main thread and the bot's async event loop uses `threading.Event` and `asyncio.run_coroutine_threadsafe()`.

```
bot.py
┌──────────────────────────────────────────┐
│  _shared_app   (single Application)      │
│  _app_loop     (single event loop)       │
│  _app_ready    (threading.Event)         │
│                                          │
│  CommandHandler  /start    group=0       │
│  CommandHandler  /status   group=0       │
│  CommandHandler  /history  group=0       │
│  CommandHandler  /report   group=0       │
└──────────────────┬───────────────────────┘
                   │  get_shared_app()
                   │  get_app_loop()
                   v
approval.py
┌──────────────────────────────────────────┐
│  No new Application                      │
│  No new start_polling()                  │
│                                          │
│  Dynamic add/remove:                     │
│    CallbackQueryHandler   group=10       │
│    MessageHandler         group=11       │
│                                          │
│  threading.Event   cross-thread signal   │
│  run_coroutine_threadsafe   send msgs    │
└──────────────────────────────────────────┘
```

### ReAct Loop

The agent loop in `brain/react_loop.py` follows the ReAct pattern: Reasoning and Acting in alternating steps. At each stage the agent decides what action to take based on available context, executes it and observes the result before proceeding. This makes the control flow explicit and traceable rather than a monolithic pipeline.

### Voice Scoring

Every generated post is scored across four axes before being sent for approval. If the score is below 70, the post is discarded and regenerated — up to 3 attempts. The highest-scoring attempt is kept, not the last one.

Banned phrases are enforced at the Python level in addition to the LLM prompt. If the model generates a banned phrase despite the instruction, `voice_scorer.py` detects it in code and forces a retry before the scoring step.

---

## Tech Stack

| Layer | Tool | Notes |
|-------|------|-------|
| LLM | Groq API — Llama 3.3 70B | Post generation and image prompt generation |
| Image (primary) | Stability AI REST API | 25 free credits on signup |
| Image (fallback) | HuggingFace FLUX.1-schnell | Automatic failover |
| Hosting | GitHub Actions | Free on public repos |
| Mobile control | Telegram Bot API | Approval flow and commands |
| Publishing | LinkedIn Official API (ugcPosts) | No scraping |
| Memory | SQLite — Python stdlib | Post history, topic deduplication, voice scores |
| Research | feedparser + googlesearch-python | 4 RSS feeds + keyword-filtered Google Search |
| Terminal UI | Rich | Local runs only |

**Total infrastructure cost: $0**

---

## Project Structure

```
LIAM/
├── .github/
│   └── workflows/
│       └── liam.yml              # Cron schedule, secrets injection, memory.db persistence
├── brain/
│   ├── prompts.py                # System prompt, writing rules, structure templates
│   └── react_loop.py             # THINK → ACT → OBSERVE loop, image prompt generation
├── cli/
│   └── interface.py              # Rich terminal panel (local runs)
├── modules/
│   ├── image_gen.py              # Stability AI primary, HuggingFace fallback
│   ├── memory.py                 # SQLite CRUD — history, deduplication, drift detection
│   ├── poster.py                 # LinkedIn API, safety checks, 429 retry
│   ├── research.py               # RSS + Google Search, keyword filtering, deduplication
│   ├── scheduler.py              # APScheduler jobs for local/server deployment
│   ├── voice_scorer.py           # 4-axis scoring, hard banned phrase enforcement
│   └── writer.py                 # Groq API call, voice profile injection
├── telegram_bot/
│   ├── approval.py               # Dynamic handler groups, threading.Event, 5-button UI
│   ├── bot.py                    # Single Application singleton, startup message
│   ├── commands.py               # /start /status /history /report
│   └── notifications.py          # Async notification helpers
├── tests/                        # 15 tests, all passing
├── tools/
│   └── get_token.py              # LinkedIn OAuth2 flow, auto-saves token to .env
├── voice_profile/
│   ├── banned_phrases.txt        # Phrases enforced at code level, not just prompt level
│   ├── sample_posts.txt          # Reference posts — style only, not topic
│   └── style_guide.txt           # Tone, length, structure rules
├── .env.example
├── liam.py                       # Entry point — CLI args, bot startup, loop dispatch
└── requirements.txt
```

---

## Setup

### Accounts Required (All Free)

| Service | Purpose | Link |
|---------|---------|------|
| Groq | LLM — post and image prompt generation | [console.groq.com](https://console.groq.com/) |
| Telegram | Approval UI and bot commands | [@BotFather](https://t.me/BotFather) |
| LinkedIn Developer | Official posting API | [developer.linkedin.com](https://developer.linkedin.com/) |
| HuggingFace | Image generation fallback | [huggingface.co](https://huggingface.co/) |
| Stability AI | Primary image generation | [platform.stability.ai](https://platform.stability.ai/) |

### LinkedIn Developer App

1. Go to [developer.linkedin.com](https://developer.linkedin.com/) and create an app
2. Under Products, request access to **Share on LinkedIn** — this grants `w_member_social`
3. Copy **Client ID** and **Client Secret** from the Auth tab
4. Add `http://localhost:8000/callback` as a redirect URI

Approval typically takes 1–2 days.

### Installation

```bash
git clone https://github.com/SinhaRepo/LIAM.git
cd LIAM
pip install -r requirements.txt
cp .env.example .env
# Fill in all API keys in .env
```

### Environment Variables

```env
GROQ_API_KEY=
STABILITY_API_KEY=
HUGGINGFACE_TOKEN=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_ACCESS_TOKEN=
TIMEZONE=Asia/Kolkata
MAX_POSTS_PER_DAY=2
VOICE_SCORE_THRESHOLD=70
TOPIC_COOLDOWN_DAYS=7
```

To get your `TELEGRAM_CHAT_ID`: send any message to your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates`. Your ID is in the `id` field.

### LinkedIn Access Token

```bash
python tools/get_token.py
```

Opens a browser OAuth flow. Authorizes the app, exchanges the code for an access token and writes it directly to `.env`. Token expires every ~60 days.

### Voice Profile

This is the most important setup step. Three files in `voice_profile/` control how LIAM writes.

**`sample_posts.txt`** — Paste 3–5 of your real LinkedIn posts. LIAM reads these as style references — sentence length, tone and structure. It does not copy topics.

```
---
POST 1:
[your actual LinkedIn post]

---
POST 2:
[another real post]
```

**`style_guide.txt`** — Your personal writing rules in plain text.

**`banned_phrases.txt`** — One phrase per line. These are checked in Python code after generation — not just in the LLM prompt — so they are always enforced.

### Run Locally

```bash
# Auto-research and full approval flow
python liam.py

# Specific topic
python liam.py "building AI agents with Python"

# Continuous scheduler mode
python liam.py --schedule

# Post history
python liam.py --history
```

---

## GitHub Actions Deployment

### Step 1 — Push to GitHub

```bash
git add .
git status       # confirm .env is not listed
git commit -m "init"
git push origin main
```

### Step 2 — Add Repository Secrets

Navigate to **Settings → Secrets and variables → Actions → New repository secret** and add all 8 keys from the environment variables section above.

### Step 3 — Enable Workflows

Go to the **Actions** tab and click **"I understand my workflows, go ahead and enable them"**.

### Step 4 — First Test Run

Go to **Actions → LIAM — LinkedIn Autonomous Agent → Run workflow**, enter an optional topic and click Run.

Within 5 minutes you should receive a Telegram message with the generated post and 5 approval buttons.

### Automatic Schedule

| Time (IST) | Days |
|------------|------|
| 8:00 AM | Monday to Friday |
| 12:30 PM | Monday to Friday |

The GitHub Actions job persists `memory.db` back to the repository after every run so topic deduplication and voice drift tracking carry over across runs.

---

## Telegram Bot

### Approval Buttons

| Button | Behavior |
|--------|----------|
| Approve | Posts to LinkedIn after a random 60–480 second delay |
| Edit Post | Bot prompts for your version — posts your exact text (10 min window) |
| Regenerate | Rewrites the post on the same topic (max 3 attempts) |
| New Topic | Runs full research cycle and returns a different trending topic |
| Skip Today | Exits cleanly, no post |

No response within 1 hour triggers an automatic skip. A reminder is sent at the 45-minute mark if the post is still waiting.

### Commands

| Command | Output |
|---------|--------|
| `/start` | Available commands |
| `/status` | Last post time, posts today, pending drafts |
| `/history` | Last 5 published posts with dates and voice scores |
| `/report` | Voice drift status |

---

## Voice Profile and Scoring

Every post is scored from 0 to 100 before being sent for approval. Posts below 70 are regenerated.

| Component | Max | Criteria |
|-----------|-----|----------|
| Buzzword penalty | 30 | Deducts 10 per banned phrase found |
| Length | 15 | 15 pts for 150–250 words, 10 pts for 100–300 |
| Structure | 15 | Hook present, hashtags included, 3+ paragraphs |
| Authenticity | 40 | First-person voice, sentence variety |

The banned phrase check runs in Python after generation. If the LLM included a flagged phrase despite the prompt instruction, the post is discarded and the attempt counter increments. The highest-scoring attempt across all retries is returned — not the last one.

When the rolling average of the last 10 voice scores drops below 65, LIAM sends an automatic warning to Telegram.

---

## Safety Guardrails

Six checks run before every post. Any failure raises a `SafetyError` — the run exits without posting and sends a Telegram notification.

| Rule | Value | Enforced in |
|------|-------|-------------|
| Human approval required | Always | `approval.py` |
| Minimum gap between posts | 4 hours (uses publish time, not draft time) | `poster.py` |
| Daily post limit | 2 (configurable) | `poster.py` |
| Weekdays only | Monday–Friday | `poster.py` |
| Human-like delay | 60–480 seconds random | `poster.py` |
| Approval timeout | 1 hour | `approval.py` |

---

## Tests

```bash
python -m pytest tests/ -v
```

```
tests/test_guardrails.py     PASSED
tests/test_image_gen.py      PASSED
tests/test_memory.py         PASSED
tests/test_poster.py         PASSED
tests/test_react_loop.py     PASSED
tests/test_research.py       PASSED
tests/test_telegram.py       PASSED
tests/test_voice_scorer.py   PASSED
tests/test_writer.py         PASSED

15 passed
```

`test_react_loop.py` covers all 7 decision branches of the approval flow (approve, regenerate, edit, new_topic, skip, timeout, error) using mocks — no live API calls required.

---

## LinkedIn Token Renewal

LinkedIn access tokens expire every ~60 days. LIAM sends a Telegram reminder 5 days before expiry.

When you receive the reminder:

```bash
python tools/get_token.py
# Complete the browser OAuth flow
# Copy the new token printed to terminal
```

Then update `LINKEDIN_ACCESS_TOKEN` in your GitHub repository secrets.

---

## Known Limitations

| Limitation | Notes |
|-----------|-------|
| LinkedIn token expires every ~60 days | LIAM sends a 5-day advance reminder |
| Stability AI: 25 free credits | Falls back automatically to HuggingFace (free, no credit limit) |
| GitHub Actions is stateless | `memory.db` is committed back to the repo after each run to maintain state |
| `/pause` command not functional on Actions | Disable the workflow from the Actions tab instead |
| RSS feeds update every 1–6 hours | Not real-time, sufficient for twice-daily posting |

---

## Roadmap

- [ ] LinkedIn post analytics — impressions, likes and comments pulled back via API
- [ ] Persistent memory via GitHub Gist instead of committed SQLite file
- [ ] Multi-niche topic routing
- [ ] Web dashboard for post history and score trends

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built by [Ansh Sinha](https://github.com/SinhaRepo) · [LinkedIn](https://linkedin.com/in/sinhaansh)

</div>
