import os
import re
from pymongo import MongoClient, UpdateOne

# ==========================================
# 基本設定與資料庫連線參數
# ==========================================
from dotenv import load_dotenv

load_dotenv()

# MongoDB 連線設定
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")  # 您的 MongoDB 連線字串
DB_NAME = "copyright"                    # 目標資料庫名稱
COLL_NAME = "TC_new_format_opinion"         # 這裡讀取 opinion_parser 存入的目標 collection

BATCH_SIZE = 500                         # 批次寫入的大小
DRY_RUN = False                          # 設定為 True 時只會印出結果，不會真的寫入資料庫
PROJECTION = {"urls_dic": 1}             # 為了加速，從資料庫讀取時只拿取 urls_dic 欄位

# ==========================================
# 分類規則的正則表達式 (Regular Expressions)
# ==========================================

# 匹配案件名稱例如 "A v. B"
RE_CASE_V = re.compile(r"\b[A-Z][A-Za-z0-9.&' -]+ v\. [A-Z][A-Za-z0-9.&' -]+")
# 匹配常見的案件前綴字例如 "In re" 或 "Ex parte"
RE_CASE_ALT = re.compile(r"\b(In re|Ex parte)\b", re.I)
# 匹配各種判例彙編 (Reporters) 的縮寫，例如 U.S., S.Ct., F.3d 等等
RE_REPORTER = re.compile(
    r"\b(\d+\s+(U\.S\.|S\.Ct\.|L\.Ed\.|F\.3d|F\.2d|F\.Supp\. ?\d*|USPQ|N\.E\. ?\d*|N\.W\. ?\d*|P\. ?\d*|So\. ?\d*|A\. ?\d*|Cal\.|N\.Y\.|Mass\.|Tex\.))\b"
)

# 匹配美國法典 (USC)
RE_USC = re.compile(r"\b\d+\s*U\.?S\.?C\.?\b", re.I)
# 匹配特定條文的關鍵字
RE_SECTION_WORD = re.compile(r"\bsection\s+\d+", re.I)
# 匹配聯邦法規規則集 (CFR)
RE_CFR = re.compile(r"\b\d+\s*C\.?F\.?R\.?\b", re.I)
# 匹配法庭規則，例如聯邦民事訴訟規則 (Fed. R. Civ. P.)
RE_RULES = re.compile(r"(fed\.\s*r\.)|(f\.r\.(civ|app|evid)\.\s*p\.)|(local\s+rule)", re.I)
# 匹配美國憲法
RE_CONS = re.compile(r"u\.s\.\s*const\.", re.I)
# 匹配常見的次要法學文獻或專著名稱
RE_TREATISE = re.compile(r"(nimmer|patry|mccarthy|wright\s*&\s*miller|restatement|matthew\s+bender)", re.I)

# 這個正則用來抓取「法條碎片」類別，也就是只由數字、符號、跟少量字母組成的字串
RE_MOSTLY_NUMERIC_SYMBOLS = re.compile(r"^[\s\d§().,;a-zA-Z-]+$")


def looks_like_statute_fragment(text: str) -> bool:
    """
    判斷傳入的字串是否看起來像是單純的法條碎片。
    如果是空字串、或者是案件名稱，就會直接回傳 False。
    """
    t = (text or "").strip()
    if not t:
        return False
    # 如果字串包含了上述允許範圍以外的字元，就不是法條碎片
    if not RE_MOSTLY_NUMERIC_SYMBOLS.match(t):
        return False
    # 必須至少包含一個數字
    if not re.search(r"\d", t):
        return False
    # 避免把案件名稱誤判為法條碎片
    if RE_CASE_V.search(t):
        return False
    return True


def classify_category(raw_text: str, link: str):
    """
    這個函式負責將超連結與其關聯文字，分類到 7 大類別之中。
    回傳的格式為 (分類名稱, 判定依據, 信心水準, 規則編號)。
    
    七大類別為：
      A. Lexis Commentary
      B. Statutes / Legislation
      C. Cases
      D. Secondary Sources
      E. Regulations / Court Rules
      F. Constitution
      G. Others
    """
    t = (raw_text or "").strip()
    l = (link or "").strip().lower()

    # --- 類別 A: Lexis Commentary (LexisNexis 的編者註解、Headnote 等) ---
    if "lnhnref" in l or re.match(r"^hn\d+", t, re.I) or "headnote" in t.lower():
        return "Lexis Commentary", ("link_collection" if "lnhnref" in l else "raw_text_regex"), 1.0, "A_HN"

    # --- 優先使用超連結本身的特徵來進行判定 ---
    if "collection=statutes-legislation" in l:
        return "Statutes / Legislation", "link_collection", 1.0, "B_link_statutes"

    if "collection=cases" in l:
        return "Cases", "link_collection", 1.0, "C_link_cases"

    if "collection=analytical-materials" in l:
        return "Secondary Sources", "link_collection", 1.0, "D_link_analytical"

    if "collection=law-reviews-journals" in l:
        return "Secondary Sources", "link_collection", 1.0, "D_link_lawreviews"  # 期刊論文也歸類為次要來源

    if "collection=dockets" in l:
        return "Others", "link_collection", 1.0, "G_link_dockets"

    # --- 若連結中沒有明確的分類，則使用文字特徵 (正則表達式) 來判定 ---
    
    # 類別 B: Statutes / Legislation (法案或立法)
    if ("§" in t) or RE_USC.search(t) or RE_SECTION_WORD.search(t) or looks_like_statute_fragment(t):
        return "Statutes / Legislation", "raw_text_regex", 0.9, "B_regex"

    # 類別 E: Regulations / Court Rules (法規或法庭規則)
    if RE_CFR.search(t) or RE_RULES.search(t):
        return "Regulations / Court Rules", "raw_text_regex", 0.9, "E_regex"

    # 類別 F: Constitution (憲法)
    if RE_CONS.search(t) or re.search(r"\bconstitution\b", t, re.I):
        return "Constitution", "raw_text_regex", 0.85, "F_regex"

    # 類別 D: Secondary Sources (次要文獻，例如實務指南或法律評論)
    if RE_TREATISE.search(t):
        return "Secondary Sources", "raw_text_regex", 0.85, "D_regex"

    # 類別 C: Cases (判例)
    if RE_CASE_V.search(t) or RE_CASE_ALT.search(t) or RE_REPORTER.search(t):
        return "Cases", "raw_text_regex", 0.85, "C_regex"

    # 類別 G: Others (其他無法辨識的類別)
    return "Others", "none", 0.3, "G_fallback"


def main():
    # 建立 MongoDB 連線
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLL_NAME]

    total_docs = 0
    updated_docs = 0
    ops = []

    # 找出所有包含 urls_dic 的文件
    cursor = col.find({"urls_dic": {"$exists": True}}, PROJECTION)
    
    for doc in cursor:
        total_docs += 1
        urls = doc.get("urls_dic", []) or []
        new_urls = []
        dirty = False  # 標記這份文件是否需要被更新

        for u in urls:
            raw_text = u.get("raw_text", "") or ""
            link = u.get("link", "") or ""

            # 呼叫分類函式取得分類結果
            category, signal, conf, rule_id = classify_category(raw_text, link)

            # 比較目前資料庫裡的分類資料，跟我們剛剛判定出來的有沒有不一樣
            need_update = (
                u.get("category") != category or
                u.get("source_signal") != signal or
                float(u.get("confidence", -1)) != float(conf) or
                u.get("rule_id") != rule_id
            )
            
            if need_update:
                # 複製舊有的 url 字典並更新欄位
                nu = dict(u)
                nu.update({
                    "category": category,
                    "source_signal": signal,
                    "confidence": conf,
                    "rule_id": rule_id,
                })
                new_urls.append(nu)
                dirty = True
            else:
                new_urls.append(u)

        # 如果文件內的網址有經過更新分類，就加入更新佇列 (ops) 準備寫入資料庫
        if dirty:
            updated_docs += 1
            if not DRY_RUN:
                ops.append(
                    UpdateOne({"_id": doc["_id"]}, {"$set": {"urls_dic": new_urls}})
                )
                # 批次寫入，避免一次寫入太多筆造成記憶體與效能問題
                if len(ops) >= BATCH_SIZE:
                    col.bulk_write(ops, ordered=False)
                    ops = []

    # 迴圈結束後，把剩下的佇列資料也寫入資料庫
    if ops and not DRY_RUN:
        col.bulk_write(ops, ordered=False)

    print(f"處理完成！總共掃描了 {total_docs} 筆文件，並更新了 {updated_docs} 筆。 (測試模式: {DRY_RUN})")


if __name__ == "__main__":
    main()
