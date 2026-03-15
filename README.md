# CopyRight

這個專案是一個**美國版權法案例解析與資料庫建置系統**，支援將 PDF 解析後，層層粹取、清理、打標，並寫入 MongoDB，最終形成結構化的法學研究庫。專案包含可維運的 FastAPI 服務，以及接續的資料清理與分析腳本。

## 系統資料處理流程 (Pipeline)

整體流程分為兩大階段：「API 擷取入庫」與「資料後處理與擴充」。

### 第一階段：API 解析匯入 (PDF -> MongoDB)
透過 FastAPI 的各種 endpoints，自動解析 LexisNexis 下載的 PDF 文件，建立基礎資料庫：
1. **Metadata 擷取 (`/api/metadata/ingest`)**：
   - 擷取案件核心與周邊資訊（法官、律師、歷審紀錄、Core Terms 等）。
   - 寫入集合：`TC_index_todo`
2. **Footnote 擷取 (`/api/footnotes/ingest`)**：
   - 擷取腳註文字，並自動透過 `TC_index_todo` 映射對應的案件 No。
   - 寫入集合：`TC_footNote_testing`
3. **Opinion 擷取 (`/api/opinions/ingest`)**：
   - 擷取法官意見書的正文內容，並萃取內含的 LexisNexis 超連結與對應文字 (`urls_dic`)。
   - 寫入集合：`TC_new_format_opinion`

### 第二階段：資料後處理與擴充 (Post-Processing & Enrichment)
基礎資料匯入後，可透過根目錄下的獨立腳本與 Jupyter Notebooks 進行進一步的清洗與標註：
1. **Metadata 清理與轉型 (`index_preprocess.py`)**：
   - 清除文字中殘留的 Lexis 腳註標記（如 `[*1]`）。
   - 將字串格式的時間轉型為 timezone-aware datetime 格式，便於後續日期查詢。
2. **引用連結分類 (`link_classify.py` / `link_classify.ipynb`)**：
   - 將 `urls_dic` 中的引用連結，按正則表達式自動分類為 7 大類別（如 Cases, Statutes, Secondary Sources 等 A~G 類別）。
3. **判例引用庫建立 (`buildup_case_urn.ipynb`)**：
   - 從被分類為 Cases 的連結中，提取唯一的 Lexis URN，建立獨立的引用連結對照集合 `TC_case_link`。
4. **法院層級標註 (`circuit_level.ipynb`)**：
   - 根據法院名稱，自動標註並寫入 Court Level（如 District, Circuit, Supreme）。
5. **法官背景資料庫建置 (`judge.ipynb`)**：
   - 提取案件中的法官名單，自動爬取 Ballotpedia，獲取法官黨派、學歷、經歷等背景資料並儲存至 `TC_judges` 集合中。

---

## 專案結構

```text
CopyRight/
├── app/
│   ├── main.py                    # FastAPI 服務入口
│   ├── config.py                  # 環境變數與配置
│   ├── schemas.py                 # API request/response models
│   ├── repository.py              # MongoDB 存取層
│   ├── parsers/                   # PDF 內容解析模組
│   │   ├── footnote_parser.py
│   │   ├── metadata_parser.py
│   │   └── opinion_parser.py
│   └── services/
│       └── ingest_service.py      # 整合解析與資料庫寫入的業務邏輯
├── index_preprocess.py            # Metadata 清理與日期轉型腳本
├── link_classify.py               # 連結自動分類腳本 (A~G 類別)
├── buildup_case_urn.ipynb         # 提取 Lexis URN 並建立引用庫
├── circuit_level.ipynb            # 自動判別法院級別腳本
├── judge.ipynb                    # 爬取法官背景資料腳本
├── link_classify.ipynb            # 連結分類 (Notebook 版本)
└── setting_index.ipynb            # PDF 前置測試與解析草稿
```

（舊檔案 `footnote.py`、`lexis_metadata_extractor.py`、`opinion.py` 已改為 **legacy CLI wrapper**，內部改呼叫新的 `app/services`）

---

## 環境變數

可使用 `.env` 檔案或系統環境變數進行設定：

- `MONGO_URI`（預設 `mongodb://localhost:27017`）
- `MONGO_DB`（預設 `copyright`）
- `DATA_DIR`（預設 `data`）

## 啟動 API 服務

```bash
uvicorn app.main:app --reload
```

## API Endpoints

### 1) 匯入 metadata
`POST /api/metadata/ingest`
```json
{
  "pdf_filename": "cp01.pdf",
  "start_page": 1
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
如果在舊有的開發動線下：
```bash
python lexis_metadata_extractor.py --pdf cp01.pdf --start-page 44
python opinion.py --pdf cp01.pdf
python footnote.py
```
