# CopyRight

將原本分散的 PDF 解析腳本整理成可維運的 API 架構，支援「解析 → 寫入資料庫（MongoDB）」的實務流程。

## 功能

- **Metadata 解析與寫入**：從指定頁面擷取 Lexis front-matter。
- **Footnote 解析與寫入**：擷取腳註並自動回填對應 `No`。
- **Opinion 解析與寫入**：擷取 Opinion 段落、頁碼區間與超連結。
- **批次 Footnote 匯入**：掃描 `data/` 下所有 PDF。

## 專案結構

```text
app/
  main.py                    # FastAPI 入口
  config.py                  # 環境參數設定
  schemas.py                 # API request/response models
  repository.py              # MongoDB 存取層
  parsers/
    footnote_parser.py
    metadata_parser.py
    opinion_parser.py
  services/
    ingest_service.py        # 解析+寫入整合
```

舊檔案 `footnote.py`、`lexis_metadata_extractor.py`、`opinion.py` 已改為 **legacy CLI wrapper**，內部改呼叫新 service。

## 環境變數

可用 `.env` 或系統環境變數：

- `MONGO_URI`（預設 `mongodb://localhost:27017`）
- `MONGO_DB`（預設 `copyright`）
- `DATA_DIR`（預設 `data`）

## 啟動 API

```bash
uvicorn app.main:app --reload
```

## API endpoints

### 1) 匯入 metadata

`POST /api/metadata/ingest`

```json
{
  "pdf_filename": "cp01.pdf",
  "start_page": 44
}
```

### 2) 匯入 footnotes

`POST /api/footnotes/ingest`

```json
{
  "pdf_filename": "cp01.pdf"
}
```

### 3) 匯入 opinions

`POST /api/opinions/ingest`

```json
{
  "pdf_filename": "cp01.pdf"
}
```

### 4) 批次匯入 footnotes

`POST /api/footnotes/ingest-all`

## Legacy CLI 用法

```bash
python lexis_metadata_extractor.py --pdf cp01.pdf --start-page 44
python opinion.py --pdf cp01.pdf
python footnote.py
```
