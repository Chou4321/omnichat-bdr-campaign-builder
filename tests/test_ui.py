import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class UiSmokeTests(unittest.TestCase):
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
        self.assertIn("合作單位 / 講者", labels)
        self.assertIn("活動重點 1", labels)
        self.assertIn("活動重點 4", labels)
        self.assertIn("信件大標 A（選填）", labels)
        areas = [item.label for item in app.text_area]
        self.assertIn("活動一句話摘要", areas)
        self.assertIn("活動介紹", areas)
        self.assertNotIn("Landing Page 內容", areas)
        self.assertNotIn("活動議程", areas)
        self.assertNotIn("複製活動", [item.label for item in app.button])

    def test_email_builder_v1_has_only_simplified_fields(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        self.assertEqual(app.selectbox[1].options, [
            "陌生開發邀約", "活動前提醒", "活動後跟進", "自主報名確認", "一般開發信"
        ])
        text_areas = [item.label for item in app.text_area]
        text_inputs = [item.label for item in app.text_input]
        self.assertNotIn("活動介紹 *", text_areas)
        self.assertIn("品牌觀察（選填）", text_areas)
        self.assertIn("品牌名稱 *", text_inputs)
        self.assertIn("窗口（選填）", text_inputs)
        self.assertNotIn("品牌觀察來源", [item.label for item in app.selectbox])
        self.assertNotIn("活動 Landing Page 內容", text_areas)
        self.assertNotIn("活動議程", text_areas)
        self.assertEqual(app.selectbox[0].label, "選擇活動")
        self.assertIn("是否引用產業資料庫", [item.label for item in app.checkbox])

    def test_email_builder_v1_has_banner_and_generate_button(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("file_uploader")), 0)
        self.assertIn("產生 Email 信件", [item.label for item in app.button])

    def test_general_email_allows_empty_activity_intro(self):
        app_path = Path(__file__).parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)
        app.sidebar.radio[0].set_value("Email 信件").run(timeout=10)
        app.selectbox[1].set_value("一般開發信").run(timeout=10)
        brand = next(item for item in app.text_input if item.label == "品牌名稱 *")
        brand.set_value("測試品牌")
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
        self.assertIn("Omnichat 可應用情境（每行一筆）", areas)
        self.assertIn("Showcase / 品牌案例", areas)
        self.assertIn("常用 CTA（每行一筆）", areas)


if __name__ == "__main__":
    unittest.main()
