from pathlib import Path
from datetime import date
import json
from typing import Optional
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components

from generators import (
    generate_banner,
    generate_email,
    generate_line,
)
from models import Campaign, EMAIL_SCENARIOS, LINE_SCENARIOS
from line_contact_finder import (
    generate_activity_reply,
    generate_email_provided_reply,
    generate_first_contact_message,
)
from storage import (
    delete_campaign,
    delete_industry_template,
    load_campaigns,
    load_industry_templates,
    save_campaign,
    save_industry_template,
    update_campaign,
    update_industry_template,
)


BASE_DIR = Path(__file__).parent
UPLOADS = BASE_DIR / "uploads"
UPLOADS.mkdir(exist_ok=True)

st.set_page_config(page_title="Omnichat Campaign Builder", page_icon="🚀", layout="wide")
st.markdown(
    """
    <style>
    .stButton > button, .stDownloadButton > button { min-height: 44px; }
    [data-testid="stImage"] img { max-width: 100%; height: auto; }
    @media (max-width: 700px) {
      [data-testid="stHorizontalBlock"] { flex-direction: column; gap: 0.5rem; }
      [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
      .block-container { padding-left: 1rem; padding-right: 1rem; }
      textarea { min-height: 140px !important; }
      .stButton > button, .stDownloadButton > button { width: 100%; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def campaign_selector(key: str) -> Optional[dict]:
    campaigns = load_campaigns()
    if not campaigns:
        st.info("請先到「活動管理」新增一個活動。")
        return None
    labels = {item["id"]: item["name"] for item in campaigns}
    selected_id = st.selectbox(
        "選擇活動",
        options=list(labels),
        format_func=lambda item_id: labels[item_id],
        key=key,
    )
    return next(item for item in campaigns if item["id"] == selected_id)


def _selected_industry_context(campaign: dict, enabled: bool) -> Optional[dict]:
    if not enabled:
        return None
    industry_name = campaign.get("primary_industry") or campaign.get("suitable_industries", "")
    template = next(
        (item for item in load_industry_templates() if item.get("industry_name") == industry_name),
        None,
    )
    if not template:
        st.info(f"產業別資料庫尚未建立「{industry_name or '未指定產業'}」資料，本次不引用。")
    return template


def line_lead_inputs() -> dict[str, str]:
    brand = st.text_input("品牌（選填）", key="LINE_brand")
    contact = st.text_input("窗口（選填）", key="LINE_contact")
    note = st.text_area("補充資訊（選填）", key="LINE_note")
    return {
        "brand": brand,
        "contact": contact,
        "observation": note,
    }


def copyable_line_output(state_key: str) -> None:
    if state_key not in st.session_state:
        return
    edited_text = st.text_area(
        "產生結果（可直接修改）",
        key=state_key,
        height=230,
        help="修改後離開欄位，複製按鈕會使用最新內容。",
    )
    text_json = json.dumps(edited_text, ensure_ascii=False)
    components.html(
        f"""
        <button id="copy-btn" style="border:1px solid #d0d5dd;border-radius:8px;
          background:white;padding:8px 16px;cursor:pointer;font-size:14px;">
          一鍵複製
        </button>
        <span id="copy-status" style="margin-left:10px;color:#475467;font-size:14px;"></span>
        <script>
          const text = {text_json};
          document.getElementById('copy-btn').onclick = async () => {{
            try {{
              await navigator.clipboard.writeText(text);
              document.getElementById('copy-status').textContent = '已複製';
            }} catch (error) {{
              const area = document.createElement('textarea');
              area.value = text;
              document.body.appendChild(area);
              area.select();
              document.execCommand('copy');
              area.remove();
              document.getElementById('copy-status').textContent = '已複製';
            }}
          }};
        </script>
        """,
        height=48,
    )


def line_contact_finder() -> None:
    st.header("LINE 找窗口")
    st.caption("透過品牌官方 LINE 找到行銷、會員經營、品牌經營或數位行銷相關窗口。")
    campaign = campaign_selector("line_finder_campaign")
    if not campaign:
        return
    brand = st.text_input("品牌名稱", key="line_finder_brand")
    has_emailed = st.checkbox("已寄信到公司信箱", key="line_finder_has_emailed")
    st.text_area(
        "補充說明（選填）",
        key="line_finder_note",
        placeholder="僅供本次聯繫紀錄，不會自動加入第一則訊息。",
    )
    if st.button("產生第一則 LINE 找窗口訊息", type="primary"):
        st.session_state["line_finder_output"] = generate_first_contact_message(
            has_emailed, campaign
        )

    st.subheader("客服回覆情境")
    response_scenario = st.radio(
        "選擇客服回覆",
        ["尚未回覆", "A｜請問是什麼活動？", "B｜客服提供 Email", "C｜客服表示自己就是窗口"],
        key="line_finder_response_scenario",
    )
    if response_scenario == "A｜請問是什麼活動？":
        if st.button("產生活動簡介回覆"):
            st.session_state["line_finder_output"] = generate_activity_reply(campaign)
    elif response_scenario == "B｜客服提供 Email":
        if st.button("產生感謝回覆"):
            st.session_state["line_finder_output"] = generate_email_provided_reply()
    elif response_scenario == "C｜客服表示自己就是窗口":
        contact_role = st.text_input(
            "窗口身分",
            key="line_finder_contact_role",
            placeholder="例如：行銷經理、會員經營窗口",
        )
        if st.button("帶入 Email 信件", type="primary"):
            st.session_state["pending_email_transfer"] = {
                "campaign_id": campaign["id"],
                "brand": brand,
                "contact": contact_role,
            }
            st.rerun()

    copyable_line_output("line_finder_output")


def _campaign_form_fields(prefix: str, campaign: Optional[dict] = None) -> tuple[dict, object]:
    campaign = campaign or {}
    try:
        current_date = date.fromisoformat(campaign.get("event_date", ""))
    except ValueError:
        current_date = date.today()
    formats = ["實體", "線上"]
    current_format = campaign.get("event_format", "實體")
    if current_format not in formats:
        current_format = "實體"
    industries = [item["industry_name"] for item in load_industry_templates()]
    current_industry = campaign.get("primary_industry") or campaign.get("suitable_industries", "")
    if current_industry and current_industry not in industries:
        industries.append(current_industry)
    if not industries:
        industries = ["食品 / 伴手禮"]

    st.markdown("### Step 1｜基本資訊")
    name = st.text_input("活動名稱 *", campaign.get("name", ""), key=f"{prefix}_name")
    col1, col2 = st.columns(2)
    event_date = col1.date_input("活動日期 *", current_date, key=f"{prefix}_date")
    event_time = col2.text_input(
        "活動時間", campaign.get("event_time", ""), key=f"{prefix}_time",
        placeholder="例如：14:00–16:30",
    )
    event_format = st.radio(
        "活動形式", formats, horizontal=True,
        index=formats.index(current_format), key=f"{prefix}_format",
    )
    location = st.text_input("活動地點", campaign.get("location", ""), key=f"{prefix}_location")
    address = st.text_input("活動地址", campaign.get("address", ""), key=f"{prefix}_address")
    col3, col4 = st.columns(2)
    registration = col3.text_input(
        "報名連結", campaign.get("registration_url", ""), key=f"{prefix}_registration"
    )
    booking = col4.text_input(
        "預約交流連結", campaign.get("booking_url", ""), key=f"{prefix}_booking"
    )
    partner = st.text_input(
        "合作單位 / 講者", campaign.get("partner", ""), key=f"{prefix}_partner"
    )
    industry_index = industries.index(current_industry) if current_industry in industries else 0
    primary_industry = st.selectbox(
        "主要產業 *", industries, index=industry_index, key=f"{prefix}_industry"
    )

    st.markdown("### Step 2｜活動核心內容")
    summary = st.text_area(
        "活動一句話摘要",
        campaign.get("summary", ""),
        height=120,
        key=f"{prefix}_summary",
        help="建議 1～2 句，Email、LINE 與活動圖文會直接共用。",
    )
    introduction = st.text_area(
        "活動介紹",
        campaign.get("introduction") or campaign.get("highlights", ""),
        height=220,
        key=f"{prefix}_introduction",
        help="完整活動背景、主題、內容或議程集中填在這裡。",
    )
    points = [
        st.text_input(
            f"活動重點 {index}",
            campaign.get(f"activity_point_{index}", ""),
            key=f"{prefix}_point_{index}",
        )
        for index in range(1, 5)
    ]
    email_titles = [
        st.text_input(
            f"信件大標 {label}（選填）",
            campaign.get(f"email_title_{label.lower()}", ""),
            key=f"{prefix}_title_{label.lower()}",
        )
        for label in ("A", "B", "C")
    ]
    image = st.file_uploader(
        "活動 Banner（選填）",
        type=["png", "jpg", "jpeg", "webp"],
        key=f"{prefix}_banner",
        help="僅保存並供 Email、LINE、活動圖文使用，不進行圖片辨識。",
    )
    if campaign.get("image_path"):
        st.caption(f"目前 Banner：{campaign['image_path']}")

    values = {
        "name": name.strip(),
        "event_date": event_date.isoformat(),
        "event_time": event_time.strip(),
        "event_format": event_format,
        "location": location.strip(),
        "address": address.strip(),
        "registration_url": registration.strip(),
        "booking_url": booking.strip(),
        "partner": partner.strip(),
        "primary_industry": primary_industry,
        "summary": summary.strip(),
        "introduction": introduction.strip(),
        "activity_point_1": points[0].strip(),
        "activity_point_2": points[1].strip(),
        "activity_point_3": points[2].strip(),
        "activity_point_4": points[3].strip(),
        "email_title_a": email_titles[0].strip(),
        "email_title_b": email_titles[1].strip(),
        "email_title_c": email_titles[2].strip(),
        "image_path": campaign.get("image_path", ""),
        # Keep legacy readers compatible without duplicating UI fields.
        "highlights": introduction.strip(),
        "suitable_industries": primary_industry,
        "topic": campaign.get("topic", ""),
        "case_industries": campaign.get("case_industries", ""),
    }
    return values, image


def _save_banner(image: object, current_path: str = "") -> str:
    if not image:
        return current_path
    safe_name = f"{uuid4()}_{Path(image.name).name}"
    target = UPLOADS / safe_name
    target.write_bytes(image.getvalue())
    return str(target.relative_to(BASE_DIR))


def _show_industry_knowledge(industry_name: str) -> None:
    template = next(
        (item for item in load_industry_templates() if item["industry_name"] == industry_name),
        None,
    )
    if not template:
        return
    with st.expander(f"產業參考｜{industry_name}"):
        st.caption("只供開發參考，不會覆蓋或混入活動內容。")
        st.write("**常見品牌經營情境**")
        st.write("、".join(template.get("brand_scenarios", [])))
        st.write("**常見痛點**")
        for item in template.get("pain_points", []):
            st.write(f"• {item}")
        st.write("**Showcase 分類**")
        for category, brands in template.get("showcases", {}).items():
            st.write(f"{category}：{'、'.join(brands)}")


def campaign_manager() -> None:
    st.header("活動管理")
    st.caption("活動資料中心｜儲存後由 Email 與 LINE 直接共用。")
    campaigns = load_campaigns()
    with st.expander("＋ 新增活動", expanded=not campaigns):
        with st.form("campaign_create_form", clear_on_submit=True):
            values, image = _campaign_form_fields("create")
            submitted = st.form_submit_button("儲存活動", type="primary")
        if submitted:
            if not values["name"] or not values["primary_industry"]:
                st.error("請填寫活動名稱並選擇主要產業。")
            else:
                values["image_path"] = _save_banner(image)
                save_campaign(Campaign(**values).to_dict())
                st.success("活動已儲存。")
                st.rerun()
        _show_industry_knowledge(values["primary_industry"])

    campaigns = load_campaigns()
    st.subheader(f"活動列表（{len(campaigns)}）")
    for campaign in campaigns:
        with st.expander(f"{campaign['name']}｜{campaign.get('event_date', '')}"):
            with st.form(f"campaign_edit_{campaign['id']}"):
                values, image = _campaign_form_fields(f"edit_{campaign['id']}", campaign)
                col1, col2 = st.columns(2)
                update = col1.form_submit_button("儲存修改", type="primary")
                delete = col2.form_submit_button("刪除活動")
            if update:
                if not values["name"] or not values["primary_industry"]:
                    st.error("請填寫活動名稱並選擇主要產業。")
                else:
                    values["image_path"] = _save_banner(image, values["image_path"])
                    update_campaign(campaign["id"], values)
                    st.success("活動已更新。")
                    st.rerun()
            if delete:
                delete_campaign(campaign["id"])
                st.success("活動已刪除。")
                st.rerun()
            _show_industry_knowledge(values["primary_industry"])
            st.download_button(
                "下載此活動 JSON",
                data=json.dumps({**campaign, **values}, ensure_ascii=False, indent=2),
                file_name=f"{campaign['name']}.json",
                mime="application/json",
                key=f"download_{campaign['id']}",
            )


def line_message_generator() -> None:
    st.header("LINE 邀約訊息")
    st.caption("選擇已儲存活動後，產出手機閱讀友善的邀約與追蹤訊息。")
    st.subheader("Step 1｜選擇活動")
    campaign = campaign_selector("LINE_campaign")
    if not campaign:
        return
    st.subheader("Step 2｜選擇情境")
    scenario = st.selectbox("LINE 情境", LINE_SCENARIOS, key="LINE_scenario")
    st.subheader("Step 3｜品牌資訊")
    lead = line_lead_inputs()
    use_industry = st.checkbox(
        "是否引用產業資料庫", value=False, key="LINE_use_industry"
    )
    lead["industry_context"] = _selected_industry_context(campaign, use_industry)
    st.subheader("Step 4｜產生 LINE 訊息")
    if st.button("產生 LINE 訊息", type="primary", key="generate_LINE"):
        st.session_state["LINE_result"] = generate_line(campaign, scenario, lead)
    result = st.session_state.get("LINE_result")
    if result:
        st.text_area("產生結果（可直接修改）", result, height=360, key="LINE_output")
        st.download_button("下載文字檔", result, file_name="line_draft.txt")


def email_builder_v1() -> None:
    st.header("Email 信件")
    st.caption("選擇已儲存活動，使用五種固定 Template 產生 Email。")

    st.subheader("Step 1｜選擇活動")
    campaign = campaign_selector("Email_campaign")
    if not campaign:
        return

    st.subheader("Step 2｜選擇 Email 情境")
    scenario = st.selectbox("情境", EMAIL_SCENARIOS, key="Email_scenario")
    st.subheader("Step 3｜品牌資訊")
    brand = st.text_input("品牌名稱 *", key="Email_brand")
    contact = st.text_input("窗口（選填）", key="Email_contact")
    observation = st.text_area(
        "品牌觀察（選填）",
        key="Email_observation",
        placeholder="沒有可留白，例如：近期主打中秋禮盒、官網有會員制度、近期推出新品、有 LINE 官方帳號等。",
    )
    use_industry = st.checkbox(
        "是否引用產業資料庫", value=False, key="Email_use_industry"
    )
    industry_context = _selected_industry_context(campaign, use_industry)

    st.subheader("Step 4｜產生 Email")
    if st.button("產生 Email 信件", type="primary", key="generate_Email_v1"):
        if not brand.strip():
            st.error("請填寫品牌名稱。")
        else:
            subjects, body, cta = generate_email(
                campaign,
                scenario,
                {
                    "brand": brand.strip(),
                    "contact": contact.strip(),
                    "observation": observation.strip(),
                    "industry_context": industry_context,
                },
            )
            st.session_state["Email_result"] = (
                "信件主旨 3 版：\n"
                + "\n".join(f"{index}. {subject}" for index, subject in enumerate(subjects, 1))
                + f"\n\nEmail 內文：\n{body}\n\nCTA：\n{cta}"
            )

    result = st.session_state.get("Email_result")
    if result:
        copyable_line_output("Email_result")
        st.download_button(
            "下載文字檔", st.session_state["Email_result"], file_name="email_draft.txt"
        )


def banner_generator() -> None:
    st.header("活動圖文")
    st.caption("依據活動內容產出宣傳素材所需文案。")
    campaign = campaign_selector("banner_campaign")
    if not campaign:
        return
    if st.button("產生活動圖文", type="primary"):
        st.session_state.banner_result = generate_banner(campaign)
    if "banner_result" in st.session_state:
        for label, value in st.session_state.banner_result.items():
            st.text_area(label, value, height=130, key=f"banner_{label}")


def _multiline(value: object) -> str:
    return "\n".join(value) if isinstance(value, list) else ""


def _line_items(value: str) -> list[str]:
    return [line.strip().lstrip("-• ") for line in value.splitlines() if line.strip()]


def _showcase_text(cases: list[dict]) -> str:
    return "\n".join(
        "｜".join([
            case.get("brand_name", ""), case.get("category", ""),
            case.get("summary", ""), case.get("use_cases", ""),
        ]) for case in cases
    )


def _parse_showcases(value: str) -> list[dict]:
    cases = []
    for line in value.splitlines():
        if not line.strip():
            continue
        fields = [item.strip() for item in line.split("｜", 3)]
        fields += [""] * (4 - len(fields))
        cases.append({
            "brand_name": fields[0], "category": fields[1],
            "summary": fields[2], "use_cases": fields[3],
        })
    return cases


def _industry_form(prefix: str, item: Optional[dict] = None) -> dict:
    item = item or {}
    name = st.text_input("產業名稱 *", item.get("industry_name", ""), key=f"{prefix}_name")
    description = st.text_area(
        "產業說明", item.get("description", ""), key=f"{prefix}_description"
    )
    pain_points = st.text_area(
        "常見痛點（每行一筆）", _multiline(item.get("pain_points", [])),
        key=f"{prefix}_pains", height=150,
    )
    angles = st.text_area(
        "常見開發切角（每行一筆）", _multiline(item.get("development_angles", [])),
        key=f"{prefix}_angles", height=130,
    )
    scenarios = st.text_area(
        "Omnichat 可應用情境（每行一筆）", _multiline(item.get("omnichat_scenarios", [])),
        key=f"{prefix}_scenarios", height=130,
    )
    showcases = st.text_area(
        "Showcase / 品牌案例",
        _showcase_text(item.get("showcase_cases", [])), key=f"{prefix}_showcases", height=150,
        help="每行格式：品牌名稱｜品牌分類｜案例簡述｜可引用情境",
    )
    ctas = st.text_area(
        "常用 CTA（每行一筆）", _multiline(item.get("common_ctas", [])),
        key=f"{prefix}_ctas", height=130,
    )
    return {
        "industry_name": name.strip(), "description": description.strip(),
        "pain_points": _line_items(pain_points),
        "development_angles": _line_items(angles),
        "omnichat_scenarios": _line_items(scenarios),
        "showcase_cases": _parse_showcases(showcases),
        "common_ctas": _line_items(ctas),
        # Preserve legacy knowledge fields when editing an existing record.
        "brand_scenarios": item.get("brand_scenarios", []),
        "showcases": item.get("showcases", {}),
        "case_rules": item.get("case_rules", []),
    }


def industry_database() -> None:
    st.header("產業別資料庫")
    st.caption("由使用者維護產業開發 Know-how；不使用任何 AI API。")
    industries = load_industry_templates()

    with st.expander("＋ 新增產業", expanded=not industries):
        with st.form("industry_create_form", clear_on_submit=True):
            values = _industry_form("industry_create")
            submitted = st.form_submit_button("新增產業", type="primary")
        if submitted:
            if not values["industry_name"]:
                st.error("請填寫產業名稱。")
            else:
                save_industry_template({"id": str(uuid4()), **values})
                st.success("產業資料已新增。")
                st.rerun()

    st.subheader(f"產業清單（{len(industries)}）")
    for item in industries:
        with st.expander(item.get("industry_name", "未命名產業")):
            with st.form(f"industry_edit_{item['id']}"):
                values = _industry_form(f"industry_{item['id']}", item)
                col1, col2 = st.columns(2)
                update = col1.form_submit_button("儲存修改", type="primary")
                delete = col2.form_submit_button("刪除產業")
            if update:
                if not values["industry_name"]:
                    st.error("請填寫產業名稱。")
                else:
                    update_industry_template(item["id"], values)
                    st.success("產業資料已更新。")
                    st.rerun()
            if delete:
                delete_industry_template(item["id"])
                st.success("產業資料已刪除。")
                st.rerun()


if "pending_email_transfer" in st.session_state:
    transfer = st.session_state.pop("pending_email_transfer")
    st.session_state["active_page"] = "Email 信件"
    st.session_state["Email_campaign"] = transfer["campaign_id"]
    st.session_state["Email_brand"] = transfer["brand"]
    st.session_state["Email_contact"] = transfer["contact"]

st.sidebar.title("Omnichat")
st.sidebar.caption("BDR Campaign Builder")
NAV_ITEMS = ["活動管理", "Email 信件", "LINE 邀約訊息", "產業別資料庫"]
if st.session_state.get("active_page") not in NAV_ITEMS:
    st.session_state["active_page"] = "活動管理"
page = st.sidebar.radio(
    "功能選單",
    NAV_ITEMS,
    key="active_page",
)

pages = {
    "活動管理": campaign_manager,
    "Email 信件": email_builder_v1,
    "LINE 邀約訊息": line_message_generator,
    "產業別資料庫": industry_database,
}
pages[page]()
