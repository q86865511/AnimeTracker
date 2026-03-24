# AnimeTracker

一款以 PyQt6 建構的 Windows 桌面應用程式，整合巴哈姆特動畫瘋 API，提供流暢的動畫目錄瀏覽體驗。

## 功能

- **首頁** — 近期熱播動畫卡片格狀瀏覽
- **本季新番** — 依週幾排列的播出時間表，使用動畫封面圖（非單集縮圖）
- **新上架** — 最新上架動畫，支援往下載入更多
- **所有動畫** — Web API 完整動畫清單，含標籤篩選 chips（動作/校園/戀愛等 34 種）
- **推薦主題** — 巴哈姆特編輯推薦分類，點擊可查看該主題所有作品
- **我的最愛** — 本機持久化收藏清單，跨次啟動保留
- **關鍵字搜尋** — 400 ms 防抖，搜尋結果含評分顯示
- **動畫詳情** — 評分（從 API 動態載入）、劇情簡介、導演、標籤、分集列表（點擊直接開啟官網）
- **評分快取** — 查看詳情後評分自動回填至卡片，切換頁面後仍保留
- **封面圖快取** — 磁碟快取，7 天 TTL，離線可用舊快取
- **非同步載入** — 所有 API 與圖片下載均在背景執行，UI 不卡頓
- **巴哈姆特深色主題** — 仿巴哈姆特深色模式配色（極深藍黑背景 + 橘紅強調色）

## 系統需求

- Windows 10 / 11（64-bit）
- Python 3.10 以上（使用 Python 版執行時需要）
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

# 2. 安裝 PyInstaller（若尚未安裝）
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
│   │   ├── client.py               # BahamutAnimeClient（mobile + web API）
│   │   └── models.py               # AnimeItem（含 tags）、AnimeDetail 資料模型
│   ├── ui/
│   │   ├── main_window.py          # 主視窗（score_cache、tag_filter_changed）
│   │   ├── search_bar.py           # 頂部搜尋列（含防抖）
│   │   ├── category_sidebar.py     # 左側靜態導覽側欄
│   │   ├── anime_grid.py           # 多模式卡片格狀版面（世代計數器、tag chips）
│   │   ├── anime_card.py           # 單張動畫卡片（QPushButton 最愛按鈕）
│   │   ├── anime_detail_dialog.py  # 動畫詳情對話框（detail_loaded signal）
│   │   └── theme.py                # 全域暗色主題樣式表
│   ├── workers/
│   │   ├── api_worker.py           # ApiWorker（QRunnable + WorkerSignals）
│   │   └── image_worker.py         # ImageWorker（背景下載封面圖）
│   └── utils/
│       ├── cache.py                # 磁碟圖片快取（%APPDATA%/AnimeTracker/cache）
│       └── store.py                # 本機 JSON 儲存（最愛清單）
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

### 評分快取機制

```
點擊卡片 → AnimeDetailDialog.exec()
                 ↓ detail_loaded(sn, score) signal（detail 載入後）
         MainWindow._score_cache[sn] = score
                 ↓ dialog 關閉
         AnimeGrid.update_card_score(sn, score)   ← 更新當前卡片
         ── 切換頁面時 ──
         display_*() → apply_score_cache(cache)  ← 套用所有已快取評分
```

### 標籤篩選架構

```
AnimeGrid 的 tag chip 點擊
    ↓ tag_filter_changed.emit(tag)
MainWindow._on_tag_filter_changed(tag)
    ↓ _load_all_anime(tags=tag)
ApiWorker → get_web_anime_list(tags=tag)
    ↓ _on_all_anime_loaded(items)
display_all_with_filter(items, active_tag=tag)
```

### API 端點狀態

| 功能 | 端點 | 狀態 |
|------|------|------|
| 首頁 / 分類索引 | mobile `v3/index.php` | ✅ 正常 |
| 搜尋 | mobile `v1/search.php?kw={keyword}` | ✅ 正常（含評分） |
| 詳情 | mobile `v3/video.php?anime_sn={id}` | ✅ 正常（含評分、集數） |
| 所有動畫（tag 篩選）| web `v1/anime_list.php?tags={tag}&page={n}` | ✅ 正常（含 tags 欄位） |
| 分類列表 | mobile `v2/list.php` | ❌ API 版本限制 |

> `v2/list.php` 回傳「APP版本過舊」，已改以 `v3/index.php` 各分區與 web API 提供替代內容。

請求策略：mobile API 間隔 ≥ 1 秒、失敗重試 3 次（指數退避）；web API 使用獨立 session。

### 本機儲存（最愛）

`LocalStore` 以 JSON 持久化至 `%APPDATA%\AnimeTracker\data\`：

```
favorites.json   ← 最愛清單
```

## 資料儲存路徑

| 用途 | 路徑 |
|------|------|
| 封面圖快取 | `%APPDATA%\AnimeTracker\cache\images\{anime_sn}.jpg` |
| 最愛清單 | `%APPDATA%\AnimeTracker\data\favorites.json` |

## 注意事項

- 本應用程式僅供個人學習，請遵守[巴哈姆特使用條款](https://www.gamer.com.tw/tos.php)
- 不提供串流播放功能；點擊集數按鈕或「在動畫瘋觀看」會開啟瀏覽器前往官方頁面
- 卡片評分在首次點開詳情後載入；之後切換頁面仍會保留（評分快取機制）
