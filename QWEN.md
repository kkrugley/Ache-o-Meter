# Ache-o-Meter Project Context

## Project Overview

**Ache-o-Meter** is a Telegram bot designed specifically for weather-sensitive people. It daily analyzes weather conditions, geomagnetic activity, and solar activity to warn users about potential health discomfort (headaches, joint pain, etc.).

### Core Functionality

- **Daily personalized forecasts** delivered at a user-specified time based on their location
- **On-demand analysis** via `/forecast_now` command
- **Flexible settings** — users can change city and notification time via `/settings`
- **Risk analysis** based on multiple factors:
  - Atmospheric pressure changes (>3-7 mmHg/24h)
  - Temperature fluctuations (>5-10°C day-over-day)
  - Humidity extremes (>85% or <30%)
  - Geomagnetic activity (Kp-index >= 3 or >= 5)
  - Solar wind activity

### Data Sources

| Source | Data |
|--------|------|
| [Open-Meteo](https://open-meteo.com/) | Temperature, pressure, humidity |
| [NOAA SWPC](https://www.swpc.noaa.gov/) | Kp-index forecast, solar wind data |
| Yandex Geocoder | City coordinates and timezone |

## Architecture

```
Ache-o-Meter/
├── bot.py           # Main entry point: Telegram bot handlers, scheduler, geocoding
├── database.py      # SQLite database layer (users, settings, subscriptions)
├── forecast.py      # Weather data collection and risk analysis logic
├── Dockerfile       # Container definition (python:3.10-slim)
├── docker-compose.yml  # Service orchestration with volume persistence
├── requirements.txt # Python dependencies
├── .env.example     # Environment variables template
└── data/            # SQLite database directory (created at runtime)
```

### Key Components

- **`bot.py`** — Aiogram 3.x dispatcher, FSM states for user interaction, APScheduler for hourly checks, text/callback handlers
- **`database.py`** — SQLite wrapper with functions: `init_db()`, `add_or_update_user()`, `set_user_active()`, `update_user_notification_time()`, `get_all_active_users()`, `get_user_by_id()`
- **`forecast.py`** — Data collection (`get_forecast_data()`, `get_open_meteo_data()`, `get_noaa_geo_data()`, `get_solar_activity_data()`) and analysis (`analyze_data_and_form_message()`)

## Tech Stack

- **Python 3.10+**
- **Aiogram 3.x** — async Telegram Bot API framework
- **APScheduler** — scheduled job execution
- **AIOHTTP** — async HTTP requests
- **SQLite** — lightweight user data storage
- **Docker & Docker Compose** — deployment

## Building and Running

### Prerequisites

- Docker and Docker Compose installed
- Telegram bot token (from @BotFather)
- Yandex Geocoder API key

### Setup

1. **Clone and configure:**
   ```bash
   cp .env.example .env
   # Edit .env with BOT_TOKEN and YANDEX_API_KEY
   ```

2. **Build and run:**
   ```bash
   docker compose up --build -d
   ```

3. **Data persistence:** SQLite database is stored in `./data/users.db` (mounted as volume in Docker Compose).

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and start using the bot |
| `/settings` | Change city or notification time |
| `/forecast_now` | Get forecast immediately |
| `/stop` | Pause daily notifications |
| `/info` | Learn about analysis factors |
| `/help` | Show command reference |

## Development Notes

### Coding Style

- Russian language for user-facing messages
- English for code identifiers, comments, and logging
- Async/await pattern throughout for all I/O operations
- SQLite used with parameterized queries (no ORM)

### User Flow

1. User sends `/start` → bot asks for city name
2. User sends city → bot geocodes via Yandex, shows confirmation
3. User confirms → bot saves to DB and activates subscription
4. APScheduler checks every hour if any user's local time matches their `notification_time`
5. Match found → bot fetches forecast data, analyzes risks, sends message

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    city TEXT,
    lat REAL,
    lon REAL,
    timezone TEXT,
    is_active INTEGER DEFAULT 1,
    notification_time TEXT DEFAULT '08:00'
)
```

### Planned Features (Roadmap)

- Pressure/temperature change rate calculation (mmHg/hour, °C/hour)
- Time-of-day risk identification
- Ap-index integration
- Solar flare and coronal mass ejection data
- User profiles (age, conditions, sensitivity)
- Allergen-aware analysis
- Adaptive risk thresholds per user
- User feedback history (accuracy polling)
