# Hermes Cron Setup

Dokumen ini fokus menjalankan monitor sebagai Hermes cron `no_agent=True`.

## Kenapa `no_agent=True`?

Mode `no_agent=True` membuat scheduler hanya menjalankan script dan mengirim stdout apa adanya. Tidak ada LLM yang dipanggil untuk setiap tick.

Dampaknya:

- murah;
- silent kalau tidak ada perubahan;
- output script langsung menjadi notifikasi Telegram;
- non-zero exit akan menjadi error alert sehingga monitor rusak tidak gagal diam-diam.

## Install file

```bash
mkdir -p ~/.hermes/scripts ~/.hermes/data/monitors
cp scripts/post-monitor.py ~/.hermes/scripts/post-monitor.py
cp examples/post-monitor-config.example.json ~/.hermes/data/monitors/post-monitor-config.json
chmod +x ~/.hermes/scripts/post-monitor.py
```

Edit config:

```bash
${EDITOR:-nano} ~/.hermes/data/monitors/post-monitor-config.json
```

Test manual:

```bash
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

## Buat job

Dengan CLI Hermes:

```bash
hermes cron create "every 5m" \\
  --name generic-post-monitor \\
  --script post-monitor.py \\
  --no-agent \\
  --deliver origin \\
  "Script-only generic monitor for configured X handles and website RSS/Atom feeds. Prints only when new posts are detected."
```

Parameter penting:

| Parameter | Nilai |
| --- | --- |
| `schedule` | `every 5m` |
| `script` | `post-monitor.py` |
| `no_agent` | `true` |
| `deliver` | `origin` atau tujuan Telegram lain |

## Cek job

```bash
hermes cron list
```

Pastikan job aktif dan script menunjuk ke `post-monitor.py`.

## Pause job lama

Kalau sebelumnya punya monitor dedicated, pause agar notifikasi tidak dobel:

```bash
hermes cron pause <job_id>
```

Atau hapus jika sudah yakin:

```bash
hermes cron remove <job_id>
```

## Run manual dari scheduler

```bash
hermes cron run <job_id>
```

Ini berguna untuk memastikan delivery ke Telegram berjalan.

## Desain interval

Cron generic bisa jalan tiap 5 menit, sementara tiap source punya interval sendiri:

```json
{
  "id": "x-username",
  "min_interval_seconds": 600
}
```

Jika cron tick belum melewati interval source, source tersebut dilewati.

## Output behavior

| Kondisi | stdout | Efek Hermes |
| --- | --- | --- |
| Tidak ada post baru | kosong | Tidak mengirim pesan |
| Ada post baru | teks notifikasi | Dikirim ke Telegram |
| Semua source due gagal | exit non-zero | Hermes kirim error alert |
| Sebagian source gagal, sebagian sukses | ringkasan/error di state, exit 0 jika masih ada sukses | Tidak spam error kecuali semua gagal |

## Config aktif Basim

Untuk setup awal Basim, gunakan:

```bash
cp examples/post-monitor-config.basim.example.json ~/.hermes/data/monitors/post-monitor-config.json
python3 ~/.hermes/scripts/post-monitor.py --force --summary
```

Lalu buat cron generic.
