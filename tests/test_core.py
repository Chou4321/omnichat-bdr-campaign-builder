import json
import tempfile
import unittest
from pathlib import Path

from generators import (
    generate_banner,
    generate_email,
    generate_line,
    validate_cold_email_sources,
)
from models import EMAIL_SCENARIOS, LINE_SCENARIOS
from storage import (
    JsonStore,
    delete_campaign,
    load_campaigns,
    load_industry_templates,
    save_campaign,
    update_campaign,
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


class StoreTests(unittest.TestCase):
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

    def test_food_industry_knowledge_exists(self):
        template = load_industry_templates()[0]
        self.assertEqual(template["industry_name"], "食品 / 伴手禮")
        self.assertIn("星球工坊爆米花", template["showcases"]["食品伴手禮"])
        self.assertGreaterEqual(len(template["pain_points"]), 6)


class GeneratorTests(unittest.TestCase):
    def test_email(self):
        subjects, body, cta = generate_email(CAMPAIGN, "活動前提醒", LEAD)
        self.assertEqual(len(subjects), 3)
        self.assertIn("活動前提醒", subjects[0])
        self.assertIn("王小姐", body)
        self.assertIn(CAMPAIGN["introduction"], body)
        self.assertIn("如需協助", cta)

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
            "陌生開發邀約", "活動前提醒", "活動後跟進", "自主報名確認", "一般開發信"
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
            "陌生開發邀約",
            lead,
        )
        self.assertIn("官網目前以節慶禮盒為主要溝通內容。", body)
        self.assertNotIn("測試品牌 的產業與現況", body)

    def test_five_v1_templates_are_distinct_and_grounded(self):
        bodies = []
        for scenario in EMAIL_SCENARIOS:
            subjects, body, cta = generate_email(CAMPAIGN, scenario, LEAD)
            self.assertEqual(len(subjects), 3)
            self.assertIn(CAMPAIGN["introduction"], body)
            self.assertTrue(cta)
            bodies.append(body)
        self.assertEqual(len(set(bodies)), 5)

    def test_v1_banner_is_optional(self):
        _, without_banner, _ = generate_email(
            {"introduction": "活動介紹內容"}, "一般開發信", LEAD
        )
        _, with_banner, _ = generate_email(
            {"introduction": "活動介紹內容", "image_path": "uploads/banner.png"},
            "一般開發信", LEAD,
        )
        self.assertIn("活動 Banner｜（未上傳）", without_banner)
        self.assertIn("活動 Banner｜uploads/banner.png", with_banner)


if __name__ == "__main__":
    unittest.main()
