# Ache-o-Meter Project Context

## Project Overview

**Ache-o-Meter** is a Telegram bot designed specifically for weather-sensitive people. It daily analyzes weather conditions, geomagnetic activity, solar activity, air quality, and other environmental factors to warn users about potential health discomfort (headaches, joint pain, respiratory issues, etc.).

### Core Functionality

- **Daily personalized forecasts** delivered at a user-specified time based on their location
- **On-demand analysis** via `/forecast_now` command
- **Flexible settings** — users can change city, notification time, sensitivity factors, and allergens via `/settings`
- **Risk analysis** based on 13+ factors:
  - Atmospheric pressure changes (>3-7 mmHg/24h) and rate of change (mmHg/hour)
  - Temperature fluctuations (>5-10°C day-over-day) and rate of change (°C/hour)
  - Humidity extremes (>85% or <30%)
  - Geomagnetic activity (Kp-index >= 3 or >= 5)
  - Solar wind activity
  - Air quality (PM2.5, PM10, NO₂, O₃)
  - UV index (>= 3 moderate, >= 5 high, >= 8 very high)
  - Pollen concentration (alder, birch, grass, mugwort, olive, ragweed)
  - Apparent vs real temperature difference (>5°C or >8°C)
  - Dew point extremes (>16°C or >20°C, <-15°C)
  - Visibility (<5km, <1km, <200m — fog/smoke)
  - Convective energy / storm activity (CAPE >500, >1000, >2500 J/kg)
  - Freezing level height changes (>500m or >800m/24h)

### Data Sources

| Source | Data |
|--------|------|
| [Open-Meteo Weather API](https://open-meteo.com/) | Temperature, apparent temperature, pressure, humidity, dew point, visibility, cloud cover, CAPE, freezing level height |
| [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) | PM2.5, PM10, NO₂, O₃, UV index, pollen (6 types) |
| [NOAA SWPC](https://www.swpc.noaa.gov/) | Kp-index forecast, solar wind data |
| [Nominatim (OpenStreetMap)](https://nominatim.openstreetmap.org/) | City geocoding (coordinates, display name) — free, no API key |
| [TimezoneFinder](https://pypi.org/project/timezonefinder/) | Timezone detection from coordinates |

## Architecture

```
Ache-o-Meter/
├── bot.py           # Main entry point: Telegram bot handlers, scheduler, geocoding
├── database.py      # PostgreSQL layer (asyncpg) — users, settings, sensitivities, allergens
├── forecast.py      # Weather data collection, air quality, and risk analysis logic
├── Dockerfile       # Container definition (python:3.10-slim)
├── docker-compose.yml  # Service orchestration
├── requirements.txt # Python dependencies
├── .env.example     # Environment variables template
├── Procfile         # Railway/Heroku process file
├── railway.toml     # Railway deployment config
└── data/            # (legacy) SQLite database directory — no longer used
```

### Key Components

- **`bot.py`** — Aiogram 3.x dispatcher, FSM states (`UserState`) for user interaction, APScheduler for hourly checks, inline keyboard handlers for settings (location, sensitivity, allergens), text/callback handlers
- **`database.py`** — PostgreSQL async wrapper (asyncpg) with connection pool. Functions: `init_pool()`, `add_or_update_user()`, `set_user_active()`, `update_user_notification_time()`, `update_user_sensitivity()`, `update_user_allergen()`, `get_all_active_users()`, `get_user_by_id()`. Auto-migration for new columns.
- **`forecast.py`** — Data collection (`get_forecast_data()`, `get_open_meteo_data()`, `get_air_quality_data()`, `get_noaa_geo_data()`, `get_solar_activity_data()`) and analysis (`analyze_data_and_form_message()`) with 13 risk factors and user profile support.

## Tech Stack

- **Python 3.10+**
- **Aiogram 3.x** — async Telegram Bot API framework
- **APScheduler** — scheduled job execution
- **AIOHTTP** — async HTTP requests
- **PostgreSQL (asyncpg)** — user data storage with connection pooling
- **TimezoneFinder** — timezone detection from coordinates
- **Docker & Docker Compose** — deployment
- **Railway** — cloud hosting option

## Building and Running

### Prerequisites

- Docker and Docker Compose installed
- Telegram bot token (from @BotFather)
- PostgreSQL database (local or cloud)
- No API keys needed for weather/geocoding (all free APIs)

### Setup

1. **Clone and configure:**
   ```bash
   cp .env.example .env
   # Edit .env with BOT_TOKEN and DATABASE_URL
   ```

2. **Build and run:**
   ```bash
   docker compose up --build -d
   ```

3. **Data persistence:** PostgreSQL handles persistence. Railway auto-provisions a managed PostgreSQL instance.

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and start using the bot |
| `/settings` | Change city, time, sensitivity factors, allergens |
| `/forecast_now` | Get forecast immediately |
| `/stop` | Pause daily notifications |
| `/info` | Learn about all 13+ analysis factors |
| `/help` | Show command reference |

## Development Notes

### Coding Style

- Russian language for user-facing messages
- English for code identifiers, comments, and logging
- Async/await pattern throughout for all I/O operations
- PostgreSQL used with asyncpg and parameterized queries (no ORM)

### User Flow

1. User sends `/start` → bot asks for city name
2. User sends city → bot geocodes via Nominatim, detects timezone via TimezoneFinder, shows confirmation
3. User confirms → bot saves to DB and activates subscription
4. APScheduler checks every hour if any user's local time matches their `notification_time`
5. Match found → bot fetches weather + air quality + NOAA data, analyzes 13 risk factors, sends message

### Settings Menu

The `/settings` command opens an inline keyboard with three sections:
- **🌍 Город и время** — change city or notification time
- **⚡ Чувствительность** — toggle 11 sensitivity factors (on/off)
- **🌿 Аллергены** — toggle 6 pollen allergens (on/off)

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    city TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    timezone TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    notification_time TEXT DEFAULT '08:00',
    sensitivity_pressure BOOLEAN DEFAULT TRUE,
    sensitivity_temperature BOOLEAN DEFAULT TRUE,
    sensitivity_humidity BOOLEAN DEFAULT TRUE,
    sensitivity_geomagnetic BOOLEAN DEFAULT TRUE,
    sensitivity_air_quality BOOLEAN DEFAULT TRUE,
    sensitivity_uv BOOLEAN DEFAULT TRUE,
    sensitivity_apparent_temperature BOOLEAN DEFAULT TRUE,
    sensitivity_dew_point BOOLEAN DEFAULT TRUE,
    sensitivity_visibility BOOLEAN DEFAULT TRUE,
    sensitivity_storm BOOLEAN DEFAULT TRUE,
    sensitivity_freezing_level BOOLEAN DEFAULT TRUE,
    allergen_alder BOOLEAN DEFAULT FALSE,
    allergen_birch BOOLEAN DEFAULT FALSE,
    allergen_grass BOOLEAN DEFAULT FALSE,
    allergen_mugwort BOOLEAN DEFAULT FALSE,
    allergen_olive BOOLEAN DEFAULT FALSE,
    allergen_ragweed BOOLEAN DEFAULT FALSE
)
```

### Risk Levels

| Level | Icon | Trigger Examples |
|-------|------|-----------------|
| Высокий (High) | 🔴 | Pressure change >7mmHg/24h, PM2.5 >35, UV >=8, CAPE >2500, apparent temp diff >8°C |
| Средний (Medium) | 🟡 | Pressure change >3mmHg/24h, temp change >5°C, Kp >=3, PM2.5 >15, UV >=5, CAPE >1000 |
| Низкий (Low) | 🟢 | Humidity >85% or <30%, UV >=3, PM10 >50, dew point >16°C, visibility <5km |

### Planned Features (Roadmap)

- Ap-index integration (geomagnetic analysis)
- Solar flare and coronal mass ejection data
- Adaptive risk thresholds per user based on feedback
- User feedback history (accuracy polling — opt-in)
- Lightning Potential Index (LPI) analysis
- Cloud cover impact on mood and barometric perception
- Historical weather data comparison (anomaly detection)
