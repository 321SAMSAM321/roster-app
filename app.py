import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
import calendar
import holidays
from datetime import date

st.set_page_config(page_title="旺角社區客廳 排更系統", layout="wide")
st.title("📅 旺角社區客廳 - 智能排更與微調系統")

# ==========================================
# 左側邊欄 (Sidebar)
# ==========================================
st.sidebar.header("👥 員工名單與固定休假")

default_sw = "李絲格(SW)\n陳家俊(SW)\n朱信恆(SW)\n韓浩文(SW)"
default_normal = "許紫慧\n王琴美\n許曉彬\n李琳\n曾詠詩"

sw_text = st.sidebar.text_area("💼 社工 (SW) 名單：", value=default_sw, height=120)
normal_text = st.sidebar.text_area("🧑‍💼 一般員工名單：", value=default_normal, height=120)

sw_staffs = [name.strip() for name in sw_text.split('\n') if name.strip()]
normal_staffs = [name.strip() for name in normal_text.split('\n') if name.strip()]
all_staffs = sw_staffs + normal_staffs
num_staff = len(all_staffs)

st.sidebar.markdown("---")
st.sidebar.subheader("🗓️ 固定星期幾休假")
default_fixed_rest = "朱信恆(SW): 日\n陳家俊(SW): 二, 五, 六"
fixed_rest_text = st.sidebar.text_area("✍️ 在此輸入固定放假要求：", value=default_fixed_rest, height=80)

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
                if days:
                    fixed_dict[name] = days
    return fixed_dict

# 🌟 新增 1：上月底上班紀錄 (跨月防過勞)
st.sidebar.markdown("---")
st.sidebar.subheader("⏮️ 跨月防過勞：上月底上班紀錄")
st.sidebar.info("請輸入同事在上個月底【最後連續上班的天數】（沒輸入代表上月底最後一天放假）。")
default_prev_work = "王琴美: 3\n曾詠詩: 1"
prev_work_text = st.sidebar.text_area("格式 `名字: 連續天數`", value=default_prev_work, height=80)

def parse_prev_work(text, staffs):
    prev_dict = {}
    if not text.strip(): return prev_dict
    text = text.replace('：', ':')
    for line in text.split('\n'):
        if ':' in line:
            parts = line.split(':')
            name = parts[0].strip()
            if name in staffs and parts[1].strip().isdigit():
                prev_dict[name] = min(6, int(parts[1].strip())) # 最多記錄前6天
    return prev_dict

# 🌟 新增 2：分開設定「平日」與「週末/紅日」的人手需求
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 每日人手需求設定")
st.sidebar.markdown("**🏢 平日 (一至五)**")
col_min1, col_max1 = st.sidebar.columns(2)
with col_min1: min_staff_wd = st.number_input("平日最少總人數", min_value=1, value=5)
with col_max1: min_sw_wd = st.number_input("平日最少社工", min_value=0, value=2)

st.sidebar.markdown("**🏖️ 週末及香港公眾假期 (紅日)**")
col_min2, col_max2 = st.sidebar.columns(2)
with col_min2: min_staff_hd = st.number_input("紅日最少總人數", min_value=1, value=6)
with col_max2: min_sw_hd = st.number_input("紅日最少社工", min_value=0, value=3)

# 簡化最高人數設定 (預設為最低人數+1)
max_staff_wd, max_sw_wd = min_staff_wd + 1, min_sw_wd + 1
max_staff_hd, max_sw_hd = min_staff_hd + 1, min_sw_hd + 1

# ==========================================
# 主畫面
# ==========================================
col1, col2 = st.columns(2)
with col1:
    selected_year = st.selectbox("🗓️ 請選擇年份", [2024, 2025, 2026, 2027, 2028], index=2)
with col2:
    selected_month = st.selectbox("📅 請選擇月份", list(range(1, 13)), index=4)

st.markdown("### 🏖️ 指定日期請假 (大假 AL / 補假 CL)")
st.info("格式：`名字: 12, 13, 25` (換行輸入另一位)。")
leave_requests_text = st.text_area("✍️ 在此輸入單次請假需求：", height=100)

def parse_leave_requests(text, staffs):
    leave_dict = {}
    if not text.strip(): return leave_dict
    text = text.replace('：', ':').replace('，', ',')
    for line in text.split('\n'):
        if ':' in line:
            parts = line.split(':')
            name = parts[0].strip()
            if name in staffs:
                dates_str = parts[1]
                dates = [int(x.strip()) for x in dates_str.split(',') if x.strip().isdigit()]
                leave_dict[name] = dates
    return leave_dict

# 自動診斷函數 (加入紅日判斷)
def diagnose_conflicts(year, month, leave_dict, fixed_rest_dict, sw_list, all_list):
    start_day_index = calendar.weekday(year, month, 1)
    num_days = calendar.monthrange(year, month)[1] 
    days_name = ['一', '二', '三', '四', '五', '六', '日']
    hk_holidays = holidays.HK(years=[year]) # 取得香港紅日
    issues = []
    
    for d in range(num_days):
        current_date = date(year, month, d+1)
        current_weekday = (start_day_index + d) % 7
        is_holiday = current_weekday >= 5 or current_date in hk_holidays
        date_str = f"{month}月{d+1}日(星期{days_name[current_weekday]}){' 🎈紅日' if is_holiday else ''}"
        
        req_min_t = min_staff_hd if is_holiday else min_staff_wd
        req_min_s = min_sw_hd if is_holiday else min_sw_wd
        
        unavailable_staff = []
        unavailable_sw = []
        
        for name in all_list:
            is_out = False
            if name in fixed_rest_dict and current_weekday in fixed_rest_dict[name]: is_out = True
            if name in leave_dict and (d + 1) in leave_dict[name]: is_out = True
            
            if is_out:
                unavailable_staff.append(name)
                if name in sw_list: unavailable_sw.append(name)
        
        available_total = len(all_list) - len(unavailable_staff)
        available_sw = len(sw_list) - len(unavailable_sw)
        
        if available_total < req_min_t:
            issues.append(f"🔴 **{date_str}**：最少需 {req_min_t} 人，但當天有 **{len(unavailable_staff)} 人** 放假 (`{', '.join(unavailable_staff)}`)，只剩 **{available_total}** 人。")
        if available_sw < req_min_s:
            issues.append(f"🟠 **{date_str}**：最少需 {req_min_s} 名社工，但社工只剩 **{available_sw}** 人 (當天放假：`{', '.join(unavailable_sw) if unavailable_sw else '無'}`)。")
            
    return issues

# 核心排班大腦
def generate_schedule(year, month, leave_dict, fixed_rest_dict, prev_work_dict, sw_list, all_list):
    start_day_index = calendar.weekday(year, month, 1)
    num_days = calendar.monthrange(year, month)[1] 
    days_name = ['一', '二', '三', '四', '五', '六', '日']
    total_staff_count = len(all_list)
    hk_holidays = holidays.HK(years=[year]) # 載入香港紅日
    
    model = cp_model.CpModel()
    work = {}
    for s in range(total_staff_count):
        for d in range(num_days):
            work[(s, d)] = model.NewBoolVar(f'work_s{s}_d{d}')

    # 1. 動態配置平日與紅日的人手需求
    for d in range(num_days):
        current_date = date(year, month, d+1)
        current_weekday = (start_day_index + d) % 7
        is_holiday = current_weekday >= 5 or current_date in hk_holidays
        
        req_min_t = min_staff_hd if is_holiday else min_staff_wd
        req_max_t = max_staff_hd if is_holiday else max_staff_wd
        req_min_s = min_sw_hd if is_holiday else min_sw_wd
        req_max_s = max_sw_hd if is_holiday else max_sw_wd

        model.Add(sum(work[(s, d)] for s in range(total_staff_count)) >= req_min_t)
        model.Add(sum(work[(s, d)] for s in range(total_staff_count)) <= req_max_t)
        model.Add(sum(work[(s, d)] for s in range(len(sw_list))) >= req_min_s)
        model.Add(sum(work[(s, d)] for s in range(len(sw_list))) <= req_max_s)

    # 2. 🌟 完美的跨月防過勞機制 (納入上月底紀錄)
    past_work = {}
    for s in range(total_staff_count):
        name = all_list[s]
        consecutive_days = prev_work_dict.get(name, 0)
        # 設定上個月最後 6 天的上班狀態 (past_d: 0~5，5代表上個月最後一天)
        for past_d in range(6):
            past_work[(s, past_d)] = 1 if past_d >= (6 - consecutive_days) else 0

    for s in range(total_staff_count):
        # 檢查每一個 7 天的區間（包含跨月區間）
        for start_offset in range(-6, num_days - 6):
            window_sum = 0
            for i in range(7):
                day_idx = start_offset + i
                if day_idx < 0:
                    past_d = 6 + day_idx
                    window_sum += past_work[(s, past_d)]
                else:
                    window_sum += work[(s, day_idx)]
            model.Add(window_sum <= 4)
            
        target_work_days = int((num_days / 7) * 4) 
        model.Add(sum(work[(s, d)] for d in range(num_days)) >= target_work_days - 1)
        model.Add(sum(work[(s, d)] for d in range(num_days)) <= target_work_days + 1)

    # 3. 固定星期幾休假
    for name, weekdays in fixed_rest_dict.items():
        if name in all_list:
            s_idx = all_list.index(name)
            for d in range(num_days):
                if (start_day_index + d) % 7 in weekdays:
                    model.Add(work[(s_idx, d)] == 0)

    # 4. 特定日期請假
    for name, dates in leave_dict.items():
        if name in all_list:
            s_idx = all_list.index(name)
            for day in dates:
                if 1 <= day <= num_days:
                    model.Add(work[(s_idx, day - 1)] == 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0 
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        columns = ['同事姓名']
        for d in range(num_days):
            current_date = date(year, month, d+1)
            current_weekday = (start_day_index + d) % 7
            is_holiday = current_weekday >= 5 or current_date in hk_holidays
            # 標題自動加上紅日標記
            header = f"{month}/{d+1}\n({days_name[current_weekday]})" + ("🎈" if is_holiday else "")
            columns.append(header)

        data = []
        for s in range(total_staff_count):
            row = [all_list[s]]
            for d in range(num_days):
                row.append("DO" if solver.Value(work[(s, d)]) == 1 else "OFF")
            data.append(row)
        return pd.DataFrame(data, columns=columns)
    else:
        return None

# ==========================================
# 執行與匯出
# ==========================================
st.markdown("---")
if st.button(f"🚀 讓 AI 生成 {selected_year} 年 {selected_month} 月份更表", use_container_width=True):
    with st.spinner('AI 正在協調假期、香港紅日與跨月工時 (最多運算 10 秒)...'):
        parsed_leaves = parse_leave_requests(leave_requests_text, all_staffs)
        parsed_fixed = parse_fixed_weekdays(fixed_rest_text, all_staffs)
        parsed_prev = parse_prev_work(prev_work_text, all_staffs)
        
        df = generate_schedule(selected_year, selected_month, parsed_leaves, parsed_fixed, parsed_prev, sw_staffs, all_staffs)
        
        if df is not None:
            st.session_state['schedule_df'] = df
            st.success(f"✅ 生成成功！已套用香港公眾假期，並確保所有人跨月無過勞。")
        else:
            st.error("❌ 無法排班！AI 診斷報告如下：")
            conflict_reports = diagnose_conflicts(selected_year, selected_month, parsed_leaves, parsed_fixed, sw_staffs, all_staffs)
            
            if conflict_reports:
                for report in conflict_reports: st.warning(report)
                st.info("💡 解決方案：請減少上述日期的請假人數，或前往左側調低「最少總人數」。")
            else:
                st.warning("⚠️ 診斷結果：排班失敗是因為勞工規則。可能是因為某人「上月底連續上班紀錄」加上「本月初期沒有請假」，導致 AI 無法在第一週為他安排合法假期。")

if 'schedule_df' in st.session_state:
    st.markdown("### 📝 手動微調區 (雙擊表格修改，🎈代表週末或紅日)")
    edited_df = st.data_editor(st.session_state['schedule_df'], use_container_width=True)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        edited_df.to_excel(writer, index=False, sheet_name=f'{selected_month}月更表')
    
    st.download_button(
        label=f"💾 下載最終 Excel 檔",
        data=buffer.getvalue(),
        file_name=f"旺角社區客廳_{selected_year}年{selected_month}月更表.xlsx",
        mime="application/vnd.ms-excel"
    )
