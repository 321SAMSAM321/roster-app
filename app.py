import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
import calendar

st.set_page_config(page_title="旺角社區客廳 排更系統", layout="wide")
st.title("📅 旺角社區客廳 - 智能排更與微調系統")
st.markdown("請設定年份、月份與預先請假名單。生成後，可在下方表格點擊微調，最後下載 Excel。")

# 1. 選擇年月
col1, col2 = st.columns(2)
with col1:
    selected_year = st.selectbox("🗓️ 請選擇年份", [2024, 2025, 2026, 2027, 2028], index=2)
with col2:
    selected_month = st.selectbox("📅 請選擇月份", list(range(1, 13)), index=4)

# 2. 🌟 新增：預先請假輸入區
st.markdown("### 🏖️ 預先請假 / 指定休假設定 (選填)")
st.info("請依照格式輸入：`同事名字: 日期, 日期` (使用半形或全形冒號/逗號皆可，換行輸入另一位)。\n\n**範例：**\n王琴美: 12, 13\n許曉彬: 25\n李絲格(SW): 4, 5, 6")
leave_requests_text = st.text_area("✍️ 在此輸入請假需求：", height=120)

# 解析請假文字的函數
def parse_leave_requests(text, staffs):
    leave_dict = {}
    if not text.strip():
        return leave_dict
        
    # 處理全形與半形符號，讓系統更聰明防呆
    text = text.replace('：', ':').replace('，', ',')
    for line in text.split('\n'):
        if ':' in line:
            parts = line.split(':')
            name = parts[0].strip()
            if name in staffs:
                # 抓出所有的日期數字
                dates_str = parts[1]
                dates = [int(x.strip()) for x in dates_str.split(',') if x.strip().isdigit()]
                leave_dict[name] = dates
    return leave_dict

# 核心排更函數
def generate_schedule(year, month, leave_dict):
    start_day_index = calendar.weekday(year, month, 1)
    num_days = calendar.monthrange(year, month)[1] 
    days_name = ['一', '二', '三', '四', '五', '六', '日']
    
    sw_staffs = ['李絲格(SW)', '陳家俊(SW)', '朱信恆(SW)', '韓浩文(SW)']
    normal_staffs = ['許紫慧', '王琴美', '許曉彬', '李琳', '曾詠詩']
    all_staffs = sw_staffs + normal_staffs
    num_staff = len(all_staffs)
    
    model = cp_model.CpModel()
    work = {}
    for s in range(num_staff):
        for d in range(num_days):
            work[(s, d)] = model.NewBoolVar(f'work_s{s}_d{d}')

    # 基本人手與休假邏輯
    for d in range(num_days):
        model.Add(sum(work[(s, d)] for s in range(num_staff)) >= 5)
        model.Add(sum(work[(s, d)] for s in range(num_staff)) <= 6)
        model.Add(sum(work[(s, d)] for s in range(len(sw_staffs))) >= 2)
        model.Add(sum(work[(s, d)] for s in range(len(sw_staffs))) <= 3)

    for s in range(num_staff):
        for d in range(num_days - 6):
            model.Add(sum(work[(s, d + i)] for i in range(7)) <= 4)
        min_work_days = int((num_days / 7) * 4) 
        model.Add(sum(work[(s, d)] for d in range(num_days)) >= min_work_days - 1)
        model.Add(sum(work[(s, d)] for d in range(num_days)) <= min_work_days + 1)

    # 處理陳家俊與朱信恆的固定休假
    chen_idx = all_staffs.index('陳家俊(SW)')
    chu_idx = all_staffs.index('朱信恆(SW)')
    for d in range(num_days):
        if (start_day_index + d) % 7 == 6:
            model.Add(work[(chu_idx, d)] == 0)
        if (start_day_index + d) % 7 in [1, 4, 5]:
            model.Add(work[(chen_idx, d)] == 0)

    # 🌟 新增：寫入你在網頁上手動輸入的請假要求
    for name, dates in leave_dict.items():
        s_idx = all_staffs.index(name)
        for day in dates:
            if 1 <= day <= num_days:
                # 設定該名同事在那一天 (day-1 是因為程式從 0 開始算) 狀態必須為 0 (放假)
                model.Add(work[(s_idx, day - 1)] == 0)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        columns = ['同事姓名']
        for d in range(num_days):
            current_weekday = (start_day_index + d) % 7
            columns.append(f"{month}/{d+1}\n({days_name[current_weekday]})")

        data = []
        for s in range(num_staff):
            row = [all_staffs[s]]
            for d in range(num_days):
                row.append("DO" if solver.Value(work[(s, d)]) == 1 else "OFF")
            data.append(row)
        return pd.DataFrame(data, columns=columns)
    else:
        return None

# 3. 按鈕與執行邏輯
st.markdown("---")
if st.button(f"🚀 讓 AI 生成 {selected_year} 年 {selected_month} 月份更表", use_container_width=True):
    with st.spinner('AI 正在協調大家的假期並尋找最佳排班...'):
        all_staffs_list = ['李絲格(SW)', '陳家俊(SW)', '朱信恆(SW)', '韓浩文(SW)', '許紫慧', '王琴美', '許曉彬', '李琳', '曾詠詩']
        parsed_leaves = parse_leave_requests(leave_requests_text, all_staffs_list)
        
        df = generate_schedule(selected_year, selected_month, parsed_leaves)
        
        if df is not None:
            st.session_state['schedule_df'] = df
            st.success(f"✅ 生成成功！已為您避開 {len(parsed_leaves)} 位同事的指定假期。")
        else:
            st.error("❌ 無法排班！可能是大家請假的日子撞在一起（例如太多人同選一天），導致當天湊不齊最低上班人數。請嘗試放寬或刪減一些請假要求後再試一次。")

# 4. 手動微調與下載
if 'schedule_df' in st.session_state:
    st.markdown("### 📝 手動微調區 (雙擊表格修改)")
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
