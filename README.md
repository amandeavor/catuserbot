# ◈ AETHERIS USERBOT v4.0 ◈

> The most refined, high-performance, and aesthetic Telegram userbot engine. Built on Telethon with intelligent asynchronous task management, live dynamic hot-reloading, CLI flag parsing, and multi-tier AI routing.

---

## ⚡ Key Highlights & Core Upgrades

- **◈ Aesthetic UI & Telemetry**: Redesigned `.alive`, `.ping`, `.sysinfo`, `.aetheris`, and interactive inline control deck with minimal high-contrast unicode styling.
- **🚀 Dynamic Hot-Reloading (Hikka-Inspired)**: Live reload individual plugins (`.reload <plugin>`) or all active modules (`.reload`) without restarting the bot container or dropping Telegram connections.
- **📊 Async Background Task Manager (Userge-Inspired)**: Run long jobs in the background, inspect active executions with `.tasks`, and cancel hung jobs gracefully with `.taskkill <id>`.
- **🎛️ CLI Argument & Flag Parser**: Seamlessly pass flags to commands (e.g. `.quickpurge --limit 50`) alongside standard intuitive single-word commands.
- **🛡️ FloodWait Auto-Backoff Shield**: Automatic rate-limit interceptor that sleeps and resumes smoothly on Telegram 420 flood errors rather than crashing operations.
- **⚡ Parallel File Transfer Engine**: Fast chunk streaming powered by FastTelethon for maximum upload and download throughput.
- **🧠 Multi-Tier AI text Engine**: Google Gemini AI model router with auto-healing and dynamic fallbacks.

---

## 🛠️ Essential Commands

| Command | Action | Description |
| :--- | :--- | :--- |
| `.alive` | Status HUD | Displays engine health, database status, latency, uptime, and versions |
| `.ping` | Latency Check | Measures roundtrip response time to Telegram servers (`-a` for 3-sample average) |
| `.aetheris` | System Dashboard | Full real-time dashboard with active tasks, memory consumption, and quick controls |
| `.reload [plugin]` | Dynamic Hot-Reload | Hot-reloads plugin(s) in-memory in milliseconds with zero downtime |
| `.tasks` | Task Registry | Lists all active background asynchronous jobs and durations |
| `.taskkill <id>` | Cancel Task | Safely aborts a background task by numeric ID |
| `.sysinfo` / `.spc` | Hardware Metrics | CPU load, memory usage, storage, network bandwidth, and OS details |
| `.help` | Command Guide | Interactive inline menu and command manual |

---

## 📦 Deployment

### Docker / VPS / Localhost
```bash
git clone https://github.com/amandeavor/catuserbot.git
cd catuserbot
pip3 install -r requirements.txt
python3 -m userbot
```

### Render / Heroku Cloud Deploy
1. Fork or push to your personal GitHub repository (`amandeavor/catuserbot`).
2. Connect repository to your Render Web Service or Heroku Dyno.
3. Configure environment variables (`STRING_SESSION`, `APP_ID`, `API_HASH`, `TG_BOT_TOKEN`, `DATABASE_URL`).
4. Automatic redeploy triggers on every push to `master`.

---

## 📜 License & Credits

- Licensed under **GNU Affero General Public License v3.0**.
- Built with [Telethon](https://github.com/LonamiWebs/Telethon).
- Architectural patterns inspired by **Ultroid**, **Hikka**, and **Userge**.
