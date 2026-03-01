import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
import calendar

st.set_page_config(page_title="旺角社區客廳 排更系統", layout="wide")
st.title("📅 旺角社區客廳 - 智能排更與微調系統")

# ==========================================
# 🌟 新增：左側邊欄 (Sidebar) - 員工名單管理
# ==========================================
st.sidebar.header("👥 員工名單管理")
st.sidebar.info("請在此新增或刪除同事名字（每行輸入一位）。系統會自動辨識並更新排班。")

# 預設名單
default_sw = "李絲格(SW)\n陳家俊(SW)\n朱信恆(SW)\n韓浩文(SW)"
default_normal = "許紫慧\n王琴美\n許曉彬\n李琳\n曾詠詩"

# 讓使用者在側邊欄修改名單
sw_text = st.sidebar.text_area("💼 社工 (SW) 名單：", value=default_sw, height=150)
normal_text = st.sidebar.text_area("🧑‍💼 一般員工名單：", value=default_normal, height=150)

# 將文字框的內容轉換為程式可以讀取的清單 (並自動去除空白)
sw_staffs = [name.strip() for name in sw_text.split('\n') if name.strip()]
normal_staffs = [name.strip() for name in normal_text.split('\n') if name.strip()]
all_staffs = sw_staffs + normal_staffs
num_staff = len(all_staffs)

st.sidebar.success(f"目前共計：{num_staff} 人 (含 {len(sw_staffs)} 位社工)")

# ==========================================
# 主畫面：選擇年月與預先請假
# ==========================================
col1, col2 = st.columns(2)
with col1:
    selected_year = st.selectbox("🗓️ 請選擇年份", [2024, 2025, 2026, 2027, 2028], index=2)
with col2:
    selected_month = st.selectbox("📅 請選擇月份", list(range(1, 13)), index=4)

st.markdown("### 🏖️ 預先請假 / 指定休假設定 (選填)")
st.info("請依照格式輸入：`同事名字: 日期, 日期` (換行輸入另一位)。")
leave_requests_text = st.text_area("✍️ 在此輸入請假需求：", height=100)

def parse_leave_requests(text, staffs):
    leave_dict = {}
    if not text.strip():
        return leave_dict
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

# ==========================================
# 核心排班大腦 (引入動態名單)
# ==========================================
def generate_schedule(year, month, leave_dict, sw_list, all_list):
    start_day_index = calendar.weekday(year, month, 1)
    num_days = calendar.monthrange(year, month)[1] 
    days_name = ['一', '二', '三', '四', '五', '六', '日']
    total_staff_count = len(all_list)
    
    model = cp_model.CpModel()
    work = {}
    for s in range(total_staff_count):
        for d in range(num_days):
            work[(s, d)] = model.NewBoolVar(f'work_s{s}_d{d}')

    # 基本人手限制 (每天至少 5 人，包含 2 名社工)
    for d in range(num_days):
        model.Add(sum(work[(s, d)] for s in range(total_staff_count)) >= 5)
        model.Add(sum(work[(s, d)] for s in range(total_staff_count)) <= 6)
        model.Add(sum(work[(s, d)] for s in range(len(sw_list))) >= 2)
        model.Add(sum(work[(s, d)] for s in range(len(sw_list))) <= 3)

    # 個人工時與休假頻率
    for s in range(total_staff_count):
        for d in range(num_days - 6):
            model.Add(sum(work[(s, d + i)] for i in range(7)) <= 4)
        min_work_days = int((num_days / 7) * 4) 
        model.Add(sum(work[(s, d)] for d in range(num_days)) >= min_work_days - 1)
        model.Add(sum(work[(s, d)] for d in range(num_days)) <= min_work_days + 1)

    # 🌟 防呆機制：檢查名單裡是否還有這兩位同事，有的話才套用特定規則
    if '朱信恆(SW)' in all_list:
        chu_idx = all_list.index('朱信恆(SW)')
        for d in range(num_days):
            if (start_day_index + d) % 7 == 6:
                model.Add(work[(chu_idx, d)] == 0)
                
    if '陳家俊(SW)' in all_list:
        chen_idx = all_list.index('陳家俊(SW)')
        for d in range(num_days):
            if (start_day_index + d) % 7 in [1, 4, 5]:
                model.Add(work[(chen_idx, d)] == 0)

    # 處理手動輸入的請假要求
    for name, dates in leave_dict.items():
        if name in all_list:
            s_idx = all_list.index(name)
            for day in dates:
                if 1 <= day <= num_days:
                    model.Add(work[(s_idx, day - 1)] == 0)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        columns = ['同事姓名']
        for d in range(num_days):
            current_weekday = (start_day_index + d) % 7
            columns.append(f"{month}/{d+1}\n({days_name[current_weekday]})")

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
    # 檢查人數是否足夠營運
    if num_staff < 6:
        st.warning("⚠️ 警告：目前總員工人數過少，可能無法滿足每天最低 5 人的排班需求，AI 可能會計算失敗。")
        
    with st.spinner('AI 正在協調假期並尋找最佳排班...'):
        parsed_leaves = parse_leave_requests(leave_requests_text, all_staffs)
        df = generate_schedule(selected_year, selected_month, parsed_leaves, sw_staffs, all_staffs)
        
        if df is not None:
            st.session_state['schedule_df'] = df
            st.success(f"✅ 生成成功！已套用左側名單內的 {num_staff} 位同事。")
        else:
            st.error("❌ 無法排班！請檢查：1. 是否請假人數過多？ 2. 員工人數是否足夠應付每天的最低人手需求？")

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
