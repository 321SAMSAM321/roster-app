import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
import calendar # 🌟 新增：用來自動計算日曆的超級工具

# 網頁標題與設定
st.set_page_config(page_title="旺角社區客廳 排更系統", layout="wide")
st.title("📅 旺角社區客廳 - 智能排更與微調系統")
st.markdown("請先選擇年份與月份，點擊生成後，可在下方表格中點擊並修改任何內容，最後下載成 Excel 檔案。")

# 🌟 新增：建立兩個並排的下拉式選單 (年份與月份)
col1, col2 = st.columns(2)
with col1:
    selected_year = st.selectbox("🗓️ 請選擇年份", [2024, 2025, 2026, 2027, 2028], index=2) # 預設選中 2026
with col2:
    selected_month = st.selectbox("📅 請選擇月份", list(range(1, 13)), index=4) # 預設選中 5 月 (清單索引4為5)

# 將年份和月份傳入生成函數
def generate_schedule(year, month):
    # 🌟 新增：讓系統自動算出這個月有幾天，以及 1 號是星期幾
    # calendar.weekday() 回傳 0 是星期一，6 是星期日，剛好符合我們的設定！
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
        
        # 🌟 動態調整：依照該月總天數按比例計算最少上班日
        min_work_days = int((num_days / 7) * 4) 
        model.Add(sum(work[(s, d)] for d in range(num_days)) >= min_work_days - 1)
        model.Add(sum(work[(s, d)] for d in range(num_days)) <= min_work_days + 1)

    chen_idx = all_staffs.index('陳家俊(SW)')
    chu_idx = all_staffs.index('朱信恆(SW)')
    for d in range(num_days):
        if (start_day_index + d) % 7 == 6:
            model.Add(work[(chu_idx, d)] == 0)
        if (start_day_index + d) % 7 in [1, 4, 5]:
            model.Add(work[(chen_idx, d)] == 0)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        columns = ['同事姓名']
        for d in range(num_days):
            current_weekday = (start_day_index + d) % 7
            columns.append(f"{month}/{d+1}\n({days_name[current_weekday]})") # 標題加上月份

        data = []
        for s in range(num_staff):
            row = [all_staffs[s]]
            for d in range(num_days):
                row.append("DO" if solver.Value(work[(s, d)]) == 1 else "OFF")
            data.append(row)
            
        return pd.DataFrame(data, columns=columns)
    else:
        return None

# 按鈕文字會根據選單自動變化
if st.button(f"🚀 1. 讓 AI 生成 {selected_year} 年 {selected_month} 月份初步更表"):
    with st.spinner('正在計算最佳排班...'):
        df = generate_schedule(selected_year, selected_month)
        if df is not None:
            st.session_state['schedule_df'] = df
            st.success(f"✅ {selected_month} 月份生成成功！請在下方表格直接點擊修改。")
        else:
            st.error("❌ 無法找到符合條件的排班。可能是當月週末分佈導致條件衝突，請稍後重試。")

if 'schedule_df' in st.session_state:
    st.markdown("### 📝 2. 手動微調區")
    edited_df = st.data_editor(st.session_state['schedule_df'], use_container_width=True)
    
    st.markdown("### 📥 3. 下載最終更表")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        edited_df.to_excel(writer, index=False, sheet_name=f'{selected_month}月更表')
    
    st.download_button(
        label=f"💾 下載 {selected_month} 月份 Excel 檔",
        data=buffer.getvalue(),
        file_name=f"旺角社區客廳_{selected_year}年{selected_month}月更表.xlsx",
        mime="application/vnd.ms-excel"
    )
