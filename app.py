import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
import calendar

st.set_page_config(page_title="旺角社區客廳 排更系統", layout="wide")
st.title("📅 旺角社區客廳 - 智能排更與微調系統")

# ==========================================
# 左側邊欄 (Sidebar) - 員工與固定假期管理
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

st.sidebar.success(f"目前共計：{num_staff} 人 (含 {len(sw_staffs)} 位社工)")

# 固定星期幾休假
st.sidebar.markdown("---")
st.sidebar.subheader("🗓️ 固定星期幾休假")
default_fixed_rest = "朱信恆(SW): 日\n陳家俊(SW): 二, 五, 六"
fixed_rest_text = st.sidebar.text_area("✍️ 在此輸入固定放假要求：", value=default_fixed_rest, height=100)

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

# 每日人手需求設定區
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 每日人手需求設定")
st.sidebar.info("請設定每天最少/最多需要多少人上班。")
col_min, col_max = st.sidebar.columns(2)
with col_min:
    min_staff = st.number_input("最少總人數", min_value=1, max_value=20, value=5)
    min_sw = st.number_input("最少社工", min_value=0, max_value=10, value=2)
with col_max:
    max_staff = st.number_input("最多總人數", min_value=1, max_value=20, value=6)
    max_sw = st.number_input("最多社工", min_value=0, max_value=10, value=3)

# ==========================================
# 主畫面：選擇年月與預先請假
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

# 🌟 新增：衝突自動診斷函數
def diagnose_conflicts(year, month, leave_dict, fixed_rest_dict, sw_list, all_list, min_t, min_s):
    start_day_index = calendar.weekday(year, month, 1)
    num_days = calendar.monthrange(year, month)[1] 
    days_name = ['一', '二', '三', '四', '五', '六', '日']
    issues = []
    
    for d in range(num_days):
        current_weekday = (start_day_index + d) % 7
        date_str = f"{month}月{d+1}日(星期{days_name[current_weekday]})"
        
        unavailable_staff = []
        unavailable_sw = []
        
        # 核對當天有誰不能上班
        for name in all_list:
            is_out = False
            if name in fixed_rest_dict and current_weekday in fixed_rest_dict[name]:
                is_out = True
            if name in leave_dict and (d + 1) in leave_dict[name]:
                is_out = True
            
            if is_out:
                unavailable_staff.append(name)
                if name in sw_list:
                    unavailable_sw.append(name)
        
        available_total = len(all_list) - len(unavailable_staff)
        available_sw = len(sw_list) - len(unavailable_sw)
        
        # 如果剩下的人數低於左側設定的最低要求，就寫入報告
        if available_total < min_t:
            issues.append(f"🔴 **{date_str}**：最少需 {min_t} 人，但當天有 **{len(unavailable_staff)} 人** 放假 (`{', '.join(unavailable_staff)}`)，只剩 **{available_total}** 人。")
            
        if available_sw < min_s:
            issues.append(f"🟠 **{date_str}**：最少需 {min_s} 名社工，但社工只剩 **{available_sw}** 人 (當天放假社工：`{', '.join(unavailable_sw) if unavailable_sw else '無'}`)。")
            
    return issues

# ==========================================
# 核心排班大腦 (維持第十五版的嚴格規則)
# ==========================================
def generate_schedule(year, month, leave_dict, fixed_rest_dict, sw_list, all_list, min_t, max_t, min_s, max_s):
    start_day_index = calendar.weekday(year, month, 1)
    num_days = calendar.monthrange(year, month)[1] 
    days_name = ['一', '二', '三', '四', '五', '六', '日']
    total_staff_count = len(all_list)
    
    model = cp_model.CpModel()
    work = {}
    for s in range(total_staff_count):
        for d in range(num_days):
            work[(s, d)] = model.NewBoolVar(f'work_s{s}_d{d}')

    # 1. 每天人手需求動態設定
    for d in range(num_days):
        model.Add(sum(work[(s, d)] for s in range(total_staff_count)) >= min_t)
        model.Add(sum(work[(s, d)] for s in range(total_staff_count)) <= max_t)
        model.Add(sum(work[(s, d)] for s in range(len(sw_list))) >= min_s)
        model.Add(sum(work[(s, d)] for s in range(len(sw_list))) <= max_s)

    # 2. 第十五版嚴格的個人工時與休假頻率
    for s in range(total_staff_count):
        # 任何連續 7 天內，最多只能上班 4 天
        for d in range(num_days - 6):
            model.Add(sum(work[(s, d + i)] for i in range(7)) <= 4)
            
        min_work_days = int((num_days / 7) * 4) 
        model.Add(sum(work[(s, d)] for d in range(num_days)) >= min_work_days - 1)
        model.Add(sum(work[(s, d)] for d in range(num_days)) <= min_work_days + 1)

    # 3. 處理「固定星期幾休假」
    for name, weekdays in fixed_rest_dict.items():
        if name in all_list:
            s_idx = all_list.index(name)
            for d in range(num_days):
                if (start_day_index + d) % 7 in weekdays:
                    model.Add(work[(s_idx, d)] == 0)

    # 4. 處理「指定日期請假」
    for name, dates in leave_dict.items():
        if name in all_list:
            s_idx = all_list.index(name)
            for day in dates:
                if 1 <= day <= num_days:
                    model.Add(work[(s_idx, day - 1)] == 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0 # 給 AI 最多 10 秒鐘思考，避免網頁卡死
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
    if num_staff < min_staff:
        st.warning(f"⚠️ 警告：目前總員工只有 {num_staff} 人，但你設定每天最少要 {min_staff} 人上班，這絕對排不出來！請調低需求或增加員工。")
    elif max_staff < min_staff or max_sw < min_sw:
         st.warning(f"⚠️ 警告：「最多人數」不能小於「最少人數」，請檢查左側的數字設定！")
    else:
        with st.spinner('AI 正在協調假期並尋找最佳排班 (最多運算 10 秒)...'):
            parsed_leaves = parse_leave_requests(leave_requests_text, all_staffs)
            parsed_fixed = parse_fixed_weekdays(fixed_rest_text, all_staffs)
            
            df = generate_schedule(selected_year, selected_month, parsed_leaves, parsed_fixed, sw_staffs, all_staffs, min_staff, max_staff, min_sw, max_sw)
            
            if df is not None:
                st.session_state['schedule_df'] = df
                st.success(f"✅ 生成成功！已確保每天最少 {min_staff} 人上班（含 {min_sw} 位社工）。")
            else:
                st.error("❌ 無法排班！AI 診斷報告如下：")
                
                # 觸發診斷系統
                conflict_reports = diagnose_conflicts(selected_year, selected_month, parsed_leaves, parsed_fixed, sw_staffs, all_staffs, min_staff, min_sw)
                
                if conflict_reports:
                    # 情況一：明顯有人手不足的日子
                    for report in conflict_reports:
                        st.warning(report)
                    st.info("💡 解決方案：請減少上述日期的請假人數，或前往左側調低「最少總人數」及「最少社工」的要求。")
                else:
                    # 情況二：帳面人數足夠，但因為第十五版的「嚴格勞工法則」導致衝突
                    st.warning("⚠️ 診斷結果：這週並沒有任何一天的可用人數低於最低要求。排班失敗是因為條件太過緊繃。")
                    st.info("💡 發生原因：目前系統採用最嚴格的「每連續 7 天內最多只能上班 4 天」規則。如果某位同事請了特定假期，加上他原本的固定休假，會迫使其他同事必須連續代班，從而觸發「不准連返 5 日」的保護機制，導致 AI 放棄排班。\n\n**解決方案：請嘗試減少一兩位同事的請假設定，給 AI 多一點排班的呼吸空間。**")

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
