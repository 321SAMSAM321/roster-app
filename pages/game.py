import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
import calendar
import holidays
from datetime import date
import random

st.set_page_config(page_title="旺角社區客廳系統", layout="wide")

# ==========================================
# 🌟 超級選單
# ==========================================
st.sidebar.title("🎛️ 系統選單")
app_mode = st.sidebar.radio("請選擇你要使用的功能：", ["📅 智能排更系統", "🎮 前線社工生存戰"])
st.sidebar.markdown("---")

# ==========================================
# 功能一：📅 智能排更系統 (保留原有完美功能)
# ==========================================
if app_mode == "📅 智能排更系統":
    st.title("📅 旺角社區客廳 - 智能排更與微調系統")
    st.sidebar.header("👥 員工名單與固定休假")
    default_sw = "李絲格(SW)\n陳家俊(SW)\n朱信恆(SW)\n韓浩文(SW)"
    default_normal = "許紫慧\n王琴美\n許曉彬\n李琳\n曾詠詩"
    sw_text = st.sidebar.text_area("💼 社工 (SW) 名單：", value=default_sw, height=120)
    normal_text = st.sidebar.text_area("🧑‍💼 一般員工名單：", value=default_normal, height=120)
    sw_staffs = [name.strip() for name in sw_text.split('\n') if name.strip()]
    normal_staffs = [name.strip() for name in normal_text.split('\n') if name.strip()]
    all_staffs = sw_staffs + normal_staffs
    
    st.sidebar.markdown("---")
    default_fixed_rest = "朱信恆(SW): 日\n陳家俊(SW): 二, 五, 六"
    fixed_rest_text = st.sidebar.text_area("✍️ 固定星期幾休假：", value=default_fixed_rest, height=80)

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
    prev_work_text = st.sidebar.text_area("⏮️ 上月底連續上班紀錄 (名字:天數)", value="王琴美: 3", height=80)

    def parse_prev_work(text, staffs):
        prev_dict = {}
        if not text.strip(): return prev_dict
        text = text.replace('：', ':')
        for line in text.split('\n'):
            if ':' in line:
                parts = line.split(':')
                name = parts[0].strip()
                if name in staffs and parts[1].strip().isdigit():
                    prev_dict[name] = min(6, int(parts[1].strip()))
        return prev_dict

    st.sidebar.markdown("---")
    col_min1, col_max1 = st.sidebar.columns(2)
    with col_min1: min_staff_wd = st.number_input("平日最少總人數", min_value=1, value=5)
    with col_max1: min_sw_wd = st.number_input("平日最少社工", min_value=0, value=2)
    col_min2, col_max2 = st.sidebar.columns(2)
    with col_min2: min_staff_hd = st.number_input("紅日最少總人數", min_value=1, value=6)
    with col_max2: min_sw_hd = st.number_input("紅日最少社工", min_value=0, value=3)
    max_staff_wd, max_sw_wd = min_staff_wd + 1, min_sw_wd + 1
    max_staff_hd, max_sw_hd = min_staff_hd + 1, min_sw_hd + 1

    col1, col2 = st.columns(2)
    with col1: selected_year = st.selectbox("🗓️ 年份", [2024, 2025, 2026, 2027, 2028], index=2)
    with col2: selected_month = st.selectbox("📅 月份", list(range(1, 13)), index=4)

    leave_requests_text = st.text_area("🏖️ 單次請假需求 (名字: 日期,日期)：", height=100)

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

    def generate_schedule(year, month, leave_dict, fixed_rest_dict, prev_work_dict, sw_list, all_list):
        start_day_index = calendar.weekday(year, month, 1)
        num_days = calendar.monthrange(year, month)[1] 
        days_name = ['一', '二', '三', '四', '五', '六', '日']
        total_staff_count = len(all_list)
        hk_holidays = holidays.HK(years=[year]) 
        
        model = cp_model.CpModel()
        work = {}
        for s in range(total_staff_count):
            for d in range(num_days):
                work[(s, d)] = model.NewBoolVar(f'work_s{s}_d{d}')

        for d in range(num_days):
            current_date = date(year, month, d+1)
            current_weekday = (start_day_index + d) % 7
            is_holiday = current_weekday >= 5 or current_date in hk_holidays
            model.Add(sum(work[(s, d)] for s in range(total_staff_count)) >= (min_staff_hd if is_holiday else min_staff_wd))
            model.Add(sum(work[(s, d)] for s in range(total_staff_count)) <= (max_staff_hd if is_holiday else max_staff_wd))
            model.Add(sum(work[(s, d)] for s in range(len(sw_list))) >= (min_sw_hd if is_holiday else min_sw_wd))
            model.Add(sum(work[(s, d)] for s in range(len(sw_list))) <= (max_sw_hd if is_holiday else max_sw_wd))

        past_work = {}
        for s in range(total_staff_count):
            consecutive_days = prev_work_dict.get(all_list[s], 0)
            for past_d in range(6):
                past_work[(s, past_d)] = 1 if past_d >= (6 - consecutive_days) else 0

        for s in range(total_staff_count):
            for start_offset in range(-6, num_days - 6):
                window_sum = 0
                for i in range(7):
                    day_idx = start_offset + i
                    if day_idx < 0: window_sum += past_work[(s, 6 + day_idx)]
                    else: window_sum += work[(s, day_idx)]
                model.Add(window_sum <= 4)
                
            target_work_days = int((num_days / 7) * 4) 
            model.Add(sum(work[(s, d)] for d in range(num_days)) >= target_work_days - 1)
            model.Add(sum(work[(s, d)] for d in range(num_days)) <= target_work_days + 1)

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
            columns = ['同事姓名']
            for d in range(num_days):
                current_weekday = (start_day_index + d) % 7
                is_holiday = current_weekday >= 5 or date(year, month, d+1) in hk_holidays
                columns.append(f"{month}/{d+1}\n({days_name[current_weekday]})" + ("🎈" if is_holiday else ""))

            data = []
            for s in range(total_staff_count):
                row = [all_list[s]]
                for d in range(num_days):
                    row.append("DO" if solver.Value(work[(s, d)]) == 1 else "OFF")
                data.append(row)
            return pd.DataFrame(data, columns=columns)
        return None

    if st.button(f"🚀 生成 {selected_month} 月更表", use_container_width=True):
        with st.spinner('運算中...'):
            df = generate_schedule(selected_year, selected_month, parse_leave_requests(leave_requests_text, all_staffs), parse_fixed_weekdays(fixed_rest_text, all_staffs), parse_prev_work(prev_work_text, all_staffs), sw_staffs, all_staffs)
            if df is not None:
                st.session_state['schedule_df'] = df
                st.success("✅ 生成成功！")
            else:
                st.error("❌ 條件衝突，無法排班！請放寬請假條件。")

    if 'schedule_df' in st.session_state:
        edited_df = st.data_editor(st.session_state['schedule_df'], use_container_width=True)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            edited_df.to_excel(writer, index=False, sheet_name=f'{selected_month}月更表')
        st.download_button("💾 下載 Excel", data=buffer.getvalue(), file_name=f"旺角社區客廳_{selected_month}月更表.xlsx", mime="application/vnd.ms-excel")

# ==========================================
# 功能二：🎮 前線社工生存戰 (趣味升級版)
# ==========================================
elif app_mode == "🎮 前線社工生存戰":
    # 初始化遊戲數值
    if 'scene' not in st.session_state:
        st.session_state.scene = 'start'
        st.session_state.energy = 100
        st.session_state.trust = 50
        st.session_state.time = "11:00 AM"
        st.session_state.inventory = 1 # 1杯凍檸茶

    def reset_game():
        st.session_state.scene = 'start'
        st.session_state.energy = 100
        st.session_state.trust = 50
        st.session_state.time = "11:00 AM"
        st.session_state.inventory = 1

    st.title("🏢 旺角社區客廳：前線社工生存戰")
    
    # 🌟 道具系統 (顯示在側邊欄)
    if st.session_state.scene != 'start' and not st.session_state.scene.startswith('game_over'):
        st.sidebar.markdown("### 🎒 你的背包")
        if st.session_state.inventory > 0:
            st.sidebar.info(f"🥤 少甜凍檸茶 x {st.session_state.inventory}")
            if st.sidebar.button("飲啖凍檸茶 (回復 30 體力)"):
                st.session_state.energy = min(100, st.session_state.energy + 30)
                st.session_state.inventory -= 1
                st.sidebar.success("爽啊！體力大增！")
                st.rerun()
        else:
            st.sidebar.warning("背包空空如也，得個吉。")

    st.markdown("---")

    # 狀態列
    if st.session_state.scene != 'start':
        st.markdown(f"**🕒 目前時間：{st.session_state.time}**")
        col1, col2 = st.columns(2)
        with col1: 
            # 體力低於 30 變紅色警告
            if st.session_state.energy > 30: st.progress(st.session_state.energy / 100, text=f"🔋 體力值：{st.session_state.energy}/100")
            else: st.error(f"⚠️ 體力告急：{st.session_state.energy}/100 (快飲檸茶！)")
        with col2: 
            st.progress(st.session_state.trust / 100, text=f"❤️ 街坊信任度：{st.session_state.trust}/100")
        st.markdown("---")

    # ---------------- 遊戲劇本 ----------------
    if st.session_state.scene == 'start':
        st.header("歡迎來到地獄... 啊不是，是社區客廳！")
        st.write("身為前線社工，你今天的目標很簡單：**準時 8:00 PM 收工，且不要被送進醫院。**")
        if st.button("🚀 打卡上班", type="primary"):
            st.session_state.scene = 'level_1'
            st.rerun()

    # 【第一關】
    elif st.session_state.scene == 'level_1':
        st.header("第一關：洗衣房的戰火 🧺")
        st.write("陳師奶和黃阿姨正為了一部剛空出來的洗衣機爭執不下。")
        st.info("🗣️ **陳師奶**：「我個洗衣籃 10 點半就擺喺度排隊啦！」\n\n🗣️ **黃阿姨**：「我有打電話預約 11 點 3 個字㗎！我趕住去覆診啊！」")
        
        if st.button("A. 📋 【鐵面無私】按中心規矩辦事，預約者優先。"):
            st.session_state.energy -= 10
            st.session_state.trust += 5
            st.session_state.time = "1:00 PM"
            st.session_state.scene = 'level_1_A'
            st.rerun()
        if st.button("B. 🤝 【社工上身】運用高級輔導技巧，耐心調解。"):
            st.session_state.energy -= 25 # 扣超多體力
            st.session_state.trust += 20
            st.session_state.time = "1:30 PM"
            st.session_state.scene = 'level_1_B'
            st.rerun()

    elif st.session_state.scene == 'level_1_A':
        st.subheader("結果：得罪師奶，但保住規矩")
        st.write("陳師奶死死氣拎走個洗衣籃，雖然她很不爽，但其他街坊覺得你很公道。")
        if st.button("🕒 繼續巡視中心 ➡️"):
            st.session_state.scene = 'level_2_intro'
            st.rerun()

    elif st.session_state.scene == 'level_1_B':
        st.subheader("結果：世界和平，但你講到口乾")
        st.write("你成功安撫了兩人，中心充滿了愛。但你覺得自己彷彿老了三歲。")
        if st.button("🕒 繼續巡視中心 ➡️"):
            st.session_state.scene = 'level_2_intro'
            st.rerun()

    # 【第二關】
    elif st.session_state.scene == 'level_2_intro':
        st.header("第二關：功課輔導班大暴走 🎒")
        st.write("時間來到下午 4:30，小學生大軍殺到！")
        st.write("小明和小華為了一粒印著比卡超的擦膠大打出手，旁邊的家長陳太正在投訴冷氣太凍，而你的直線電話又剛好響起...")
        
        # 🌟 隨機事件分歧
        if st.button("A. 🗣️ 【獅吼功】大喝一聲叫全場安靜，然後去聽電話。"):
            st.session_state.energy -= 15
            st.session_state.trust -= 15
            st.session_state.time = "6:00 PM"
            st.session_state.scene = 'level_2_A'
            st.rerun()
            
        if st.button("B. 🍬 【銀彈戰術】立刻派發包裝小蛋糕，分散小朋友注意力。"):
            st.session_state.energy -= 5
            st.session_state.trust += 15
            st.session_state.time = "6:00 PM"
            st.session_state.scene = 'level_2_B'
            st.rerun()
            
        if st.button("C. 🙋‍♂️ 【呼叫外援】叫旁邊的大專實習生去處理打架，你去接電話。"):
            # 引入機率：實習生有機會搞砸
            luck = random.randint(1, 10)
            if luck <= 3: # 30% 失敗機率
                st.session_state.scene = 'level_2_C_fail'
            else:
                st.session_state.scene = 'level_2_C_success'
            st.session_state.time = "6:00 PM"
            st.rerun()

    elif st.session_state.scene == 'level_2_A':
        st.subheader("結果：全場死寂")
        st.write("小朋友被你嚇哭了，家長在背後指指點點。電話那頭是主任打來問你做緊咩...")
        if st.button("🕒 捱到收工 ➡️"):
            st.session_state.scene = 'end_game'
            st.rerun()

    elif st.session_state.scene == 'level_2_B':
        st.subheader("結果：食物治百病")
        st.write("拿到蛋糕的小朋友瞬間安靜，陳太也順便拿了一個蛋糕，忘記了投訴冷氣。你優雅地接起電話。")
        if st.button("🕒 準備收工 ➡️"):
            st.session_state.scene = 'end_game'
            st.rerun()

    elif st.session_state.scene == 'level_2_C_success':
        st.subheader("結果：神仙隊友！")
        st.write("實習哥哥用變魔術的方式逗笑了小明和小華，完美解決危機！你安然無恙地處理了電話。")
        st.success("體力完全無扣，實習生真香！")
        if st.button("🕒 準備收工 ➡️"):
            st.session_state.scene = 'end_game'
            st.rerun()

    elif st.session_state.scene == 'level_2_C_fail':
        st.subheader("結果：實習生被搞哭了😭")
        st.write("實習哥哥不但沒勸服他們，反而被小明扔出的筆袋擊中，委屈地哭了。你不但要哄小孩，還要哄實習生！")
        st.error("壓力爆煲！體力 -30，信任度 -10")
        st.session_state.energy -= 30
        st.session_state.trust -= 10
        if st.button("🕒 崩潰地捱到收工 ➡️"):
            st.session_state.scene = 'end_game'
            st.rerun()

    # 【遊戲結算】
    elif st.session_state.scene == 'end_game':
        st.header("🎉 晚上 8:00，拉閘收工！")
        st.write("你成功活過了這一天！來看看你的年度績效考核：")
        
        score = st.session_state.energy + st.session_state.trust
        if score >= 150:
            st.balloons()
            st.success("🏆 評價：【社區客廳守護神】你不但精力充沛，還深受街坊愛戴，升職加薪指日可待！")
        elif score >= 100:
            st.info("👍 評價：【稱職的好社工】有驚無險地度過一天，明天請繼續努力。")
        else:
            st.warning("🥲 評價：【燃燒殆盡的打工仔】你看起來就像一條被吸乾靈魂的鹹魚，放假記得好好休息。")
            
        if st.button("🔄 明天再戰 (重新開始)"):
            reset_game()
            st.rerun()

    # ---------------- 死亡判定 ----------------
    if st.session_state.energy <= 0 and not st.session_state.scene.startswith('game_over'):
        st.session_state.scene = 'game_over_energy'
        st.rerun()
    if st.session_state.trust < 20 and not st.session_state.scene.startswith('game_over'):
        st.session_state.scene = 'game_over_trust'
        st.rerun()

    if st.session_state.scene == 'game_over_energy':
        st.error("💥 【GAME OVER】體力透支！你因為過勞暈倒在 pantry，被白車送往廣華醫院。")
        if st.button("🔄 重新開始"):
            reset_game()
            st.rerun()
            
    if st.session_state.scene == 'game_over_trust':
        st.error("💥 【GAME OVER】公關災難！街坊集體打上總辦事處投訴，主任把你叫進房間「照肺」兩小時。")
        if st.button("🔄 重新開始"):
            reset_game()
            st.rerun()
