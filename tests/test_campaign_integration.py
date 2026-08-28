import tempfile
import unittest
from pathlib import Path

from generators import generate_banner, generate_email, generate_line
from line_contact_finder import generate_activity_reply, generate_first_contact_message
from storage import load_campaigns, save_campaign


FOOD_CAMPAIGN = {
    "id": "food-test",
    "name": "食品品牌會員成長交流會",
    "event_date": "2026-08-26",
    "event_time": "14:00–16:30",
    "event_format": "實體",
    "location": "台北活動會場",
    "address": "台北市測試路 1 號",
    "registration_url": "https://example.com/food-event",
    "booking_url": "https://example.com/book",
    "partner": "食品研究所、台灣牧場、Omnichat",
    "primary_industry": "食品 / 伴手禮",
    "summary": "本次活動從食品產業趨勢、會員數據到品牌實戰，分享食品品牌建立持續成長的顧客經營模式。",
    "introduction": "活動聚焦食品消費變化、會員資料整理、精準分眾與品牌案例。",
    "activity_point_1": "掌握食品產業趨勢與消費行為",
    "activity_point_2": "建立會員數據經營策略",
    "activity_point_3": "透過精準分眾提升顧客互動",
    "activity_point_4": "食品品牌第一線實戰分享",
    "email_title_a": "食品品牌如何建立持續成長模式？",
    "email_title_b": "從會員數據到品牌回購成長",
    "email_title_c": "食品品牌會員成長交流會邀請",
    "image_path": "uploads/food-test-banner.png",
}


class CampaignIntegrationTests(unittest.TestCase):
    def test_all_modules_share_one_food_campaign(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaigns.json"
            save_campaign(FOOD_CAMPAIGN, path)
            campaign = load_campaigns(path)[0]

        lead = {"brand": "測試伴手禮", "contact": "王小姐", "industry": "食品 / 伴手禮"}
        subjects, cold_body, _ = generate_email(campaign, "陌生開發邀約", lead)
        _, precall_body, _ = generate_email(campaign, "自主報名確認", lead)
        line_message = generate_line(campaign, "活動邀約", lead)
        finder_message = generate_first_contact_message(False, campaign)
        finder_reply = generate_activity_reply(campaign)
        visual_copy = generate_banner(campaign)

        self.assertEqual(len(subjects), 3)
        self.assertIn(FOOD_CAMPAIGN["activity_point_1"], cold_body)
        self.assertIn("我是 Omnichat 市場團隊的周周", cold_body)
        self.assertIn(FOOD_CAMPAIGN["name"], precall_body)
        self.assertIn(FOOD_CAMPAIGN["event_date"], precall_body)
        self.assertIn(FOOD_CAMPAIGN["event_date"], line_message)
        self.assertIn(FOOD_CAMPAIGN["registration_url"], line_message)
        self.assertIn(FOOD_CAMPAIGN["name"], finder_message)
        self.assertIn(FOOD_CAMPAIGN["summary"], finder_reply)
        self.assertIn(FOOD_CAMPAIGN["summary"], visual_copy["活動副標"])
        self.assertNotIn("AI 在品牌", cold_body)
        self.assertNotIn("CRM", cold_body)
        self.assertNotIn("Meta", cold_body)


if __name__ == "__main__":
    unittest.main()
