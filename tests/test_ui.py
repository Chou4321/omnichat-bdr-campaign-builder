import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class UiSmokeTests(unittest.TestCase):
    def setUp(self):
        os.environ["OMNICHAT_TEST_INDUSTRY_JSON"] = "1"

    def tearDown(self):
        os.environ.pop("OMNICHAT_TEST_INDUSTRY_JSON", None)

    def test_sidebar_and_default_page_render(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        self.assertFalse(app.exception)
        self.assertEqual(
            app.sidebar.radio[0].options,
            [
                "活動管理",
                "Email 信件",
                "LINE 邀約訊息",
                "產業別資料庫",
            ],
        )
        self.assertEqual(app.header[0].value, "活動管理")

    def test_hidden_pages_are_not_in_navigation(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        self.assertFalse(app.exception)
        options = app.sidebar.radio[0].options
        self.assertNotIn("LINE 找窗口", options)
        self.assertNotIn("活動圖文", options)
        self.assertNotIn("AI 文案資料庫", options)

    def test_activity_manager_has_single_campaign_builder_form(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("活動管理").run(timeout=10)
        self.assertFalse(app.exception)
        labels = [item.label for item in app.text_input]
        self.assertIn("活動名稱 *", labels)
        self.assertIn("活動時間", labels)
        self.assertIn("活動地點", labels)
        self.assertIn("活動地址", labels)
        self.assertIn("報名連結", labels)
        self.assertIn("預約交流連結", labels)
        self.assertIn("活動簡報整理連結（選填）", labels)
        self.assertIn("合作單位 / 講者", labels)
        self.assertNotIn("活動重點 1", labels)
        self.assertNotIn("活動重點 2", labels)
        self.assertNotIn("活動重點 3", labels)
        self.assertNotIn("活動重點 4", labels)
        self.assertNotIn("信件大標 A（選填）", labels)
        self.assertNotIn("信件大標 B（選填）", labels)
        self.assertNotIn("信件大標 C（選填）", labels)
        self.assertNotIn("問題式", labels)
        self.assertNotIn("效益式", labels)
        self.assertNotIn("趨勢 / 活動式", labels)
        self.assertNotIn("自訂大標", labels)
        self.assertIn("產生 3 個信件大標", [item.label for item in app.button])
        areas = [item.label for item in app.text_area]
        self.assertIn("活動介紹", areas)
        self.assertIn("活動重點", areas)
        self.assertIn("💡 活動開發 Hook／我想強調的點（選填）", areas)
        self.assertNotIn("活動一句話摘要", areas)
        self.assertNotIn("Landing Page 內容", areas)
        self.assertNotIn("活動議程", areas)
        self.assertNotIn("複製活動", [item.label for item in app.button])

    def test_activity_subject_suggestions_generate_and_rotate(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        create_inputs = {}
        for item in app.text_input:
            create_inputs.setdefault(item.label, item)
        for label, value in {"活動名稱 *": "測試食品活動"}.items():
            create_inputs[label].set_value(value)
        create_areas = {}
        for item in app.text_area:
            create_areas.setdefault(item.label, item)
        create_areas["活動介紹"].set_value(
            "分享食品產業趨勢、會員數據與分眾行銷實務。"
        )
        create_areas["活動重點"].set_value(
            "・掌握食品產業趨勢\n・建立會員數據策略"
        )
        next(
            item for item in app.button if item.label == "產生 3 個信件大標"
        ).click().run(timeout=10)
        self.assertFalse(app.exception)
        first_subjects = [
            next(item for item in app.text_input if item.label == label).value
            for label in ("問題式", "效益式", "趨勢 / 活動式")
        ]
        self.assertEqual(len(set(first_subjects)), 3)
        self.assertTrue(all(subject for subject in first_subjects))
        self.assertIn("選擇預設信件大標", [item.label for item in app.radio])
        self.assertNotIn("自訂大標", [item.label for item in app.text_input])
        next(
            item for item in app.button if item.label == "重新產生 3 個建議"
        ).click().run(timeout=10)
        second_subjects = [
            next(item for item in app.text_input if item.label == label).value
            for label in ("問題式", "效益式", "趨勢 / 活動式")
        ]
        self.assertNotEqual(first_subjects, second_subjects)

    def test_subject_suggestions_do_not_require_activity_points(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        next(
            item for item in app.text_input if item.label == "活動名稱 *"
        ).set_value("測試活動")
        next(
            item for item in app.text_area if item.label == "活動介紹"
        ).set_value("分享品牌成長與會員經營實務。")
        next(
            item for item in app.button if item.label == "產生 3 個信件大標"
        ).click().run(timeout=10)
        self.assertFalse(app.exception)
        labels = [item.label for item in app.text_input]
        self.assertIn("問題式", labels)
        self.assertIn("效益式", labels)
        self.assertIn("趨勢 / 活動式", labels)

    def test_activity_subject_generation_receives_hook_location_and_partner(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        text_inputs = {}
        for item in app.text_input:
            text_inputs.setdefault(item.label, item)
        text_inputs["活動名稱 *"].set_value(
            "Google 廣告精準獲客 × Omnichat 對話商務"
        )
        text_inputs["活動地點"].set_value("Google 台北辦公室")
        text_inputs["合作單位 / 講者"].set_value("Google；Omnichat")
        text_areas = {}
        for item in app.text_area:
            text_areas.setdefault(item.label, item)
        text_areas["活動介紹"].set_value(
            "從 Google Ads 獲客到 Ads-to-Chat 對話商務，席次有限，採審核制。"
        )
        text_areas["活動重點"].set_value(
            "Google Ads 精準獲客\n接住每一次廣告點擊\n打造全通路轉換閉環"
        )
        text_areas["💡 活動開發 Hook／我想強調的點（選填）"].set_value(
            "活動辦在 Google 台北辦公室，希望用走進 Google 辦公室作為話題。"
        )
        next(
            item for item in app.button if item.label == "產生 3 個信件大標"
        ).click().run(timeout=10)
        self.assertFalse(app.exception)
        subjects = {
            item.label: item.value
            for item in app.text_input
            if item.label in ("問題式", "效益式", "趨勢 / 活動式")
        }
        self.assertEqual(
            subjects["問題式"],
            "👀 想走進 Google 辦公室一探究竟嗎？",
        )
        self.assertEqual(
            subjects["效益式"],
            "✨ 廣告帶來流量後，下一步怎麼接住顧客？",
        )
        self.assertEqual(
            subjects["趨勢 / 活動式"],
            "📍 Google 限定邀請｜從廣告獲客到對話商務",
        )

    def test_email_builder_has_six_consolidated_scenarios(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        self.assertEqual(app.selectbox[1].options, [
            "活動前陌生開發", "活動前確認出席通知",
            "活動後關懷", "活動未出席／活動精華分享",
        ])
        text_inputs = [item.label for item in app.text_input]
        self.assertIn("品牌名稱（選填）", text_inputs)
        self.assertIn("聯絡人姓名（選填）", text_inputs)
        self.assertNotIn("品牌名稱 *", text_inputs)
        self.assertEqual(app.selectbox[0].label, "選擇活動")
        self.assertIn("產業（選填）", [item.label for item in app.selectbox])

    def test_non_event_email_hides_activity_selector(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        app.radio[0].set_value("非活動信件").run(timeout=10)
        self.assertNotIn("選擇活動", [item.label for item in app.selectbox])
        scenario = next(item for item in app.selectbox if item.label == "信件情境")
        self.assertEqual(scenario.options, ["陌生開發", "二次追蹤"])

    def test_attendance_confirmation_shows_fixed_subject_notice(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        app.selectbox[1].set_value("活動前確認出席通知").run(timeout=10)
        self.assertTrue(any("活動確認出席" in item.value for item in app.info))

    def test_email_builder_has_no_banner_uploader_and_can_generate(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("file_uploader")), 0)
        self.assertIn("產生 Email 信件", [item.label for item in app.button])

    def test_campaign_manager_has_no_banner_uploader(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("file_uploader")), 0)
        self.assertNotIn("活動 Banner（選填）", [item.label for item in app.text_input])

    def test_email_industry_comes_directly_from_industry_database(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        selector = next(item for item in app.selectbox if item.label == "產業（選填）")
        self.assertEqual(selector.options[0], "不選產業")
        self.assertIn("食品 / 伴手禮", selector.options)

    def test_line_industry_reference_is_limited_to_one_each(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("LINE 邀約訊息").run(timeout=10)
        checkbox = next(item for item in app.checkbox if item.label == "引用產業別資料庫")
        checkbox.set_value(True).run(timeout=10)
        labels = [item.label for item in app.selectbox]
        self.assertIn("引用 1 個痛點", labels)
        self.assertIn("引用 1 個開發切角", labels)
        self.assertIn("引用 1 個 Showcase", labels)

    def test_general_email_allows_empty_activity_intro(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        app.radio[0].set_value("非活動信件").run(timeout=10)
        button = next(item for item in app.button if item.label == "產生 Email 信件")
        button.click().run(timeout=10)
        self.assertFalse(app.exception)
        self.assertNotIn("請填寫活動介紹。", [item.value for item in app.error])
        self.assertIn("Email 內文", app.session_state["Email_result"])

    def test_line_activity_invitation_does_not_repeat_campaign_fields(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("LINE 邀約訊息").run(timeout=10)
        app.selectbox[1].set_value("活動邀約").run(timeout=10)
        self.assertFalse(app.exception)
        labels = [item.label for item in app.text_input]
        self.assertIn("品牌（選填）", labels)
        self.assertIn("窗口（選填）", labels)
        self.assertIn("補充資訊（選填）", [item.label for item in app.text_area])
        self.assertNotIn("活動類型標籤", labels)
        self.assertNotIn("活動時間", labels)
        self.assertNotIn("活動地點或線上形式", labels)
        self.assertNotIn("報名連結", labels)

    def test_industry_database_fields_render(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("產業別資料庫").run(timeout=10)
        self.assertFalse(app.exception)
        self.assertEqual(app.header[0].value, "產業別資料庫")
        areas = [item.label for item in app.text_area]
        self.assertIn("產業說明", areas)
        self.assertIn("常見痛點（每行一筆）", areas)
        self.assertIn("常見開發切角（每行一筆）", areas)
        self.assertIn("Omnichat 對應應用（每行一筆）", areas)
        self.assertIn("Showcase / 品牌案例", areas)
        self.assertIn("常用 CTA（每行一筆）", areas)
        self.assertIn("常見經營情境（每行一筆）", areas)
        self.assertIn("禁用 / 注意事項（每行一筆）", areas)
        self.assertIn("複製資料", [item.label for item in app.button])


if __name__ == "__main__":
    unittest.main()
