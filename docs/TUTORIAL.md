# Tutorial: Monitor Banyak Akun X dan Website

Tutorial ini menjelaskan cara memakai `post-monitor.py` dari nol sampai berjalan otomatis.

## 1. Prasyarat

- Linux/macOS/WSL atau VPS.
- Python 3.11+.
- Git.
- Opsional: Hermes Agent jika ingin notifikasi otomatis ke Telegram via cron.

Cek Python:

```bash
python3 --version
```

Script tidak butuh package eksternal.

## 2. Clone repo

```bash
git clone https://github.com/muhamadbasim/monitoring-x-web.git
cd monitoring-x-web
```

Validasi syntax:

```bash
python3 -m py_compile scripts/post-monitor.py
```

## 3. Buat config

Mulai dari template:

```bash
cp examples/post-monitor-config.example.json post-monitor-config.json
```

Edit:

```bash
${EDITOR:-nano} post-monitor-config.json
```

Minimal source X:

```json
{
  "id": "x-basimseason",
  "type": "x",
  "enabled": true,
  "name": "@basimseason",
  "handle": "basimseason",
  "min_interval_seconds": 600,
  "nitter_instances": ["https://nitter.net"],
  "direct_x_fallback": true
}
```

Minimal source website dengan RSS explicit:

```json
{
  "id": "website-cerita-basim",
  "type": "website",
  "enabled": true,
  "name": "Cerita Basim",
  "url": "https://cerita.basim.id/",
  "feed_urls": [
    "https://cerita.basim.id/rss.xml",
    "https://cerita.basim.id/rss-karya.xml"
  ],
  "min_interval_seconds": 300
}
```

## 4. Test manual tanpa menyimpan state

```bash
python3 scripts/post-monitor.py \
  --config ./post-monitor-config.json \
  --state ./post-monitor-state.json \
  --force \
  --dry-run \
  --summary
```

Arti flag:

| Flag | Fungsi |
| --- | --- |
| `--config` | Path file config JSON |
| `--state` | Path file dedupe state JSON |
| `--force` | Abaikan interval dan cek semua source sekarang |
| `--dry-run` | Jangan tulis state |
| `--summary` | Print ringkasan walau tidak ada post baru |

## 5. Seed state agar tidak spam

Saat sudah yakin config benar, jalankan sekali tanpa `--dry-run`:

```bash
python3 scripts/post-monitor.py \
  --config ./post-monitor-config.json \
  --state ./post-monitor-state.json \
  --force \
  --summary
```

Ini akan menyimpan item yang sudah ada ke state. Setelah itu, run berikutnya hanya melaporkan item baru.

## 6. Jalankan berkala tanpa Hermes

Dengan cron Linux biasa:

```bash
crontab -e
```

Tambahkan:

```cron
*/5 * * * * cd /path/to/monitoring-x-web && python3 scripts/post-monitor.py --config ./post-monitor-config.json --state ./post-monitor-state.json
```

Cron ini silent kalau tidak ada post baru. Arahkan stdout ke notifikasi sendiri jika tidak memakai Hermes.

## 7. Jalankan dengan Hermes cron

Install file ke lokasi default Hermes:

```bash
mkdir -p ~/.hermes/scripts ~/.hermes/data/monitors
cp scripts/post-monitor.py ~/.hermes/scripts/post-monitor.py
cp post-monitor-config.json ~/.hermes/data/monitors/post-monitor-config.json
chmod +x ~/.hermes/scripts/post-monitor.py
```

Test:

```bash
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

Buat job:

```bash
hermes cron create "every 5m" \\
  --name generic-post-monitor \\
  --script post-monitor.py \\
  --no-agent \\
  --deliver origin \\
  "Script-only generic monitor for configured X handles and website RSS/Atom feeds."
```

Cek job:

```bash
hermes cron list
```

## 8. Menambah source baru

1. Edit config.
2. Tambahkan object source baru dengan `id` unik.
3. Jalankan:

```bash
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

4. Jika output normal, cron akan lanjut memakai config baru.

## 9. Update script dari repo

```bash
cd monitoring-x-web
git pull
cp scripts/post-monitor.py ~/.hermes/scripts/post-monitor.py
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

## 10. Rollback cepat

Kalau perubahan config membuat error:

```bash
cp ~/.hermes/data/monitors/post-monitor-config.json ~/.hermes/data/monitors/post-monitor-config.broken.json
cp examples/post-monitor-config.basim.example.json ~/.hermes/data/monitors/post-monitor-config.json
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```
