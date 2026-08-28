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
    generate_subject_suggestions,
)
from models import (
    Campaign,
    EVENT_EMAIL_SCENARIOS,
    LINE_SCENARIOS,
    NON_EVENT_EMAIL_SCENARIOS,
)
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


def industry_reference_selector(campaign: dict, channel: str) -> Optional[dict]:
    enabled = st.checkbox(
        "引用產業別資料庫", value=False, key=f"{channel}_use_industry"
    )
    if not enabled:
        return None
    templates = load_industry_templates()
    if not templates:
        st.info("產業別資料庫目前沒有資料。")
        return None
    activity_industry = campaign.get("primary_industry") or campaign.get("suitable_industries", "")
    names = [item.get("industry_name", "未命名產業") for item in templates]
    default_index = names.index(activity_industry) if activity_industry in names else 0
    selected_name = st.selectbox(
        "選擇引用產業", names, index=default_index, key=f"{channel}_industry_reference"
    )
    template = next(item for item in templates if item.get("industry_name") == selected_name)

    if channel == "Email":
        categories = st.multiselect(
            "選擇引用內容",
            ["常見痛點", "Omnichat 應用", "Showcase", "開發切角", "CTA"],
            key="Email_industry_categories",
        )
        pains = st.multiselect(
            "選擇常見痛點", template.get("pain_points", []),
            key="Email_industry_pains",
        ) if "常見痛點" in categories else []
        applications = st.multiselect(
            "選擇 Omnichat 應用",
            template.get("omnichat_applications") or template.get("omnichat_scenarios", []),
            key="Email_industry_applications",
        ) if "Omnichat 應用" in categories else []
        public_cases = [case for case in template.get("showcase_cases", []) if case.get("public")]
        case_labels = {
            f"{case.get('brand_name')}｜{case.get('use_cases')}": case for case in public_cases
        }
        selected_cases = st.multiselect(
            "選擇 Showcase（最多 2 個）", list(case_labels), max_selections=2,
            key="Email_industry_cases",
        ) if "Showcase" in categories else []
        angles = st.multiselect(
            "選擇開發切角", template.get("development_angles", []),
            key="Email_industry_angles",
        ) if "開發切角" in categories else []
        ctas = st.multiselect(
            "選擇 CTA（最多 1 個）", template.get("common_ctas", []), max_selections=1,
            key="Email_industry_ctas",
        ) if "CTA" in categories else []
        return {
            "industry_name": selected_name,
            "pain_points": pains,
            "omnichat_applications": applications,
            "showcase_cases": [case_labels[label] for label in selected_cases],
            "development_angles": angles,
            "common_ctas": ctas,
            "cautions": template.get("cautions", []),
        }

    def choose_one(label: str, values: list, key: str) -> str:
        return st.selectbox(label, ["不引用", *values], key=key)

    pain = choose_one("引用 1 個痛點", template.get("pain_points", []), "LINE_industry_pain")
    angle = choose_one("引用 1 個開發切角", template.get("development_angles", []), "LINE_industry_angle")
    public_cases = [case for case in template.get("showcase_cases", []) if case.get("public")]
    case_labels = {f"{case.get('brand_name')}｜{case.get('use_cases')}": case for case in public_cases}
    case_label = choose_one("引用 1 個 Showcase", list(case_labels), "LINE_industry_case")
    return {
        "industry_name": selected_name,
        "pain_points": [] if pain == "不引用" else [pain],
        "development_angles": [] if angle == "不引用" else [angle],
        "showcase_cases": [] if case_label == "不引用" else [case_labels[case_label]],
        "omnichat_applications": [], "common_ctas": [],
        "cautions": template.get("cautions", []),
    }


def email_industry_selector() -> Optional[dict]:
    """Select one live Industry Knowledge record; no second Email-only data source."""
    templates = load_industry_templates()
    options = ["不選產業", *[item.get("industry_name", "未命名產業") for item in templates]]
    selected = st.selectbox(
        "產業（選填）",
        options,
        key="Email_selected_industry",
        help="選擇產業後，將自動引用產業別資料庫中的痛點、應用情境與案例。",
    )
    if selected == "不選產業":
        return None
    return next(
        (item for item in templates if item.get("industry_name") == selected), None
    )


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


def _subject_copy_control(value: str, control_id: str) -> None:
    text_json = json.dumps(value, ensure_ascii=False)
    components.html(
        f"""
        <button id="{control_id}" style="border:1px solid #d0d5dd;border-radius:8px;
          background:white;padding:7px 12px;cursor:pointer;font-size:14px;width:100%;">
          複製
        </button>
        <script>
          document.getElementById('{control_id}').onclick = async () => {{
            try {{
              await navigator.clipboard.writeText({text_json});
            }} catch (error) {{
              const area = document.createElement('textarea');
              area.value = {text_json};
              document.body.appendChild(area);
              area.select();
              document.execCommand('copy');
              area.remove();
            }}
            document.getElementById('{control_id}').textContent = '已複製';
          }};
        </script>
        """,
        height=42,
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


def _campaign_form_fields(prefix: str, campaign: Optional[dict] = None) -> dict:
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
    materials_url = st.text_input(
        "活動簡報整理連結（選填）",
        campaign.get("materials_url") or campaign.get("presentation_url", ""),
        key=f"{prefix}_materials_url",
        placeholder="例如：Google Drive、Dropbox 或公開簡報連結",
    )
    partner = st.text_input(
        "合作單位 / 講者", campaign.get("partner", ""), key=f"{prefix}_partner"
    )
    industry_index = industries.index(current_industry) if current_industry in industries else 0
    primary_industry = st.selectbox(
        "主要產業 *", industries, index=industry_index, key=f"{prefix}_industry"
    )

    st.markdown("### Step 2｜活動核心內容")
    introduction = st.text_area(
        "活動介紹",
        campaign.get("introduction") or campaign.get("highlights", ""),
        height=220,
        key=f"{prefix}_introduction",
        help="填寫完整活動內容、活動定位、主辦單位、適合對象等資訊。",
    )
    development_hook = st.text_area(
        "💡 活動開發 Hook／我想強調的點（選填）",
        campaign.get("development_hook", ""),
        height=120,
        key=f"{prefix}_development_hook",
        help=(
            "用自然語言說明這場活動最值得拿來開發的話題、商業問題或限定亮點。"
            "系統會把它當作文案方向，不會逐字貼入信件。"
        ),
        placeholder=(
            "例如：活動辦在 Google 台北辦公室，希望增加話題性；"
            "開場可從走進 Google 辦公室切入，最後帶回廣告獲客與轉換。"
        ),
    )
    existing_points = campaign.get("activity_points", [])
    if not isinstance(existing_points, list):
        existing_points = []
    activity_points_text = st.text_area(
        "活動重點",
        "\n".join(str(item) for item in existing_points),
        height=160,
        key=f"{prefix}_activity_points",
        help="可輸入多個活動重點，每行一個。",
        placeholder="・精準獲客與第一方數據蒐集\n・LINE 會員分眾與自動化經營\n・品牌會員經營實際案例",
    )
    points = _line_items(activity_points_text)
    st.markdown("### 信件大標建議")
    existing_subjects = [
        st.session_state.get(
            f"{prefix}_subject_{label}",
            campaign.get(f"subject_{label}") or campaign.get(f"email_title_{label}", ""),
        )
        for label in ("a", "b", "c")
    ]
    round_key = f"{prefix}_subject_generation_round"
    if round_key not in st.session_state:
        st.session_state[round_key] = int(campaign.get("subject_generation_round", 0))
    generated_key = f"{prefix}_subjects_generated"
    has_generated_subjects = bool(
        any(existing_subjects) or st.session_state.get(generated_key)
    )
    generation_label = (
        "重新產生 3 個建議" if has_generated_subjects else "產生 3 個信件大標"
    )
    generate_subjects = st.form_submit_button(generation_label)
    if generate_subjects:
        if not name.strip():
            st.error("請先填寫活動名稱。")
        elif not (introduction.strip() or points):
            st.error("請至少填寫活動介紹或活動重點。")
        else:
            if has_generated_subjects:
                st.session_state[round_key] = (st.session_state[round_key] + 1) % 3
            generated = generate_subject_suggestions({
                "name": name.strip(),
                "event_date": event_date.isoformat(),
                "primary_industry": primary_industry,
                "summary": campaign.get("summary", ""),
                "introduction": introduction.strip(),
                "activity_points": points,
            }, st.session_state[round_key])
            for label, value in zip(("a", "b", "c"), generated):
                st.session_state[f"{prefix}_subject_{label}"] = value
            st.session_state[generated_key] = True
            st.rerun()

    saved_selected = campaign.get("selected_subject", "")
    subjects = list(existing_subjects)
    selected_subject = saved_selected
    if not has_generated_subjects:
        st.caption("填妥活動資料後按下按鈕，系統才會顯示三個建議大標。")
    else:
        st.caption("以下內容由活動資料自動產生；可直接修改、複製並選為預設大標。")
        subject_labels = ("問題式", "效益式", "趨勢 / 活動式")
        subjects = []
        for label, key_label, default in zip(
            subject_labels, ("a", "b", "c"), existing_subjects
        ):
            col_subject, col_copy = st.columns([5, 1])
            subject = col_subject.text_input(
                label, default, key=f"{prefix}_subject_{key_label}"
            )
            with col_copy:
                st.caption("　")
                _subject_copy_control(subject, f"copy_{prefix}_{key_label}")
            subjects.append(subject)

        selected_key = next(
            (
                key for key, value in zip(("a", "b", "c"), subjects)
                if value and value == saved_selected
            ),
            "custom" if saved_selected else "a",
        )
        subject_options = ["a", "b", "c", "custom"]
        selected_option = st.radio(
            "選擇預設信件大標",
            subject_options,
            index=subject_options.index(selected_key),
            format_func=lambda option: {
                "a": "建議 A｜問題式",
                "b": "建議 B｜效益式",
                "c": "建議 C｜趨勢 / 活動式",
                "custom": "自訂大標",
            }[option],
            horizontal=True,
            key=f"{prefix}_selected_subject_option",
        )
        if selected_option == "custom":
            custom_default = (
                saved_selected if saved_selected and saved_selected not in subjects else ""
            )
            selected_subject = st.text_input(
                "自訂大標",
                custom_default,
                key=f"{prefix}_custom_subject",
                placeholder="輸入這封活動預設使用的大標",
            ).strip()
        else:
            selected_subject = subjects[("a", "b", "c").index(selected_option)].strip()
    values = {
        "name": name.strip(),
        "event_date": event_date.isoformat(),
        "event_time": event_time.strip(),
        "event_format": event_format,
        "location": location.strip(),
        "address": address.strip(),
        "registration_url": registration.strip(),
        "booking_url": booking.strip(),
        "materials_url": materials_url.strip(),
        "partner": partner.strip(),
        "primary_industry": primary_industry,
        # Keep the legacy summary value readable for existing campaigns. New
        # campaigns derive copy from introduction and activity_points instead.
        "summary": campaign.get("summary", ""),
        "introduction": introduction.strip(),
        "development_hook": development_hook.strip(),
        "activity_points": points,
        # Mirror the first four lines for legacy template compatibility.
        **{
            f"activity_point_{index}": points[index - 1] if len(points) >= index else ""
            for index in range(1, 5)
        },
        "subject_a": subjects[0].strip(),
        "subject_b": subjects[1].strip(),
        "subject_c": subjects[2].strip(),
        "selected_subject": selected_subject,
        "subject_generation_round": st.session_state[round_key],
        "image_path": campaign.get("image_path", ""),
        # Keep legacy readers compatible without duplicating UI fields.
        "highlights": introduction.strip(),
        "suitable_industries": primary_industry,
        "topic": campaign.get("topic", ""),
        "case_industries": campaign.get("case_industries", ""),
    }
    return values


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
        with st.form("campaign_create_form", clear_on_submit=False):
            values = _campaign_form_fields("create")
            submitted = st.form_submit_button("儲存活動", type="primary")
        if submitted:
            if not values["name"] or not values["primary_industry"]:
                st.error("請填寫活動名稱並選擇主要產業。")
            else:
                save_campaign(Campaign(**values).to_dict())
                st.success("活動已儲存。")
                st.rerun()
        _show_industry_knowledge(values["primary_industry"])

    campaigns = load_campaigns()
    st.subheader(f"活動列表（{len(campaigns)}）")
    for campaign in campaigns:
        with st.expander(f"{campaign['name']}｜{campaign.get('event_date', '')}"):
            with st.form(f"campaign_edit_{campaign['id']}"):
                values = _campaign_form_fields(f"edit_{campaign['id']}", campaign)
                col1, col2 = st.columns(2)
                update = col1.form_submit_button("儲存修改", type="primary")
                delete = col2.form_submit_button("刪除活動")
            if update:
                if not values["name"] or not values["primary_industry"]:
                    st.error("請填寫活動名稱並選擇主要產業。")
                else:
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
    st.subheader("Step 4｜產業資料引用")
    lead["industry_context"] = industry_reference_selector(campaign, "LINE")
    st.subheader("Step 5｜產生 LINE 訊息")
    if st.button("產生 LINE 訊息", type="primary", key="generate_LINE"):
        st.session_state["LINE_result"] = generate_line(campaign, scenario, lead)
    result = st.session_state.get("LINE_result")
    if result:
        st.text_area("產生結果（可直接修改）", result, height=360, key="LINE_output")
        st.download_button("下載文字檔", result, file_name="line_draft.txt")


def email_builder_v1() -> None:
    st.header("Email 信件")
    st.caption("依信件用途選擇活動與產業資料，套用既有 Template Engine 產生 Email。")

    email_type = st.radio(
        "信件類型",
        ["活動信件", "非活動信件"],
        horizontal=True,
        key="Email_type",
    )
    is_event_email = email_type == "活動信件"
    campaign: dict = {}
    if is_event_email:
        campaign = campaign_selector("Email_campaign") or {}
        if not campaign:
            return
        scenarios = EVENT_EMAIL_SCENARIOS
    else:
        scenarios = NON_EVENT_EMAIL_SCENARIOS

    scenario = st.selectbox("信件情境", scenarios, key="Email_scenario_v2")
    if scenario == "活動前確認出席通知":
        st.info(
            "此情境固定使用「活動確認出席｜【活動名稱】活動出席確認信（Energy）」主旨格式。"
        )

    industry_context = email_industry_selector()
    brand = st.text_input("品牌名稱（選填）", key="Email_brand_v2")
    contact = st.text_input("聯絡人姓名（選填）", key="Email_contact_v2")

    selection_signature = (
        email_type,
        campaign.get("id", ""),
        scenario,
        (industry_context or {}).get("id", ""),
    )
    if st.session_state.get("Email_selection_signature") != selection_signature:
        st.session_state.pop("Email_result", None)
        st.session_state["Email_selection_signature"] = selection_signature

    if st.button("產生 Email 信件", type="primary", key="generate_Email_v1"):
        subjects, body, cta = generate_email(
            campaign,
            scenario,
            {
                "brand": brand.strip(),
                "contact": contact.strip(),
                "industry_context": industry_context,
                "is_event_email": is_event_email,
            },
            event_details={
                "service_intro_url": campaign.get("service_intro_url", ""),
                "materials_url": (
                    campaign.get("materials_url")
                    or campaign.get("presentation_url", "")
                ),
            },
        )
        st.session_state["Email_result"] = (
            "信件主旨：\n"
            + subjects[0]
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
    return [
        line.strip().lstrip("-•・ ")
        for line in value.splitlines()
        if line.strip().lstrip("-•・ ")
    ]


def _showcase_text(cases: list[dict]) -> str:
    return "\n".join(
        "｜".join([
            case.get("brand_name", ""), case.get("category", ""),
            case.get("use_cases", ""),
            case.get("key_points") or case.get("summary", ""),
            "Yes" if case.get("public", False) else "No",
        ]) for case in cases
    )


def _parse_showcases(value: str) -> list[dict]:
    cases = []
    for line in value.splitlines():
        if not line.strip():
            continue
        fields = [item.strip() for item in line.split("｜", 4)]
        fields += [""] * (5 - len(fields))
        cases.append({
            "brand_name": fields[0], "category": fields[1],
            "use_cases": fields[2], "key_points": fields[3],
            "public": fields[4].lower() in {"yes", "y", "true", "是", "可"},
        })
    return cases


def _industry_form(prefix: str, item: Optional[dict] = None) -> dict:
    item = item or {}
    name = st.text_input("產業名稱 *", item.get("industry_name", ""), key=f"{prefix}_name")
    description = st.text_area(
        "產業說明", item.get("description", ""), key=f"{prefix}_description"
    )
    brand_scenarios = st.text_area(
        "常見經營情境（每行一筆）", _multiline(item.get("brand_scenarios", [])),
        key=f"{prefix}_brand_scenarios", height=150,
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
        "Omnichat 對應應用（每行一筆）",
        _multiline(item.get("omnichat_applications") or item.get("omnichat_scenarios", [])),
        key=f"{prefix}_scenarios", height=130,
    )
    showcases = st.text_area(
        "Showcase / 品牌案例",
        _showcase_text(item.get("showcase_cases", [])), key=f"{prefix}_showcases", height=150,
        help="每行格式：品牌名稱｜品牌分類｜使用情境｜可引用重點｜Yes/No",
    )
    ctas = st.text_area(
        "常用 CTA（每行一筆）", _multiline(item.get("common_ctas", [])),
        key=f"{prefix}_ctas", height=130,
    )
    cautions = st.text_area(
        "禁用 / 注意事項（每行一筆）", _multiline(item.get("cautions", [])),
        key=f"{prefix}_cautions", height=130,
    )
    return {
        "industry_name": name.strip(), "description": description.strip(),
        "brand_scenarios": _line_items(brand_scenarios),
        "pain_points": _line_items(pain_points),
        "development_angles": _line_items(angles),
        "omnichat_applications": _line_items(scenarios),
        "showcase_cases": _parse_showcases(showcases),
        "common_ctas": _line_items(ctas),
        "cautions": _line_items(cautions),
        # Preserve legacy knowledge fields when editing an existing record.
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
        pain_count = len(item.get("pain_points", []))
        app_count = len(item.get("omnichat_applications") or item.get("omnichat_scenarios", []))
        case_count = len(item.get("showcase_cases", []))
        with st.expander(
            f"{item.get('industry_name', '未命名產業')}｜痛點 {pain_count}｜應用 {app_count}｜案例 {case_count}"
        ):
            st.caption(item.get("description", "尚未填寫產業說明"))
            with st.form(f"industry_edit_{item['id']}"):
                values = _industry_form(f"industry_{item['id']}", item)
                col1, col2, col3 = st.columns(3)
                update = col1.form_submit_button("儲存修改", type="primary")
                copy = col2.form_submit_button("複製資料")
                delete = col3.form_submit_button("刪除產業")
            if update:
                if not values["industry_name"]:
                    st.error("請填寫產業名稱。")
                else:
                    update_industry_template(item["id"], values)
                    st.success("產業資料已更新。")
                    st.rerun()
            if copy:
                save_industry_template({
                    "id": str(uuid4()), **values,
                    "industry_name": f"{values['industry_name']}（副本）",
                })
                st.success("產業知識已複製，請再修改產業名稱與內容。")
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
