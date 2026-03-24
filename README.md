# AnimeTracker

一款以 PyQt6 建構的 Windows 桌面應用程式，整合巴哈姆特動畫瘋行動版 API，提供流暢的動畫目錄瀏覽體驗。

## 功能

- **首頁 / 熱門動畫** — 即時熱門、本季新番、新上架分類瀏覽
- **推薦主題** — 巴哈姆特每日編輯推薦（動態載入，無需額外請求）
- **關鍵字搜尋** — 400ms 防抖節流，搜尋結果含評分顯示
- **動畫詳情** — 劇情簡介、評分、導演、製作公司、分集列表（點擊集數直接開啟官網）
- **我的最愛** — 本機持久化收藏清單，跨次啟動保留
- **觀看清單** — 本機持久化待看清單，跨次啟動保留
- **封面圖快取** — 磁碟快取，7 天 TTL，離線可用舊快取
- **非同步載入** — 所有 API 與圖片下載均在背景執行，UI 不卡頓
- **巴哈姆特深色主題** — 仿巴哈姆特深色模式配色（極深藍黑背景 + 橘紅強調色）

## 系統需求

- Windows 10 / 11（64-bit）
- Python 3.10 以上（使用 Python 版執行）
- 或直接執行 `dist\AnimeTracker\AnimeTracker.exe`（免安裝 Python）

## 安裝與執行

### 使用 Python 執行

```bash
# 1. 建立虛擬環境
python -m venv venv
venv\Scripts\activate

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 執行
python main.py
```

### 使用 .exe 執行

```
dist\AnimeTracker\AnimeTracker.exe
```

## 編譯 .exe（選用）

若需要重新編譯獨立執行檔：

```bash
# 1. 確認虛擬環境已啟動
venv\Scripts\activate

# 2. 安裝 PyInstaller
pip install pyinstaller

# 3. 編譯（或直接雙擊 build.bat）
venv\Scripts\pyinstaller.exe AnimeTracker.spec --clean --noconfirm
```

輸出位置：`dist\AnimeTracker\AnimeTracker.exe`

> **注意**：`.exe` 不會自動生成，需手動執行 `build.bat` 或上述指令。

## 開發

```bash
# 安裝開發依賴（包含測試框架）
pip install -r requirements-dev.txt

# 執行所有測試
pytest

# 執行特定測試檔
pytest tests/test_models.py -v
pytest tests/test_api_client.py::test_search_success -v
```

## 專案結構

```
AnimeTracker/
├── main.py                          # 程式進入點
├── requirements.txt                 # 執行期依賴
├── requirements-dev.txt             # 開發 / 測試依賴
├── AnimeTracker.spec                # PyInstaller 編譯設定
├── build.bat                        # 一鍵編譯腳本（手動執行）
├── src/
│   ├── api/
│   │   ├── client.py               # BahamutAnimeClient（速率限制、重試）
│   │   └── models.py               # AnimeItem、AnimeDetail 資料模型
│   ├── ui/
│   │   ├── main_window.py          # 主視窗（協調所有元件）
│   │   ├── search_bar.py           # 頂部搜尋列（含防抖）
│   │   ├── category_sidebar.py     # 左側導覽側欄（含動態推薦主題）
│   │   ├── anime_grid.py           # 動畫卡片格狀版面（世代計數器）
│   │   ├── anime_card.py           # 單張動畫卡片（含最愛/觀看清單按鈕）
│   │   ├── anime_detail_dialog.py  # 動畫詳情對話框
│   │   └── theme.py                # 全域暗色主題樣式表
│   ├── workers/
│   │   ├── api_worker.py           # ApiWorker（QRunnable + WorkerSignals）
│   │   └── image_worker.py         # ImageWorker（背景下載封面圖）
│   └── utils/
│       ├── cache.py                # 磁碟圖片快取（%APPDATA%/AnimeTracker/cache）
│       └── store.py                # 本機 JSON 儲存（最愛 / 觀看清單）
└── tests/
    ├── test_models.py              # 資料模型解析測試
    └── test_api_client.py          # API 客戶端測試（HTTP mock）
```

## 架構說明

### 非同步模式

所有耗時操作（API、圖片下載）均使用 `QRunnable` + `QThreadPool`：

```
主執行緒 → ApiWorker.run() [工作執行緒]
                 ↓ signals.result.emit()
         Qt 事件佇列 → 主執行緒 slot
```

`WorkerSignals(QObject)` 是 `QRunnable` 的伴隨物件，負責跨執行緒安全地發出信號。圖片以 `bytes` 傳遞（非 QPixmap），確保 `QPixmap` 只在主執行緒建立。

### 世代計數器（AnimeGrid）

每次切換頁面時 `_generation` 遞增，`ImageWorker` 結果帶有派送時的世代號碼，過期結果直接丟棄：

```python
if generation != self._generation:
    return  # 丟棄過期圖片回調
```

### 本機儲存（最愛 / 觀看清單）

`LocalStore` 以 JSON 持久化至 `%APPDATA%\AnimeTracker\data\`：

```
favorites.json   ← 最愛清單
watchlist.json   ← 觀看清單
```

### API 端點狀態

使用巴哈姆特行動版非官方 API：

| 功能 | 端點 | 狀態 |
|------|------|------|
| 首頁 / 所有分類 | `v3/index.php` | ✅ 正常 |
| 搜尋 | `v1/search.php?kw={keyword}` | ✅ 正常（含評分） |
| 詳情 | `v3/video.php?anime_sn={id}` | ✅ 正常 |
| 分類列表 | `v2/list.php?c={0-13}&page={n}` | ❌ API 版本限制 |

> `v2/list.php` 目前回傳「APP版本過舊」錯誤，已改以 `v3/index.php` 的各分區提供替代內容。

請求間隔 ≥ 1 秒，失敗時最多重試 3 次（指數退避）。

## 資料儲存路徑

| 用途 | 路徑 |
|------|------|
| 封面圖快取 | `%APPDATA%\AnimeTracker\cache\images\{anime_sn}.jpg` |
| 最愛清單 | `%APPDATA%\AnimeTracker\data\favorites.json` |
| 觀看清單 | `%APPDATA%\AnimeTracker\data\watchlist.json` |

## 注意事項

- 本應用程式僅供個人學習，請遵守[巴哈姆特使用條款](https://www.gamer.com.tw/tos.php)
- 不提供串流播放功能；點擊集數按鈕或「在動畫瘋觀看」會開啟瀏覽器前往官方頁面
- 評分資料僅搜尋結果具有；熱門/新番頁面依 API 限制不提供評分
