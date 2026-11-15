<div align="center">

# 🌐 NationStates → Discord Webhook

A tiny, self-hosted Python bot that checks the NationStates announcements page and posts new announcements to a Discord channel's webhook.

[Quick start](#-quick-start) · [How it works](#-how-it-works) · [Configuration](#️-configuration) · [Troubleshooting](#-troubleshooting)

</div>

---

## 🚀 Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Also requires Chromium.

```bash
git clone https://github.com/jtpotato/nationstates-webhook.git
cd nationstates-webhook
cp .env.example .env
```

Open `.env` and paste in a Discord webhook URL. Create one in **Discord → Server Settings → Integrations → Webhooks**.

```bash
uv sync
uv run playwright install chromium
uv run python ns_news_webhook.py
```

The first run announces everything currently listed on the page; later runs announce only unseen entries.

---

the rest is lowk whatever AI wanted to write so feel free to ignore

## ✨ What it does

- 📰 Fetches and parses NationStates announcements
- 🔔 Sends new items to Discord through a webhook
- 🎨 Formats each post as a clean, clickable Discord embed
- 🧠 Keeps a local SQLite ledger, so already-sent items aren't reposted
- 🕘 Installs a daily cron schedule with one script
- 🧪 Clears its local history for a clean test run
- 🔐 Keeps credentials in `.env` (excluded from Git)

No bot account, gateway connection, or database server required.



## ⏰ Daily polling

```bash
./scripts/install-cron.sh
```

This installs a **09:00 local-time** cron job and writes output to `.state/cron.log`. Run it again to update the existing job. To remove it, edit your crontab with `crontab -e` and delete the line marked `# ns-news-webhook`.

## ⚙️ Configuration

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `DISCORD_WEBHOOK_URL` | ✅ | — | Discord channel webhook URL |
| `NATIONSTATES_NEWS_URL` | | `https://www.nationstates.net/page=news` | Page to poll |
| `NATIONSTATES_USER_AGENT` | | Chrome-style Linux User-Agent | Browser User-Agent used for the page fetch |

The script polls once each time it runs. Change the schedule in `scripts/install-cron.sh` if you want a different time or cadence.

## 🧹 Test from scratch

```bash
./scripts/clear-storage.sh
uv run python ns_news_webhook.py
```

Clearing storage makes all announcements currently on the page eligible to post again. The SQLite database lives at `.state/announcements.sqlite3`.

## 🛠️ How it works

1. Fetches the configured page with a descriptive User-Agent.
2. Fetches with headless Chromium and the identifying User-Agent because ordinary HTTP requests to the page return 403 in the target environment. If Chromium also receives an error, the run fails.
3. Extracts announcement titles, links, and short previews from the page markup.
4. Uses each announcement URL as a stable identity and records it in SQLite.
5. Posts unsent records to Discord, marking each delivered only after Discord accepts it.

If delivery fails, the pending item remains in storage and will be retried next run. As with any webhook delivery, a process interruption after Discord accepts a message but before the local database records success can very rarely cause a duplicate.

## 🩺 Troubleshooting

- **No webhook configured:** check `.env` and make sure the variable is named `DISCORD_WEBHOOK_URL`.
- **Cron isn't running:** confirm the job with `crontab -l`; cron uses your machine's local timezone. Check `.state/cron.log`.
- **No announcements found:** the upstream page markup may have changed. Run the script manually and inspect the page URL configured in `.env`.
- **Chromium executable missing:** run `uv run playwright install chromium`. On Linux VPSes, Playwright may also need OS libraries; see [Playwright's Linux setup](https://playwright.dev/python/docs/browsers#install-system-dependencies).
- **Discord rejects the post:** confirm the webhook is still valid and has not been deleted.

## 🛡️ Privacy & safety

Your webhook URL grants permission to post in its channel. Never share it.

## 📄 License

MIT — see [LICENSE](LICENSE).