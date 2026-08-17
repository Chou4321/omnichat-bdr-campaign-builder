from typing import Any, Optional

from storage import load_industry_templates


def _campaign_industry(campaign: dict[str, Any]) -> str:
    return campaign.get("primary_industry") or campaign.get("suitable_industries") or "品牌"


def _campaign_points(campaign: dict[str, Any]) -> list[str]:
    explicit = [
        campaign.get(f"activity_point_{index}", "").strip()
        for index in range(1, 5)
        if campaign.get(f"activity_point_{index}", "").strip()
    ]
    if explicit:
        return explicit
    _, fallback = _grounded_activity_content(campaign, {}, _campaign_industry(campaign))
    return fallback[:4]


def _campaign_summary(campaign: dict[str, Any]) -> str:
    if campaign.get("summary", "").strip():
        return campaign["summary"].strip()
    summary, _ = _grounded_activity_content(campaign, {}, _campaign_industry(campaign))
    return summary


def _campaign_titles(campaign: dict[str, Any], fallback: list[str]) -> list[str]:
    titles = [
        campaign.get("email_title_a", "").strip(),
        campaign.get("email_title_b", "").strip(),
        campaign.get("email_title_c", "").strip(),
    ]
    titles = [title for title in titles if title]
    return titles or fallback


def _campaign_context(campaign: dict[str, Any]) -> str:
    return (
        f"{campaign.get('name', '本次活動')}｜{campaign.get('event_date', '')}｜"
        f"{campaign.get('event_format', '')}"
    )


def generate_email(
    campaign: dict[str, Any], scenario: str, lead: dict[str, str],
    event_details: Optional[dict[str, Any]] = None,
) -> tuple[list[str], str, str]:
    if scenario == "陌生開發邀約":
        return _generate_cold_outreach_email(campaign, lead, event_details or {})
    if scenario == "活動報名後打招呼":
        return _generate_precall_email(campaign, lead, event_details or {})

    brand = lead.get("brand") or "貴品牌"
    contact = lead.get("contact") or "貴品牌團隊"
    subjects = [
        f"【{scenario}】{campaign.get('name', 'Omnichat 活動')}｜{brand}",
        f"邀請 {brand} 交流：{campaign.get('topic') or campaign.get('name', '活動資訊')}",
        f"{contact} 您好｜一場與{lead.get('needs') or '會員成長'}有關的活動",
    ]
    body = f"""{contact} 您好，

我是 Omnichat 團隊。這封信想和您分享「{_campaign_context(campaign)}」。

我們觀察到 {brand} 在{lead.get('industry') or '品牌經營'}領域持續投入。{lead.get('observation') or '許多品牌正積極整合會員互動與轉換流程。'}

本次活動主題：{campaign.get('topic') or '待補充'}
活動亮點：{campaign.get('highlights') or '待補充'}
與貴品牌的可能連結：{lead.get('needs') or '期待進一步了解目前的會員經營需求。'}

{_scenario_email_paragraph(scenario, campaign)}

先前交流紀錄：{lead.get('precall') or '尚無'}

若您方便，歡迎直接回覆此信，我會協助安排後續交流。

Omnichat 團隊"""
    cta = _scenario_cta(scenario, campaign)
    return subjects, body, cta


def _generate_precall_email(
    campaign: dict[str, Any], lead: dict[str, str], event: dict[str, Any]
) -> tuple[list[str], str, str]:
    contact = lead.get("contact") or "貴品牌團隊"
    industry = lead.get("industry") or _campaign_industry(campaign)
    event_name = campaign.get("name") or "本次活動"
    topic = campaign.get("topic") or event_name
    summary = _campaign_summary(campaign)
    activity_points = _campaign_points(campaign)
    if len(activity_points) < 3:
        warning = (
            "活動內容不足，無法在不猜測的前提下整理四個關注重點。"
            "請先到活動管理補充活動介紹、活動主題與活動亮點。"
        )
        return _precall_email_headlines(event_name, topic), warning, ""

    subjects = _campaign_titles(campaign, _precall_email_headlines(event_name, topic))
    selected_title = event.get("selected_email_title", "")
    if selected_title in subjects:
        subjects = [selected_title] + [title for title in subjects if title != selected_title]
    concerns = "\n".join(f"• {point}" for point in activity_points[:4])
    booking = campaign.get("booking_url") or "（請於活動管理補上預約連結）"
    banner = campaign.get("image_path") or "（請於活動管理上傳活動 Banner）"
    service_pdf = event.get("service_pdf_name") or "（請附上 Omnichat 服務介紹 PDF）"
    cta = f"""很樂意在活動前依您的產業與品牌現況，分享相關案例作為參考，讓當天交流更有收穫！

👉 歡迎直接回覆方便時段，或點此快速預約【{booking}】
（彈性安排 15 分鐘交流）"""
    body = f"""Dear {contact} 您好，

收到您報名【{event_name}】，目前正在陸續確認名單中，先與您打聲招呼！

{summary}

💡 若您近期正關注：
{concerns}

{cta}

【活動 Banner｜{banner}】

📄 Omnichat 服務介紹｜{service_pdf}

期待活動前能先認識您，讓當天交流更有收穫😊"""
    return subjects, body, cta


def _precall_email_headlines(event_name: str, topic: str) -> list[str]:
    return [
        f"【{event_name}｜{topic}】",
        f"【活動前交流：一起掌握「{topic}」】",
        f"【參與「{event_name}」前，先掌握活動交流重點】",
    ]


def _generate_cold_outreach_email(
    campaign: dict[str, Any], lead: dict[str, str], event: dict[str, Any]
) -> tuple[list[str], str, str]:
    brand = lead.get("brand") or "貴品牌"
    contact = lead.get("contact") or "貴品牌團隊"
    industry = lead.get("industry") or _campaign_industry(campaign)
    event_name = campaign.get("name") or "Omnichat 產業交流活動"
    event_topic = (
        campaign.get("topic")
        or campaign.get("summary")
        or event_name
    ).strip().splitlines()[0]
    if len(event_topic) > 60:
        event_topic = event_topic[:60].rstrip("，。；; ")
    registration = event.get("registration_url") or campaign.get("registration_url") or "（請填寫報名連結）"
    subjects = _campaign_titles(campaign, _cold_email_headlines(event_topic, industry))
    selected_title = event.get("selected_email_title", "")
    if selected_title in subjects:
        subjects = [selected_title] + [title for title in subjects if title != selected_title]
    pain_opening = _industry_pain_opening(industry, campaign)
    observation = lead.get("observation", "").strip()
    observation_paragraph = f"\n\n{observation}" if observation else ""
    summary = _campaign_summary(campaign)
    activity_points = _campaign_points(campaign)
    if len(activity_points) < 3:
        warning = (
            "活動內容不足，無法在不猜測的前提下整理活動重點。"
            "請先到活動管理補充 3～4 個活動重點。"
        )
        return subjects, warning, ""
    highlights = "\n".join(f"✔ {point}" for point in activity_points[:4])
    info_block = _activity_info_block(campaign, event, registration)
    cta = (
        "若方便，\n"
        "也歡迎直接回覆信件，\n"
        f"我也很樂意分享{industry}相關案例供您參考。"
    )

    body = f"""Dear {contact} 您好，

{pain_opening}{observation_paragraph}

{summary}

【活動重點】
{highlights}

{info_block}

{cta}

【活動 Banner｜{campaign.get('image_path') or '（請於活動管理上傳）'}】"""
    return subjects, body, cta


def validate_cold_email_sources(
    campaign: dict[str, Any], event: dict[str, Any], industry: str
) -> Optional[str]:
    points = _campaign_points(campaign)
    if len(points) >= 3:
        return None
    return (
        f"目前只能從活動內容取得 {len(points)} 個活動重點。"
        "請先到活動管理補充活動重點後再生成。"
    )


def _activity_source(campaign: dict[str, Any], event: dict[str, Any]) -> str:
    ordered_sources = [
        campaign.get("introduction", ""),
        campaign.get("summary", ""),
        *[campaign.get(f"activity_point_{index}", "") for index in range(1, 5)],
        event.get("landing_page_content", ""),
        event.get("activity_intro", ""),
        event.get("activity_copy", ""),
        event.get("agenda", ""),
        event.get("banner_copy", ""),
    ]
    content = "\n".join(str(value).strip() for value in ordered_sources if str(value).strip())
    if content:
        return content
    return "\n".join([
        campaign.get("topic", ""),
        campaign.get("highlights", ""),
        campaign.get("partner", ""),
    ]).strip()


def _grounded_activity_content(
    campaign: dict[str, Any], event: dict[str, Any], industry: str
) -> tuple[str, list[str]]:
    source = _activity_source(campaign, event)
    topic = (
        campaign.get("topic")
        or campaign.get("summary")
        or campaign.get("name")
        or ""
    ).strip()
    partner = campaign.get("partner", "").strip()
    rules = [
        (("產業趨勢", "市場趨勢", "消費行為"), f"掌握{industry}產業趨勢與消費行為"),
        (("會員旅程",), "建立完整會員旅程"),
        (("會員數據", "會員資料"), "建立會員數據經營策略"),
        (("顧客輪廓",), "運用數據建立顧客輪廓"),
        (("分眾",), "透過精準分眾提升顧客互動"),
        (("回購",), "建立持續回購的會員經營方式"),
        (("LINE",), "LINE 在會員經營流程中的實際應用"),
        (("CRM",), "CRM 與會員資料的整合應用"),
        (("AI",), "AI 在品牌經營流程中的應用"),
        (("自動化",), "運用自動化延續顧客互動"),
        (("私域",), "深化私域流量與會員關係"),
        (("數位轉型",), f"拆解{industry}數位轉型的關鍵策略"),
        (("實戰案例", "品牌案例", "案例分享", "擔任講者"), f"{industry}品牌實戰案例分享"),
    ]
    points = []
    for keywords, point in rules:
        if any(keyword in source for keyword in keywords) and point not in points:
            points.append(point)

    focus = points[:2]
    if topic and focus:
        focus_text = "，並".join(focus)
        if partner:
            summary = f"本次活動將邀請「{partner}」與 Omnichat，聚焦「{topic}」，分享如何{focus_text}。"
        else:
            summary = f"本次活動聚焦「{topic}」，分享如何{focus_text}。"
    elif topic:
        summary = f"本次活動聚焦「{topic}」。"
    else:
        summary = "請補充活動主題與活動介紹。"
    return summary, points


def _cold_email_headlines(topic: str, industry: str) -> list[str]:
    """Create three topic-led headlines without using a single fixed event title."""
    audience = industry or "品牌"
    if any(keyword in topic for keyword in ("會員", "分眾", "數據")):
        return [
            f"【{audience}如何把會員數據變成回購成長？】",
            f"【{audience}下一波成長，不只是導流】",
            f"【從會員數據到分眾經營：{audience}如何持續成長？】",
        ]
    if any(keyword in topic for keyword in ("AI", "自動化")):
        return [
            f"【{audience}如何用 AI 打造自動化成長模式？】",
            f"【從互動到轉換：{topic}能帶來什麼改變？】",
            f"【{audience}下一步，如何讓行銷自動運轉？】",
        ]
    return [
        f"【{audience}如何掌握「{topic}」的成長機會？】",
        f"【從市場變化到品牌成長：{topic}】",
        f"【{audience}下一波成長，可以從哪裡開始？】",
    ]


def _industry_pain_opening(industry: str, campaign: dict[str, Any]) -> str:
    template = next(
        (
            item for item in load_industry_templates()
            if item.get("industry_name") == industry
            or item.get("id") == "food-gift"
            and any(keyword in industry for keyword in ("食品", "伴手禮"))
        ),
        None,
    )
    if not template:
        return f"不少{industry}品牌正重新思考，如何把一次互動累積成持續的顧客關係。"
    activity_source = _activity_source(campaign, {})
    restricted = ("AI", "LINE", "CRM", "Meta", "自動化")
    pains = [
        pain for pain in template.get("pain_points", [])
        if not any(term in pain and term not in activity_source for term in restricted)
    ][:2]
    if not pains:
        return f"不少{industry}品牌正重新思考，如何把一次互動累積成持續的顧客關係。"
    return f"不少{industry}品牌常遇到「{pains[0]}」的情況。" + (
        f"同時也需要面對「{pains[1]}」。" if len(pains) > 1 else ""
    )


def _market_trend_funnel(campaign: dict[str, Any], industry: str) -> str:
    topic = f"{campaign.get('topic', '')} {campaign.get('highlights', '')}"
    if any(keyword in topic for keyword in ("會員", "分眾", "數據", "私域")):
        stages = ["流量持續增加", "會員資料沒有完整累積", "無法精準分眾", "回購與再行銷難以延續"]
    elif any(keyword in topic for keyword in ("AI", "自動化")):
        stages = ["行銷任務持續增加", "團隊仍依賴人工操作", "互動無法即時延續", "成效難以規模化"]
    else:
        stages = ["市場投入持續增加", "顧客互動沒有累積", "品牌關係難以延續", "成長停留在單次轉換"]
    return "許多品牌開始面臨：\n\n" + "\n↓\n\n".join(stages)


def _activity_feature(campaign: dict[str, Any]) -> str:
    topic = campaign.get("topic") or campaign.get("name") or "會員經營"
    highlights = (campaign.get("highlights") or "").strip().splitlines()
    summary = highlights[0].strip() if highlights else ""
    if "。" in summary:
        summary = summary.split("。", 1)[0].strip() + "。"
    elif len(summary) > 90:
        summary = "聚焦產業趨勢、會員數據與品牌實戰經驗。"
    if summary:
        return f"本次以「{topic}」為核心，{summary}"
    return f"本次以「{topic}」為核心，聚焦產業趨勢、會員數據與品牌實戰經驗。"


def _activity_info_block(
    campaign: dict[str, Any], event: dict[str, Any], registration: str
) -> str:
    event_date = event.get("event_date") or campaign.get("event_date") or "（請填寫）"
    event_time = event.get("event_time") or campaign.get("event_time") or "（請填寫）"
    event_format = event.get("event_format") or campaign.get("event_format") or "實體"
    if event_format == "線上":
        location = event.get("online_method") or campaign.get("location") or "線上"
    else:
        location = event.get("location") or campaign.get("location") or "（請於活動管理填寫）"
    lines = [
        "【活動資訊】",
        "",
        f"活動時間｜{event_date} {event_time}",
        f"活動地點｜{location}",
    ]
    if event_format != "線上":
        lines.append(f"活動地址｜{event.get('address') or campaign.get('address') or '（請於活動管理填寫）'}")
    lines.extend(["", f"報名連結｜{registration}"])
    return "\n".join(lines)


def _scenario_email_paragraph(scenario: str, campaign: dict[str, Any]) -> str:
    registration = campaign.get("registration_url") or "（報名連結待補）"
    booking = campaign.get("booking_url") or "（預約連結待補）"
    messages = {
        "陌生開發邀約": f"如果這也是您近期關注的方向，歡迎參考活動資訊：{registration}",
        "活動報名後打招呼": "謝謝您報名這場活動，想先和您打聲招呼，也了解您最期待交流的主題。",
        "活動前交流邀約": f"活動開始前，想先了解您的需求，讓現場交流更聚焦：{booking}",
        "活動審核通知": "您的活動報名資料已完成審核，期待在活動中與您交流。",
        "活動出席確認": "想和您確認是否能如期出席，方便團隊為您保留交流席次。",
        "活動前提醒": f"提醒您活動即將開始，請預留時間參與。活動資訊：{registration}",
        "活動後關懷": "謝謝您參與活動，想了解今天的內容是否回應到您目前的需求。",
        "講者簡報分享": "附上講者簡報重點，方便您與團隊延伸討論。",
        "活動回放分享": "分享本次活動回放資訊，您可以依方便的時間觀看。",
        "報名未出席 Follow-up": "當天未能與您碰面有些可惜，特別整理活動重點供您參考。",
        "Demo 邀約": f"若想進一步了解實際應用方式，可由此預約 Demo：{booking}",
        "第二次追蹤": "想再次確認先前分享的內容是否符合您目前的規劃，也歡迎告訴我合適的交流時間。",
        "最後追蹤": "這是本次最後一次跟進；若目前時機尚未合適，我們也可以在未來有需要時再聯繫。",
    }
    return messages.get(scenario, messages["陌生開發邀約"])


def _scenario_cta(scenario: str, campaign: dict[str, Any]) -> str:
    if scenario in {"Demo 邀約", "活動前交流邀約"}:
        return f"預約交流：{campaign.get('booking_url') or '（預約連結待補）'}"
    return f"查看活動資訊：{campaign.get('registration_url') or '（報名連結待補）'}"


def generate_line(
    campaign: dict[str, Any], scenario: str, lead: dict[str, str],
    event_details: Optional[dict[str, Any]] = None,
) -> str:
    # Every LINE scenario uses the same mobile-first short-message structure.
    # `scenario` controls the UI selection only and is intentionally not printed.
    return _generate_line_invitation(campaign, lead, event_details or {})


def _generate_line_invitation(
    campaign: dict[str, Any], lead: dict[str, str], event: dict[str, Any]
) -> str:
    contact = lead.get("contact", "").strip()
    greeting = f"{contact}您好" if contact else "您好"
    industry = lead.get("industry") or _campaign_industry(campaign)
    event_type_tag = event.get("event_type_tag") or f"{campaign.get('event_format', '活動')}活動"
    feature_tag = event.get("feature_tag") or _line_feature_tag(campaign)
    topic = campaign.get("topic") or campaign.get("summary") or campaign.get("name") or "品牌成長"
    question = _line_invitation_question(topic, industry)
    pain_points = _line_industry_pain_points(industry, campaign)
    activity_points = _campaign_points(campaign)
    if len(activity_points) < 3:
        return (
            "活動內容不足，無法在不猜測的前提下整理四個活動亮點。"
            "請先到活動管理補充活動介紹與活動亮點。"
        )
    event_date = event.get("event_date") or campaign.get("event_date") or "（請填寫日期）"
    event_time = event.get("event_time") or campaign.get("event_time") or ""
    location = event.get("location_or_online") or campaign.get("location") or campaign.get("event_format") or ""
    fee_capacity = event.get("fee_capacity") or campaign.get("fee_capacity") or ""
    fee_line = f"\n🎟 {fee_capacity}" if fee_capacity else ""
    registration = event.get("registration_url") or campaign.get("registration_url") or "（請填寫報名連結）"
    summary = _campaign_summary(campaign)

    short_points = [_short_line_point(point) for point in activity_points[:4]]

    return f"""{greeting}，我是 Omnichat 周周👋

#{event_type_tag.strip().replace(' ', '')} #{feature_tag.strip().replace(' ', '')}

🚀 {question}

{summary}

如果您正關注：

{chr(10).join(f'✔ {point}' for point in pain_points)}

本次將分享：

{chr(10).join(f'✅ {point}' for point in short_points)}

📅 {event_date} {event_time}

📍 {location}
{fee_line}

👉 {registration}"""


def _short_line_point(point: str) -> str:
    replacements = {
        "掌握食品產業趨勢與消費行為": "掌握食品市場與消費行為變化",
        "建立會員數據經營策略": "建立完整的會員數據經營策略",
        "透過精準分眾提升顧客互動": "精準分眾提升顧客互動與回購",
        "深化私域流量與會員關係": "深化私域流量與會員關係經營",
    }
    shortened = replacements.get(point, point)
    return shortened if len(shortened) <= 22 else shortened[:22].rstrip("，。；; ")


def _line_feature_tag(campaign: dict[str, Any]) -> str:
    source = f"{campaign.get('topic', '')} {campaign.get('highlights', '')}"
    if "會員數據" in source:
        return "會員數據實戰"
    if "分眾" in source:
        return "分眾行銷"
    if "回購" in source:
        return "回購成長"
    return "品牌成長實戰"


def _line_invitation_question(topic: str, industry: str) -> str:
    if any(keyword in topic for keyword in ("會員", "分眾", "數據")):
        return f"{industry}如何把會員數據變成持續成長？"
    return f"{industry}如何掌握「{topic}」的下一波成長機會？"


def _line_industry_pain_points(
    industry: str, campaign: dict[str, Any]
) -> list[str]:
    template = next(
        (item for item in load_industry_templates() if item.get("industry_name") == industry),
        None,
    )
    if template:
        source = _activity_source(campaign, {})
        restricted = ("AI", "LINE", "CRM", "Meta", "自動化")
        points = [
            item for item in template.get("pain_points", [])
            if not any(term in item and term not in source for term in restricted)
        ]
        if len(points) >= 4:
            return points[:4]
    return [
        "新客互動難以持續累積",
        "會員資料缺乏清楚整理",
        "顧客溝通難以有效分眾",
        "回購與再行銷難以延續",
    ]


def generate_banner(campaign: dict[str, Any]) -> dict[str, str]:
    industry = _campaign_industry(campaign)
    summary = _campaign_summary(campaign)
    points = _campaign_points(campaign)
    points_text = "\n".join(
        f"{index}. {point}" for index, point in enumerate(points[:4], 1)
    ) or "請先到活動管理填寫活動重點"
    event_datetime = " ".join(
        item for item in (campaign.get("event_date", ""), campaign.get("event_time", ""))
        if item
    )
    return {
        "活動大標": campaign.get("name") or "活動名稱待補",
        "活動副標": summary,
        "4 個產業痛點": "\n".join(
            f"{index}. {point}"
            for index, point in enumerate(_line_industry_pain_points(industry, campaign), 1)
        ),
        "4 個活動亮點": points_text,
        "CTA": "立即報名，預留席次",
        "EDM 文案": f"{campaign.get('name', '本次活動')}\n{summary}\n\n{points_text}\n\n{event_datetime}\n{campaign.get('registration_url', '')}",
        "Banner 文案": f"{campaign.get('name', '本次活動')}｜{event_datetime}",
        "社群貼文文案": f"{campaign.get('name', '本次活動')}\n\n{summary}\n\n👉 {campaign.get('registration_url') or '報名連結待補'}",
        "一頁式介紹圖文案": f"活動名稱：{campaign.get('name', '')}\n活動摘要：{summary}\n活動重點：\n{points_text}\n活動時間：{event_datetime}\n報名連結：{campaign.get('registration_url', '')}\nBanner：{campaign.get('image_path') or '尚未上傳'}",
    }
