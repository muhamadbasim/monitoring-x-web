---
name: monitoring-x-web
description: Use when setting up reusable near-realtime monitoring for public X handles and website RSS/Atom feeds with Hermes cron no-agent notifications.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [monitoring, x, twitter, rss, hermes-cron, automation]
    related_skills: [github-repo-management, github-pr-workflow, hermes-agent]
---

# Monitoring X + Website Skill

## Overview

Use this skill to deploy or modify the `monitoring-x-web` workflow: one Python script monitors many public X handles and many website/RSS/Atom feeds, dedupes seen posts locally, and emits Telegram-ready notifications only when new content appears.

The preferred runtime is Hermes cron with `no_agent=True`, so polling does not spend LLM tokens. The script stays silent when nothing changes and exits non-zero only when monitoring is broken enough that the user should be alerted.

## When to Use

Use this when the user asks to:

- monitor an X/Twitter account for new posts without using paid X API credentials;
- monitor a website, blog, news page, or RSS/Atom feed for new content;
- add more X handles or website feeds to an existing monitor;
- migrate dedicated one-off monitors into one reusable generic config;
- send new-post notifications to Telegram through Hermes cron.

Do **not** use this for:

- true second-level realtime X streaming; use X API v2 filtered stream instead;
- private/authenticated websites unless a credential strategy is explicitly provided;
- JavaScript-only pages with no RSS unless you are ready to add browser automation or a custom scraper.

## Files

Default Hermes deployment paths:

```text
~/.hermes/scripts/post-monitor.py
~/.hermes/data/monitors/post-monitor-config.json
~/.hermes/data/monitors/post-monitor-state.json
```

Repo paths:

```text
scripts/post-monitor.py
examples/post-monitor-config.example.json
examples/post-monitor-config.basim.example.json
docs/TUTORIAL.md
docs/CONFIGURATION.md
docs/HERMES_CRON.md
```

## Deployment Workflow

1. Clone the repo:

   ```bash
   git clone https://github.com/muhamadbasim/monitoring-x-web.git
   cd monitoring-x-web
   ```

2. Validate the script:

   ```bash
   python3 -m py_compile scripts/post-monitor.py
   ```

3. Install into Hermes:

   ```bash
   mkdir -p ~/.hermes/scripts ~/.hermes/data/monitors
   cp scripts/post-monitor.py ~/.hermes/scripts/post-monitor.py
   cp examples/post-monitor-config.example.json ~/.hermes/data/monitors/post-monitor-config.json
   chmod +x ~/.hermes/scripts/post-monitor.py
   ```

4. Edit config:

   ```bash
   ${EDITOR:-nano} ~/.hermes/data/monitors/post-monitor-config.json
   ```

5. Seed/verify state:

   ```bash
   python3 ~/.hermes/scripts/post-monitor.py --force --summary
   ```

6. Create Hermes cron:

   ```bash
   hermes cron create "every 5m" \\
        --name generic-post-monitor \\
        --script post-monitor.py \\
        --no-agent \\
        --deliver origin \\
        "Script-only generic monitor for configured X handles and website RSS/Atom feeds. Prints only when new posts are detected."
   ```

## Add an X Handle

Add this to `sources`:

```json
{
  "id": "x-username",
  "type": "x",
  "enabled": true,
  "name": "@username",
  "handle": "username",
  "min_interval_seconds": 600,
  "nitter_instances": ["https://nitter.net"],
  "direct_x_fallback": true,
  "include_replies": true,
  "include_reposts": true
}
```

Then verify:

```bash
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

## Add a Website

Prefer explicit RSS/Atom feed URLs:

```json
{
  "id": "website-example",
  "type": "website",
  "enabled": true,
  "name": "Example Blog",
  "url": "https://example.com/",
  "feed_urls": ["https://example.com/rss.xml"],
  "min_interval_seconds": 300
}
```

If unknown, provide only homepage URL and let the script auto-discover feed links.

If RSS is incomplete, add HTML listing URLs and URL filters:

```json
{
  "id": "website-html-listing",
  "type": "website",
  "enabled": true,
  "name": "Example Blog",
  "url": "https://example.com/",
  "feed_urls": ["https://example.com/rss.xml"],
  "html_urls": ["https://example.com/blog/"],
  "html_link_include_patterns": ["/blog/"],
  "html_category": "Example Blog",
  "html_max_links": 20,
  "html_fetch_item_pages": true,
  "min_interval_seconds": 300
}
```

## Common Pitfalls

1. **Changing source IDs resets dedupe.** The state key is `source.id`; changing it can re-notify old posts.
2. **Committing real state.** State may contain seen post IDs and timestamps. Commit only `examples/post-monitor-state.example.json` unless explicitly desired.
3. **Over-polling X mirrors.** The script enforces a minimum 600-second interval for `type: "x"` sources; keep X polling around 10 minutes or more to avoid mirror blocks.
4. **Relying on Nitter for production-critical alerts.** Nitter mirrors can go down; use official X API for strong guarantees.
5. **Leaving old cron jobs active.** If migrating from dedicated scripts, pause/remove old jobs to prevent duplicate notifications.

## Verification Checklist

- [ ] `python3 -m py_compile scripts/post-monitor.py` passes.
- [ ] Config JSON parses.
- [ ] `python3 ~/.hermes/scripts/post-monitor.py --force --summary` exits 0.
- [ ] State path points to the intended file.
- [ ] Hermes cron uses `no_agent=True`.
- [ ] Old duplicate cron jobs are paused or removed.
- [ ] A test run with temporary empty state can produce expected notification text.
