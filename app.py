import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io

# 網頁標題與設定
st.set_page_config(page_title="旺角社區客廳 排更系統", layout="wide")
st.title("📅 旺角社區客廳 - 智能排更與微調系統")
st.markdown("點擊下方按鈕生成初步更表。生成後，您可以**直接在下方表格中點擊並修改任何內容**，最後再下載成 Excel 檔案。")

def generate_schedule():
    num_days = 30 
    start_day_index = 2 # 4月1日是星期三
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

    # 基本人手與休假邏輯 (與之前相同)
    for d in range(num_days):
        model.Add(sum(work[(s, d)] for s in range(num_staff)) >= 5)
        model.Add(sum(work[(s, d)] for s in range(num_staff)) <= 6)
        model.Add(sum(work[(s, d)] for s in range(len(sw_staffs))) >= 2)
        model.Add(sum(work[(s, d)] for s in range(len(sw_staffs))) <= 3)

    for s in range(num_staff):
        for d in range(num_days - 6):
            model.Add(sum(work[(s, d + i)] for i in range(7)) <= 4)
        model.Add(sum(work[(s, d)] for d in range(num_days)) >= 17)
        model.Add(sum(work[(s, d)] for d in range(num_days)) <= 18)

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
            columns.append(f"{d+1}\n({days_name[current_weekday]})")

        data = []
        for s in range(num_staff):
            row = [all_staffs[s]]
            for d in range(num_days):
                row.append("DO" if solver.Value(work[(s, d)]) == 1 else "OFF")
            data.append(row)
            
        return pd.DataFrame(data, columns=columns)
    else:
        return None

# 按鈕：生成更表
if st.button("🚀 1. 讓 AI 生成 4 月份初步更表"):
    with st.spinner('正在計算最佳排班...'):
        df = generate_schedule()
        if df is not None:
            # 將算出的更表存入 session_state，讓它不會在網頁刷新時消失
            st.session_state['schedule_df'] = df
            st.success("✅ 生成成功！請在下方表格直接點擊修改（例如將 OFF 改成 AL）。")
        else:
            st.error("❌ 無法找到符合條件的排班。")

# 如果已經生成了更表，顯示互動式表格
if 'schedule_df' in st.session_state:
    st.markdown("### 📝 2. 手動微調區")
    
    # st.data_editor 是靈魂所在！它讓使用者可以直接在網頁上編輯表格
    edited_df = st.data_editor(st.session_state['schedule_df'], use_container_width=True)
    
    # 準備將修改後的表格轉換為 Excel
    st.markdown("### 📥 3. 下載最終更表")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        edited_df.to_excel(writer, index=False, sheet_name='4月更表')
    
    st.download_button(
        label="💾 下載修改後的 Excel 檔",
        data=buffer.getvalue(),
        file_name="旺角社區客廳_手動修改版更表.xlsx",
        mime="application/vnd.ms-excel"
    )
