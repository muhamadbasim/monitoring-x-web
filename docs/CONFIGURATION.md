# Configuration Reference

`post-monitor.py` membaca satu file JSON. Default path saat dipakai di Hermes:

```text
~/.hermes/data/monitors/post-monitor-config.json
```

Bisa dioverride dengan flag:

```bash
python3 scripts/post-monitor.py --config ./post-monitor-config.json
```

Atau env var:

```bash
POST_MONITOR_CONFIG=./post-monitor-config.json python3 scripts/post-monitor.py
```

## Top-level schema

```json
{
  "version": 1,
  "state_path": "~/.hermes/data/monitors/post-monitor-state.json",
  "user_agent": "Mozilla/5.0 ...",
  "timeout_seconds": 30,
  "nitter_instances": ["https://nitter.net"],
  "direct_x_fallback": true,
  "notification": {
    "max_text_chars": 700,
    "max_items_per_run": 20
  },
  "sources": []
}
```

| Field | Required | Default | Keterangan |
| --- | --- | --- | --- |
| `version` | no | `1` | Versi config. |
| `state_path` | no | `~/.hermes/data/monitors/post-monitor-state.json` | Path state dedupe. `~` didukung. |
| `user_agent` | no | built-in Hermes UA | Header untuk request HTTP. |
| `timeout_seconds` | no | `30` | Timeout per request. |
| `nitter_instances` | no | `https://nitter.net` | Default mirror Nitter untuk source X. |
| `direct_x_fallback` | no | `true` | Coba HTML X langsung jika Nitter gagal. |
| `notification.max_text_chars` | no | `700` | Potong isi teks notifikasi per item. |
| `notification.max_items_per_run` | no | `20` | Batas item baru yang dikirim per run. |
| `sources` | yes | `[]` | Array source yang dipantau. |

## Source type: `x`

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

| Field | Required | Keterangan |
| --- | --- | --- |
| `id` | yes | ID unik untuk state, jangan diubah setelah berjalan kecuali ingin reset dedupe. |
| `type` | yes | `x`. |
| `enabled` | no | `true`/`false`. |
| `name` | no | Nama tampil di notifikasi. |
| `handle` | yes | X handle tanpa `@`. |
| `min_interval_seconds` | no | Interval minimum source ini. Untuk `type: "x"`, script menegakkan minimum 600 detik walau config diisi lebih rendah. |
| `nitter_instances` | no | Override mirror untuk source ini. |
| `direct_x_fallback` | no | Override fallback HTML X langsung. |
| `include_replies` | no | Saat parsing Nitter RSS, simpan reply juga. |
| `include_reposts` | no | Saat parsing Nitter RSS, simpan repost juga. |

## Source type: `website`

Dengan feed URL explicit:

```json
{
  "id": "website-my-blog",
  "type": "website",
  "enabled": true,
  "name": "My Blog",
  "url": "https://example.com/",
  "feed_urls": [
    "https://example.com/rss.xml",
    "https://example.com/feed.xml"
  ],
  "min_interval_seconds": 300
}
```

Dengan auto-discovery:

```json
{
  "id": "website-my-blog",
  "type": "website",
  "enabled": true,
  "name": "My Blog",
  "url": "https://example.com/",
  "min_interval_seconds": 300
}
```

| Field | Required | Keterangan |
| --- | --- | --- |
| `id` | yes | ID unik untuk state. |
| `type` | yes | `website`. |
| `enabled` | no | `true`/`false`. |
| `name` | no | Nama tampil. |
| `url` | yes jika tidak ada `feed_urls` | Homepage untuk auto-discovery. |
| `feed_urls` | no | Array RSS/Atom URL explicit. |
| `min_interval_seconds` | no | Disarankan 300 detik atau lebih. |

## Source type: `rss`

Shortcut untuk satu feed langsung:

```json
{
  "id": "rss-example",
  "type": "rss",
  "enabled": true,
  "name": "Example RSS",
  "url": "https://example.com/rss.xml",
  "min_interval_seconds": 300
}
```

## State file

State berbentuk JSON dan dibuat otomatis jika belum ada:

```json
{
  "version": 1,
  "created_at": "...",
  "updated_at": "...",
  "sources": {
    "x-username": {
      "seen_ids": ["1234567890"],
      "last_checked_at": "..."
    }
  }
}
```

Jangan commit state production berisi `seen_ids` real kecuali memang sengaja. Repo ini hanya menyertakan template state kosong.

## Best practices

- Gunakan `id` stabil dan human-readable.
- Jangan terlalu agresif polling X; mulai dari 10 menit.
- Untuk website dengan RSS bagus, 5 menit biasanya aman.
- Jalankan manual dengan `--force --summary` setelah edit config.
- Simpan config production di `~/.hermes/data/monitors/`, bukan di repo publik jika mengandung URL private.
