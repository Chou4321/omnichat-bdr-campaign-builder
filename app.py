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
    validate_cold_email_sources,
)
from models import Campaign, CONTENT_SECTIONS, EMAIL_SCENARIOS, LINE_SCENARIOS, Template
from line_contact_finder import (
    generate_activity_reply,
    generate_email_provided_reply,
    generate_first_contact_message,
)
from storage import (
    delete_campaign,
    delete_copy_template,
    load_campaigns,
    load_copy_templates,
    load_industry_templates,
    save_campaign,
    save_copy_template,
    update_campaign,
    update_copy_template,
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


def lead_inputs(prefix: str) -> dict[str, str]:
    col1, col2 = st.columns(2)
    brand = col1.text_input("品牌", key=f"{prefix}_brand")
    contact = col2.text_input("窗口", key=f"{prefix}_contact")
    industry = col1.text_input("品牌產業", key=f"{prefix}_industry")
    observation = col2.text_area("品牌觀察", key=f"{prefix}_observation")
    precall = col1.text_area("Pre-call 紀錄", key=f"{prefix}_precall")
    needs = col2.text_area("品牌需求", key=f"{prefix}_needs")
    return {
        "brand": brand,
        "contact": contact,
        "industry": industry,
        "observation": observation,
        "precall": precall,
        "needs": needs,
    }


def _industry_observation_template(industry: str) -> str:
    template = next(
        (
            item for item in load_industry_templates()
            if item.get("industry_name") == industry
            or any(keyword in industry for keyword in ("食品", "伴手禮"))
            and item.get("id") == "food-gift"
        ),
        None,
    )
    if not template:
        return "目前沒有對應的產業模板；請改用手動輸入或 AI 文案資料庫。"
    return "\n".join(f"• {item}" for item in template.get("pain_points", [])[:4])


def cold_outreach_lead_inputs() -> dict[str, str]:
    col1, col2 = st.columns(2)
    brand = col1.text_input("品牌", key="Email_brand")
    contact = col2.text_input("窗口", key="Email_contact")
    industry = st.text_input("品牌產業", key="Email_industry")
    source = st.selectbox(
        "品牌觀察來源",
        ["手動輸入", "AI 文案資料庫", "對應產業模板"],
        key="Email_observation_source",
    )
    observation = ""
    if source == "手動輸入":
        observation = st.text_area(
            "品牌觀察",
            key="Email_observation",
            placeholder="只填寫已確認的品牌資訊；留白時不會自動補寫。",
        )
    elif source == "AI 文案資料庫":
        library_items = [
            item for item in load_copy_templates()
            if item.get("channel") in {"產業切角", "品牌案例"}
        ]
        if library_items:
            selected_id = st.selectbox(
                "選擇資料庫內容",
                [item["id"] for item in library_items],
                format_func=lambda item_id: next(
                    item["name"] for item in library_items if item["id"] == item_id
                ),
                key="Email_observation_library",
            )
            observation = next(
                item["content"] for item in library_items if item["id"] == selected_id
            )
            st.text_area("引用內容", observation, disabled=True)
        else:
            st.info("AI 文案資料庫目前沒有「產業切角」或「品牌案例」內容，本次不加入品牌觀察。")
    else:
        observation = _industry_observation_template(industry)
        st.text_area("對應產業模板", observation, disabled=True)
    return {
        "brand": brand,
        "contact": contact,
        "industry": industry,
        "observation": observation,
        "observation_source": source,
        "precall": "",
        "needs": "",
    }


def precall_attachment_inputs(campaign: dict) -> dict:
    """Attachments used only by 活動報名後打招呼 (Pre-call)."""
    st.subheader("Pre-call 信件附件")
    banner_path = campaign.get("image_path", "")
    if banner_path and (BASE_DIR / banner_path).exists():
        st.image(
            str(BASE_DIR / banner_path),
            caption="附件① 活動 Banner（由活動管理帶入）",
            width=480,
        )
    else:
        st.warning("活動管理尚未上傳活動 Banner。")
    service_pdf = st.file_uploader(
        "附件② Omnichat 服務介紹 PDF",
        type=["pdf"],
        key=f"precall_service_pdf_{campaign['id']}",
    )
    return {"service_pdf_name": service_pdf.name if service_pdf else ""}


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
    st.caption("建立單一活動資料，Email、LINE 與活動圖文會直接共用。")
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


def message_generator(channel: str) -> None:
    if channel == "Email":
        email_builder_v1()
        return
    title = "Email 信件" if channel == "Email" else "LINE 邀約訊息"
    st.header(title)
    if channel == "Email":
        st.caption("依不同活動階段產出 Email 信件。")
        scenarios = EMAIL_SCENARIOS
    else:
        st.caption("產出 BDR 在 LINE 上使用的活動開發、邀約與追蹤訊息。")
        scenarios = LINE_SCENARIOS
    st.subheader("Step 1｜選擇活動")
    campaign = campaign_selector(f"{channel}_campaign")
    if not campaign:
        return
    st.subheader("Step 2｜選擇情境")
    scenario = st.selectbox("情境", scenarios, key=f"{channel}_scenario")
    event_details = None
    selected_email_title = ""
    if channel == "Email" and scenario == "活動報名後打招呼":
        event_details = precall_attachment_inputs(campaign)
    if channel == "Email" and scenario in {"陌生開發邀約", "活動報名後打招呼"}:
        saved_titles = [
            campaign.get("email_title_a", ""),
            campaign.get("email_title_b", ""),
            campaign.get("email_title_c", ""),
        ]
        saved_titles = [title for title in saved_titles if title]
        if saved_titles:
            selected_email_title = st.selectbox(
                "選擇信件大標", saved_titles, key=f"{channel}_{scenario}_selected_title"
            )
    st.subheader("Step 3｜輸入品牌資訊")
    if channel == "Email" and scenario == "陌生開發邀約":
        lead = cold_outreach_lead_inputs()
    else:
        lead = lead_inputs(channel)
    st.subheader("Step 4｜產生內容")
    if st.button(f"產生{title}", type="primary", key=f"generate_{channel}"):
        if channel == "Email":
            source_warning = None
            if scenario == "陌生開發邀約":
                source_warning = validate_cold_email_sources(
                    campaign, event_details or {}, lead.get("industry", "")
                )
            if source_warning:
                st.error(source_warning)
                subjects, body, cta = [], "", ""
            else:
                details = dict(event_details or {})
                details["selected_email_title"] = selected_email_title
                subjects, body, cta = generate_email(
                    campaign, scenario, lead, event_details=details
                )
            if scenario == "陌生開發邀約" and not source_warning:
                displayed_title = selected_email_title or subjects[0]
                st.session_state[f"{channel}_result"] = (
                    f"信件大標：\n{displayed_title}\n\nEmail 內文：\n{body}"
                )
            elif scenario == "活動報名後打招呼" and not source_warning:
                displayed_title = selected_email_title or subjects[0]
                st.session_state[f"{channel}_result"] = (
                    f"信件大標：\n{displayed_title}\n\nEmail 內文：\n{body}"
                )
            elif not source_warning:
                st.session_state[f"{channel}_result"] = (
                    "信件主旨 3 版：\n"
                    + "\n".join(
                        f"{index}. {subject}" for index, subject in enumerate(subjects, 1)
                    )
                    + f"\n\nEmail 內文：\n{body}\n\nCTA：\n{cta}"
                )
        else:
            st.session_state[f"{channel}_result"] = generate_line(
                campaign, scenario, lead, event_details=event_details
            )
    result = st.session_state.get(f"{channel}_result")
    if result:
        st.text_area("產生結果（可直接修改）", result, height=360, key=f"{channel}_output")
        st.download_button("下載文字檔", result, file_name=f"{channel.lower()}_draft.txt")


def email_builder_v1() -> None:
    st.header("Email 信件")
    st.caption("V1.0 精簡版｜使用五種固定 Template，不串接外部 AI API。")

    st.subheader("Step 1｜選擇情境")
    scenario = st.selectbox("情境", EMAIL_SCENARIOS, key="Email_scenario")

    st.subheader("Step 2｜活動內容")
    introduction = st.text_area(
        "活動介紹 *",
        height=240,
        key="Email_activity_introduction",
        placeholder="請貼上本次活動的完整介紹；信件只會依此內容產生。",
    )
    banner = st.file_uploader(
        "活動 Banner（選填）",
        type=["png", "jpg", "jpeg", "webp"],
        key="Email_banner",
        help="僅作為信件附圖保存，不進行圖片辨識。",
    )
    if banner:
        st.image(banner, caption="本次 Email Banner", width=480)

    st.subheader("Step 3｜品牌資訊")
    brand = st.text_input("品牌名稱 *", key="Email_brand")
    contact = st.text_input("窗口（選填）", key="Email_contact")
    observation = st.text_area(
        "品牌觀察（選填）",
        key="Email_observation",
        placeholder="可留白；系統不會自行補寫品牌資訊。",
    )

    st.subheader("Step 4｜產生 Email")
    if st.button("產生 Email", type="primary", key="generate_Email_v1"):
        if not introduction.strip():
            st.error("請填寫活動介紹。")
        elif not brand.strip():
            st.error("請填寫品牌名稱。")
        else:
            image_path = _save_banner(banner) if banner else ""
            subjects, body, cta = generate_email(
                {"introduction": introduction.strip(), "image_path": image_path},
                scenario,
                {
                    "brand": brand.strip(),
                    "contact": contact.strip(),
                    "observation": observation.strip(),
                },
            )
            st.session_state["Email_result"] = (
                "信件主旨 3 版：\n"
                + "\n".join(f"{index}. {subject}" for index, subject in enumerate(subjects, 1))
                + f"\n\nEmail 內文：\n{body}\n\nCTA：\n{cta}"
            )

    result = st.session_state.get("Email_result")
    if result:
        st.text_area("產生結果（可直接修改）", result, height=420, key="Email_output")
        st.download_button("下載文字檔", result, file_name="email_draft.txt")


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


def template_library() -> None:
    st.header("AI 文案資料庫")
    st.caption("第一版提供文案資料管理，不串接 AI API。")
    templates = load_copy_templates()
    tabs = st.tabs(CONTENT_SECTIONS)
    for section, tab in zip(CONTENT_SECTIONS, tabs):
        with tab:
            section_items = [item for item in templates if item.get("channel") == section]
            with st.expander(f"＋ 新增{section}", expanded=not section_items):
                with st.form(f"new_{section}", clear_on_submit=True):
                    name = st.text_input("資料名稱 *")
                    content = st.text_area("內容 *", height=180)
                    submitted = st.form_submit_button("新增", type="primary")
                if submitted:
                    if not name.strip() or not content.strip():
                        st.error("資料名稱與內容為必填。")
                    else:
                        save_copy_template(Template(name, section, "資料庫", content).to_dict())
                        st.success("資料已新增。")
                        st.rerun()
            if not section_items:
                st.info("目前尚無資料。")
            for item in section_items:
                with st.expander(f"查看｜{item['name']}"):
                    with st.form(f"edit_{item['id']}"):
                        name = st.text_input("資料名稱", item["name"])
                        content = st.text_area("內容", item["content"], height=180)
                        col1, col2 = st.columns(2)
                        update = col1.form_submit_button("儲存修改")
                        delete = col2.form_submit_button("刪除")
                    if update:
                        update_copy_template(item["id"], {
                            "name": name, "channel": section,
                            "scenario": item.get("scenario", "資料庫"), "content": content,
                        })
                        st.success("資料已更新。")
                        st.rerun()
                    if delete:
                        delete_copy_template(item["id"])
                        st.success("資料已刪除。")
                        st.rerun()


if "pending_email_transfer" in st.session_state:
    transfer = st.session_state.pop("pending_email_transfer")
    st.session_state["active_page"] = "Email 信件"
    st.session_state["Email_brand"] = transfer["brand"]
    st.session_state["Email_contact"] = transfer["contact"]
    transferred_campaign = next(
        (item for item in load_campaigns() if item["id"] == transfer["campaign_id"]),
        None,
    )
    if transferred_campaign:
        st.session_state["Email_activity_introduction"] = (
            transferred_campaign.get("introduction")
            or transferred_campaign.get("summary")
            or ""
        )

st.sidebar.title("Omnichat")
st.sidebar.caption("BDR Campaign Builder")
page = st.sidebar.radio(
    "功能選單",
    ["LINE 找窗口", "活動管理", "Email 信件", "LINE 邀約訊息", "活動圖文", "AI 文案資料庫"],
    key="active_page",
)

pages = {
    "LINE 找窗口": line_contact_finder,
    "活動管理": campaign_manager,
    "Email 信件": lambda: message_generator("Email"),
    "LINE 邀約訊息": lambda: message_generator("LINE"),
    "活動圖文": banner_generator,
    "AI 文案資料庫": template_library,
}
pages[page]()
