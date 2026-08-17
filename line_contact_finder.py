from typing import Any


def generate_first_contact_message(
    has_emailed_company: bool, campaign: dict[str, Any] = None
) -> str:
    email_note = "也有寄簡單活動資訊到貴公司信箱，" if has_emailed_company else ""
    activity_reference = (
        f"「{campaign.get('name')}」" if campaign and campaign.get("name")
        else "一場與貴品牌產業相關的交流活動"
    )
    return (
        "您好，想請問是否有負責行銷、會員經營或品牌經營的窗口可以聯繫？\n\n"
        f"這邊近期將舉辦{activity_reference}，{email_note}"
        "想與相關窗口交流一下，謝謝🙏"
    )


def generate_activity_reply(campaign: dict[str, Any]) -> str:
    name = campaign.get("name") or "本次交流活動"
    subtitle = campaign.get("topic", "").strip()
    partner = (campaign.get("partner") or "相關產業夥伴").replace(" & ", "、")
    speakers = partner if "Omnichat" in partner else f"{partner}與 Omnichat"
    feature = campaign.get("summary") or _one_sentence_feature(campaign)
    return (
        f"這場活動是「{name}{f'｜{subtitle}' if subtitle else ''}」，由{speakers} 共同分享。\n\n"
        f"{feature}想請問是否方便協助轉給行銷、會員經營或品牌經營相關窗口？謝謝🙏"
    )


def generate_email_provided_reply() -> str:
    return (
        "謝謝您😊\n"
        "我再將完整活動資訊寄給窗口參考，也期待有機會交流，謝謝您的協助🙏"
    )


def _one_sentence_feature(campaign: dict[str, Any]) -> str:
    text = (campaign.get("highlights") or "").strip().splitlines()[0]
    if "。" in text:
        return text.split("。", 1)[0].strip() + "。"
    if text:
        return text[:100].rstrip("，；; ") + "。"
    topic = campaign.get("topic") or "品牌經營"
    return f"活動將聚焦「{topic}」的實務經驗與案例。"
