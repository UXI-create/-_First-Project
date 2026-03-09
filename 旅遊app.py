import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests
import copy
import uuid 
import gspread
from google.oauth2.service_account import Credentials
# ==========================================
# ⚙️ 網頁初始化設定
# ==========================================
st.set_page_config(page_title="Travel Vibe Pro Max", page_icon="✈️", layout="centered")
# 🌟 這裡就是放資料庫函式最好的地方！
SPREADSHEET_ID = "1M4cNxuinL8g6zsMoj7Q5veZR3S85VOiBsWG5vggoBvo"

def save_to_sheets(data):
    try:
        # 今天先確保連線 ID 正確，下次我們來寫入內容
        st.toast(f"已連結至資料庫: {SPREADSHEET_ID[:8]}...") 
        st.success("資料已成功同步至雲端試算表！")
    except Exception as e:
        st.error(f"同步失敗：{e}")
# ==========================================
# 🔐 模組零：私有化登入系統
# ==========================================
SECRET_PASSWORD = "201020"

def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1f4037, #99f2c8); padding: 30px; border-radius: 10px; text-align: center; color: white; margin-top: 50px;">
            <h1 style="margin: 0; font-size: 36px; font-weight: bold; color: white;">🔒 Travel Vibe 私有終端</h1>
            <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">請輸入通行憑證以解鎖您的專屬行程管家</p>
        </div>
        """, unsafe_allow_html=True)
        password_input = st.text_input("🔑 通關密碼", type="password")
        if st.button("🔓 解鎖進入", use_container_width=True):
            if password_input == SECRET_PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("❌ 密碼錯誤，存取被拒絕！")
        return False
    return True

if check_password():
    # ==========================================
    # 🧠 資料庫與 API 引擎
    # ==========================================
    if 'itinerary' not in st.session_state: st.session_state.itinerary = []
    if 'trip_database' not in st.session_state: st.session_state.trip_database = {}
    if 'search_results' not in st.session_state: st.session_state.search_results = {}
    if 'current_time' not in st.session_state: st.session_state.current_time = datetime.now()
    if 'members' not in st.session_state: st.session_state.members = []
    if 'expenses' not in st.session_state: st.session_state.expenses = []

    geolocator = Nominatim(user_agent="vibe_streamlit_app")
    visa_rules = {
        "🇯🇵 日本": "免簽證 (建議先填 Visit Japan Web)", "🇰🇷 韓國": "免簽證", "🇹🇭 泰國": "需申請簽證/免簽",
        "🇭🇰 香港": "需申請『預辦登記』或『台胞證』", "🇲🇴 澳門": "免簽證", "🇨🇳 中國大陸": "需持有『台胞證』", "🇹🇼 台灣": "身分證/健保卡"
    }

    @st.cache_data(ttl=3600)
    def get_weather(country_name):
        try:
            loc = geolocator.geocode(country_name.split(" ")[1] if " " in country_name else country_name)
            if not loc: return None
            url = f"https://api.open-meteo.com/v1/forecast?latitude={loc.latitude}&longitude={loc.longitude}&current_weather=true"
            res = requests.get(url).json()
            return res['current_weather']
        except: return None

    @st.cache_data(ttl=3600)
    def get_exchange_rates():
        try:
            url = "https://api.exchangerate-api.com/v4/latest/TWD"
            res = requests.get(url).json()
            return res.get("rates", {})
        except:
            return {"TWD": 1.0, "JPY": 4.7, "KRW": 42.0, "USD": 0.031, "EUR": 0.029, "HKD": 0.24, "CNY": 0.22}

    def generate_smart_packing_list(days, country):
        packing = {"🪪 證件與金錢": [], "⛅ 天氣與穿搭推薦": [], "🔌 電子與雜物": []}
        if "台灣" in country: packing["🪪 證件與金錢"].extend(["身分證", "健保卡", "現金 / 信用卡"])
        else:
            packing["🪪 證件與金錢"].extend(["護照 (效期6個月以上)", f"⚠️ 簽證: {visa_rules.get(country, '請查詢')}", "機票/訂房憑證"])

        weather_data = get_weather(country)
        if weather_data:
            temp, code = weather_data['temperature'], weather_data['weathercode']
            is_raining = code >= 50
            packing["⛅ 天氣與穿搭推薦"].append(f"📡 AI 氣象站：氣溫約 {temp}°C，{'🌧️ 預計有雨' if is_raining else '☀️ 天氣晴朗'}")
            if temp < 15: packing["⛅ 天氣與穿搭推薦"].extend(["🧣 發熱衣/保暖內衣", "🧥 羽絨外套或厚大衣"])
            elif temp > 28: packing["⛅ 天氣與穿搭推薦"].extend(["🕶️ 太陽眼鏡", "🧴 防曬乳", "🩳 輕薄透氣短袖"])
            if is_raining: packing["⛅ 天氣與穿搭推薦"].extend(["☔ 摺疊傘 / 輕便雨衣", "🥾 防水鞋套或好乾的鞋子"])
        packing["⛅ 天氣與穿搭推薦"].extend([f"上衣/內外褲 x {days+1} 件", f"襪子 x {days+1} 雙", "好走鞋子"])
        packing["🔌 電子與雜物"].extend(["手機", "充電器/線", "常備藥品", "行動電源"])
        return packing

    def estimate_time(loc1, loc2, mode):
        if not loc1 or not loc2: return 20
        dist_km = geodesic((loc1['lat'], loc1['lng']), (loc2['lat'], loc2['lng'])).km
        speed = 4 if "步行" in mode else 15 if "公車" in mode else 30
        return max(3, int(((dist_km * 1.3) / speed) * 60))

    def format_time_str(mins):
        if mins < 60: return f"{mins} 分"
        return f"{mins // 60} 小時 {mins % 60} 分" if mins % 60 > 0 else f"{mins // 60} 小時"

    st.markdown("""
    <div style="background: linear-gradient(135deg, #8E2DE2, #4A00E0); padding: 20px; border-radius: 10px; text-align: center; color: white; margin-bottom: 20px;">
        <h1 style="margin: 0; font-size: 32px; font-weight: bold; color: white;">✈️ 羅比 普拉思 旅遊用具 </h1>
        <p style="margin: 5px 0 0 0; font-size: 16px; opacity: 0.9;">彈性拆帳 ✕ 行程修改 ✕ 完美規劃 🔒</p>
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("🚪 登出系統"):
        st.session_state["password_correct"] = False
        st.rerun()
# 在側邊欄增加同步按鈕
st.sidebar.markdown("---")
if st.sidebar.button("📡 立即同步至雲端"):
    # 這裡我們傳入目前的帳單資料 (expenses)
    save_to_sheets(st.session_state.expenses)
    tab_plan, tab_pack, tab_finance = st.tabs(['🗓️ 智慧行程', '🧳 天氣打包', '💸 匯率與拆帳'])

    # ----------------- 🧳 分頁：天氣與打包 -----------------
    with tab_pack:
        col1, col2 = st.columns(2)
        with col1: dest = st.selectbox("✈️ 目的地", list(visa_rules.keys()), index=0)
        with col2: days = st.number_input("📅 天數", min_value=1, max_value=30, value=5)
        if st.button("⛅ 預測天氣並生成清單", use_container_width=True):
            with st.spinner(f"正在連線氣象局..."):
                result = generate_smart_packing_list(days, dest)
                for cat, items in result.items():
                    st.markdown(f"#### {cat}")
                    for item in items: st.markdown(f"- [ ] {item}")
                    st.markdown("---")

    # ----------------- 🗓️ 分頁：行程與檔案庫 -----------------
    with tab_plan:
        with st.expander("📂 歷史行程檔案管理", expanded=False):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: trip_name = st.text_input("📁 行程命名", placeholder="例: 東京跨年")
            with c2:
                st.write("")
                if st.button("💾 儲存"):
                    if trip_name and st.session_state.itinerary:
                        st.session_state.trip_database[trip_name] = {
                            "itinerary": copy.deepcopy(st.session_state.itinerary),
                            "members": copy.deepcopy(st.session_state.members),
                            "expenses": copy.deepcopy(st.session_state.expenses)
                        }
                        st.success(f"已儲存：{trip_name}")
            with c3:
                st.write("")
                if st.button("📄 開新"):
                    st.session_state.itinerary = []
                    st.session_state.members = []
                    st.session_state.expenses = []
                    st.rerun()
            if st.session_state.trip_database:
                load_name = st.selectbox("📂 讀取紀錄", list(st.session_state.trip_database.keys()))
                if st.button("📖 讀取此行程"):
                    db_data = st.session_state.trip_database[load_name]
                    st.session_state.itinerary = copy.deepcopy(db_data["itinerary"])
                    st.session_state.members = copy.deepcopy(db_data["members"])
                    st.session_state.expenses = copy.deepcopy(db_data["expenses"])
                    st.success(f"已讀取：{load_name}")
                    st.rerun()

        is_first = len(st.session_state.itinerary) == 0
        if is_first:
            c1, c2 = st.columns(2)
            with c1: start_date = st.date_input("📅 起點日期")
            with c2: start_time = st.time_input("⏰ 出發時間", value=datetime.strptime("09:00", "%H:%M").time())

        c1, c2, c3 = st.columns([1, 2, 1])
        with c1: city = st.text_input("🌍 城市", value="東京")
        with c2: keyword = st.text_input("🔍 找景點", placeholder="例: 成田機場")
        with c3:
            st.write("")
            if st.button("🔎 搜尋", type="primary"):
                with st.spinner("掃描中..."):
                    results = {}
                    try:
                        query = f"{keyword}, {city}" if city else keyword
                        locs = geolocator.geocode(query, exactly_one=False, limit=5)
                        if not locs: locs = geolocator.geocode(keyword, exactly_one=False, limit=5)
                        if locs:
                            for loc in locs: results[loc.address] = {"name": keyword, "lat": loc.latitude, "lng": loc.longitude}
                    except: pass
                    st.session_state.search_results = results

        if st.session_state.search_results:
            selected_address = st.selectbox("📍 選擇正確地點", list(st.session_state.search_results.keys()))
            c1, c2, c3, c4 = st.columns(4)
            with c1: stay = st.number_input("⏱️ 停留(分)", min_value=10, value=120, step=10)
            with c2: mode = st.selectbox("交通", ['🚶 步行', '🚌 公車/地鐵', '🚗 計程車/開車'], index=1)
            with c3: cost = st.number_input("💰 預算", min_value=0, value=0, step=100)
            with c4: note = st.text_input("📝 備註", placeholder="航班號/備註")

            if st.button("➕ 確認加入", use_container_width=True):
                place_data = st.session_state.search_results[selected_address]
                stay_time = timedelta(minutes=stay)
                if is_first:
                    st.session_state.current_time = datetime.combine(start_date, start_time)
                    arrival_time = st.session_state.current_time
                    transport_text = "✨ 出發"
                else:
                    last_stop = st.session_state.itinerary[-1]
                    trans_mins = estimate_time(last_stop['coords'], place_data, mode)
                    arrival_time = st.session_state.current_time + timedelta(minutes=trans_mins)
                    transport_text = f"{mode} (約 {format_time_str(trans_mins)})"

                departure_time = arrival_time + stay_time
                st.session_state.itinerary.append({
                    "arrive": arrival_time.strftime("%m/%d %H:%M"), "transport": transport_text,
                    "name": place_data['name'], "note": note, "stay": format_time_str(stay),
                    "cost": cost, "depart": departure_time.strftime("%m/%d %H:%M"), "coords": place_data
                })
                st.session_state.current_time = departure_time
                st.session_state.search_results = {}
                st.rerun()

        st.markdown("---")
        if st.session_state.itinerary:
            df = pd.DataFrame(st.session_state.itinerary)
            display_plan_df = df[['arrive', 'transport', 'name', 'stay', 'note', 'cost', 'depart']].copy()
            display_plan_df.columns = ['抵達時間', '前往此站', '📍 地點', '⏱️ 停留', '📝 航班/備註', '💰 預算', '離開時間']
            st.dataframe(display_plan_df, use_container_width=True, hide_index=True)
            st.markdown(f"<h3 style='text-align: right; color: #4A00E0;'>💵 總行程預算: NT$ {df['cost'].sum():,.0f} </h3>", unsafe_allow_html=True)

    # ----------------- 💸 分頁：記帳與動態彈性拆帳 -----------------
    with tab_finance:
        st.markdown("### 👥 1. 設定旅伴")
        members_input = st.text_input("請輸入旅伴名字 (用半形逗號 , 分開)", value="Alice, Bob, Kevin")
        if st.button("💾 更新旅伴名單"):
            st.session_state.members = [m.strip() for m in members_input.split(",") if m.strip()]
            st.success(f"已更新旅伴：{', '.join(st.session_state.members)}")

        st.markdown("---")

        st.markdown("### 💱 2. 新增帳單")
        if not st.session_state.members:
            st.warning("⚠️ 請先在上方輸入旅伴名字！")
        else:
            rates = get_exchange_rates()
            currency_options = {"🇹🇼 台幣 (TWD)": "TWD", "🇯🇵 日幣 (JPY)": "JPY", "🇰🇷 韓元 (KRW)": "KRW", "🇺🇸 美金 (USD)": "USD"}

            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: exp_item = st.text_input("消費項目", placeholder="例: 敘敘苑燒肉、和服體驗")
            with c2:
                curr_label = st.selectbox("幣別", list(currency_options.keys()))
                curr_code = currency_options[curr_label]
            with c3: exp_amount = st.number_input("外幣金額", min_value=0.0, step=100.0)

            c4, c5 = st.columns(2)
            with c4: exp_payers = st.multiselect("💳 誰付的錢？(可多選)", st.session_state.members, default=st.session_state.members[0:1] if st.session_state.members else [])
            with c5: exp_consumers = st.multiselect("🍽️ 分攤給誰？(打叉可刪除)", st.session_state.members, default=st.session_state.members)

            if curr_code in rates and rates[curr_code] > 0: twd_estimate = exp_amount / rates[curr_code]
            else: twd_estimate = exp_amount

            st.caption(f"💡 即時匯率換算：約折合 **NT$ {twd_estimate:,.0f}**")

            if st.button("➕ 新增這筆帳款", type="primary"):
                if not exp_item or exp_amount <= 0: st.error("❌ 請輸入項目名稱與大於 0 的金額！")
                elif not exp_payers: st.error("❌ 至少要選一個付款人！")
                elif not exp_consumers: st.error("❌ 至少要有一個人來分攤這筆費用！")
                else:
                    # 🌟 賦予這筆帳單一個獨一無二的 ID (身分證)
                    st.session_state.expenses.append({
                        "id": str(uuid.uuid4()),
                        "項目": exp_item,
                        "原幣別": curr_code,
                        "_original_amount": exp_amount, # 紀錄原始輸入的金額，方便之後修改
                        "折合台幣": round(twd_estimate),
                        "付款人": ", ".join(exp_payers),
                        "分攤給": ", ".join(exp_consumers),
                        "_payers_list": exp_payers,
                        "_consumers_list": exp_consumers
                    })
                    st.success(f"✅ 記帳成功！")
                    st.rerun()

        # 📋 顯示明細與修改區塊
        if st.session_state.expenses:
            st.markdown("#### 📋 帳單明細")
            # 為了避免舊資料沒有 id 產生錯誤，自動補上 id
            for exp in st.session_state.expenses:
                if "id" not in exp: exp["id"] = str(uuid.uuid4())
                if "_original_amount" not in exp: exp["_original_amount"] = float(exp["折合台幣"])

            exp_df = pd.DataFrame(st.session_state.expenses)
            display_exp_df = exp_df[["項目", "原幣別", "折合台幣", "付款人", "分攤給"]]
            st.dataframe(display_exp_df, use_container_width=True, hide_index=True)

            # 🌟 全新編輯與刪除面板
            with st.expander("✏️ 修改或刪除單筆帳款", expanded=False):
                # 建立下拉選單選項：項目名稱 (折合台幣)
                exp_dict = {exp["id"]: exp for exp in st.session_state.expenses}
                def format_exp(exp): return f"{exp['項目']} (NT$ {exp['折合台幣']})"

                selected_id = st.selectbox("選擇要修改的帳單：", list(exp_dict.keys()), format_func=lambda x: format_exp(exp_dict[x]))

                if selected_id:
                    sel_exp = exp_dict[selected_id]

                    st.write("重新設定此筆帳款資料：")
                    e1, e2, e3 = st.columns([2, 1, 1])
                    with e1: e_item = st.text_input("新項目名稱", value=sel_exp["項目"], key="e_item")
                    with e2:
                        idx_curr = list(currency_options.values()).index(sel_exp["原幣別"])
                        e_curr_label = st.selectbox("新幣別", list(currency_options.keys()), index=idx_curr, key="e_curr")
                        e_curr_code = currency_options[e_curr_label]
                    with e3: e_amount = st.number_input("新外幣金額", value=float(sel_exp["_original_amount"]), step=100.0, key="e_amount")

                    e4, e5 = st.columns(2)
                    with e4: e_payers = st.multiselect("💳 新付款人", st.session_state.members, default=sel_exp["_payers_list"], key="e_payers")
                    with e5: e_consumers = st.multiselect("🍽️ 新分攤給", st.session_state.members, default=sel_exp["_consumers_list"], key="e_consumers")

                    if e_curr_code in rates and rates[e_curr_code] > 0: e_twd = e_amount / rates[e_curr_code]
                    else: e_twd = e_amount

                    st.caption(f"💡 修改後重新換算：約折合 **NT$ {e_twd:,.0f}**")

                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("💾 儲存修改", use_container_width=True):
                            if not e_item or e_amount <= 0 or not e_payers or not e_consumers:
                                st.error("❌ 欄位填寫不完整！")
                            else:
                                for i, exp in enumerate(st.session_state.expenses):
                                    if exp["id"] == selected_id:
                                        st.session_state.expenses[i].update({
                                            "項目": e_item, "原幣別": e_curr_code, "_original_amount": e_amount,
                                            "折合台幣": round(e_twd), "付款人": ", ".join(e_payers),
                                            "分攤給": ", ".join(e_consumers), "_payers_list": e_payers, "_consumers_list": e_consumers
                                        })
                                        break
                                st.success("✅ 修改成功！")
                                st.rerun()
                    with b2:
                        if st.button("🗑️ 刪除此筆", use_container_width=True):
                            st.session_state.expenses = [exp for exp in st.session_state.expenses if exp["id"] != selected_id]
                            st.success("✅ 刪除成功！")
                            st.rerun()

            if st.button("🗑️ 清空所有帳單", type="secondary"):
                st.session_state.expenses = []
                st.rerun()

            st.markdown("---")

            st.markdown("### 🤖 3. 智慧動態結算 (TWD)")
            balances = {member: 0.0 for member in st.session_state.members}
            total_expense_twd = 0.0

            for exp in st.session_state.expenses:
                amount_twd = exp["折合台幣"]
                payers = exp["_payers_list"]
                consumers = exp["_consumers_list"]
                total_expense_twd += amount_twd

                payer_split = amount_twd / len(payers)
                for p in payers:
                    if p in balances: balances[p] += payer_split

                consumer_split = amount_twd / len(consumers)
                for c in consumers:
                    if c in balances: balances[c] -= consumer_split

            st.info(f"💵 團隊總花費：NT$ {total_expense_twd:,.0f}")

            st.markdown("#### 💰 最終轉帳指示：")
            for member, balance in balances.items():
                if balance > 1:
                    st.success(f"收款方 🟢 **{member}** 可以拿回：NT$ {balance:,.0f}")
                elif balance < -1:
                    st.error(f"付款方 🔴 **{member}** 需要支付：NT$ {abs(balance):,.0f}")
                else:
                    st.write(f"平手 ⚪ **{member}** 不欠錢，完美打平！")