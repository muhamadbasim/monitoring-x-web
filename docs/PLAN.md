# Realtime X + Website Monitoring Plan

> **For Hermes:** Use subagent-driven-development skill only if this plan later becomes an implementation task. For now: planning/brainstorming only.

**Goal:** Membuat sistem yang bisa mendeteksi post baru dari akun X dan website teman, mengambil datanya, menormalisasi hasilnya, lalu mengirim/menyimpan event saat ada post baru.

**Architecture:** Gunakan pendekatan source-adapter: satu adapter untuk X, satu adapter untuk website, lalu hasilnya masuk ke normalizer + dedupe store + notifier. Untuk MVP, gunakan polling terjadwal karena lebih stabil dan murah. Untuk “realtime” sungguhan di X, upgrade ke X API filtered stream jika akses API/plan mendukung.

**Tech Stack:** Python 3.11, SQLite, `xurl`/X API v2, RSS/Atom/blogwatcher-cli atau scraper HTML, cron/systemd/Docker, Telegram/webhook/notifier opsional.

---

## 1. Ringkasan kebutuhan

Teman meminta: “ambil data realtime akun X dan website ketika dia post sesuatu.”

Terjemahan teknisnya:

- Monitor akun X tertentu.
- Monitor website tertentu.
- Deteksi konten baru.
- Ambil data post terbaru.
- Hindari duplikasi.
- Kirim/ekspor data ke tujuan tertentu.
- Jalankan terus-menerus dengan logging dan retry.

---

## 2. Pertanyaan yang perlu dikunci sebelum implementasi

1. **Sumber X**
   - Handle akun X apa?
   - Akun milik teman sendiri atau akun publik pihak ketiga?
   - Yang dipantau hanya tweet original, atau termasuk reply/repost/quote?
   - Butuh media: gambar/video/link preview?

2. **Sumber website**
   - URL website apa?
   - Ada RSS/Atom feed?
   - Konten baru muncul di halaman blog/news, sitemap, atau halaman custom?
   - Website statis atau butuh JavaScript render?

3. **Definisi realtime**
   - Realtime = beberapa detik?
   - Near realtime = 1–5 menit cukup?
   - Batas rate limit dan biaya X API diterima?

4. **Output**
   - Dikirim ke mana: Telegram, Discord, email, Google Sheet, database, webhook, dashboard?
   - Format data yang dibutuhkan apa?
   - Perlu menyimpan raw JSON/HTML untuk audit?

5. **Deployment**
   - Jalan di laptop, VPS, Docker, serverless, atau langsung lewat Hermes cron?
   - Perlu 24/7 uptime?
   - Siapa yang pegang credentials X API?

---

## 3. Analisa pendekatan

### Opsi A — Quick MVP dengan polling

**Cara kerja:**

- Setiap 1–5 menit, cek akun X dan website.
- Ambil item terbaru.
- Bandingkan dengan state SQLite.
- Jika belum pernah terlihat, simpan dan kirim notifikasi.

**Kelebihan:**

- Paling mudah dibuat.
- Cocok untuk website yang tidak punya webhook.
- Lebih murah dan lebih gampang dideploy.
- Bisa jalan via cron, systemd timer, Docker, atau Hermes cron.

**Kekurangan:**

- Bukan realtime detik-ke-detik.
- Kena rate limit kalau interval terlalu agresif.

**Cocok untuk:** MVP pertama.

---

### Opsi B — X streaming + website polling

**Cara kerja:**

- X dipantau via X API filtered stream.
- Website tetap dipantau via RSS/scraping polling.

**Kelebihan:**

- X bisa mendekati realtime.
- Website tetap realistis karena mayoritas website tidak menyediakan push event.

**Kekurangan:**

- Butuh akses X API yang mendukung streaming.
- Lebih kompleks: koneksi streaming harus auto-reconnect.
- Website tetap tidak realtime sempurna kecuali ada webhook/RSS cepat.

**Cocok untuk:** Jika teman benar-benar butuh deteksi X dalam hitungan detik.

---

### Opsi C — Webhook/native integration jika website milik teman

**Cara kerja:**

- Jika website teman bisa dimodifikasi, tambahkan webhook saat post publish.
- X tetap via polling/streaming.

**Kelebihan:**

- Website bisa benar-benar realtime.
- Lebih hemat request dan lebih akurat.

**Kekurangan:**

- Butuh akses ke CMS/backend website.
- Implementasi tergantung platform: WordPress, Ghost, custom CMS, static site, dsb.

**Cocok untuk:** Website milik teman dan kita bisa pasang plugin/webhook.

---

## 4. Rekomendasi awal

Mulai dengan **Opsi A: polling MVP**:

- Interval X: 2–5 menit untuk awal.
- Interval website: 2–10 menit tergantung RSS/sitemap/scraping.
- Store: SQLite.
- Dedupe: berdasarkan `source + external_id` atau `canonical_url + content_hash`.
- Output awal: Telegram/webhook/log JSON.

Lalu upgrade bertahap:

1. Jika X API plan mendukung streaming, upgrade X adapter ke filtered stream.
2. Jika website milik teman, pasang webhook publish event dari CMS.
3. Jika volume tinggi, pindahkan state/event ke Postgres + queue.

---

## 5. Data model minimum

Tabel `seen_items`:

| Field | Type | Keterangan |
| --- | --- | --- |
| `id` | text | ID internal, misalnya hash |
| `source` | text | `x` atau `website` |
| `external_id` | text | tweet ID, article URL, atau CMS post ID |
| `url` | text | URL canonical |
| `title` | text | Judul jika ada |
| `text` | text | Isi singkat / body excerpt |
| `author` | text | Handle/author |
| `published_at` | datetime | Waktu publish dari source |
| `detected_at` | datetime | Waktu sistem mendeteksi |
| `content_hash` | text | Hash konten untuk deteksi perubahan |
| `raw_json` | json/text | Payload mentah opsional |
| `status` | text | `new`, `sent`, `failed`, `ignored` |

Event output minimum:

```json
{
  "source": "x",
  "external_id": "1234567890",
  "url": "https://x.com/handle/status/1234567890",
  "title": null,
  "text": "Isi post...",
  "author": "@handle",
  "published_at": "2026-06-20T10:00:00Z",
  "detected_at": "2026-06-20T10:02:10Z",
  "media": [],
  "raw": {}
}
```

---

## 6. Rencana struktur project jika dibangun sebagai service

```text
realtime-post-monitor/
  README.md
  .env.example
  config.example.yaml
  pyproject.toml
  src/
    monitor/
      __init__.py
      main.py
      config.py
      db.py
      models.py
      scheduler.py
      sources/
        __init__.py
        x_source.py
        website_source.py
        rss_source.py
        scraper_source.py
      notifiers/
        __init__.py
        telegram.py
        webhook.py
        stdout.py
      utils/
        hashing.py
        time.py
        logging.py
  tests/
    test_dedupe.py
    test_x_source_parse.py
    test_rss_source_parse.py
    test_website_source_parse.py
    test_notifier_payload.py
  deploy/
    systemd/monitor.service
    systemd/monitor.timer
    docker/Dockerfile
    docker/docker-compose.yml
```

---

## 7. Step-by-step implementation plan

### Task 1: Kunci acceptance criteria

**Objective:** Pastikan scope tidak melebar.

**Deliverable:** Dokumen singkat berisi:

- X handle target.
- Website URL target.
- Definisi realtime.
- Output destination.
- Jenis konten yang diambil.
- Batasan legal/ToS.

**Verification:** Teman menyetujui format event contoh.

---

### Task 2: Source discovery untuk website

**Objective:** Cari metode paling bersih untuk website.

**Langkah:**

1. Cek RSS/Atom auto-discovery dari homepage.
2. Cek `/feed`, `/rss`, `/atom.xml`, `/sitemap.xml`.
3. Jika ada RSS, gunakan RSS/blogwatcher-style polling.
4. Jika tidak ada RSS, tentukan CSS selector untuk list post.
5. Jika konten butuh JS, gunakan Playwright scraper.

**Verification:** Bisa mengambil 3 item terbaru dari website dengan URL canonical dan tanggal publish.

---

### Task 3: Source discovery untuk X

**Objective:** Validasi akses dan metode X.

**Langkah:**

1. Pastikan `xurl` terinstall.
2. User/teman melakukan setup credentials X API secara manual, jangan paste token ke chat.
3. Verifikasi hanya dengan `xurl auth status`.
4. Ambil user id dari handle.
5. Coba ambil tweet terbaru via X API v2.
6. Tentukan apakah polling cukup atau butuh streaming.

**Catatan keamanan:** Jangan membaca atau membagikan isi `~/.xurl`.

**Verification:** Bisa mendapatkan tweet terbaru dalam JSON tanpa exposing secret.

---

### Task 4: Buat state store SQLite

**Objective:** Dedupe agar notifikasi tidak dobel.

**Files:**

- Create: `src/monitor/db.py`
- Create: `src/monitor/models.py`
- Test: `tests/test_dedupe.py`

**Logic:**

- `seen_before(source, external_id)`
- `insert_item(item)`
- `mark_sent(item_id)`
- unique index: `(source, external_id)`

**Verification:** Item yang sama hanya diproses sekali.

---

### Task 5: Buat X source adapter

**Objective:** Mengubah payload X API menjadi event internal.

**Files:**

- Create: `src/monitor/sources/x_source.py`
- Test: `tests/test_x_source_parse.py`

**Polling MVP:**

- Lookup user id dari handle.
- Ambil tweet terbaru.
- Filter sesuai kebutuhan: exclude retweet/reply jika diminta.
- Normalize ke model event.

**Streaming upgrade:**

- Gunakan filtered stream rule seperti `from:handle -is:retweet` jika API mendukung.
- Auto-reconnect dengan backoff.

**Verification:** Event internal berisi `external_id`, `url`, `text`, `author`, `published_at`.

---

### Task 6: Buat website source adapter

**Objective:** Mengubah RSS/scraped website item menjadi event internal.

**Files:**

- Create: `src/monitor/sources/rss_source.py`
- Create: `src/monitor/sources/scraper_source.py` jika perlu
- Create: `src/monitor/sources/website_source.py`
- Test: `tests/test_rss_source_parse.py`
- Test: `tests/test_website_source_parse.py`

**Logic:**

- Prefer RSS/Atom.
- Fallback HTML selector.
- Normalize canonical URL.
- Compute `content_hash` dari title + url + published_at/body excerpt.

**Verification:** Item website baru terdeteksi dan item lama tidak dikirim ulang.

---

### Task 7: Buat notifier

**Objective:** Kirim event ke tujuan yang dipilih.

**Files:**

- Create: `src/monitor/notifiers/stdout.py`
- Create: `src/monitor/notifiers/telegram.py` atau `webhook.py`
- Test: `tests/test_notifier_payload.py`

**MVP:**

- `stdout` JSON lines untuk debugging.
- Webhook POST atau Telegram message untuk real usage.

**Verification:** Saat event dummy dikirim, receiver menerima format yang benar.

---

### Task 8: Buat scheduler/runner

**Objective:** Jalankan loop monitoring dengan interval.

**Files:**

- Create: `src/monitor/scheduler.py`
- Create: `src/monitor/main.py`
- Modify: `config.example.yaml`

**Logic:**

- Load config.
- Run each source.
- For each normalized item:
  - Check dedupe.
  - Insert if new.
  - Notify.
  - Mark sent/failed.
- Retry transient errors.
- Structured logs.

**Verification:** Dengan data mock, runner mendeteksi item baru satu kali dan tidak dobel pada run kedua.

---

### Task 9: Deployment

**Objective:** Sistem jalan 24/7.

**Opsi deployment:**

1. **Hermes cron quick test**
   - Cocok untuk prototype pribadi.
   - Interval 5 menit.
   - Output balik ke Telegram.

2. **Linux cron/systemd timer**
   - Cocok untuk VPS kecil.
   - Lebih mudah debug.

3. **Docker Compose**
   - Cocok untuk deploy rapi dan portable.

4. **Serverless scheduled function**
   - Cocok kalau tidak butuh long-running stream.

**Verification:** Service restart otomatis dan logs bisa dilihat.

---

### Task 10: Monitoring dan alerting

**Objective:** Kalau sistem mati atau API error, ketahuan.

**Implement:**

- Log setiap run.
- Alert kalau 3x run gagal berturut-turut.
- Simpan last successful run per source.
- Dashboard ringan atau healthcheck endpoint opsional.

**Verification:** Simulasi error API menghasilkan alert, bukan silent failure.

---

## 8. Risiko dan tradeoff

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| X API berbayar/limited | Tidak bisa realtime gratis | Mulai polling rendah, cek plan API |
| Rate limit | Data telat / request gagal | Backoff, caching, interval realistis |
| Website tidak punya RSS | Scraper rapuh | Pakai selector stabil, test berkala |
| Website render JS | Scraper biasa gagal | Gunakan Playwright jika perlu |
| Duplicate notification | Spam ke user | SQLite unique index + content hash |
| Secret leakage | Security incident | Jangan paste token, jangan baca file credential |
| ToS/robots.txt | Legal/akses diblokir | Hanya public/authorized data, patuhi robots/rate limit |
| “Realtime” tidak jelas | Ekspektasi mismatch | Definisikan SLA: detik vs menit |

---

## 9. MVP scope yang disarankan

**Masuk MVP:**

- Monitor 1 akun X.
- Monitor 1 website.
- Polling tiap 5 menit.
- Dedupe SQLite.
- Output Telegram atau webhook.
- Log error dan success.

**Tidak masuk MVP dulu:**

- Dashboard UI.
- Multi-account banyak source.
- Analytics kompleks.
- Full text archive besar.
- Streaming X kecuali memang wajib.

---

## 10. Definition of Done

- [ ] X source bisa mendeteksi post baru.
- [ ] Website source bisa mendeteksi post baru.
- [ ] Event dinormalisasi ke format yang sama.
- [ ] Item lama tidak dikirim ulang.
- [ ] Notifikasi terkirim ke tujuan.
- [ ] Sistem bisa jalan minimal 24 jam tanpa intervensi.
- [ ] Error API/scraping tercatat jelas.
- [ ] Credentials tidak pernah masuk repo/log/chat.

---

## 11. Next action

Sebelum implementasi, minta info berikut dari teman:

```text
1. X handle yang dipantau:
2. Website URL:
3. Output mau dikirim ke mana:
4. Realtime target: detik / 1 menit / 5 menit:
5. Konten yang perlu diambil: text saja / media / link / full article:
6. Website milik sendiri dan bisa pasang webhook? ya/tidak:
7. Deploy target: laptop / VPS / Docker / Hermes cron:
```

Jika jawaban belum lengkap, tetap bisa mulai dari MVP polling dengan asumsi default:

- Interval 5 menit.
- Hanya public posts.
- Output Telegram/webhook.
- Store SQLite lokal.
