import re
from datetime import date
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


# Permanent tone and structure reference for 活動前陌生開發. This is a style
# guide, not a Google-specific body template; generated copy remains grounded
# in each campaign's own fields.
EVENT_COLD_OUTREACH_STYLE_REFERENCE = """Dear XXX 您好，

我是 Omnichat 市場團隊的周周，這次想特別邀請您走進活動現場，參與限定交流。

先以一個收件者真正關心的商業問題切入，再自然帶出活動價值與 3～4 個重點；
接著提供活動資訊、報名 CTA、品牌可能關注的經營議題與 15 分鐘交流 CTA。
語氣像 BDR 一對一邀請，避免制式 EDM、公關稿或誇大內容。"""


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
    """Create three BDR subjects after ranking the campaign's strongest hook."""
    analysis = _analyze_bdr_subject_hook(campaign)
    style = variant % 3
    subjects = (
        analysis["curiosity_variants"][style],
        analysis["benefit_variants"][style],
        analysis["trend_variants"][style],
    )
    return tuple(_subject_clip(subject) for subject in subjects)


def _analyze_bdr_subject_hook(campaign: dict[str, Any]) -> dict[str, Any]:
    """Rank recipient-relevant hooks before rendering any subject line.

    This is deliberately deterministic: activity data remains the only source,
    while the optional development_hook guides priority without being copied
    wholesale into the result.
    """
    name = (campaign.get("name") or "活動交流").strip()
    industry = _subject_industry(_campaign_industry(campaign))
    summary = (campaign.get("summary") or "").strip()
    introduction = (campaign.get("introduction") or "").strip()
    development_hook = (campaign.get("development_hook") or "").strip()
    source_phrases = _campaign_points(campaign)
    if not source_phrases:
        source_phrases = _intro_points(summary or introduction)
    first = _subject_phrase(source_phrases[0] if source_phrases else name)
    second = _subject_phrase(source_phrases[1] if len(source_phrases) > 1 else (summary or name))
    source = " ".join(
        str(value) for value in (
            name, summary, introduction, development_hook, campaign.get("location", ""),
            campaign.get("partner", ""), *source_phrases,
        ) if value
    )
    location = (campaign.get("location") or "").strip()
    partner = (campaign.get("partner") or "").strip()
    external_partner = _subject_external_partner(partner, location, name)
    venue = _subject_special_venue(location, external_partner)
    limited = any(word in source for word in ("限定", "審核制", "席次有限", "限量"))
    value = _subject_business_value(source, first, second)
    problem = _subject_business_problem(source, industry, first)
    hook_payoff = _subject_hook_payoff(source, value)
    explicit_question = _subject_explicit_hook_question(development_hook)
    curiosity = _subject_curiosity_variants(
        external_partner=external_partner,
        venue=venue,
        limited=limited,
        industry=industry,
        hook_payoff=hook_payoff,
        problem=problem,
        explicit_question=explicit_question,
    )
    benefits = _subject_benefit_variants(source, problem, hook_payoff)
    trend_label = _subject_display_partner(external_partner) or industry
    scarcity = "限定邀請" if limited or venue else "實戰交流"
    collaboration = (
        f"{trend_label} × Omnichat"
        if external_partner and "Omnichat" in source
        else trend_label
    )
    format_label = "實體小聚" if campaign.get("event_format") == "實體" else "線上交流"
    trends = [
        f"📍 {trend_label} {scarcity}｜{value}",
        f"📍 {collaboration} {format_label}｜{value}",
        f"📍 {trend_label} 現場交流｜{value}",
    ]
    return {
        "primary_hook_type": (
            "explicit_hook" if development_hook
            else "special_venue" if venue
            else "external_partner" if external_partner
            else "scarcity" if limited
            else "business_problem"
        ),
        "external_partner": external_partner,
        "special_venue": venue,
        "limited": limited,
        "business_problem": problem,
        "business_value": value,
        "curiosity_variants": curiosity,
        "benefit_variants": benefits,
        "trend_variants": trends,
    }


def _subject_external_partner(partner: str, location: str, name: str) -> str:
    """Prefer a recognisable external host; Omnichat is never the first hook."""
    partner_source = f"{partner} {location} {name}"
    for token in ("Google", "Meta", "LINE Biz-Solutions", "LINE"):
        if token in partner_source:
            return token
    for raw in re.split(r"[、,，；;&＆×\n]+", partner):
        candidate = raw.strip()
        candidate = candidate.split("｜", 1)[0].strip()
        candidate = re.sub(r"[（(].*?[）)]", "", candidate).strip()
        if candidate and "Omnichat" not in candidate:
            return _token_safe_truncate(candidate, 14)
    return ""


def _subject_special_venue(location: str, external_partner: str) -> str:
    """Return only venues with real invitation value, not generic locations."""
    if not location or location in ("線上", "線上直播", "待確認"):
        return ""
    venue_terms = ("辦公室", "總部", "園區", "實驗室", "旗艦店", "門市", "酒店", "飯店")
    if not any(term in location for term in venue_terms):
        return ""
    if external_partner and external_partner in location and "辦公室" in location:
        return f"{external_partner} 辦公室"
    return _token_safe_truncate(location, 16)


def _subject_display_partner(external_partner: str) -> str:
    """Use the clearest compact identity when a formal partner name is long."""
    if external_partner == "LINE Biz-Solutions":
        return "LINE"
    return external_partner


def _subject_explicit_hook_question(development_hook: str) -> str:
    """Use an explicit BDR question when the user supplied one in the Hook."""
    if not development_hook:
        return ""
    quoted = re.search(r"[「『\"]([^」』\"]+[？?])[」』\"]", development_hook)
    if quoted:
        return quoted.group(1).replace("?", "？").strip()
    question = re.search(r"([^。；;\n]{5,40}[？?])", development_hook)
    if question:
        return question.group(1).replace("?", "？").strip(" ，,")
    return ""


def _subject_brand_hook(source: str) -> str:
    """Pick a recognisable partner token only when it exists in campaign data."""
    for token in ("Google", "Meta", "LINE Biz-Solutions", "LINE", "Omnichat"):
        if token in source:
            return token
    return ""


def _subject_business_value(source: str, first: str, second: str) -> str:
    lowered = source.lower()
    if ("google ads" in lowered or "廣告" in source) and any(
        term in lowered for term in ("ads-to-chat", "對話商務", "轉換閉環")
    ):
        return "從廣告獲客到對話商務"
    if "會員" in source and "分眾" in source:
        return "從會員數據到精準分眾"
    if "會員" in source and "回購" in source:
        return "從會員經營到持續回購"
    if "獲客" in source and "轉換" in source:
        return "從精準獲客到有效轉換"
    if first != second:
        return f"從{first}到{second}"
    return first


def _subject_business_problem(source: str, industry: str, first: str) -> str:
    lowered = source.lower()
    if ("google ads" in lowered or "廣告" in source) and any(
        term in lowered for term in ("ads-to-chat", "對話商務", "轉換")
    ):
        return "廣告帶來點擊後，下一步怎麼接住顧客？"
    if "會員" in source and "回購" in source:
        return "會員持續累積後，如何帶動下一次回購？"
    if "會員" in source and "分眾" in source:
        return "會員資料累積後，如何真正做到精準分眾？"
    if "獲客" in source and "轉換" in source:
        return "流量進站後，如何進一步提升轉換？"
    return f"{industry}如何把{first}轉成實際成長？"


def _subject_hook_payoff(source: str, value: str) -> str:
    """Turn the campaign's commercial value into a compact curiosity payoff."""
    lowered = source.lower()
    if "google ads" in lowered or "廣告" in source:
        return "廣告點擊如何變顧客"
    if "會員" in source and "回購" in source:
        return "會員如何持續回購"
    if "會員" in source and "分眾" in source:
        return "會員資料如何精準分眾"
    if "獲客" in source and "轉換" in source:
        return "流量如何真正轉換"
    return value


def _subject_benefit_variants(
    source: str, problem: str, hook_payoff: str
) -> list[str]:
    """Speak from the recipient's business problem, never a product feature."""
    lowered = source.lower()
    if "google ads" in lowered or "廣告" in source:
        return [
            "✨ 廣告帶來流量後，下一步怎麼接住顧客？",
            "流量進來之後，怎麼真正留下顧客？",
            "每一次廣告點擊，怎麼走向後續轉換？",
        ]
    if ("好友" in source or "line" in lowered) and "會員" in source:
        return [
            "好友一直增加，為什麼真正能經營的會員還是不夠？",
            "好友加入之後，怎麼變成能持續經營的會員？",
            "LINE 好友累積後，下一步怎麼深化會員關係？",
        ]
    if "會員" in source and "回購" in source:
        return [
            "新客進來後，怎麼讓會員願意持續回購？",
            "檔期帶來新客，下一次回購要怎麼發生？",
            "會員持續累積，為什麼回購還是沒有跟上？",
        ]
    if "會員" in source and "分眾" in source:
        return [
            "會員資料累積後，怎麼真正做到精準分眾？",
            "知道會員是誰之後，下一步怎麼持續互動？",
            "會員持續增加，品牌怎麼做出更精準的溝通？",
        ]
    return [
        f"✨ {problem}",
        f"{hook_payoff}，品牌下一步該怎麼做？",
        f"{problem.rstrip('？')}，有哪些實戰做法？",
    ]


def _subject_curiosity_variants(
    *, external_partner: str, venue: str, limited: bool, industry: str,
    hook_payoff: str, problem: str, explicit_question: str,
) -> list[str]:
    if explicit_question:
        return [
            f"👀 {explicit_question}",
            f"這場限定交流，為什麼從{hook_payoff}談起？",
            f"👀 {hook_payoff}，現場會怎麼拆解？",
        ]
    if external_partner and "辦公室" in venue:
        return [
            f"👀 想走進 {venue}一探究竟嗎？",
            f"這次在{venue}，品牌可以帶走什麼？",
            f"👀 {external_partner}現場限定，會怎麼解開這道題？",
        ]
    if venue:
        return [
            f"👀 這場交流為什麼選在{venue}？",
            f"走進{venue}，品牌可以帶走什麼？",
            f"👀 在{venue}，這次要解開什麼問題？",
        ]
    if external_partner and limited:
        return [
            f"👀 {external_partner}限定交流，品牌可以帶走什麼？",
            f"為什麼這場{external_partner}交流採限定邀請？",
            f"👀 和{external_partner}現場交流，這次會拆解什麼？",
        ]
    if external_partner:
        return [
            f"👀 和{external_partner}現場交流，品牌可以帶走什麼？",
            f"{external_partner}分享的實戰，哪一題最值得關注？",
            f"👀 {hook_payoff}，{external_partner}會怎麼看？",
        ]
    if limited:
        return [
            "👀 這場限定交流，品牌可以帶走什麼？",
            f"為什麼這場交流要從{hook_payoff}談起？",
            f"👀 {problem.rstrip('？')}，現場會怎麼拆解？",
        ]
    return [
        f"👀 {hook_payoff}，為什麼現在值得重新思考？",
        f"這場交流，會怎麼回答{industry}正在面對的問題？",
        f"👀 {problem.rstrip('？')}，這次從哪裡開始？",
    ]


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
        "活動未出席／活動精華分享", "陌生開發", "二次追蹤",
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
    "報名未出席 Follow-up": "活動未出席／活動精華分享",
    "活動未到場分享": "活動未出席／活動精華分享",
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
    speaker = (campaign.get("partner") or "").strip()
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
        material_lines.append(f"📄 活動簡報整理｜{materials}")
    material_lines.append(service_line)
    resources = "\n".join(material_lines)

    if scenario == "活動前陌生開發":
        subjects = list(generate_subject_suggestions(campaign))
        if (lead.get("selected_subject") or "").strip():
            subjects = [lead["selected_subject"].strip()]
        source = _activity_source(campaign, {})
        collaboration = _campaign_collaboration_label(campaign)
        opening = _cold_event_hook_opening(campaign, collaboration)
        observation = (lead.get("observation") or "").strip()
        observation_block = f"我也留意到：{observation}" if observation else ""
        business_question = _subject_business_problem(
            source, industry_name or _subject_industry(_campaign_industry(campaign)),
            _subject_phrase(points[0] if points else introduction or event_name),
        )
        value_intro = _cold_event_value_intro(campaign, collaboration, points)
        event_info = _cold_event_info(campaign)
        registration_cta = f"👉 立即報名｜{registration}" if registration else ""
        interest = _cold_event_interest(reference, campaign, points)
        exchange_cta = (
            "若方便，也很樂意在活動前安排 15 分鐘快速交流，\n"
            "先了解目前品牌的獲客與經營方式，並分享相關應用案例供您參考。"
        )
        booking_line = (
            f"👉 快速聯繫我｜{booking}" if booking
            else "👉 也歡迎直接回覆方便的交流時段"
        )
        closing = _cold_event_closing(campaign)
        body = f"""{greeting}

{opening}

{observation_block}

{business_question}

{value_intro}

{points_block}

{event_info}

{registration_cta}

{interest}

{exchange_cta}

{booking_line}

{closing}{banner_block}"""
        return subjects, _clean_email(body), f"{exchange_cta}\n\n{booking_line}"

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
        subject_label = _token_safe_truncate(event_name, 12)
        subject = (
            f"✨ 感謝參與 {date_label}《{subject_label}》｜重點與簡報"
        )
        activity_topic = introduction or campaign.get("summary") or event_name
        topic_phrase = _activity_topic_phrase(activity_topic)
        speaker_copy = (
            f"{speaker} 分享了「{topic_phrase}」"
            if speaker else f"活動中分享了「{topic_phrase}」"
        )
        insight = _commercial_insight(points, activity_topic)
        cta_topics = "、".join(points[:3]) or "本次活動議題"
        cta = (
            f"歡迎回覆方便聯繫的時段，或直接與我聯繫 👉 {booking}"
            if booking else "歡迎回覆方便聯繫的時段，我再協助安排 15 分鐘交流。"
        )
        body = f"""{greeting}

感謝您撥空參加《{event_name}》活動，當天現場議程較緊湊，若未能與您進一步交流，先將活動重點與當日相關資料整理分享給您！

本次活動中，{speaker_copy}，主要聚焦於：

{points_block}

【活動核心商業洞察】
{insight}{industry_paragraph}

{resources}

若您對活動中提到的 {cta_topics} 有興趣，很樂意安排一段 15 分鐘交流，依據目前品牌經營情境，分享相關產業應用案例供您參考。

{cta}

再次感謝您的參與，也期待有機會與您進一步交流！{banner_block}"""
        selected = (lead.get("selected_subject") or "").strip()
        return [selected or _subject_clip(subject)], _clean_email(body), cta

    if scenario == "活動未出席／活動精華分享":
        date_label = _subject_date(campaign.get("event_date", ""))
        brand_suffix = f"（{brand}）" if brand else ""
        date_part = f"{date_label} " if date_label else ""
        subject = f"【{event_name}】{date_part}活動精華整理{brand_suffix}"
        prior_contact = (
            "我是先前有與您通話的 Omnichat 周周。\n\n"
            if (lead.get("precall") or "").strip() else ""
        )
        cta_topics = "、".join(points[:3]) or "本次活動議題"
        insight = _commercial_insight(points, introduction or event_name)
        host_topic = (
            f"本次《{event_name}》由 {speaker} 分享「{_activity_topic_phrase(introduction or campaign.get('summary') or event_name)}」，主要聚焦於："
            if speaker else
            f"本次《{event_name}》主要分享「{_activity_topic_phrase(introduction or campaign.get('summary') or event_name)}」，並聚焦於："
        )
        contact_cta = (
            f"歡迎回覆可聯繫的時段，或直接與我聯繫 👉 {booking}"
            if booking else "歡迎回覆可聯繫的時段，我再協助安排交流。"
        )
        cta = (
            f"若您對活動中提到的 {cta_topics} 有興趣，很樂意安排一段 15 分鐘交流，"
            "依據目前品牌經營情境，分享相關產業應用案例供您參考。"
        )
        body = f"""{greeting}

{prior_contact}活動當天您可能因排程未能前往，我將本次活動的重點內容整理給您，希望能協助您快速掌握分享精華。

{host_topic}

{points_block}

【活動核心商業洞察】
{insight}{industry_paragraph}

{resources}

{cta}

{contact_cta}

期待後續有機會與您進一步交流！{banner_block}"""
        return [subject], _clean_email(body), cta

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
    case = next(iter(reference.get("showcase_cases", [])), {})
    focus = angle or application
    case_sentence = ""
    if case.get("brand_name"):
        case_focus = case.get("key_points") or case.get("use_cases") or "相關應用"
        case_sentence = f"也可參考 {case['brand_name']} 在「{case_focus}」上的實務經驗。"
    if pain and focus:
        return (
            f"\n\n以{industry}的經營情境來看，若目前也在面對「{pain}」，"
            f"可進一步從「{focus}」延伸思考，讓本次活動議題更貼近實際應用。"
            f"{case_sentence}"
        )
    if pain:
        return (
            f"\n\n對{industry}而言，「{pain}」也是可從本次活動延伸交流的方向。"
            f"{case_sentence}"
        )
    if focus:
        return (
            f"\n\n若以{industry}為例，也可進一步交流「{focus}」的實際應用。"
            f"{case_sentence}"
        )
    return ""


def _campaign_collaboration_label(campaign: dict[str, Any]) -> str:
    source = " ".join(str(campaign.get(key, "")) for key in ("name", "partner"))
    names = []
    for token in ("Google", "Meta", "LINE Biz-Solutions", "LINE", "Omnichat"):
        if token in source and not any(token in existing for existing in names):
            names.append(token)
    if names:
        return " × ".join(names[:2])
    partner = (campaign.get("partner") or "").strip()
    return partner or "Omnichat"


def _event_date_with_weekday(value: str) -> str:
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        return _subject_date(value)
    weekdays = "一二三四五六日"
    return f"{parsed.month}/{parsed.day}（{weekdays[parsed.weekday()]}）"


def _cold_event_hook_opening(campaign: dict[str, Any], collaboration: str) -> str:
    date_label = _subject_date(campaign.get("event_date", ""))
    location = (campaign.get("location") or "").strip()
    event_format = (campaign.get("event_format") or "").strip()
    source = " ".join(
        str(campaign.get(key, ""))
        for key in ("development_hook", "introduction", "summary", "name")
    )
    limited = any(word in source for word in ("限定", "席次有限", "審核制", "限量"))
    if event_format == "線上":
        first_line = f"{date_label} 一起在線上參與，" if date_label else "一起在線上參與，"
    elif location and "辦公室" in location:
        first_line = f"{date_label} 一起走進 {location}，" if date_label else f"一起走進 {location}，"
    elif location:
        first_line = f"{date_label} 一起到 {location}，" if date_label else f"一起到 {location}，"
    else:
        first_line = f"{date_label} 一起參與這場交流，" if date_label else "一起參與這場交流，"
    activity_label = "限定" if limited else "專場"
    format_label = "線上交流" if event_format == "線上" else "實體交流"
    return (
        "我是 Omnichat 市場團隊的周周，這次想特別邀請您\n"
        f"{first_line}\n參與 {collaboration} {activity_label}{format_label}！"
    )


def _cold_event_value_intro(
    campaign: dict[str, Any], collaboration: str, points: list[str]
) -> str:
    source = _activity_source(campaign, {})
    if "Google Ads" in source:
        starting_point = "品牌熟悉的 Google Ads 精準獲客"
    elif points:
        starting_point = _subject_phrase(points[0])
    else:
        starting_point = _subject_phrase(campaign.get("introduction") or campaign.get("name", "活動主題"))
    return f"這次將從{starting_point}出發，\n由 {collaboration} 團隊共同分享："


def _cold_event_info(campaign: dict[str, Any]) -> str:
    date_label = _event_date_with_weekday(campaign.get("event_date", ""))
    event_time = (campaign.get("event_time") or "").strip()
    location = (campaign.get("location") or "").strip()
    event_format = (campaign.get("event_format") or "").strip()
    source = " ".join(
        str(campaign.get(key, ""))
        for key in ("development_hook", "introduction", "summary", "highlights")
    )
    first = " ".join(value for value in (date_label, event_time) if value)
    if location:
        first = f"{first}｜{location}" if first else location
    lines = [f"📍 {first}"] if first else []
    qualifiers = []
    if "限定" in source:
        qualifiers.append("限定交流")
    elif event_format:
        qualifiers.append(f"{event_format}活動")
    for phrase in ("席次有限", "採審核制"):
        if phrase in source:
            qualifiers.append(phrase)
    if qualifiers:
        lines.append(f"🎟️ {'｜'.join(qualifiers)}")
    return "\n".join(lines)


def _cold_event_interest(
    reference: dict[str, Any], campaign: dict[str, Any], points: list[str]
) -> str:
    topics = []
    topics.extend(reference.get("pain_points", [])[:1])
    topics.extend(reference.get("development_angles", [])[:1])
    if len(topics) < 2:
        source = _activity_source(campaign, {})
        if "廣告" in source or "Google Ads" in source:
            topics.extend(["廣告投放效益", "點擊後的轉換承接"])
        elif "會員" in source and "分眾" in source:
            topics.extend(["會員數據經營", "精準分眾"])
        elif "回購" in source:
            topics.extend(["顧客留存", "持續回購"])
        else:
            topics.extend(_subject_phrase(point) for point in points[:2])
    topics = list(dict.fromkeys(topic for topic in topics if topic))[:2]
    if not topics:
        return "若您近期也正在思考相關的品牌成長方向，很推薦把握這次交流機會。"
    joined = "或".join(topics)
    industry = (reference.get("industry_name") or "").strip()
    audience = f"如果您是{industry}品牌，近期也正在思考" if industry else "若您近期也正在思考"
    return (
        f"{audience}{joined}，\n"
        "很推薦把握這次機會，看看品牌下一步可以怎麼做！"
    )


def _cold_event_closing(campaign: dict[str, Any]) -> str:
    date_label = _subject_date(campaign.get("event_date", ""))
    location = (campaign.get("location") or "").strip()
    if campaign.get("event_format") == "線上":
        return f"期待 {date_label} 在線上與您交流！" if date_label else "期待在線上與您交流！"
    if date_label and location:
        short_location = location.replace("台北辦公室", "").strip() or location
        return f"期待 {date_label} 有機會在 {short_location} 與您見面！"
    if date_label:
        return f"期待 {date_label} 有機會與您見面！"
    return "期待有機會在活動現場與您交流！"


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


def _activity_topic_phrase(value: str) -> str:
    phrase = str(value).strip().rstrip("。！？!?；;")
    if phrase.startswith("分享") and len(phrase) > 4:
        phrase = phrase[2:].strip()
    return phrase


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
    stored_points = campaign.get("activity_points", [])
    if isinstance(stored_points, str):
        stored_points = [stored_points]
    ordered_sources = [
        campaign.get("development_hook", ""),
        campaign.get("introduction", ""),
        campaign.get("summary", ""),
        *stored_points,
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
