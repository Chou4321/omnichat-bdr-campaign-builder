import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from generators import (
    generate_banner,
    generate_email,
    generate_line,
    generate_subject_suggestions,
    validate_cold_email_sources,
)
from models import EMAIL_SCENARIOS, LINE_SCENARIOS
from storage import (
    IndustryStorageError,
    JsonStore,
    _create_supabase_client,
    _supabase_credentials,
    delete_campaign,
    delete_industry_template,
    load_campaigns,
    load_industry_templates,
    save_campaign,
    save_industry_template,
    update_campaign,
    update_industry_template,
)


CAMPAIGN = {
    "name": "零售成長論壇",
    "event_date": "2026-08-20",
    "event_time": "14:00–16:00",
    "event_format": "線上",
    "location": "線上直播",
    "address": "",
    "topic": "會員成長",
    "highlights": "品牌案例與實戰分享",
    "primary_industry": "零售",
    "summary": "本次活動分享零售品牌如何整理會員資料並建立持續互動策略。",
    "introduction": "零售市場趨勢、會員數據、精準分眾與品牌案例分享。",
    "activity_point_1": "掌握零售市場與消費變化",
    "activity_point_2": "建立會員數據經營策略",
    "activity_point_3": "透過精準分眾提升互動",
    "activity_point_4": "零售品牌實戰案例分享",
    "email_title_a": "零售品牌會員成長實戰",
    "email_title_b": "從會員資料到持續互動",
    "email_title_c": "零售成長論壇活動邀請",
    "registration_url": "https://example.com/register",
    "booking_url": "https://example.com/book",
    "suitable_industries": "零售",
}
LEAD = {"brand": "測試品牌", "contact": "王小姐", "needs": "提升回購"}

GOOGLE_CAMPAIGN = {
    **CAMPAIGN,
    "name": "Google 實體小聚 - 全通路獲客與轉換閉環：Google Ads 精準獲客 × Omnichat 對話商務",
    "event_date": "2026-09-16",
    "introduction": "分享 Google Ads 精準獲客與 Omnichat 對話商務，建立全通路轉換閉環。",
    "activity_points": [
        "Google Ads 精準獲客", "Omnichat 對話商務", "全通路獲客與轉換閉環",
    ],
}
HEALTH_INDUSTRY = {
    "id": "health", "industry_name": "保健品",
    "pain_points": ["廣告新客增加，但後續回購有限"],
    "development_angles": ["依產品需求建立會員輪廓"],
    "omnichat_applications": ["會員分眾與再行銷"],
    "showcase_cases": [], "common_ctas": [],
}
PET_INDUSTRY = {
    "id": "pet", "industry_name": "寵物",
    "pain_points": ["飼主與寵物產品偏好資料分散"],
    "development_angles": ["依寵物生命階段推動回購"],
    "omnichat_applications": ["飼主會員分眾"],
    "showcase_cases": [], "common_ctas": [],
}


class StoreTests(unittest.TestCase):
    def test_event_cold_outreach_style_reference_is_versioned(self):
        reference_path = Path(__file__).parents[1] / "data" / "email_style_references.json"
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        style = reference["event_cold_outreach"]
        self.assertEqual(len(style["structure"]), 9)
        self.assertIn("Google 台北辦公室", style["google_good_example"])
        self.assertIn("誠摯邀請您參與", style["forbidden_phrases"])

    def test_supabase_credentials_reject_publishable_key(self):
        fake_secrets = {
            "supabase": {
                "url": "https://example.supabase.co",
                "secret_key": "sb_publishable_not_allowed",
            }
        }
        with patch("streamlit.secrets", fake_secrets):
            with self.assertRaisesRegex(IndustryStorageError, "sb_secret_"):
                _supabase_credentials()

    def test_supabase_client_disables_user_auth_session(self):
        with patch("supabase.create_client") as create_client:
            _create_supabase_client.cache_clear()
            _create_supabase_client(
                "https://example.supabase.co", "sb_secret_server_test"
            )
        options = create_client.call_args.kwargs["options"]
        self.assertFalse(options.auto_refresh_token)
        self.assertFalse(options.persist_session)
        _create_supabase_client.cache_clear()

    def test_crud(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JsonStore(Path(directory) / "items.json")
            store.add({"id": "1", "name": "A"})
            self.assertEqual(store.load()[0]["name"], "A")
            self.assertTrue(store.update("1", {"name": "B"}))
            self.assertEqual(store.load()[0]["name"], "B")
            self.assertTrue(store.delete("1"))
            self.assertEqual(store.load(), [])

    def test_json_is_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "items.json"
            JsonStore(path).save_all([{"name": "活動"}])
            self.assertEqual(json.loads(path.read_text())[0]["name"], "活動")

    def test_campaign_domain_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaigns.json"
            save_campaign({"id": "c1", "name": "測試活動"}, path)
            self.assertEqual(load_campaigns(path)[0]["name"], "測試活動")
            self.assertTrue(update_campaign("c1", {"summary": "一句摘要"}, path))
            self.assertEqual(load_campaigns(path)[0]["summary"], "一句摘要")
            self.assertTrue(delete_campaign("c1", path))
            self.assertEqual(load_campaigns(path), [])

    def test_campaign_subject_suggestions_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaigns.json"
            record = {
                "id": "subject-test",
                "name": "測試活動",
                "subject_a": "問題式大標",
                "subject_b": "效益式大標",
                "subject_c": "趨勢式大標",
                "selected_subject": "效益式大標",
            }
            save_campaign(record, path)
            reloaded = load_campaigns(path)[0]
            self.assertEqual(reloaded["subject_a"], "問題式大標")
            self.assertEqual(reloaded["selected_subject"], "效益式大標")

    def test_campaign_development_hook_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaigns.json"
            save_campaign({
                "id": "hook-event", "name": "Google 活動",
                "development_hook": "用 Google 辦公室作為話題 Hook",
            }, path)
            self.assertEqual(
                load_campaigns(path)[0]["development_hook"],
                "用 Google 辦公室作為話題 Hook",
            )

    def test_legacy_campaign_points_are_normalized_without_data_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaigns.json"
            save_campaign({
                "id": "legacy-points",
                "name": "舊活動",
                "activity_point_1": "舊重點一",
                "activity_point_2": "舊重點二",
                "activity_point_3": "舊重點三",
                "activity_point_4": "舊重點四",
            }, path)
            reloaded = load_campaigns(path)[0]
            self.assertEqual(
                reloaded["activity_points"],
                ["舊重點一", "舊重點二", "舊重點三", "舊重點四"],
            )

    def test_food_industry_knowledge_exists(self):
        template = load_industry_templates(Path("data/industry_templates.json"))[0]
        self.assertEqual(template["industry_name"], "食品 / 伴手禮")
        self.assertIn("星球工坊爆米花", template["showcases"]["食品伴手禮"])
        self.assertGreaterEqual(len(template["pain_points"]), 6)
        self.assertEqual(len(template["showcase_cases"]), 8)
        self.assertTrue(all("public" in case for case in template["showcase_cases"]))
        self.assertGreaterEqual(len(template["omnichat_applications"]), 8)
        self.assertGreaterEqual(len(template["cautions"]), 4)

    def test_industry_knowledge_persists_crud(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "industries.json"
            record = {
                "id": "food",
                "industry_name": "食品 / 伴手禮",
                "pain_points": ["檔期後回購有限", "會員資料分散"],
                "showcase_cases": [{
                    "brand_name": "簡單李",
                    "category": "烘焙伴手禮",
                    "use_cases": "節慶回購",
                    "key_points": "會員分眾",
                    "public": True,
                }],
            }
            save_industry_template(record, path)
            reloaded = load_industry_templates(path)[0]
            self.assertEqual(reloaded["pain_points"][0], "檔期後回購有限")
            self.assertEqual(reloaded["showcase_cases"][0]["brand_name"], "簡單李")

            self.assertTrue(update_industry_template("food", {
                "pain_points": ["會員資料分散"],
                "showcase_cases": [],
            }, path))
            reloaded = load_industry_templates(path)[0]
            self.assertEqual(reloaded["pain_points"], ["會員資料分散"])
            self.assertEqual(reloaded["showcase_cases"], [])

            self.assertTrue(delete_industry_template("food", path))
            self.assertEqual(load_industry_templates(path), [])

    def test_supabase_industry_storage_migrates_and_persists_crud(self):
        class FakeQuery:
            def __init__(self, database, table):
                self.database = database
                self.table = table
                self.operation = "select"
                self.columns = "*"
                self.values = None
                self.filters = {}

            def select(self, columns):
                self.operation = "select"
                self.columns = columns
                return self

            def insert(self, values):
                self.operation = "insert"
                self.values = values
                return self

            def upsert(self, values, **_kwargs):
                self.operation = "upsert"
                self.values = values
                return self

            def update(self, values):
                self.operation = "update"
                self.values = values
                return self

            def delete(self):
                self.operation = "delete"
                return self

            def eq(self, key, value):
                self.filters[key] = value
                return self

            def limit(self, _value):
                return self

            def order(self, _column):
                return self

            def execute(self):
                rows = self.database.setdefault(self.table, [])
                matching = [
                    row for row in rows
                    if all(row.get(key) == value for key, value in self.filters.items())
                ]
                if self.operation == "select":
                    columns = [item.strip() for item in self.columns.split(",")]
                    return SimpleNamespace(data=[
                        {key: row[key] for key in columns if key in row}
                        for row in matching
                    ])
                values = self.values if isinstance(self.values, list) else [self.values]
                if self.operation in {"insert", "upsert"}:
                    for value in values:
                        key_name = "key" if self.table == "app_migrations" else "id"
                        current = next(
                            (row for row in rows if row[key_name] == value[key_name]), None
                        )
                        if current is None:
                            rows.append(dict(value))
                        elif self.operation == "upsert":
                            current.update(value)
                elif self.operation == "update":
                    for row in matching:
                        row.update(self.values)
                elif self.operation == "delete":
                    self.database[self.table] = [row for row in rows if row not in matching]
                return SimpleNamespace(data=[])

        class FakeClient:
            def __init__(self):
                self.database = {"industry_templates": [], "app_migrations": []}

            def table(self, name):
                return FakeQuery(self.database, name)

        client = FakeClient()
        with patch("storage._supabase_client", return_value=client):
            migrated = load_industry_templates()
            self.assertEqual(migrated[0]["industry_name"], "食品 / 伴手禮")
            self.assertEqual(len(client.database["app_migrations"]), 1)

            pet = {"id": "pet", "industry_name": "寵物", "pain_points": ["回購"]}
            save_industry_template(pet)
            self.assertTrue(update_industry_template("pet", {"pain_points": ["分眾"]}))
            reloaded = {item["id"]: item for item in load_industry_templates()}
            self.assertEqual(reloaded["pet"]["pain_points"], ["分眾"])
            self.assertTrue(delete_industry_template("pet"))
            self.assertNotIn("pet", {item["id"] for item in load_industry_templates()})


class GeneratorTests(unittest.TestCase):
    def test_new_activity_points_are_shared_by_email_and_line(self):
        campaign = {
            **CAMPAIGN,
            "summary": "",
            "activity_points": ["新格式重點一", "新格式重點二"],
            "activity_point_1": "不應使用的舊重點",
        }
        _, email_body, _ = generate_email(
            campaign, "陌生開發邀約", {"brand": "測試品牌", "contact": "窗口"}
        )
        line_body = generate_line(
            campaign, "活動提醒", {"brand": "測試品牌", "contact": "窗口"}
        )
        self.assertIn("新格式重點一", email_body)
        self.assertIn("新格式重點一", line_body)
        self.assertNotIn("不應使用的舊重點", email_body)

    def test_email(self):
        subjects, body, cta = generate_email(CAMPAIGN, "活動前確認出席通知", LEAD)
        self.assertEqual(len(subjects), 1)
        self.assertIn("活動確認出席", subjects[0])
        self.assertIn("王小姐", body)
        self.assertIn(CAMPAIGN["activity_point_1"], body)
        self.assertIn("15 分鐘", cta)

    def test_rule_based_subject_suggestions_are_distinct_and_grounded(self):
        campaign = {
            **CAMPAIGN,
            "name": "食品產業成長新曲線",
            "primary_industry": "食品 / 伴手禮",
            "summary": "從會員數據到分眾行銷，建立食品品牌持續成長模式。",
            "introduction": "分享食品產業趨勢、會員數據與分眾行銷實務。",
            "activity_point_1": "掌握食品產業趨勢",
            "activity_point_2": "建立會員數據策略",
            "activity_point_3": "精準分眾提升互動",
            "activity_point_4": "食品品牌案例分享",
        }
        subjects = generate_subject_suggestions(campaign, 0)
        self.assertEqual(len(subjects), 3)
        self.assertEqual(len(set(subjects)), 3)
        self.assertTrue(subjects[0].endswith("？"))
        self.assertNotIn(campaign["name"], " ".join(subjects))
        self.assertNotEqual(subjects[0].split("｜")[0], subjects[1].split("｜")[0])
        self.assertTrue(all(len(subject) <= 32 for subject in subjects))
        combined = " ".join(subjects)
        for unsupported in ("AI", "LINE", "CRM", "Meta", "自動化"):
            self.assertNotIn(unsupported, combined)

    def test_subject_regeneration_rotates_safe_patterns(self):
        versions = [generate_subject_suggestions(CAMPAIGN, index) for index in range(3)]
        for subject_type in range(3):
            self.assertEqual(len({subjects[subject_type] for subjects in versions}), 3)
        source = " ".join(str(value) for value in CAMPAIGN.values())
        for subjects in versions:
            for unsupported in ("AI", "LINE", "CRM", "Meta", "自動化"):
                if unsupported not in source:
                    self.assertNotIn(unsupported, " ".join(subjects))

    def test_subject_suggestions_do_not_split_english_brand_tokens(self):
        campaign = {
            **CAMPAIGN,
            "name": (
                "Google 實體小聚 - 全通路獲客與轉換閉環："
                "Google Ads 精準獲客 × Omnichat 對話商務"
            ),
            "primary_industry": "零售",
            "summary": "從 Google Ads 精準獲客到 Omnichat 對話商務，建立全通路轉換閉環。",
            "introduction": "分享 Google Ads 精準獲客與 Omnichat 對話商務的實際應用。",
            "activity_points": [
                "Google Ads 精準獲客",
                "Omnichat 對話商務",
                "全通路獲客與轉換閉環",
            ],
        }
        subjects = generate_subject_suggestions(campaign, 0)
        self.assertEqual(len(subjects), 3)
        self.assertTrue(all(len(subject) <= 32 for subject in subjects))
        combined = " ".join(subjects)
        self.assertIn("Google", combined)
        self.assertIn("Omnichat", combined)
        ascii_tokens = {
            token
            for subject in subjects
            for token in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", subject)
        }
        self.assertTrue(ascii_tokens <= {"Google", "Ads", "Omnichat"})

    def test_google_subjects_use_three_distinct_b2b_hooks(self):
        campaign = {
            "name": "Google 廣告精準獲客 × Omnichat AI 對話商務｜打造全通路獲客與轉換閉環",
            "event_date": "2026-09-23",
            "event_format": "實體",
            "location": "Google 台北辦公室",
            "partner": "Google｜Amber Chen；Omnichat｜Ariel Hu",
            "primary_industry": "未指定",
            "summary": "由 Google 與 Omnichat 分享 Google Ads 精準獲客與 Ads-to-Chat 對話商務轉換。",
            "introduction": "活動於 Google 台北辦公室舉行，席次有限，採審核制。",
            "development_hook": "活動辦在 Google 台北辦公室，希望增加話題性，最後帶回 Google Ads 獲客與轉換。",
            "activity_points": [
                "從廣告曝光到實際轉換：Google Ads 獲客實戰",
                "接住每一次點擊：從 Ads-to-Chat 到對話商務轉換",
            ],
        }
        curiosity, benefit, trend = generate_subject_suggestions(campaign)
        self.assertEqual(curiosity, "👀 想走進 Google 辦公室嗎？｜廣告點擊如何變顧客")
        self.assertEqual(benefit, "✨ 廣告流量進來後，怎麼轉成可持續經營的顧客？")
        self.assertEqual(trend, "📍 Google × Omnichat 限定小聚｜打通獲客到轉換")
        self.assertEqual(len({curiosity, benefit, trend}), 3)
        self.assertTrue(all(len(subject) <= 32 for subject in (curiosity, benefit, trend)))

    def test_event_cold_outreach_uses_hook_driven_bdr_master_style(self):
        campaign = {
            **GOOGLE_CAMPAIGN,
            "event_date": "2026-09-23",
            "event_time": "14:00–16:00",
            "event_format": "實體",
            "location": "Google 台北辦公室",
            "partner": "Google｜Amber Chen；Omnichat｜Ariel Hu",
            "development_hook": (
                "活動辦在 Google 台北辦公室，希望增加話題性；"
                "最後帶回 Google Ads 獲客與轉換。席次有限，採審核制。"
            ),
            "registration_url": "https://example.com/register",
            "booking_url": "https://example.com/book",
        }
        subjects, body, cta = generate_email(
            campaign, "活動前陌生開發", {"contact": "王小姐"}
        )
        self.assertEqual(subjects[0], "👀 想走進 Google 辦公室嗎？｜廣告點擊如何變顧客")
        expected_order = [
            "我是 Omnichat 市場團隊的周周",
            "廣告帶來點擊後",
            "由 Google × Omnichat 團隊共同分享",
            "・Google Ads 精準獲客",
            "📍 9/23（三） 14:00–16:00｜Google 台北辦公室",
            "👉 立即報名｜https://example.com/register",
            "若您近期也正在思考",
            "15 分鐘快速交流",
            "👉 快速聯繫我｜https://example.com/book",
        ]
        positions = [body.index(text) for text in expected_order]
        self.assertEqual(positions, sorted(positions))
        for banned in (
            "這次想邀請貴品牌參與", "活動內容與品牌近期可能關注",
            "若您有興趣，歡迎直接回覆此信", "若希望先了解適合品牌",
            "本活動將聚焦於", "誠摯邀請您參與",
        ):
            self.assertNotIn(banned, body)
        self.assertIn("15 分鐘快速交流", cta)

    def test_selected_subject_is_the_email_subject(self):
        selected = "食品品牌如何建立會員成長策略？"
        subjects, _, _ = generate_email(
            CAMPAIGN, "陌生開發邀約", {**LEAD, "selected_subject": selected}
        )
        self.assertEqual(subjects, [selected])

    def test_line(self):
        campaign = {
            **CAMPAIGN,
            "topic": "會員數據與分眾成長",
            "highlights": "市場趨勢、會員數據、精準分眾、回購與品牌實戰案例。",
        }
        result = generate_line(campaign, "Demo Follow-up", LEAD)
        self.assertIn("我是 Omnichat 周周", result)
        self.assertNotIn("Demo Follow-up", result)
        self.assertNotIn("目前情境", result)
        self.assertNotIn("更多資訊", result)

    def test_line_activity_invitation_uses_requested_format(self):
        campaign = {
            **CAMPAIGN,
            "event_format": "實體",
            "topic": "從會員數據到分眾行銷的跨界實戰",
            "highlights": "食品市場趨勢、會員數據、精準分眾、私域經營與品牌實戰案例。",
        }
        details = {
            "event_type_tag": "食品活動",
            "feature_tag": "品牌成長實戰",
            "event_date": "2026/08/26",
            "event_time": "14:00–16:30",
            "location_or_online": "台北市區星級酒店",
            "fee_capacity": "免費參加，限量 50 席",
            "registration_url": "https://example.com/register",
        }
        lead = {"contact": "行銷團隊", "industry": "食品"}
        result = generate_line(
            campaign, "活動邀約", lead, event_details=details
        )
        self.assertTrue(result.startswith("行銷團隊您好，我是 Omnichat 周周👋"))
        self.assertIn("#食品活動 #品牌成長實戰", result)
        self.assertEqual(result.count("✔"), 4)
        self.assertEqual(result.count("✅"), 4)
        self.assertIn("📅 2026/08/26 14:00–16:30", result)
        self.assertIn("📍 台北市區星級酒店", result)
        self.assertIn("🎟 免費參加，限量 50 席", result)
        self.assertIn("👉 https://example.com/register", result)
        self.assertTrue(result.endswith("https://example.com/register"))
        self.assertNotIn("有任何問題都可以直接在 LINE", result)
        self.assertNotIn("CRM", result)
        self.assertNotIn("AI 在", result)

    def test_banner(self):
        result = generate_banner(CAMPAIGN)
        self.assertEqual(set(result), {
            "活動大標", "活動副標", "4 個產業痛點", "4 個活動亮點", "CTA",
            "EDM 文案", "Banner 文案", "社群貼文文案", "一頁式介紹圖文案",
        })

    def test_scenario_counts(self):
        self.assertEqual(EMAIL_SCENARIOS, [
            "活動前陌生開發", "活動前確認出席通知", "活動後關懷",
            "活動未出席／活動精華分享", "陌生開發", "二次追蹤",
        ])
        self.assertEqual(len(LINE_SCENARIOS), 13)

    def test_v1_uses_only_supplied_observation(self):
        lead = {
            "brand": "測試品牌",
            "contact": "行銷部",
            "industry": "食品",
            "observation": "官網目前以節慶禮盒為主要溝通內容。",
        }
        _, body, _ = generate_email(
            CAMPAIGN,
            "活動前陌生開發",
            lead,
        )
        self.assertIn("官網目前以節慶禮盒為主要溝通內容。", body)
        self.assertNotIn("測試品牌 的產業與現況", body)

    def test_six_consolidated_templates_are_distinct(self):
        bodies = []
        for scenario in [
            "活動前陌生開發", "活動前確認出席通知", "活動後關懷",
            "活動未出席／活動精華分享", "陌生開發", "二次追蹤",
        ]:
            campaign = CAMPAIGN if scenario.startswith("活動") else {}
            subjects, body, cta = generate_email(campaign, scenario, LEAD)
            self.assertGreaterEqual(len(subjects), 1)
            self.assertTrue(cta)
            bodies.append(body)
        self.assertEqual(len(set(bodies)), 6)

    def test_legacy_email_scenarios_map_to_consolidated_templates(self):
        mappings = {
            "陌生開發邀約": "活動前陌生開發",
            "活動出席確認": "活動前確認出席通知",
            "講者簡報分享": "活動後關懷",
            "報名未出席 Follow-up": "活動未出席／活動精華分享",
            "一般開發信": "陌生開發",
            "第二次追蹤": "二次追蹤",
        }
        for legacy, current in mappings.items():
            legacy_result = generate_email(CAMPAIGN, legacy, LEAD)
            current_result = generate_email(CAMPAIGN, current, LEAD)
            self.assertEqual(legacy_result, current_result)

    def test_recovered_precall_template_includes_pdf_and_banner(self):
        campaign = {**CAMPAIGN, "image_path": "uploads/banner.png"}
        subjects, body, cta = generate_email(
            campaign,
            "活動報名後打招呼",
            {**LEAD, "selected_subject": "自訂 Pre-call 主旨"},
            event_details={"service_pdf_name": "service.pdf"},
        )
        self.assertIn("活動確認出席", subjects[0])
        self.assertIn("先為您暫保留席次", body)
        self.assertIn("活動 Banner｜uploads/banner.png", body)
        self.assertIn("service.pdf", body)
        self.assertIn("15 分鐘", cta)

    def test_attendance_confirmation_precall_is_fixed_and_grounded(self):
        campaign = {**CAMPAIGN, "image_path": "uploads/event.png"}
        subjects, body, cta = generate_email(
            campaign,
            "活動前確認通知（Pre-call）",
            {
                **LEAD,
                "industry": "零售",
                "needs": "會員回購\n分眾溝通",
                "selected_subject": "不可覆蓋固定主旨",
            },
            event_details={"service_intro_url": "https://example.com/service.pdf"},
        )
        self.assertEqual(subjects, [
            "活動確認出席｜【零售成長論壇】活動出席確認信（Energy）"
        ])
        self.assertIn("我是 Omnichat 周周，是負責品牌的窗口", body)
        self.assertIn("先為您暫保留席次", body)
        self.assertIn("活動時間｜2026-08-20 14:00–16:00", body)
        self.assertIn("活動地點｜線上直播", body)
        self.assertIn("活動 Banner｜uploads/event.png", body)
        self.assertIn("為了讓當天內容更貼近品牌的實際情境", body)
        self.assertIn("・掌握零售市場與消費變化", body)
        self.assertIn("https://example.com/service.pdf", body)
        self.assertIn("15 分鐘", cta)
        self.assertTrue(body.endswith("期待活動前能先認識您，讓當天交流更有收穫😊"))

    def test_attendance_confirmation_does_not_invent_topics(self):
        subjects, body, cta = generate_email(
            {"name": "資料不足活動"},
            "活動前確認通知（Pre-call）",
            {"brand": "測試品牌", "contact": "窗口", "needs": ""},
        )
        self.assertEqual(subjects[0], "活動確認出席｜【資料不足活動】活動出席確認信（Energy）")
        self.assertNotIn("None", body)
        self.assertNotIn("{聯絡人}", body)
        self.assertTrue(cta)
        for unsupported in ("AI", "LINE", "CRM", "Meta", "自動化"):
            self.assertNotIn(unsupported, body)

    def test_v1_banner_is_optional(self):
        _, without_banner, _ = generate_email(
            {"introduction": "活動介紹內容"}, "活動前陌生開發", LEAD
        )
        _, with_banner, _ = generate_email(
            {"introduction": "活動介紹內容", "image_path": "uploads/banner.png"},
            "活動前陌生開發", LEAD,
        )
        self.assertNotIn("活動 Banner｜", without_banner)
        self.assertIn("活動 Banner｜uploads/banner.png", with_banner)

    def test_general_email_needs_no_activity_or_observation(self):
        _, body, _ = generate_email(
            {"introduction": ""},
            "陌生開發",
            {"brand": "測試品牌", "contact": "", "observation": ""},
        )
        self.assertTrue(body.startswith("您好，"))
        self.assertIn("測試品牌", body)
        self.assertNotIn("近期主打", body)
        self.assertNotIn("活動 Banner", body)

    def test_industry_reference_is_opt_in_and_activity_guarded(self):
        template = {
            "industry_name": "食品 / 伴手禮",
            "pain_points": ["節慶新客後續回購有限", "LINE 好友缺乏分眾"],
            "development_angles": ["會員回購", "LINE 分眾"],
            "omnichat_applications": ["會員分眾", "AI 客服"],
            "showcase_cases": [{
                "brand_name": "簡單李", "category": "烘焙伴手禮",
                "key_points": "會員案例", "use_cases": "會員回購",
                "public": True,
            }],
            "common_ctas": ["歡迎回覆方便時段，我再協助安排。"],
        }
        lead = {**LEAD, "industry_context": template}
        _, referenced, cta = generate_email(CAMPAIGN, "活動前陌生開發", lead)
        _, plain, _ = generate_email(CAMPAIGN, "活動前陌生開發", LEAD)
        self.assertIn("食品 / 伴手禮", referenced)
        self.assertIn("會員", referenced)
        self.assertIn("15 分鐘快速交流", cta)
        self.assertNotIn("節慶新客後續回購有限", plain)
        self.assertNotIn("LINE 好友缺乏分眾", plain)

    def test_line_industry_reference_is_short_and_opt_in(self):
        context = {
            "pain_points": ["節慶新客後續回購有限"],
            "development_angles": ["檔期後新客如何轉成回購會員"],
            "showcase_cases": [{
                "brand_name": "簡單李", "use_cases": "會員經營 / 節慶回購",
                "public": True,
            }],
        }
        referenced = generate_line(
            CAMPAIGN, "活動邀約", {**LEAD, "industry_context": context}
        )
        plain = generate_line(CAMPAIGN, "活動邀約", LEAD)
        self.assertIn("節慶新客後續回購有限", referenced)
        self.assertIn("檔期後新客如何轉成回購會員", referenced)
        self.assertIn("簡單李", referenced)
        self.assertNotIn("簡單李", plain)

    def test_acceptance_1_event_cold_email_allows_empty_optional_fields(self):
        _, body, _ = generate_email(
            GOOGLE_CAMPAIGN, "活動前陌生開發", {"brand": "", "contact": ""}
        )
        self.assertTrue(body.startswith("您好，"))
        self.assertIn("Google Ads", body)
        self.assertNotIn("None", body)

    def test_acceptance_2_and_3_industry_switch_rebuilds_content(self):
        _, health, _ = generate_email(
            GOOGLE_CAMPAIGN, "活動後關懷",
            {"industry_context": HEALTH_INDUSTRY},
        )
        _, pet, _ = generate_email(
            GOOGLE_CAMPAIGN, "活動後關懷",
            {"industry_context": PET_INDUSTRY},
        )
        self.assertIn("Google Ads", health)
        self.assertIn("保健品", health)
        self.assertIn("寵物", pet)
        self.assertIn("飼主", pet)
        self.assertNotIn("保健品", pet)
        self.assertNotIn("廣告新客增加", pet)

    def test_acceptance_4_activity_switch_does_not_leak_google_content(self):
        line_campaign = {
            **CAMPAIGN,
            "name": "LINE 會員經營交流",
            "introduction": "分享 LINE 好友識別與會員分眾實務。",
            "activity_points": ["LINE 好友識別", "會員分眾", "顧客互動"],
        }
        _, body, _ = generate_email(
            line_campaign, "活動後關懷", {"industry_context": PET_INDUSTRY}
        )
        self.assertIn("LINE", body)
        self.assertNotIn("Google Ads", body)

    def test_acceptance_5_non_event_food_email_needs_no_activity(self):
        food = {
            "id": "food", "industry_name": "食品 / 伴手禮",
            "pain_points": ["檔期新客多，但後續回購有限"],
            "development_angles": ["一次性消費轉成會員"],
            "omnichat_applications": ["會員分眾"],
            "showcase_cases": [], "common_ctas": [],
        }
        _, body, _ = generate_email(
            {}, "陌生開發", {"industry_context": food, "brand": "", "contact": ""}
        )
        self.assertIn("食品 / 伴手禮", body)
        self.assertIn("檔期新客", body)
        self.assertNotIn("活動資訊", body)

    def test_acceptance_6_second_followup_is_shorter_than_first_email(self):
        lead = {"industry_context": PET_INDUSTRY, "brand": "寵物品牌"}
        _, first, _ = generate_email({}, "陌生開發", lead)
        _, followup, _ = generate_email({}, "二次追蹤", lead)
        self.assertLess(len(followup), len(first))
        self.assertIn("延續前次分享", followup)

    def test_acceptance_7_post_event_empty_name_has_no_placeholder(self):
        _, body, _ = generate_email(
            GOOGLE_CAMPAIGN, "活動後關懷", {"brand": "", "contact": ""}
        )
        self.assertTrue(body.startswith("您好，"))
        for invalid in ("Dear 您好", "Dear None", "{聯絡人}", "XXX"):
            self.assertNotIn(invalid, body)

    def test_acceptance_8_subject_tokens_are_never_split(self):
        campaign = {
            **GOOGLE_CAMPAIGN,
            "activity_points": [
                "Google Ads × Omnichat",
                "Meta × LINE Biz-Solutions",
                "Marketing Messages × Messenger",
            ],
        }
        subjects = [
            subject
            for variant in range(3)
            for subject in generate_subject_suggestions(campaign, variant)
        ]
        allowed = {
            "Google", "Ads", "Omnichat", "Meta", "LINE", "Biz-Solutions",
            "Marketing", "Messages", "Messenger",
        }
        tokens = {
            token for subject in subjects
            for token in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", subject)
        }
        self.assertTrue(tokens <= allowed)
        self.assertTrue(all(len(subject) <= 32 for subject in subjects))

    def test_post_event_master_template_and_material_link(self):
        campaign = {
            **GOOGLE_CAMPAIGN,
            "partner": "Google 與 Omnichat",
            "materials_url": "https://example.com/slides",
        }
        _, body, cta = generate_email(
            campaign, "活動後關懷", {"industry_context": HEALTH_INDUSTRY}
        )
        expected_order = [
            "感謝您撥空參加", "本次活動中", "【活動核心商業洞察】",
            "保健品", "📄 活動簡報整理｜https://example.com/slides",
            "📄 Omnichat 服務介紹", "15 分鐘交流", "再次感謝您的參與",
        ]
        positions = [body.index(value) for value in expected_order]
        self.assertEqual(positions, sorted(positions))
        self.assertTrue(cta)

    def test_absent_event_master_template_subject_and_forbidden_phrases(self):
        campaign = {
            **GOOGLE_CAMPAIGN,
            "name": "打造 Meta 廣告 × 再行銷成長模式",
            "event_date": "2026-07-24",
            "partner": "Meta 與 Omnichat",
            "materials_url": "https://example.com/highlights",
        }
        subjects, body, cta = generate_email(
            campaign,
            "活動未出席／活動精華分享",
            {"brand": "鼎通創新股份有限公司／oee education", "contact": ""},
        )
        self.assertEqual(subjects, [
            "【打造 Meta 廣告 × 再行銷成長模式】7/24 活動精華整理"
            "（鼎通創新股份有限公司／oee education）"
        ])
        self.assertIn("活動當天您可能因排程未能前往", body)
        self.assertIn("【活動核心商業洞察】", body)
        self.assertIn("📄 活動簡報整理｜https://example.com/highlights", body)
        self.assertIn("15 分鐘交流", cta)
        for forbidden in ("感謝您的參與", "再次感謝您的參與", "感謝撥空參加"):
            self.assertNotIn(forbidden, body)

    def test_absent_event_subject_omits_brand_parentheses_when_empty(self):
        subjects, body, _ = generate_email(
            {**GOOGLE_CAMPAIGN, "event_date": "2026-07-24"},
            "活動未出席／活動精華分享",
            {"brand": "", "contact": ""},
        )
        self.assertEqual(
            subjects,
            [f"【{GOOGLE_CAMPAIGN['name']}】7/24 活動精華整理"],
        )
        self.assertNotIn("（）", subjects[0])
        self.assertNotIn("活動 Banner", body)


if __name__ == "__main__":
    unittest.main()
