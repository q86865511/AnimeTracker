# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AnimeTracker is a Windows desktop application built with PyQt6 that integrates with the Bahamut Anime Crazy (巴哈姆特動畫瘋) API to browse the anime catalog. Features include section-based navigation, weekly schedule view, keyword search with debounce, cover image caching, favorites local storage, and a detail dialog showing episodes and metadata.

## Tech Stack

- **Language**: Python 3.10+
- **GUI**: PyQt6
- **HTTP**: requests (rate-limited, retried)
- **Testing**: pytest + responses (HTTP mocking)
- **Build**: PyInstaller (optional, manual via `build.bat`)
- **Platform**: Windows desktop

## Commands

```bash
# Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt        # runtime only
pip install -r requirements-dev.txt    # includes pytest + responses

# Run
python main.py

# Test
pytest                                          # all tests
pytest tests/test_models.py -v                 # one file
pytest tests/test_api_client.py::test_search_success -v  # one test

# Build .exe (optional, manual)
build.bat                                       # or:
venv\Scripts\pyinstaller.exe AnimeTracker.spec --clean --noconfirm
```

## Architecture

### Async Pattern (critical)

`QRunnable` cannot emit signals — a companion `QObject` subclass (`WorkerSignals`) carries all signals. Workers run in `QThreadPool`; Qt's event loop queues signal delivery back to the main thread automatically.

```
MainWindow ──→ ApiWorker.run() [thread]
                     │ signals.result.emit(data)
               Qt event queue
                     │
               main thread slot
```

Image bytes are emitted as `bytes` (not `QPixmap`) because `QPixmap` is not thread-safe. Conversion happens in the main-thread slot.

### Generation Counter (AnimeGrid)

`AnimeGrid._generation` is incremented on every `display_*()` call. `ImageWorker` results carry the generation number at dispatch time; stale results (from a previous category load) are silently dropped:

```python
if generation != self._generation:
    return  # discard stale image
```

### Score Cache (MainWindow)

`MainWindow._score_cache: dict[int, float]` persists scores across page changes.
- `AnimeDetailDialog` emits `detail_loaded(anime_sn, score)` when `AnimeDetail` loads.
- `MainWindow` connects to this signal before `exec()` to populate the cache.
- After every `display_*` call, `AnimeGrid.apply_score_cache(cache)` updates all visible cards.

### Overlay Button (AnimeCard)

The favourite toggle button is a `QPushButton(parent=self)` positioned absolutely on the card.
**Critical**: `.raise_()` AND `.show()` must be called after `set_image()` to ensure the button stays on top of the cover QLabel in the Z-order.

### PyQt6 Stylesheet Escaping

In f-strings, `{{` → `{` and `}}` → `}`. Every line of a multi-line stylesheet must be an f-string if it contains CSS braces, otherwise `}}` in a plain string produces two literal braces and breaks Qt's parser.

**Correct pattern:**
```python
btn.setStyleSheet(
    f"QPushButton {{ color: {color}; }}"
    f" QPushButton:hover {{ color: {hover_color}; }}"
)
```

### Key Modules

| File | Role |
|------|------|
| `src/api/client.py` | `BahamutAnimeClient` — mobile API (thread-safe, 1 s cooldown, 3-retry); `get_web_anime_list(tags, page)` for tag-filtered 所有動畫 |
| `src/api/models.py` | `AnimeItem`, `AnimeDetail` dataclasses; `AnimeItem.tags: list[str]`; handles both camelCase and snake_case fields; filters `/2KU/` episode thumbnails |
| `src/utils/cache.py` | `ImageCache` — disk cache at `%APPDATA%/AnimeTracker/cache/images/{anime_sn}.jpg`, 7-day TTL |
| `src/utils/store.py` | `LocalStore` — JSON persistence at `%APPDATA%/AnimeTracker/data/`; used for favorites |
| `src/workers/api_worker.py` | `ApiWorker(QRunnable)` + `WorkerSignals(QObject)` — generic: wraps any callable |
| `src/workers/image_worker.py` | `ImageWorker(QRunnable)` — emits `loaded(anime_sn, bytes)` or `failed(anime_sn)` |
| `src/ui/theme.py` | `Colors` constants + `DARK_STYLESHEET` string applied once via `QApplication.setStyleSheet()` |
| `src/ui/main_window.py` | Owns all shared resources; `_score_cache`; routes signals; handles navigation IDs |
| `src/ui/category_sidebar.py` | Static navigation sidebar (6 items, no dynamic categories) |
| `src/ui/anime_grid.py` | Scrollable card grid; generation counter; `apply_score_cache()`; `tag_filter_changed` signal |
| `src/ui/anime_card.py` | 185×310 px card; QPushButton overlay for favourites; `set_image(bytes)` from main thread |
| `src/ui/anime_detail_dialog.py` | Modal dialog; `detail_loaded(sn, score)` signal; fav toggle |

### Bahamut API Reference

Mobile API base: `https://api.gamer.com.tw/mobile_app/anime/`
Web API base: `https://api.gamer.com.tw/anime/v1/`

| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| `get_index()` | mobile `v3/index.php` | ✅ Working | Returns hotAnime, newAdded, newAnime, category |
| `search(kw)` | mobile `v1/search.php` | ✅ Working | Items include `score` field |
| `get_anime_detail(anime_sn)` | mobile `v3/video.php` | ✅ Working | Full detail + episodes + score |
| `get_web_anime_list(tags, page)` | web `v1/anime_list.php` | ✅ Working | Tags-filterable list for 所有動畫 |
| `get_anime_list(c, page, sort)` | mobile `v2/list.php` | ❌ Broken | Returns "APP版本過舊" |

Mobile API required headers: `User-Agent: Animad/1.16.16 …`, `X-Bahamut-App-Android`, `X-Bahamut-App-Version: 328`.
Web API uses browser `User-Agent` + `Referer: https://ani.gamer.com.tw/`.

### Navigation ID Map (CategorySidebar / MainWindow)

| ID | Section | Data Source |
|----|---------|-------------|
| -1 | 首頁 | hotAnime from cached index |
| -2 | 我的最愛 | favorites LocalStore |
| -10 | 本季新番 | newAnime.date from cached index (grouped by weekday) |
| -11 | 新上架 | newAdded from cached index + load-more from newAnime |
| -12 | 所有動畫 | web API `anime_list.php` (with ANIME_TAGS filter chips) |
| -13 | 推薦主題 | editorial category panels from index.category |

### v3/index.php Response Structure

```
data:
  hotAnime:        list[AnimeItem-like]    # 14 items
  newAdded:        list[AnimeItem-like]    # 20 items
  newAnime:
    date:          list[AnimeItem-like]    # 56 items (weekly schedule, /2KU/ covers filtered)
    popular:       list[AnimeItem-like]    # 56 items
  category:        list[{title, intro, list[AnimeItem-like]}]   # 8 editorial picks
```

### AnimeItem Field Variants

Different endpoints use different casing. `from_dict()` handles both:

| Field | hotAnime / newAdded / category / web API | search |
|-------|------------------------------------------|--------|
| anime_sn | `animeSn` (str) | `anime_sn` (int) |
| acg_sn | `acgSn` (str) | `acg_sn` (int) |
| title | `title` or `animeName` fallback | `title` |
| score | absent (defaults 0; use detail dialog) | `score` (float) |
| popular | `popular` (str) | `popular` (int) |
| tags | `tags` (list or comma-string, web API) | absent |

### Cover URL Logic

- If `cover` field contains `/2KU/` or `/2ku/` → episode thumbnail → blank it out
- Fallback URL: `https://img.bahamut.com.tw/anime/acg/{acg_sn}.jpg`

### Local Storage

`LocalStore` uses `StoredAnime` dataclass for JSON persistence. Only favorites (no watchlist):

```python
items = fav_store.to_anime_items()  # list[AnimeItem] with cover_url derived from acg_sn
```
