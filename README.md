# Monitoring X + Website Realtime-ish

Reusable monitor untuk mengambil data post baru dari:

- akun **X/Twitter publik** tanpa X API/xAI key, via RSS mirror Nitter + fallback HTML X;
- **website/blog/news** via RSS/Atom feed, auto-discovery feed, atau URL feed explicit.

Script ini dibuat supaya bisa jalan murah sebagai **Hermes cron `no_agent=True`**: kalau tidak ada post baru, output kosong/silent; kalau ada post baru, stdout menjadi pesan notifikasi yang bisa dikirim otomatis ke Telegram.

## Fitur

- Satu script generic untuk banyak source.
- Config-driven via JSON.
- Dedupe state lokal per source agar tidak spam saat restart.
- X handle polling tanpa credential API resmi.
- Website RSS/Atom polling + auto-discovery feed dari homepage.
- Format output siap kirim ke Telegram/Discord/log/webhook.
- Tidak memakai dependency eksternal Python; cukup Python 3.11+ stdlib.

## Struktur repo

```text
.
├── scripts/
│   └── post-monitor.py                 # script monitor generic
├── examples/
│   ├── post-monitor-config.example.json # template config reusable
│   ├── post-monitor-config.basim.example.json
│   └── post-monitor-state.example.json  # template state kosong
├── docs/
│   ├── TUTORIAL.md                      # tutorial langkah demi langkah
│   ├── CONFIGURATION.md                 # referensi schema config
│   ├── HERMES_CRON.md                   # cara menjalankan via Hermes cron
│   ├── TROUBLESHOOTING.md               # masalah umum + solusi
│   └── PLAN.md                          # brainstorming/analisa awal
└── skills/
    └── monitoring-x-web/
        └── SKILL.md                     # Hermes skill/prosedur reusable
```

## Quick start lokal

```bash
git clone https://github.com/muhamadbasim/monitoring-x-web.git
cd monitoring-x-web
python3 -m py_compile scripts/post-monitor.py
cp examples/post-monitor-config.example.json ./post-monitor-config.json
python3 scripts/post-monitor.py --config ./post-monitor-config.json --state ./post-monitor-state.json --force --dry-run --summary
```

> `--dry-run` tidak menyimpan state. Hapus `--dry-run` ketika sudah siap menjalankan monitor sebenarnya.

## Quick start Hermes

```bash
mkdir -p ~/.hermes/scripts ~/.hermes/data/monitors
cp scripts/post-monitor.py ~/.hermes/scripts/post-monitor.py
cp examples/post-monitor-config.example.json ~/.hermes/data/monitors/post-monitor-config.json
chmod +x ~/.hermes/scripts/post-monitor.py

# Edit config sesuai source yang mau dipantau
${EDITOR:-nano} ~/.hermes/data/monitors/post-monitor-config.json

# Test manual
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

Buat cron Hermes script-only:

```bash
hermes cron create "every 5m" \\
  --name generic-post-monitor \\
  --script post-monitor.py \\
  --no-agent \\
  --deliver origin \\
  "Script-only generic monitor for configured X handles and website RSS/Atom feeds. Prints only when new posts are detected."
```

Kalau menggunakan API internal Hermes dari chat, konsepnya sama:

```json
{
  "action": "create",
  "name": "generic-post-monitor",
  "schedule": "every 5m",
  "script": "post-monitor.py",
  "no_agent": true,
  "deliver": "origin",
  "prompt": "Script-only generic monitor for configured X handles and website RSS/Atom feeds. Prints only when new posts are detected."
}
```

## Contoh config aktif Basim

Lihat:

```text
examples/post-monitor-config.basim.example.json
```

Isinya memonitor:

- X: `@basimseason` setiap 10 menit. Script juga menegakkan minimum 600 detik untuk semua source X walaupun config diisi lebih rendah.
- Website: `https://cerita.basim.id/rss.xml` dan `https://cerita.basim.id/rss-karya.xml` setiap 5 menit.

## Tambah akun X

Tambahkan object ini ke array `sources`:

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

## Tambah website/RSS

Kalau sudah tahu feed URL:

```json
{
  "id": "website-example",
  "type": "website",
  "enabled": true,
  "name": "Example Blog",
  "url": "https://example.com/",
  "feed_urls": [
    "https://example.com/rss.xml",
    "https://example.com/feed.xml"
  ],
  "min_interval_seconds": 300
}
```

Kalau belum tahu feed URL, cukup isi homepage dan biarkan script auto-discover:

```json
{
  "id": "website-autodiscovery",
  "type": "website",
  "enabled": true,
  "name": "Example Blog",
  "url": "https://example.com/",
  "min_interval_seconds": 300
}
```

Kalau RSS tidak memuat semua artikel, tambahkan HTML listing:

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
  "html_item_timeout_seconds": 10,
  "min_interval_seconds": 300
}
```

## Cara kerja dedupe

- State disimpan di JSON: default `~/.hermes/data/monitors/post-monitor-state.json`.
- Setiap source punya `seen_ids` sendiri.
- X dedupe pakai tweet/status ID bila tersedia.
- Website dedupe pakai `guid`, link, atau hash fallback.
- First run akan menandai item yang ditemukan sebagai seen. Kalau ingin menghindari spam, jalankan manual dulu lalu baru aktifkan cron.

## Catatan penting X

Monitoring X tanpa API resmi berarti reliability tergantung:

- ketersediaan Nitter instance;
- perubahan HTML X;
- rate limit/bot protection dari mirror.

Untuk production serius atau butuh realtime detik-ke-detik, pertimbangkan X API v2 filtered stream. Untuk biaya murah dan near-realtime 5–10 menit, mode Nitter/RSS ini cukup sebagai MVP.

## Dokumentasi lanjut

- [Tutorial lengkap](docs/TUTORIAL.md)
- [Referensi config](docs/CONFIGURATION.md)
- [Hermes cron](docs/HERMES_CRON.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Plan/analisa awal](docs/PLAN.md)
- [Hermes skill reusable](skills/monitoring-x-web/SKILL.md)
