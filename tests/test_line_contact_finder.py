import unittest

from line_contact_finder import (
    generate_activity_reply,
    generate_email_provided_reply,
    generate_first_contact_message,
)


FOOD_CAMPAIGN = {
    "name": "食品產業成長新曲線",
    "topic": "從會員數據到分眾行銷的跨界實戰",
    "partner": "台灣牧場 & 食品研究所",
    "summary": "從食品產業趨勢、會員數據到品牌實戰，分享食品品牌建立持續成長模式。",
    "highlights": "完整活動介紹與議程內容。",
}


class LineContactFinderTests(unittest.TestCase):
    def test_first_message_is_two_paragraphs_and_has_no_sales_pitch(self):
        result = generate_first_contact_message(False)
        self.assertEqual(len(result.split("\n\n")), 2)
        self.assertIn("負責行銷、會員經營或品牌經營的窗口", result)
        self.assertNotIn("Omnichat 功能", result)
        self.assertNotIn("完整活動", result)
        self.assertNotIn("寄簡單活動資訊", result)

    def test_first_message_mentions_email_only_when_selected(self):
        result = generate_first_contact_message(True)
        self.assertIn("也有寄簡單活動資訊到貴公司信箱", result)

    def test_activity_question_reply_uses_food_event_brief(self):
        result = generate_activity_reply(FOOD_CAMPAIGN)
        self.assertEqual(len(result.split("\n\n")), 2)
        self.assertIn("食品產業成長新曲線", result)
        self.assertIn(FOOD_CAMPAIGN["summary"], result)
        self.assertIn("台灣牧場、食品研究所與 Omnichat", result)
        self.assertIn("建立持續成長模式", result)
        self.assertNotIn("完整活動介紹與議程內容", result)

    def test_email_provided_reply(self):
        self.assertEqual(
            generate_email_provided_reply(),
            "謝謝您😊\n我再將完整活動資訊寄給窗口參考，也期待有機會交流，謝謝您的協助🙏",
        )


if __name__ == "__main__":
    unittest.main()
