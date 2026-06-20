# Troubleshooting

## Tidak ada notifikasi

Cek manual:

```bash
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

Jika output `new=0`, berarti belum ada post baru atau item sudah masuk state.

## Ingin mengetes notifikasi tanpa menunggu post baru

Gunakan state sementara:

```bash
python3 ~/.hermes/scripts/post-monitor.py \
  --config ~/.hermes/data/monitors/post-monitor-config.json \
  --state /tmp/post-monitor-test-state.json \
  --force \
  --dry-run \
  --summary
```

Karena state kosong, item terbaru akan dianggap baru. `--dry-run` mencegah state test ditulis.

## Banyak notifikasi lama muncul

Penyebab: state baru/kosong atau `id` source berubah.

Solusi:

1. Pastikan `id` source tidak berubah.
2. Seed state sekali:

```bash
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

3. Baru aktifkan cron.

## X/Nitter gagal

Penyebab umum:

- Nitter instance down.
- Rate limit/bot protection.
- X mengubah HTML sehingga fallback tidak berhasil.

Solusi:

- Tambah instance Nitter lain di config:

```json
"nitter_instances": [
  "https://nitter.net",
  "https://nitter.poast.org"
]
```

- Naikkan interval X ke 10–30 menit.
- Jika production kritikal, gunakan X API resmi.

## Website tidak terdeteksi

Cek apakah RSS/Atom ada:

```bash
python3 - <<'PY'
import urllib.request
for url in ['https://example.com/rss.xml', 'https://example.com/feed.xml', 'https://example.com/atom.xml']:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            print(url, r.status, r.headers.get('content-type'))
    except Exception as e:
        print(url, type(e).__name__, e)
PY
```

Jika website tidak punya RSS dan butuh JavaScript, script ini perlu adapter HTML custom atau browser automation.

## Cron tidak mengirim pesan

Pastikan job Hermes dibuat dengan:

- `no_agent=True`
- `deliver=origin` atau destination yang benar
- script berada di `~/.hermes/scripts/post-monitor.py`

Cek:

```bash
hermes cron list
```

## Script error tapi manual jalan

Perbedaan umum:

- Environment variable berbeda.
- Working directory berbeda.
- Config path default tidak ada.

Gunakan absolute/default Hermes path:

```text
~/.hermes/scripts/post-monitor.py
~/.hermes/data/monitors/post-monitor-config.json
~/.hermes/data/monitors/post-monitor-state.json
```

## Reset semua state

Hati-hati: ini bisa membuat item lama muncul sebagai baru.

```bash
mv ~/.hermes/data/monitors/post-monitor-state.json ~/.hermes/data/monitors/post-monitor-state.backup.json
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```
