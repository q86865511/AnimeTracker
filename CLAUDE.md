# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AnimeTracker is a Windows desktop application built with PyQt6 that integrates with the Bahamut Anime Crazy (巴哈姆特動畫瘋) mobile API to browse the anime catalog. Features include section-based navigation (hotAnime, newAnime, newAdded, editorial categories), keyword search with debounce, cover image caching, favorites/watchlist local storage, and a detail dialog showing episodes and metadata.

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

`AnimeGrid._generation` is incremented on every `display_anime_list()` call. `ImageWorker` results carry the generation number at dispatch time; stale results (from a previous category load) are silently dropped:

```python
if generation != self._generation:
    return  # discard stale image
```

### Overlay Buttons (AnimeCard)

Favorite and watchlist toggle buttons are overlaid on cover images as `_OverlayBtn(QLabel)` subclass instances. **Critical**: instance-level `mousePressEvent` overrides are NOT recognized by PyQt6's C++ virtual dispatch. A proper subclass with `pyqtSignal` is required:

```python
class _OverlayBtn(QLabel):
    pressed = pyqtSignal()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed.emit()
            event.accept()   # prevents propagation to parent AnimeCard
```

### Key Modules

| File | Role |
|------|------|
| `src/api/client.py` | `BahamutAnimeClient` — thread-safe HTTP, 1 s cooldown, 3-retry exponential backoff; `_parse_items()` handles multiple response shapes |
| `src/api/models.py` | `AnimeItem`, `AnimeDetail` dataclasses; each has `from_dict()` classmethod; handles both camelCase and snake_case fields |
| `src/utils/cache.py` | `ImageCache` — disk cache at `%APPDATA%/AnimeTracker/cache/images/{anime_sn}.jpg`, 7-day TTL |
| `src/utils/store.py` | `LocalStore` — JSON persistence at `%APPDATA%/AnimeTracker/data/`; used for favorites and watchlist |
| `src/workers/api_worker.py` | `ApiWorker(QRunnable)` + `WorkerSignals(QObject)` — generic: wraps any callable |
| `src/workers/image_worker.py` | `ImageWorker(QRunnable)` — emits `loaded(anime_sn, bytes)` or `failed(anime_sn)` |
| `src/ui/theme.py` | `Colors` constants + `DARK_STYLESHEET` string applied once via `QApplication.setStyleSheet()` |
| `src/ui/main_window.py` | Owns all shared resources; caches `_index_data`; routes signals; handles navigation IDs |
| `src/ui/category_sidebar.py` | Navigation sidebar; static items + dynamic editorial categories added after index loads |
| `src/ui/anime_grid.py` | Scrollable card grid; owns generation counter; dispatches `ImageWorker` per card |
| `src/ui/anime_card.py` | 185×310 px card; overlay `_OverlayBtn` for fav/watchlist; `set_image(bytes)` from main thread |
| `src/ui/anime_detail_dialog.py` | Modal dialog; shows `AnimeItem` data immediately, fetches `AnimeDetail` async on open; fav/watchlist toggles |

### Bahamut API Reference

Base: `https://api.gamer.com.tw/mobile_app/anime/`

| Method | Endpoint | Status | Notes |
|--------|----------|--------|-------|
| `get_index()` | `v3/index.php` | ✅ Working | Returns hotAnime, newAdded, newAnime, category |
| `search(kw)` | `v1/search.php` | ✅ Working | Items include `score` field |
| `get_anime_detail(anime_sn)` | `v3/video.php` | ✅ Working | Full detail + episodes |
| `get_anime_list(c, page, sort)` | `v2/list.php` | ❌ Broken | Returns "APP版本過舊" for all header versions |

Required headers on every request: `User-Agent: Animad/1.16.16 …`, `X-Bahamut-App-Android`, `X-Bahamut-App-Version: 328`.

### Navigation ID Map (CategorySidebar / MainWindow)

| ID | Section |
|----|---------|
| -1 | 首頁 (hotAnime from cached index) |
| -2 | 我的最愛 (favorites LocalStore) |
| -3 | 觀看清單 (watchlist LocalStore) |
| -10 | 本季新番 (newAnime.date from cached index) |
| -11 | 新上架 (newAdded from cached index) |
| -12 | 熱門動畫 (hotAnime from cached index) |
| -20 to -27 | 推薦主題 0-7 (editorial categories from index.category[]) |

### v3/index.php Response Structure

```
data:
  hotAnime:        list[AnimeItem-like]    # 14 items
  newAdded:        list[AnimeItem-like]    # 20 items
  newAnime:
    date:          list[AnimeItem-like]    # 56 items (schedule format)
    popular:       list[AnimeItem-like]    # 56 items
  category:        list[{title, intro, list[AnimeItem-like]}]   # 8 editorial picks
```

### AnimeItem Field Variants

Different endpoints use different casing. `from_dict()` handles both:

| Field | hotAnime / newAdded / category | search |
|-------|-------------------------------|--------|
| anime_sn | `animeSn` (str) | `anime_sn` (int) |
| acg_sn | `acgSn` (str) | `acg_sn` (int) |
| score | absent (defaults 0) | `score` (float) |
| popular | `popular` (str) | `popular` (int) |

### Local Storage

`LocalStore` uses `StoredAnime` dataclass for JSON persistence. To convert back to `AnimeItem`:

```python
items = store.to_anime_items()  # list[AnimeItem] with cover_url derived from acg_sn
```
