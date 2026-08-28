import re
from typing import Any, Optional

from storage import load_industry_templates


_PROTECTED_SUBJECT_TOKENS = (
    "LINE Biz-Solutions",
    "Marketing Messages",
    "Google Ads",
    "Omnichat",
    "Messenger",
    "Google",
    "LINE",
    "Meta",
)
_SUBJECT_TOKEN_PATTERN = re.compile(
    "(" + "|".join(re.escape(token) for token in _PROTECTED_SUBJECT_TOKENS)
    + r"|[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)"
)


def _campaign_industry(campaign: dict[str, Any]) -> str:
    return campaign.get("primary_industry") or campaign.get("suitable_industries") or "品牌"


def _campaign_points(campaign: dict[str, Any]) -> list[str]:
    stored = campaign.get("activity_points", [])
    if isinstance(stored, str):
        stored = [
            line.strip().lstrip("-•・ ")
            for line in stored.splitlines()
            if line.strip().lstrip("-•・ ")
        ]
    if isinstance(stored, list):
        points = [str(item).strip() for item in stored if str(item).strip()]
        if points:
            return points
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
        (campaign.get("subject_a") or campaign.get("email_title_a", "")).strip(),
        (campaign.get("subject_b") or campaign.get("email_title_b", "")).strip(),
        (campaign.get("subject_c") or campaign.get("email_title_c", "")).strip(),
    ]
    titles = [title for title in titles if title]
    return titles or fallback


def generate_subject_suggestions(
    campaign: dict[str, Any], variant: int = 0
) -> tuple[str, str, str]:
    """Create three grounded B2B subjects using campaign text only."""
    name = (campaign.get("name") or "活動交流").strip()
    industry = _subject_industry(_campaign_industry(campaign))
    summary = (campaign.get("summary") or "").strip()
    introduction = (campaign.get("introduction") or "").strip()
    source_phrases = _campaign_points(campaign)
    if not source_phrases:
        source_phrases = _intro_points(summary or introduction)
    first = _subject_phrase(source_phrases[0] if source_phrases else name)
    second = _subject_phrase(
        source_phrases[1] if len(source_phrases) > 1 else (summary or name)
    )
    core = first
    event_label = _subject_event_label(name)
    event_date = _subject_date(campaign.get("event_date", ""))
    style = variant % 3

    questions = [
        f"{industry}如何掌握{first}？",
        f"{industry}下一步，{first}的關鍵在哪？",
        f"如何從{first}走向{second}？",
    ]
    benefits = [
        f"從{first}到{second}｜{industry}實戰交流",
        f"{first} × {second}｜{industry}交流",
        f"{industry}實戰交流｜{first}與{second}",
    ]
    trends = [
        f"【{event_label}】{core}",
        f"【{event_date} {industry}交流】{first}" if event_date else f"【{industry}交流】{first}",
        f"【{event_label}】{second}",
    ]
    return tuple(
        _subject_clip(value) for value in (questions[style], benefits[style], trends[style])
    )


def _subject_industry(value: str) -> str:
    cleaned = value.replace("等品牌", "").replace("品牌", "").strip(" 、，,")
    cleaned = cleaned.replace(" / ", ",").replace("/", ",").replace("、", ",")
    return next((item.strip() for item in cleaned.split(",") if item.strip()), "產業")


def _subject_phrase(value: str) -> str:
    phrase = " ".join(value.replace("\n", " ").split()).strip("。！？!?，,；;｜ ")
    for separator in (" - ", " — ", "：", ":", "。", "！", "!", "？", "?", "，", ",", "；", ";", "｜"):
        phrase = phrase.split(separator, 1)[0].strip()
    for prefix in ("本次活動", "如何", "透過", "運用", "掌握", "建立", "提升", "深化", "分享"):
        if phrase.startswith(prefix) and len(phrase) > len(prefix) + 2:
            phrase = phrase[len(prefix):].strip()
            break
    return _token_safe_truncate(phrase, 16) or "活動核心議題"


def _subject_event_label(value: str) -> str:
    """Create a compact event label without cutting English brand/product names."""
    label = " ".join(str(value).replace("\n", " ").split()).strip()
    for separator in (" - ", " — ", "：", ":"):
        head = label.split(separator, 1)[0].strip()
        if head:
            label = head
            break
    return _token_safe_truncate(label, 18) or "活動交流"


def _subject_date(value: str) -> str:
    parts = str(value).split("-")
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        return f"{int(parts[1])}/{int(parts[2])}"
    return str(value).strip()


def _subject_clip(value: str) -> str:
    if len(value) <= 32:
        return value
    suffix = "？" if value.endswith("？") else ""
    if "｜" in value:
        main_clause = value.split("｜", 1)[0].rstrip()
        if 12 <= len(main_clause) <= 32:
            return main_clause
    return _token_safe_truncate(value, 32, suffix)


def _token_safe_truncate(value: str, max_length: int, suffix: str = "") -> str:
    """Trim mixed Chinese/English text while keeping English tokens indivisible."""
    text = " ".join(str(value).split()).strip()
    if len(text) <= max_length:
        return text

    budget = max_length - len(suffix)
    units: list[str] = []
    cursor = 0
    for match in _SUBJECT_TOKEN_PATTERN.finditer(text):
        units.extend(text[cursor:match.start()])
        units.append(match.group(0))
        cursor = match.end()
    units.extend(text[cursor:])

    kept: list[str] = []
    used = 0
    for unit in units:
        if used + len(unit) > budget:
            break
        kept.append(unit)
        used += len(unit)

    result = "".join(kept).rstrip("。！？!?，,、；;｜：:×- ")
    result = re.sub(r"(?:從|到|與|和|及)$", "", result).rstrip()
    return result + suffix


def _campaign_context(campaign: dict[str, Any]) -> str:
    return (
        f"{campaign.get('name', '本次活動')}｜{campaign.get('event_date', '')}｜"
        f"{campaign.get('event_format', '')}"
    )


def generate_email(
    campaign: dict[str, Any], scenario: str, lead: dict[str, str],
    event_details: Optional[dict[str, Any]] = None,
) -> tuple[list[str], str, str]:
    normalized = _EMAIL_SCENARIO_MAPPING.get(scenario, scenario)
    supported = {
        "活動前陌生開發", "活動前確認出席通知", "活動後關懷",
        "活動未到場分享", "陌生開發", "二次追蹤",
    }
    if normalized not in supported:
        raise ValueError(f"不支援的 Email 情境：{scenario}")
    return _generate_email_v2(
        campaign, normalized, lead, event_details or {}
    )


# Old scenario names remain callable so saved drafts/integrations do not break.
# The UI only exposes the six consolidated scenarios.
_EMAIL_SCENARIO_MAPPING = {
    "陌生開發邀約": "活動前陌生開發",
    "活動報名後打招呼": "活動前確認出席通知",
    "活動前交流邀約": "活動前確認出席通知",
    "活動審核通知": "活動前確認出席通知",
    "活動出席確認": "活動前確認出席通知",
    "活動前確認通知（Pre-call）": "活動前確認出席通知",
    "活動前提醒": "活動前確認出席通知",
    "活動後跟進": "活動後關懷",
    "講者簡報分享": "活動後關懷",
    "活動回放分享": "活動後關懷",
    "報名未出席 Follow-up": "活動未到場分享",
    "一般開發信": "陌生開發",
    "Demo 邀約": "陌生開發",
    "第二次追蹤": "二次追蹤",
    "最後追蹤": "二次追蹤",
    "自主報名確認": "活動前確認出席通知",
}


def _generate_email_v2(
    campaign: dict[str, Any], scenario: str, lead: dict[str, Any],
    event: dict[str, Any],
) -> tuple[list[str], str, str]:
    """Six deterministic Email templates using activity and Supabase industry data."""
    is_event = scenario.startswith("活動")
    contact = (lead.get("contact") or "").strip()
    brand = (lead.get("brand") or "").strip()
    greeting = f"Dear {contact} 您好，" if contact else "您好，"
    brand_phrase = brand or "貴品牌"
    event_name = campaign.get("name") or "本次活動"
    introduction = (campaign.get("introduction") or "").strip()
    points = _campaign_points(campaign) if campaign else []
    points = [point for point in points if point != "請參考活動介紹"][:4]
    reference = _relevant_industry_reference(
        lead.get("industry_context"), campaign, is_event
    )
    industry_name = reference.get("industry_name", "")
    industry_paragraph = _industry_personalization(reference, industry_name)
    points_block = "\n".join(f"・{point}" for point in points)
    info_block = _optional_activity_info(campaign)
    banner_block = (
        f"\n\n【活動 Banner｜{campaign['image_path']}】"
        if campaign.get("image_path") else ""
    )
    booking = campaign.get("booking_url", "")
    registration = campaign.get("registration_url", "")
    materials = event.get("materials_url") or campaign.get("materials_url", "")
    service = event.get("service_intro_url") or campaign.get("service_intro_url", "")
    if not service:
        service = event.get("service_pdf_name", "")
    service_line = "📄 Omnichat 服務介紹（含會員經營策略與實務案例）"
    if service:
        service_line += f"｜{service}"
    material_lines = []
    if materials:
        material_lines.append(f"📄 活動簡報／會後資料｜{materials}")
    material_lines.append(service_line)
    resources = "\n".join(material_lines)

    if scenario == "活動前陌生開發":
        subjects = list(generate_subject_suggestions(campaign))
        if (lead.get("selected_subject") or "").strip():
            subjects = [lead["selected_subject"].strip()]
        invitation_reason = (
            f"這次想邀請 {brand_phrase} 參與《{event_name}》，"
            "活動內容與品牌近期可能關注的經營議題相當相關。"
        )
        activity_copy = introduction or campaign.get("summary") or ""
        observation = (lead.get("observation") or "").strip()
        if observation:
            activity_copy = f"{observation}\n\n{activity_copy}".strip()
        registration_cta = (
            f"👉 活動報名｜{registration}" if registration
            else "若您有興趣，歡迎直接回覆此信，我再提供完整報名資訊。"
        )
        exchange_cta = (
            f"若希望先了解適合品牌的應用，也可安排 15 分鐘交流｜{booking}"
            if booking else
            "若希望先了解適合品牌的應用，也歡迎回覆安排 15 分鐘交流。"
        )
        exchange_cta = _reference_cta(reference) or exchange_cta
        body = f"""{greeting}

{invitation_reason}

{activity_copy}

【活動亮點】
{points_block}{industry_paragraph}

{info_block}

{registration_cta}

{exchange_cta}{banner_block}"""
        return subjects, _clean_email(body), exchange_cta

    if scenario == "活動前確認出席通知":
        subject = f"活動確認出席｜【{event_name}】活動出席確認信（Energy）"
        topics = points_block
        topics_section = (
            "\n\n為了讓當天內容更貼近品牌的實際情境，若您正在思考：\n"
            f"{topics}" if topics else ""
        )
        cta = (
            f"歡迎安排 15 分鐘快速交流 👉 {booking}" if booking
            else "歡迎直接回覆方便時段，安排 15 分鐘快速交流。"
        )
        body = f"""{greeting}

您好，我是 Omnichat 周周，是負責品牌的窗口。
提醒您所報名的《{event_name}》即將舉行。

先為您暫保留席次，想與您確認當天是否方便出席？
再麻煩協助回覆，謝謝您！

{info_block}{banner_block}{topics_section}{industry_paragraph}

我很樂意先依品牌現況分享相關案例與應用，讓您在參與活動前能具體參考！
{cta}

{service_line}

期待活動前能先認識您，讓當天交流更有收穫😊"""
        return [subject], _clean_email(body), cta

    if scenario == "活動後關懷":
        date_label = _subject_date(campaign.get("event_date", ""))
        subject = (
            f"✨ 感謝參與 {date_label}《{_subject_event_label(event_name)}》"
            "｜活動重點與簡報分享"
        )
        speaker = campaign.get("partner", "")
        speaker_copy = f"{speaker} 分享了" if speaker else "活動中分享了"
        activity_topic = introduction or campaign.get("summary") or event_name
        insight = _commercial_insight(points, activity_topic)
        cta_topics = "、".join(points[:3]) or "本次活動議題"
        cta = (
            f"歡迎回覆方便聯繫的時段，或直接與我聯繫 👉 {booking}"
            if booking else "歡迎回覆方便聯繫的時段，我再協助安排 15 分鐘交流。"
        )
        body = f"""{greeting}

感謝您撥空參加《{event_name}》活動，當天現場議程較緊湊，若未能與您進一步交流，先將活動重點與當日相關資料整理分享給您！

本次活動中，{speaker_copy} {activity_topic}，主要聚焦於：

{points_block}

【活動核心商業洞察】
{insight}{industry_paragraph}

{resources}

若您對活動中提到的 {cta_topics} 有興趣，很樂意安排一段 15 分鐘交流，依據目前品牌經營情境，分享相關產業應用案例供您參考。

{cta}

再次感謝您的參與，也期待有機會與您進一步交流！{banner_block}"""
        selected = (lead.get("selected_subject") or "").strip()
        return [selected or _subject_clip(subject)], _clean_email(body), cta

    if scenario == "活動未到場分享":
        subject = f"《{_subject_event_label(event_name)}》活動重點與會後資料分享"
        cta = (
            f"若其中有正在評估的議題，很樂意安排 15 分鐘交流｜{booking}"
            if booking else
            "若其中有正在評估的議題，很樂意另外安排 15 分鐘交流。"
        )
        body = f"""{greeting}

先前有看到您報名《{event_name}》，當天很可惜未能有機會與您現場交流，因此整理本次活動幾個重點與相關資料，提供您會後參考。

{points_block}{industry_paragraph}

{resources}

{cta}
我也很樂意依品牌目前經營情況，分享相關案例與應用。{banner_block}"""
        selected = (lead.get("selected_subject") or "").strip()
        return [selected or _subject_clip(subject)], _clean_email(body), cta

    if scenario == "陌生開發":
        subject_topic = industry_name or brand or "品牌經營"
        subject = f"想和您交流｜{subject_topic}的顧客經營方向"
        opening = (
            f"這次聯繫是希望和 {brand} 交流目前的品牌經營方向。"
            if brand else "這次聯繫是希望交流目前常見的品牌經營方向。"
        )
        value = _outbound_value(reference)
        cta = _reference_cta(reference) or "若您方便，歡迎直接回覆此信，安排 15 分鐘交流。"
        body = f"""{greeting}

{opening}

{value}

{cta}"""
        selected = (lead.get("selected_subject") or "").strip()
        return [selected or _subject_clip(subject)], _clean_email(body), cta

    subject_topic = industry_name or brand or "品牌經營"
    subject = f"延續前次分享｜{subject_topic}的一個實務切角"
    new_value = _followup_value(reference)
    cta = _reference_cta(reference) or "若近期有合適時機，歡迎回覆方便的交流時段。"
    body = f"""{greeting}

想簡短延續前次分享，不確定目前是否正好有相關規劃，因此補充一個可參考的方向：

{new_value}

不急著現在決定；若近期有合適時機，{cta}"""
    selected = (lead.get("selected_subject") or "").strip()
    return [selected or _subject_clip(subject)], _clean_email(body), cta


def _relevant_industry_reference(
    template: Optional[dict[str, Any]], campaign: dict[str, Any], is_event: bool
) -> dict[str, Any]:
    if not template:
        return {
            "industry_name": "", "pain_points": [], "omnichat_applications": [],
            "development_angles": [], "showcase_cases": [], "common_ctas": [],
        }

    source = _activity_source(campaign, {}) if is_event else ""
    concept_groups = (
        ("廣告", "Ads", "獲客", "流量", "新客", "Meta"),
        ("會員", "顧客", "好友", "識別", "輪廓", "資料"),
        ("分眾", "標籤", "溝通"),
        ("回購", "再行銷", "關懷", "留存"),
        ("LINE", "推播", "對話"),
        ("自動化", "旅程"),
        ("客服", "售後", "出貨"),
    )

    def score(text: str) -> int:
        if not source:
            return 0
        return sum(
            1 for group in concept_groups
            if any(term.lower() in source.lower() for term in group)
            and any(term.lower() in text.lower() for term in group)
        )

    def ranked(values: list[Any], limit: int) -> list[Any]:
        indexed = list(enumerate(values))
        indexed.sort(
            key=lambda pair: (-score(_reference_text(pair[1])), pair[0])
        )
        return [value for _, value in indexed[:limit]]

    public_cases = [
        case for case in template.get("showcase_cases", [])
        if case.get("public", True)
    ]
    return {
        "industry_name": template.get("industry_name", ""),
        "pain_points": ranked(template.get("pain_points", []), 2),
        "omnichat_applications": ranked(
            template.get("omnichat_applications")
            or template.get("omnichat_scenarios", []), 2
        ),
        "development_angles": ranked(template.get("development_angles", []), 2),
        "showcase_cases": ranked(public_cases, 1),
        "common_ctas": template.get("common_ctas", [])[:1],
    }


def _reference_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(str(item) for item in value.values())
    return str(value)


def _industry_personalization(reference: dict[str, Any], industry: str) -> str:
    if not industry:
        return ""
    pain = next(iter(reference.get("pain_points", [])), "")
    angle = next(iter(reference.get("development_angles", [])), "")
    application = next(iter(reference.get("omnichat_applications", [])), "")
    focus = angle or application
    if pain and focus:
        return (
            f"\n\n以{industry}的經營情境來看，若目前也在面對「{pain}」，"
            f"可進一步從「{focus}」延伸思考，讓本次活動議題更貼近實際應用。"
        )
    if pain:
        return f"\n\n對{industry}而言，「{pain}」也是可從本次活動延伸交流的方向。"
    if focus:
        return f"\n\n若以{industry}為例，也可進一步交流「{focus}」的實際應用。"
    return ""


def _optional_activity_info(campaign: dict[str, Any]) -> str:
    values = []
    event_datetime = " ".join(
        value for value in (
            campaign.get("event_date", ""), campaign.get("event_time", "")
        ) if value
    )
    if event_datetime:
        values.append(f"活動時間｜{event_datetime}")
    if campaign.get("event_format"):
        values.append(f"活動形式｜{campaign['event_format']}")
    if campaign.get("location"):
        values.append(f"活動地點｜{campaign['location']}")
    if campaign.get("event_format") != "線上" and campaign.get("address"):
        values.append(f"活動地址｜{campaign['address']}")
    return "【活動資訊】\n" + "\n".join(values) if values else ""


def _commercial_insight(points: list[str], fallback: str) -> str:
    if len(points) >= 2:
        return (
            f"從「{points[0]}」延伸到「{points[1]}」，重點不只是理解活動內容，"
            "也在於如何把相關議題轉化成後續可執行的品牌經營方向。"
        )
    if points:
        return f"「{points[0]}」是本次活動最適合延伸到品牌實際經營情境的核心議題。"
    return f"「{fallback}」是本次活動可進一步延伸到品牌經營情境的核心方向。"


def _outbound_value(reference: dict[str, Any]) -> str:
    industry = reference.get("industry_name") or "品牌"
    pain = next(iter(reference.get("pain_points", [])), "")
    application = next(iter(reference.get("omnichat_applications", [])), "")
    angle = next(iter(reference.get("development_angles", [])), "")
    case = next(iter(reference.get("showcase_cases", [])), {})
    if not any((pain, application, angle, case)):
        return "Omnichat 可分享顧客互動、會員經營與分眾溝通的相關實務案例。"
    sentences = []
    if pain:
        sentences.append(f"許多{industry}品牌近期也在思考「{pain}」。")
    if angle or application:
        sentences.append(f"這次想從「{angle or application}」分享一個可落地的應用方向。")
    if case.get("brand_name"):
        case_focus = case.get("key_points") or case.get("use_cases") or "相關應用"
        sentences.append(f"也可補充 {case['brand_name']} 在「{case_focus}」上的案例供您參考。")
    return "\n\n".join(sentences)


def _followup_value(reference: dict[str, Any]) -> str:
    angle = next(iter(reference.get("development_angles", [])[1:2]), "")
    if not angle:
        angle = next(iter(reference.get("development_angles", [])), "")
    case = next(iter(reference.get("showcase_cases", [])), {})
    application = next(iter(reference.get("omnichat_applications", [])), "")
    if case.get("brand_name"):
        focus = case.get("key_points") or case.get("use_cases") or "品牌經營"
        return f"可參考 {case['brand_name']} 在「{focus}」上的應用方式。"
    if angle or application:
        return f"「{angle or application}」可作為評估下一步時的一個實務切角。"
    return "若目前正盤點顧客經營流程，也可以先從一個明確場景小範圍交流。"


def _reference_cta(reference: dict[str, Any]) -> str:
    return next(iter(reference.get("common_ctas", [])), "")


def _clean_email(value: str) -> str:
    lines = [line.rstrip() for line in value.splitlines()]
    compact: list[str] = []
    for line in lines:
        if not line and compact and compact[-1] == "":
            continue
        compact.append(line)
    return "\n".join(compact).strip()


def _generate_attendance_confirmation_email(
    campaign: dict[str, Any], lead: dict[str, str], event: dict[str, Any]
) -> tuple[list[str], str, str]:
    """Permanent rule-based template for 活動前確認通知（Pre-call）."""
    event_name = campaign.get("name") or "本次活動"
    contact = lead.get("contact") or "貴品牌團隊"
    subject = f"活動確認出席｜【{event_name}】活動出席確認信（Energy）"
    topics = _attendance_confirmation_topics(campaign, lead)
    if len(topics) < 3:
        warning = (
            "活動與品牌需求資料不足，無法在不猜測的前提下整理 3～4 個議題。"
            "請先補充活動介紹、活動重點或品牌需求。"
        )
        return [subject], warning, ""

    event_datetime = " ".join(
        value for value in (
            campaign.get("event_date", ""), campaign.get("event_time", "")
        ) if value
    ) or "（請於活動管理填寫）"
    location = (
        campaign.get("location") or campaign.get("event_format")
        or "（請於活動管理填寫）"
    )
    visual = campaign.get("image_path") or "（活動管理尚未上傳）"
    booking = campaign.get("booking_url") or "（請於活動管理補上預約交流連結）"
    service_intro = event.get("service_intro_url") or "（請補上服務介紹連結）"
    topic_lines = "\n".join(f"• {topic}" for topic in topics[:4])
    cta = (
        "我很樂意先依品牌現況分享相關案例與應用，讓您在參與活動前能具體參考！\n"
        f"歡迎安排 15 分鐘快速交流 👉【{booking}】"
    )
    body = f"""Dear {contact} 您好，

我是 Omnichat 周周，也是本次與您聯繫的品牌窗口。
提醒您已報名【{event_name}】，這邊已先為您保留席次，想確認當天是否方便出席？

【活動資訊】
活動時間｜{event_datetime}
活動地點｜{location}
活動主視覺｜{visual}

為了讓當天內容更貼近品牌的實際情境，若您正好在思考：
{topic_lines}

{cta}

📄 Omnichat 服務介紹（含會員經營策略與實務案例）｜{service_intro}

期待活動前能先認識您，讓當天交流更有收穫😊"""
    return [subject], body, cta


def _attendance_confirmation_topics(
    campaign: dict[str, Any], lead: dict[str, str]
) -> list[str]:
    """Use only supplied campaign and brand-need text; never invent topics."""
    candidates = []
    needs = (lead.get("needs") or "").strip()
    if needs:
        candidates.extend(_intro_points(needs))
    candidates.extend(_campaign_points(campaign))
    introduction = (campaign.get("introduction") or "").strip()
    if introduction:
        candidates.extend(_intro_points(introduction))

    topics = []
    for candidate in candidates:
        normalized = str(candidate).strip().lstrip("-•・ ")
        if normalized and normalized not in topics:
            topics.append(normalized)
    return topics[:4]


def _generate_recovered_email(
    campaign: dict[str, Any], scenario: str, lead: dict[str, str]
) -> tuple[list[str], str, str]:
    """Recovered deterministic templates from commit 4857935."""
    brand = lead.get("brand") or "貴品牌"
    contact = lead.get("contact") or "貴品牌團隊"
    topic = campaign.get("topic") or campaign.get("name") or "活動資訊"
    subjects = _campaign_titles(campaign, [
        f"【{scenario}】{campaign.get('name', 'Omnichat 活動')}｜{brand}",
        f"邀請 {brand} 交流：{topic}",
        f"{contact} 您好｜一場與{lead.get('needs') or '會員成長'}有關的活動",
    ])
    selected_subject = (lead.get("selected_subject") or "").strip()
    if selected_subject:
        subjects = [selected_subject]
    body = f"""{contact} 您好，

我是 Omnichat 團隊。這封信想和您分享「{_campaign_context(campaign)}」。

我們觀察到 {brand} 在{lead.get('industry') or '品牌經營'}領域持續投入。{lead.get('observation') or '許多品牌正積極整合會員互動與轉換流程。'}

本次活動主題：{campaign.get('topic') or campaign.get('name') or '待補充'}
活動亮點：{campaign.get('introduction') or campaign.get('highlights') or '待補充'}
與貴品牌的可能連結：{lead.get('needs') or '期待進一步了解目前的會員經營需求。'}

{_scenario_email_paragraph(scenario, campaign)}

先前交流紀錄：{lead.get('precall') or '尚無'}

若您方便，歡迎直接回覆此信，我會協助安排後續交流。

Omnichat 團隊"""
    return subjects, body, _scenario_cta(scenario, campaign)


def _generate_v1_email(
    campaign: dict[str, Any], scenario: str, lead: dict[str, str]
) -> tuple[list[str], str, str]:
    """Email Builder V1.0: five deterministic templates, no external AI API."""
    introduction = (campaign.get("introduction") or "").strip()
    brand = (lead.get("brand") or "貴品牌").strip()
    contact = (lead.get("contact") or "您好").strip()
    greeting = f"Dear {contact} 您好，" if contact != "您好" else "您好，"
    observation = (lead.get("observation") or "").strip()
    observation_block = f"\n\n{observation}" if observation else ""
    topic = campaign.get("name") or _intro_topic(introduction)
    subjects = _campaign_titles(campaign, _v1_subjects(scenario, brand, topic))
    selected_subject = (lead.get("selected_subject") or "").strip()
    if selected_subject:
        subjects = [selected_subject]
    points = _campaign_points(campaign) or _intro_points(introduction)
    points_block = "\n".join(f"• {point}" for point in points)
    feature = campaign.get("summary") or _intro_feature(introduction)
    activity_info = _campaign_activity_info(campaign)
    industry_reference = _safe_industry_reference(
        lead.get("industry_context"), campaign
    )
    industry_opening = ""
    if industry_reference["pain_points"]:
        industry_opening = "\n\n" + "；".join(industry_reference["pain_points"][:2]) + "。"
    reference_block = _industry_reference_block(industry_reference)
    banner_block = (
        f"\n\n【活動 Banner｜{campaign['image_path']}】"
        if campaign.get("image_path") else ""
    )

    templates = {
        "陌生開發邀約": (
            f"{greeting}\n\n想和您分享一場與 {brand} 可能相關的交流活動。{industry_opening}"
            f"{observation_block}\n\n【活動介紹】\n{introduction}\n\n"
            f"【活動重點】\n{points_block}\n\n"
            f"【活動資訊】\n{activity_info}\n\n"
            f"{reference_block}"
            "若這也是您近期關注的方向，歡迎直接回覆此信，我很樂意進一步分享活動資訊。"
        ),
        "活動前提醒": (
            f"{greeting}\n\n已收到您的報名，活動前先與您打聲招呼！\n\n"
            f"【活動一句話特色】\n{feature}\n\n"
            f"💡 若您近期正關注：\n{points_block}\n\n"
            "很樂意在活動前依您的品牌現況分享相關案例，讓當天交流更有收穫。\n\n"
            "👉 歡迎直接回覆方便時段，彈性安排 15 分鐘交流。"
        ),
        "活動後跟進": (
            f"{greeting}\n\n謝謝您參與本次活動；若當天未能出席，也整理了重點供您參考。\n\n"
            f"【活動重點整理】\n{points_block}\n\n"
            "如需活動簡報或相關資料，歡迎直接回覆此信索取。\n\n"
            "若有希望進一步交流的方向，也很樂意安排時間討論。"
        ),
        "自主報名確認": (
            f"{greeting}\n\n已收到您報名本次活動，目前正在陸續確認名單中。\n\n"
            "若活動採審核制或有後續參與資訊，我們會再另行通知。\n\n"
            f"【活動資訊】\n{activity_info}\n\n"
            "若有任何問題，歡迎直接回覆此信。\n\n期待活動當天與您交流！"
        ),
        "一般開發信": (
            f"{greeting}{observation_block}\n\n"
            f"這次聯繫是希望和 {brand} 交流顧客經營與數位互動的實際做法。\n\n"
            "Omnichat 可分享相關品牌在顧客互動、分眾溝通與經營流程上的應用案例。"
            f"{f'{chr(10)}{chr(10)}補充資訊：{introduction}' if introduction else ''}\n\n"
            f"{reference_block}"
            "若您方便，歡迎直接回覆此信，我們可以再找合適時間交流。"
        ),
    }
    cta = {
        "陌生開發邀約": "歡迎直接回覆此信，索取完整活動資訊。",
        "活動前提醒": "如需協助，歡迎直接回覆此信。",
        "活動後跟進": "歡迎回覆您想進一步交流的方向。",
        "自主報名確認": "歡迎回覆您最關注的活動內容。",
        "一般開發信": "歡迎直接回覆此信，安排後續交流。",
    }[scenario]
    if industry_reference.get("common_ctas"):
        cta = industry_reference["common_ctas"][0]
    body = f"{templates[scenario]}{banner_block}"
    return subjects, body, cta


def _intro_topic(introduction: str) -> str:
    first_line = next((line.strip() for line in introduction.splitlines() if line.strip()), "活動交流")
    for separator in ("。", "！", "!", "？", "?"):
        first_line = first_line.split(separator, 1)[0]
    return first_line[:36].rstrip("，、；; ") or "活動交流"


def _intro_feature(introduction: str) -> str:
    if not introduction.strip():
        return "活動資訊將另行提供。"
    first = _intro_points(introduction)[0]
    return first[:100]


def _intro_points(introduction: str) -> list[str]:
    """Split only supplied activity text into up to four display points."""
    normalized = introduction.replace("\r", "\n")
    for separator in ("。", "，", ",", "；", ";", "！", "!", "？", "?"):
        normalized = normalized.replace(separator, "\n")
    points = []
    for line in normalized.splitlines():
        point = line.strip().lstrip("-–—•✔✅0123456789.、 ")
        if point and point not in points:
            points.append(point[:120])
        if len(points) == 4:
            break
    return points or ["請參考活動介紹"]


def _intro_event_info(introduction: str) -> str:
    keywords = ("日期", "時間", "地點", "地址", "形式", "報名", "連結", "網址")
    lines = [
        line.strip() for line in introduction.splitlines()
        if line.strip() and any(keyword in line for keyword in keywords)
    ]
    return "\n".join(lines[:6]) or "活動介紹未提供日期、地點或報名資訊。"


def _campaign_activity_info(campaign: dict[str, Any]) -> str:
    lines = [
        f"活動名稱｜{campaign.get('name', '')}",
        f"活動時間｜{' '.join(value for value in (campaign.get('event_date', ''), campaign.get('event_time', '')) if value)}",
        f"活動形式｜{campaign.get('event_format', '')}",
        f"活動地點｜{campaign.get('location', '')}",
    ]
    if campaign.get("event_format") != "線上" and campaign.get("address"):
        lines.append(f"活動地址｜{campaign['address']}")
    if campaign.get("registration_url"):
        lines.append(f"報名連結｜{campaign['registration_url']}")
    return "\n".join(line for line in lines if not line.endswith("｜"))


def _safe_industry_reference(
    template: Optional[dict[str, Any]], campaign: dict[str, Any]
) -> dict[str, list]:
    if not template:
        return {"pain_points": [], "development_angles": [], "showcase_cases": [], "common_ctas": []}
    activity_source = _activity_source(campaign, {})
    restricted = ("AI", "LINE", "CRM", "Meta", "自動化")

    def allowed(text: str) -> bool:
        return not any(term in text and term not in activity_source for term in restricted)

    return {
        "pain_points": [item for item in template.get("pain_points", []) if allowed(item)],
        "omnichat_applications": [
            item for item in (
                template.get("omnichat_applications")
                or template.get("omnichat_scenarios", [])
            ) if allowed(item)
        ],
        "development_angles": [item for item in template.get("development_angles", []) if allowed(item)],
        "showcase_cases": [
            item for item in template.get("showcase_cases", [])
            if item.get("public", True)
            and allowed(" ".join(str(value) for value in item.values()))
        ],
        "common_ctas": [item for item in template.get("common_ctas", []) if allowed(item)],
        "cautions": template.get("cautions", []),
    }


def _industry_reference_block(reference: dict[str, list]) -> str:
    angles = reference.get("development_angles", [])[:2]
    applications = reference.get("omnichat_applications", [])[:2]
    cases = reference.get("showcase_cases", [])[:2]
    if not angles and not applications and not cases:
        return ""
    lines = ["【產業參考】"]
    lines.extend(f"• 開發切角：{item}" for item in angles)
    lines.extend(f"• Omnichat 應用：{item}" for item in applications)
    lines.extend(
        f"• 相關案例：{case.get('brand_name')}｜{case.get('use_cases')}｜{case.get('key_points', '')}"
        for case in cases if case.get("brand_name")
    )
    return "\n".join(lines) + "\n\n"


def _v1_subjects(scenario: str, brand: str, topic: str) -> list[str]:
    labels = {
        "陌生開發邀約": "活動邀請",
        "活動前提醒": "活動前提醒",
        "活動後跟進": "活動後交流",
        "自主報名確認": "報名確認",
        "一般開發信": "交流邀請",
    }
    label = labels[scenario]
    return [
        f"【{label}】{topic}",
        f"{brand} 您好｜{topic}",
        f"關於「{topic}」的{label}",
    ]


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
    selected_title = (
        lead.get("selected_subject") or event.get("selected_email_title", "")
    ).strip()
    if selected_title:
        subjects = [selected_title]
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
    selected_reference = _safe_industry_reference(lead.get("industry_context"), campaign)
    pain_points = _line_industry_pain_points(industry, campaign, lead.get("industry_context"))
    reference_lines = []
    if selected_reference.get("development_angles"):
        reference_lines.append(f"💡 {selected_reference['development_angles'][0]}")
    if selected_reference.get("showcase_cases"):
        case = selected_reference["showcase_cases"][0]
        reference_lines.append(f"📌 案例：{case.get('brand_name')}｜{case.get('use_cases')}")
    reference_block = f"\n\n{chr(10).join(reference_lines)}" if reference_lines else ""
    activity_points = _campaign_points(campaign)
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

{summary}{reference_block}

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
    industry: str, campaign: dict[str, Any], template: Optional[dict[str, Any]] = None
) -> list[str]:
    if template:
        points = _safe_industry_reference(template, campaign)["pain_points"]
    else:
        points = []
    defaults = [
        "新客互動難以持續累積",
        "會員資料缺乏清楚整理",
        "顧客溝通難以有效分眾",
        "回購與再行銷難以延續",
    ]
    return list(dict.fromkeys([*points, *defaults]))[:4]


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
