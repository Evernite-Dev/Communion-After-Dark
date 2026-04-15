# Communion After Dark — Personal Archive

Personal archive of [Communion After Dark](https://www.communionafterdark.com),
a weekly podcast broadcasting Gothic/Industrial, EBM, and Electro music since 2008.

---

## Directory layout

```
Communion After Dark/
├── scraper/            ← archiver scripts (run on any OS)
├── player/             ← GTK4 Flatpak media player (Linux)
├── archive/            ← downloaded audio + artwork (created by scraper)
│   ├── 2025/
│   │   └── 2025-12-29_best-of-2025/
│   │       ├── audio.mp3       ← ID3-tagged MP3
│   │       ├── artwork.jpg     ← episode cover art
│   │       └── metadata.json   ← full metadata + tracklist
│   └── ...
└── data/
    └── cad_archive.db  ← SQLite index (created automatically)
```

---

## Scraper — quick start

### 1. Install Python dependencies

```bash
cd scraper
pip install -r requirements.txt
```

### 2. First run — discover all episodes

```bash
# Fastest: just the RSS feed (covers ~100 most recent episodes)
python main.py discover --rss

# Full discovery: RSS + all 18 year-archive pages (2008–2025)
python main.py discover --all
```

### 3. Scrape episode metadata and tracklists

```bash
# Process 20 episodes at a time (each request is rate-limited to 4s apart)
python main.py scrape --batch 20
```

Run repeatedly until `status` shows all episodes scraped.

### 4. Download audio files (be conservative — these are large MP3s)

```bash
# Start with a small test batch
python main.py download --audio --batch 5

# Once comfortable, larger batches
python main.py download --audio --batch 20
```

Each MP3 is ~150–300 MB.  The full archive (~900 episodes × 18 years) is
several hundred GB — plan storage accordingly.

### 5. Download artwork

```bash
python main.py download --artwork
```

### 6. Embed ID3 tags

```bash
python main.py tag
```

### 7. Check progress at any time

```bash
python main.py status
```

### Full pipeline in one command (run on a cron/schedule)

```bash
python main.py run --batch 10
```

Re-run this daily or weekly until the archive is complete.

---

## Scraper — rate limiting

The default settings in `scraper/config.py` are intentionally conservative:

| Setting | Default | Effect |
|---|---|---|
| `DELAY_BETWEEN_REQUESTS` | 4.0 s | Minimum gap between any two HTTP requests |
| `DELAY_BETWEEN_BATCHES` | 30.0 s | Extra pause after every batch of episodes |
| `BATCH_SIZE` | 10 | Episodes per batch |

Adjust these in `config.py` if needed.  Do **not** set `DELAY_BETWEEN_REQUESTS`
below 2 seconds.

---

## What gets saved per episode

| File | Contents |
|---|---|
| `audio.mp3` | Full episode MP3, ID3-tagged with title, date, description, artwork, and a JSON tracklist in a custom TXXX frame |
| `artwork.jpg` | Episode cover art (from Squarespace CDN) |
| `metadata.json` | All metadata + full tracklist in JSON format |

### metadata.json fields

```json
{
  "id": 42,
  "title": "Communion After Dark - December 29th, 2025 Edition (Best Of 2025)",
  "pub_date": "2025-12-29",
  "description": "...",
  "artwork_url": "https://...",
  "audio_url": "https://www.buzzsprout.com/...",
  "duration_sec": 7200,
  "year": 2025,
  "category": "annual",
  "page_url": "https://www.communionafterdark.com/listennow/...",
  "tracklist": [
    {
      "position": 1,
      "timestamp": "00:25",
      "artist": "Agnis",
      "title": "Gothess",
      "album": "Gothess",
      "label": "DarkTunes Music Group",
      "country": "Poland"
    }
  ]
}
```

---

## Media Player (Linux Flatpak)

The player reads your local archive and presents a 3-panel UI:
- **Left** — year/category browser
- **Centre** — episode list with date and title
- **Right** — episode artwork, description, and full tracklist

### Run without Flatpak (development)

Requires Python 3.11+, PyGObject (GTK4 + libadwaita), and GStreamer Python bindings.

```bash
# Debian/Ubuntu
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
                 gstreamer1.0-python3-plugin-loader \
                 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad

cd player
python -m cad_player.main
```

### Build and install as Flatpak

```bash
cd player
flatpak-builder --install --user build com.communionafterdark.CadPlayer.yml
flatpak run com.communionafterdark.CadPlayer
```

---

## Respecting the website

This archiver is designed for personal, non-commercial use only.

- Uses the **official Buzzsprout RSS feed** as the primary discovery source
- Adds a **4-second delay** between every HTTP request to the Squarespace site
- Identifies itself honestly via a custom `User-Agent` header
- Skips paths disallowed in `robots.txt` (config, search, account, API, static)
- Does **not** attempt to bypass any access controls or authentication
- Downloads audio directly from **Buzzsprout** (the podcast's own CDN),
  not from the Squarespace server

Please support Communion After Dark at https://www.communionafterdark.com/donate
