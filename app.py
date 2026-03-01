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
st.sidebar.subheader("⏮️
