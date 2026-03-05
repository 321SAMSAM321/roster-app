import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
import calendar
import holidays
from datetime import date

st.set_page_config(page_title="旺角社區客廳 排更系統", layout="wide")
st.title("📅 旺角社區客廳 - 智能排更與微調系統 (第十六版)")

# ==========================================
# 左側邊欄
# ==========================================
st.sidebar.header("👥 員工名單與固定休假")
default_sw = "李絲格(SW)\n陳家俊(SW)\n朱信恆(SW)\n韓浩文(SW)"
default_normal = "許紫慧\n王琴美\n許曉彬\n李琳\n曾詠詩"

sw_text = st.sidebar.text_area("💼 社工 (SW) 名單：", value=default_sw, height=120)
normal_text = st.sidebar.text_area("🧑‍💼 一般員工名單：", value=default_normal, height=120)

sw_staffs = [name.strip() for name in sw_text.split('\n') if name.strip()]
normal_staffs = [name.strip() for name in normal_text.split('\n') if name.strip()]
all_staffs = sw_staffs + normal_staffs

st.sidebar.markdown("---")
st.sidebar.subheader("🗓️ 固定星期幾休假")
default_fixed_rest = "朱信恆(SW): 日\n陳家俊(SW): 二, 五, 六"
fixed_rest_text = st.sidebar.text_area("✍️ 輸入固定放假 (如 名字: 日)：", value=default_fixed_rest, height=80)

def parse_fixed_weekdays(text, staffs):
    day_map = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6}
    fixed_dict = {}
    if not text.strip(): return fixed_dict
    text = text.replace('：', ':').replace('，', ',')
    for line in text.split('\n'):
        if ':' in line:
            parts = line.split(':')
            name = parts[0].strip()
            if name in staffs:
                days_str = parts[1]
                days = [day_map[d.strip()] for d in days_str.split(',') if d.strip() in day_map]
                if days: fixed_dict[name] = days
    return fixed_dict

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 每日人手需求設定")
# 分開平日與紅日，這能解決請假太多時的調配問題
st.sidebar.markdown("**🏢 平日設定**")
col_wd_min, col_wd_sw = st.sidebar.columns(2)
with col_wd_min: min_staff_wd = st.number_input("平日總人數", value=4)
with col_wd_sw: min_sw_wd = st.number_input("平日社工", value=2)

st.sidebar.markdown("**🎈 週末/紅日設定**")
col_hd_min, col_hd_sw = st.sidebar.columns(2)
with col_hd_min: min_staff_hd = st.number_input("紅日總人數", value=5)
with col_hd_sw: min_sw_hd = st.number_input("紅日社工", value=2)

# ==========================================
# 主畫面
# ==========================================
col1, col2 = st.columns(2)
with col1: selected_year = st.selectbox("🗓️ 年份", [2024, 2025, 2026], index=2)
with col2: selected_month = st.selectbox("📅 月份", list(range(1, 13)), index=2) # 預設3月

st.markdown("### 🏖️ 指定日期請假 (大假 AL / 補假 CL)")
leave_requests_text = st.text_area("格式：名字: 日期 (換行輸入另一位)", height=120, 
    value="李絲格(SW): 5, 6\n朱信恆(SW): 3, 6\n李琳: 4, 5\n曾詠詩: 19, 20, 21, 22\n王琴美: 9, 10, 11, 12, 13, 14")

def parse_leave_requests(text, staffs):
    leave_dict = {}
    if not text.strip(): return leave_dict
    text = text.replace('：', ':').replace('，', ',')
    for line in text.split('\n'):
        if ':' in line:
            parts = line.split(':')
            name = parts[0].strip()
            if name in staffs:
                dates = [int(x.strip()) for x in dates_str.split(',') if (dates_str := parts[1]) and x.strip().isdigit()]
                leave_dict[name] = dates
    return leave_dict

def generate_schedule(year, month, leave_dict, fixed_rest_dict, sw_list, all_list):
    start_day_index = calendar.weekday(year, month, 1)
    num_days = calendar.monthrange(year, month)[1] 
    days_name = ['一', '二', '三', '四', '五', '六', '日']
    hk_holidays = holidays.HK(years=[year])
    
    model = cp_model.CpModel()
    work = {}
    for s in range(len(all_list)):
        for d in range(num_days):
            work[(s, d)] = model.NewBoolVar(f'work_s{s}_d{d}')

    # 1. 每日人手需求 (智能識別平日/紅日)
    for d in range(num_days):
        curr_date = date(year, month, d+1)
        is_hd = (start_day_index + d) % 7 >= 5 or curr_date in hk_holidays
        req_total = min_staff_hd if is_hd else min_staff_wd
        req_sw = min_sw_hd if is_hd else min_sw_wd
        
        model.Add(sum(work[(s, d)] for s in range(len(all_list))) >= req_total)
        model.Add(sum(work[(s, d)] for s in range(len(sw_list))) >= req_sw)

    # 2. 修改核心規則：5/7 原則 (更符合現實，增加排班成功率)
    for s in range(len(all_list)):
        for d in range(num_days - 6):
            # 任何連續 7 天，最多上班 5 天 (即每週最少放 2 天假)
            model.Add(sum(work[(s, d + i)] for i in range(7)) <= 5)
        
        # 整月工時平衡
        target_days = int((num_days / 7) * 5)
        model.Add(sum(work[(s, d)] for d in range(num_days)) >= target_days - 2)
        model.Add(sum(work[(s, d)] for d in range(num_days)) <= target_days + 2)

    # 3. 處理固定休假與請假
    for name, weekdays in fixed_rest_dict.items():
        if name in all_list:
            s_idx = all_list.index(name)
            for d in range(num_days):
                if (start_day_index + d) % 7 in weekdays: model.Add(work[(s_idx, d)] == 0)

    for name, dates in leave_dict.items():
        if name in all_list:
            s_idx = all_list.index(name)
            for day in dates:
                if 1 <= day <= num_days: model.Add(work[(s_idx, day - 1)] == 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        cols = ['同事姓名']
        for d in range(num_days):
            curr_date = date(year, month, d+1)
            is_hd = (start_day_index + d) % 7 >= 5 or curr_date in hk_holidays
            cols.append(f"{month}/{d+1}\n({days_name[(start_day_index + d) % 7]})" + ("🎈" if is_hd else ""))
        
        data = [[all_list[s]] + ["DO" if solver.Value(work[(s, d)]) == 1 else "OFF" for d in range(num_days)] for s in range(len(all_list))]
        return pd.DataFrame(data, columns=cols)
    return None

# ==========================================
# 執行與匯出
# ==========================================
if st.button(f"🚀 生成 {selected_month} 月更表", use_container_width=True):
    with st.spinner('AI 正在計算最佳「互換」方案...'):
        parsed_leaves = parse_leave_requests(leave_requests_text, all_staffs)
        parsed_fixed = parse_fixed_weekdays(fixed_rest_text, all_staffs)
        df = generate_schedule(selected_year, selected_month, parsed_leaves, parsed_fixed, sw_staffs, all_staffs)
        
        if df is not None:
            st.session_state['schedule_df'] = df
            st.success("✅ 生成成功！AI 已自動完成同事間的「互換代班」。")
        else:
            st.error("❌ 依然無法排班！這代表請假天數已超過 9 人團隊的負荷極限。建議將「平日總人數」暫時調低至 3 人再試。")

if 'schedule_df' in st.session_state:
    st.data_editor(st.session_state['schedule_df'], use_container_width=True)
