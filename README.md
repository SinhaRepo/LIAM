<div align="center">

# 🤖 LIAM — LinkedIn Intelligent Autonomous Manager

**A fully autonomous Python AI agent that researches trending topics, writes LinkedIn posts in your authentic voice, gets your approval via Telegram, and publishes automatically — zero cost, no server, runs free on GitHub Actions forever.**

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-15%2F15%20passing-brightgreen)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Actions](https://img.shields.io/github/actions/workflow/status/SinhaRepo/linkedin-agent/liam.yml?label=LIAM%20Agent&logo=github)](../../actions)

**Built by [Ansh Sinha](https://github.com/SinhaRepo)** · Python Backend Developer · AI / Cloud / Python niche

</div>

---

## Table of Contents

- [How It Works](#how-it-works)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [GitHub Actions Deployment](#github-actions-deployment)
- [Telegram Bot](#telegram-bot)
- [Safety Guardrails](#safety-guardrails)
- [Voice Profile & Scoring](#voice-profile--scoring)
- [Tests](#tests)
- [LinkedIn Token Renewal](#linkedin-token-renewal)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## How It Works

LIAM runs as a **single stateless job** on GitHub Actions. It wakes up on schedule, does its job, sends you an approval message on Telegram, waits for your tap, posts to LinkedIn, then shuts down. Your laptop doesn't need to be on. There's no server to manage.

```
GitHub Actions (Cron: 8:00 AM + 12:30 PM IST, Mon–Fri)
              │
              ▼
         ┌─────────────────────────────────────────────────────┐
         │                  liam.py (entry point)              │
         │  start_command_bot() → agent_loop(topic=None)       │
         └───────────────────┬─────────────────────────────────┘
                             │
         ┌───────────────────▼─────────────────────────────────┐
         │               ReAct Loop  (brain/react_loop.py)     │
         │                                                     │
         │  THINK  ──►  No topic given. Research needed.       │
         │                         │                           │
         │  ACT    ──►  Fetch RSS feeds + Google Search        │
         │              Filter by niche keywords               │
         │              Deduplicate against memory             │
         │                         │                           │
         │  ACT    ──►  Pick random angle + hook               │
         │              Generate post via Groq (Llama 3.3 70B) │
         │              Score post 0–100 (voice scorer)        │
         │              Retry if score < 70 (max 3 attempts)   │
         │                         │                           │
         │  ACT    ──►  Generate supplementary image           │
         │              (Stability AI → HuggingFace fallback)  │
         │                         │                           │
         │  ACT    ──►  Send Telegram approval message         │
         │              (post text + image + score + 5 buttons)│
         │                         │                           │
         │  OBSERVE ──► Wait for your decision (up to 1 hour)  │
         │                         │                           │
         │  ACT    ──►  Post to LinkedIn API                   │
         │              Save to SQLite memory                   │
         │              Exit cleanly                           │
         └─────────────────────────────────────────────────────┘
```

### Telegram Bot Architecture

LIAM uses a **single shared Application instance** — the biggest architectural challenge in the build.

The naive approach creates two Application instances (one for commands, one for approvals) both calling `start_polling()` on the same bot token. Telegram rejects the second connection with a polling conflict error — the entire approval flow crashes silently on every real run.

The fix: one `Application` is created at startup and stored as a shared singleton. Approval handlers are added and removed **dynamically per session** using handler groups (group 10 for callbacks, group 11 for text replies). The command bot and approval system communicate across threads using `threading.Event` and `asyncio.run_coroutine_threadsafe()`.

```
┌─────────────────────────────────────────────────────────┐
│              Telegram Bot Architecture                  │
│                                                         │
│  bot.py                                                 │
│  ┌──────────────────────────────────────┐               │
│  │  _shared_app  (single Application)  │               │
│  │  _app_loop    (single event loop)   │               │
│  │  _app_ready   (threading.Event)     │               │
│  │                                     │               │
│  │  CommandHandler: /start             │               │
│  │  CommandHandler: /status            │               │
│  │  CommandHandler: /history           │               │
│  │  CommandHandler: /report            │               │
│  └──────────────┬───────────────────────┘               │
│                 │  get_shared_app()                     │
│                 │  get_app_loop()                       │
│                 ▼                                       │
│  approval.py                                            │
│  ┌──────────────────────────────────────┐               │
│  │  NO new Application                 │               │
│  │  NO new start_polling()             │               │
│  │                                     │               │
│  │  Dynamic add → CallbackQueryHandler │  group=10     │
│  │  Dynamic add → MessageHandler       │  group=11     │
│  │  threading.Event → cross-thread     │               │
│  │  run_coroutine_threadsafe → sends   │               │
│  │  Dynamic remove → cleanup on exit  │               │
│  └──────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

---

## Features

- 📰 **Trending topic research** via RSS feeds (TechCrunch, Hacker News, Dev.to, Google AI Blog) + Google Search — filtered by niche keywords
- ✍️ **Post generation** via Groq API (Llama 3.3 70B) in your personal voice with randomized angles and hooks
- 🎨 **Image generation** — Stability AI primary, HuggingFace FLUX.1-schnell free fallback
- 📊 **Voice scoring system** (0–100) — auto-retries if score < 70, maximum 3 attempts before Telegram alert
- 📱 **Human approval via Telegram** — 5-button approval UI before every single post
- 🛡️ **Safety guardrails** — 4hr minimum gap, 2 posts/day cap, weekdays only, human-like random delay
- 🧠 **SQLite memory** — post history, topic deduplication, voice drift detection
- ⚠️ **Proactive alerts** — low score notification, voice drift warning, LinkedIn token expiry reminder
- ☁️ **Zero-cost deployment** — runs entirely on GitHub Actions free tier, no server needed
- 🔄 **Full Telegram control** — 5 approval buttons + 4 commands, real-time status

---

## Tech Stack

| Layer | Tool | Cost |
|-------|------|------|
| LLM | Groq API — Llama 3.3 70B | Free tier |
| Image (primary) | Stability AI REST API | 25 free credits |
| Image (fallback) | HuggingFace FLUX.1-schnell | Free |
| Hosting | GitHub Actions | Free forever (public repo) |
| Mobile control | Telegram Bot API | Free |
| Publishing | LinkedIn Official API | Free |
| Memory | SQLite (via Python stdlib) | Free |
| Scheduler | GitHub Actions Cron | Free |
| Terminal UI | Rich (Python) | Free |

**Total infrastructure cost: ₹0**

---

## Project Structure

```
linkedin-agent/
├── .github/
│   └── workflows/
│       └── liam.yml              # GitHub Actions — 2x/day IST, weekdays
├── brain/
│   ├── prompts.py                # LLM system prompt + context builder
│   └── react_loop.py             # THINK → ACT → OBSERVE agent loop
├── cli/
│   └── interface.py              # Rich terminal UI (local runs)
├── modules/
│   ├── image_gen.py              # Stability AI + HuggingFace fallback
│   ├── memory.py                 # SQLite CRUD — history, dedup, drift
│   ├── poster.py                 # LinkedIn API + all safety checks
│   ├── research.py               # RSS feeds + Google Search + dedup
│   ├── scheduler.py              # APScheduler jobs (server/local mode)
│   ├── voice_scorer.py           # Post scoring engine (0–100)
│   └── writer.py                 # Groq API post generation
├── telegram_bot/
│   ├── approval.py               # Shared app, dynamic handlers, 5 buttons
│   ├── bot.py                    # Single Application instance + commands
│   ├── commands.py               # /start /status /history /report
│   └── notifications.py          # Async notification helpers
├── tests/                        # 15 tests — all passing
│   ├── test_guardrails.py
│   ├── test_image_gen.py
│   ├── test_memory.py
│   ├── test_poster.py
│   ├── test_react_loop.py
│   ├── test_research.py
│   ├── test_telegram.py
│   ├── test_voice_scorer.py
│   └── test_writer.py
├── tools/
│   └── get_token.py              # LinkedIn OAuth helper (run locally)
├── voice_profile/
│   ├── banned_phrases.txt        # Words LIAM never uses
│   ├── sample_posts.txt          # Your real posts — style reference only
│   └── style_guide.txt           # Your tone rules
├── .env.example                  # Environment template
├── liam.py                       # Entry point
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Prerequisites

### Accounts Needed (All Free)

| # | Service | Purpose | Sign Up |
|---|---------|---------|---------|
| 1 | **Groq** | LLM (Llama 3.3 70B) for post generation | [console.groq.com](https://console.groq.com/) |
| 2 | **Telegram** | Bot for approval + commands | [@BotFather](https://t.me/BotFather) on Telegram |
| 3 | **LinkedIn Developer** | Official API for publishing | [developer.linkedin.com](https://developer.linkedin.com/) |
| 4 | **HuggingFace** | FLUX image generation fallback | [huggingface.co](https://huggingface.co/) |
| 5 | **Stability AI** | Primary image generation (25 free credits) | [platform.stability.ai](https://platform.stability.ai/) |

> **Tip:** Open all 5 links in browser tabs right now, create accounts, and collect your API keys before continuing. Takes about 20 minutes total.

### LinkedIn Developer App Setup

This is the most involved step. Follow carefully:

1. Go to [LinkedIn Developer Portal](https://developer.linkedin.com/) → **Create App**
2. Fill in app name and associate it with your LinkedIn profile
3. Under **Products**, request access to **Share on LinkedIn** (gives `w_member_social` permission)
4. Copy your **Client ID** and **Client Secret** from the Auth tab
5. Add `http://localhost:8000/callback` as a redirect URI

---

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/SinhaRepo/linkedin-agent.git
cd linkedin-agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Open .env and fill in all your API keys
```

```env
GROQ_API_KEY=your_groq_key_here
STABILITY_API_KEY=your_stability_key_here
HUGGINGFACE_TOKEN=your_hf_token_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
LINKEDIN_CLIENT_ID=your_client_id_here
LINKEDIN_CLIENT_SECRET=your_client_secret_here
LINKEDIN_ACCESS_TOKEN=your_access_token_here
TIMEZONE=Asia/Kolkata
MAX_POSTS_PER_DAY=2
VOICE_SCORE_THRESHOLD=70
TOPIC_COOLDOWN_DAYS=7
```

> **How to get your Telegram Chat ID:** Message your bot once, then open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser. Your chat ID is in the `id` field.

### 3. Get LinkedIn Access Token

```bash
python tools/get_token.py
```

This opens a browser OAuth flow. After authorizing, it prints your access token. Copy it into `.env`.

### 4. Fill Your Voice Profile

This is the most important setup step. Three files control how LIAM writes:

**`voice_profile/sample_posts.txt`** — Paste 3–5 of your real LinkedIn posts here. LIAM reads these to learn your sentence length, tone, structure and vocabulary. It copies your style, not your topics.

```
---
POST 1:
[paste your actual LinkedIn post here]

---
POST 2:
[paste another real post here]
```

**`voice_profile/style_guide.txt`** — Write your personal rules:

```
- Write in first person always
- Short sentences, maximum 15 words each
- No corporate buzzwords
- One personal story or technical lesson per post
- End with a question to drive comments
- Python, AI, and Backend topics only
```

**`voice_profile/banned_phrases.txt`** — One phrase per line:

```
excited to announce
game changer
in today's fast-paced world
leverage
thought leader
```

### 5. Run Locally (Optional Test)

```bash
# Auto-researches a topic and runs the full approval flow
python liam.py

# Run with a specific topic
python liam.py "building AI agents with Python"

# Continuous scheduler mode (for server/VPS deployment)
python liam.py --schedule

# View post history
python liam.py --history
```

---

## GitHub Actions Deployment

LIAM is designed to run on GitHub Actions — free, no server, no laptop required.

### Step 1 — Push to GitHub

```bash
git add .
git status          # verify .env does NOT appear in this list
git commit -m "LIAM v1.0"
git push origin main
```

### Step 2 — Add Secrets

```
Your repo → Settings → Secrets and variables → Actions → New repository secret
```

Add all 8 secrets:

```
GROQ_API_KEY
STABILITY_API_KEY
HUGGINGFACE_TOKEN
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
LINKEDIN_CLIENT_ID
LINKEDIN_CLIENT_SECRET
LINKEDIN_ACCESS_TOKEN
```

### Step 3 — Enable Workflows

```
Your repo → Actions tab → "I understand, enable them"
```

### Step 4 — First Manual Test

```
Actions tab → LIAM — LinkedIn Autonomous Agent → Run workflow
→ Enter topic: "I just open sourced my LinkedIn AI agent"
→ Click: Run workflow
```

**What you should see:**

| Where | What Happens |
|-------|-------------|
| GitHub Actions log | Setup → Install → LIAM starts running |
| Telegram (within 2 min) | `🤖 LIAM is online and ready!` |
| Telegram (within 5 min) | Approval message with post text + 5 buttons |
| After you tap ✅ | Post appears live on your LinkedIn |

### Automatic Schedule (after setup)

| Time | Days |
|------|------|
| ⏰ 8:00 AM IST | Monday to Friday |
| ⏰ 12:30 PM IST | Monday to Friday |

---

## Telegram Bot

### Approval Buttons

Every generated post arrives on your phone with 5 buttons:

| Button | What It Does |
|--------|-------------|
| ✅ Approve | Posts immediately to LinkedIn |
| ✏️ Edit Post | Bot asks you to type your version — posts that exact text |
| 🔄 Regenerate | Generates a new post on the same topic (max 3 attempts) |
| 🎯 New Topic | Researches a completely fresh trending topic |
| ❌ Skip Today | Skips this post, LIAM exits cleanly |

> If you ignore the approval message, LIAM auto-skips after 1 hour and sends a notification. The GitHub Actions job exits cleanly within the 90-minute timeout window.

### Commands

| Command | What It Returns |
|---------|----------------|
| `/start` | Welcome message and full command list |
| `/status` | Last post time, posts today, pending drafts |
| `/history` | Last 5 published posts with dates and voice scores |
| `/report` | Voice drift status and weekly performance summary |

---

## Safety Guardrails

LIAM has 6 layers of protection against accidental or spam posting. Every guardrail is enforced in code — not just configuration.

| Guardrail | Rule | Where Enforced |
|-----------|------|---------------|
| Human approval | Required before every single post | `approval.py` |
| Minimum gap | 4 hours between any two posts | `poster.py` |
| Daily limit | Max 2 posts per day (configurable) | `poster.py` |
| Weekdays only | No posting on Saturday or Sunday | `poster.py` |
| Human-like delay | Random 60–480 second wait before API call | `poster.py` |
| Approval timeout | Auto-skips after 1 hour of no response | `approval.py` |

Violating any guardrail raises a `SafetyError` — the run exits cleanly without posting and sends a Telegram notification.

---

## Voice Profile & Scoring

LIAM scores every generated post from 0–100 before sending it for approval. A post must score ≥ 70 to proceed.

| Component | Max Score | What It Checks |
|-----------|-----------|---------------|
| Buzzword penalty | 30 pts | Deducts for phrases in `banned_phrases.txt` |
| Length | 15 pts | Optimal range: 150–250 words |
| Structure | 15 pts | Hook present, hashtags included, paragraph count |
| Authenticity | 40 pts | First person voice, sentence variety, personal tone |

**Scoring flow:**

```
Generate post → Score it
    │
    ├── Score ≥ 70 → Send for Telegram approval
    │
    └── Score < 70 → Regenerate (attempt 2)
            │
            ├── Score ≥ 70 → Send for Telegram approval
            │
            └── Score < 70 → Regenerate (attempt 3)
                    │
                    ├── Score ≥ 70 → Send for Telegram approval
                    │
                    └── All 3 failed → Telegram alert sent
                                       "Score Too Low — consider updating
                                        sample_posts.txt"
```

**Post quality improves over time.** Add your most recent real LinkedIn posts to `sample_posts.txt` every 2–3 months as your writing style evolves. When the average score over last 10 posts drops below 65, LIAM sends an automatic voice drift warning to Telegram.

---

## Tests

```bash
python -m pytest tests/ -v
```

```
tests/test_guardrails.py    ✅ passed
tests/test_image_gen.py     ✅ passed
tests/test_memory.py        ✅ passed
tests/test_poster.py        ✅ passed
tests/test_react_loop.py    ✅ passed
tests/test_research.py      ✅ passed
tests/test_telegram.py      ✅ passed
tests/test_voice_scorer.py  ✅ passed
tests/test_writer.py        ✅ passed

15 passed in X.XXs
```

---

## LinkedIn Token Renewal

LinkedIn access tokens expire every **~60 days**. LIAM tracks this and sends a Telegram reminder 5 days before expiry.

When you receive the reminder:

```bash
# Run this on your local machine
python tools/get_token.py

# Follow the OAuth flow in your browser
# Copy the new token that gets printed

# Update it in GitHub Secrets:
# Settings → Secrets → LINKEDIN_ACCESS_TOKEN → Update
```

---

## Known Limitations

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| LinkedIn token expires every ~60 days | Manual renewal needed | LIAM sends 5-day advance warning |
| Stability AI: 25 free credits total | Image generation stops after credits | Auto-falls back to HuggingFace FLUX (free, unlimited) |
| RSS feeds update every 1–6 hours | Not truly real-time | Sufficient for twice-daily posting |
| GitHub Actions is stateless | Memory resets each run | Topic variety handled naturally by RSS; quality controlled by Telegram approval |
| `/pause` command not available on GitHub Actions | Can't pause scheduled runs mid-deployment | Disable the workflow in the Actions tab instead |

---

## Roadmap

- [ ] Persistent memory via GitHub Gist (solves stateless limitation)
- [ ] LinkedIn post analytics — impressions, likes, comments tracking
- [ ] Multi-niche support with topic routing
- [ ] Web dashboard for post history and score trends
- [ ] Auto-fetch content from saved LinkedIn article URLs

---

## Author

<div align="center">

**Built by [Ansh Sinha](https://github.com/SinhaRepo)**

Python Backend Developer — building in public in the Python / AI / Cloud niche.

[GitHub](https://github.com/SinhaRepo) · [LinkedIn](https://linkedin.com/in/sinhaansh)

</div>

---

## License

MIT License — see [LICENSE](LICENSE) for details.
Free to fork, adapt, and build your own version.

---