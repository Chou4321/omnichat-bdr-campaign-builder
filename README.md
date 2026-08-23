# Omnichat BDR Campaign Builder

以 Streamlit 建立的 Campaign Builder + Industry Knowledge Template Engine。專案不使用任何 AI API、CRM、寄信或登入服務。

## 功能

- 活動管理
- Email 信件
- LINE 邀約訊息
- 產業別資料庫

活動只需建立一次。Email 與 LINE 會共用活動摘要、介紹、四個活動重點、日期時間、連結與 Banner。產業別資料庫由使用者人工維護且預設不引用；開啟引用時仍以活動內容為最高權重。

## 本機啟動

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Windows 可將 `.venv/bin/` 改為 `.venv\Scripts\`。

## Streamlit Community Cloud

1. 將此資料夾推送至 GitHub repository。
2. 在 Streamlit Community Cloud 建立 app。
3. Entrypoint 設為 `app.py`。
4. 在 App Settings → Secrets 設定 Supabase：

```toml
[supabase]
url = "https://YOUR_PROJECT.supabase.co"
secret_key = "sb_secret_YOUR_SECRET_KEY"
```

5. 在 Supabase SQL Editor 執行
   `supabase/migrations/001_industry_templates.sql`。

專案沒有綁定 IP 或本機絕對路徑。`.streamlit/config.toml` 只設定 headless、上傳限制與主題。

## Storage

- `data/campaigns.json`：活動資料
- Supabase `industry_templates`：產業 Knowledge Base 的永久主要資料來源
- `data/industry_templates.json`：首次移轉來源與唯讀備份，不再接收網頁寫入
- `data/templates.json`：既有人工文案資料（保留相容性，不顯示於主導覽）
- `uploads/`：本機上傳素材

所有資料存取集中於 `storage.py`。產業資料由 Supabase 永久保存，首次連線會將 JSON 備份中尚未存在的資料移轉一次；連線失敗時會顯示錯誤，且不會回退寫入 Streamlit 本機 JSON。活動資料與上傳素材目前仍使用本機檔案。

## 安全與版本控制

- 不包含 OpenAI、Claude、Gemini 或其他 AI SDK。
- `.streamlit/secrets.toml`、虛擬環境、快取、log 與使用者上傳素材不會提交 Git。
- 範例與測試可執行：

```bash
.venv/bin/python -m unittest discover -s tests -v
```
