import streamlit as st
import time

st.set_page_config(page_title="旺角社區客廳生存戰", page_icon="🏢", layout="centered")

# ==========================================
# 1. 遊戲初始化 (設定初始數值與場景)
# ==========================================
if 'scene' not in st.session_state:
    st.session_state.scene = 'start'
    st.session_state.energy = 100
    st.session_state.trust = 50

# 重新開始遊戲的函數
def reset_game():
    st.session_state.scene = 'start'
    st.session_state.energy = 100
    st.session_state.trust = 50

# ==========================================
# 2. UI 介面：顯示玩家狀態列
# ==========================================
st.title("🏢 旺角社區客廳：前線社工生存戰")
st.markdown("---")

# 只有在進入遊戲後才顯示數值條
if st.session_state.scene != 'start':
    col1, col2 = st.columns(2)
    with col1:
        st.progress(st.session_state.energy / 100, text=f"🔋 你的體力值：{st.session_state.energy}/100")
    with col2:
        st.progress(st.session_state.trust / 100, text=f"❤️ 街坊信任度：{st.session_state.trust}/100")
    st.markdown("---")

# ==========================================
# 3. 遊戲場景與劇本邏輯
# ==========================================

# 【場景：遊戲首頁】
if st.session_state.scene == 'start':
    st.header("歡迎來到旺角社區客廳！")
    st.write("作為這裡的前線社工，你每天都要面對街坊們大大小小的需求與突發狀況。")
    st.write("你的目標是：在**體力耗盡**或**被街坊投訴到崩潰**之前，平安度過這一天！")
    
    if st.button("🚀 開始今天的當值", type="primary"):
        st.session_state.scene = 'level_1'
        st.rerun()

# 【場景：第一關 - 洗衣機保衛戰】
elif st.session_state.scene == 'level_1':
    st.header("第一關：洗衣房的戰火 🧺")
    st.write("早上 11:00，社區客廳剛開門。你剛踏入中心，就聽到洗衣房傳來激烈的爭吵聲。")
    st.info("🗣️ **陳師奶**：「我個洗衣籃 10 點半就擺喺度排隊啦！梗係我洗先！」\n\n🗣️ **黃阿姨**：「我有打電話預約 11 點 3 個字㗎！而且我下晝要趕去廣華醫院覆診，你俾我洗先啦！」")
    st.write("旁邊已經有幾個街坊在看熱鬧，大家都在等著看你這位當值社工怎麼處理。")
    
    st.markdown("### 你決定怎麼做？")
    
    if st.button("A. 📋 鐵面無私：拿出平板核對預約紀錄，嚴格按中心規矩辦事。"):
        st.session_state.energy -= 10
        st.session_state.scene = 'level_1_result_A'
        st.rerun()
        
    if st.button("B. 🤝 動之以情：運用輔導技巧，私下勸陳師奶體諒黃阿姨覆診的急需。"):
        st.session_state.energy -= 20
        st.session_state.scene = 'level_1_result_B'
        st.rerun()
        
    if st.button("C. 🛑 冷處理：廣播宣佈「因發生爭執，洗衣機暫停使用15分鐘讓大家冷靜」。"):
        st.session_state.energy -= 5
        st.session_state.scene = 'level_1_result_C'
        st.rerun()

# 【場景：第一關結局 A】
elif st.session_state.scene == 'level_1_result_A':
    st.subheader("結果：公事公辦")
    st.write("你查閱了紀錄，證實黃阿姨確實有預約。你向陳師奶解釋中心的「預約優先」政策。")
    st.write("陳師奶雖然碎碎念了幾句「規矩死板」，但還是悻悻然地把洗衣籃拿走。旁邊的街坊覺得你處事公平，沒有偏私。")
    st.success("體力 -10 (應對壓力)。街坊信任度 +10 (處事公平)。")
    if st.button("繼續下一關 ➡️"):
        st.session_state.trust = min(100, st.session_state.trust + 10)
        st.session_state.scene = 'level_2_intro'
        st.rerun()

# 【場景：第一關結局 B】
elif st.session_state.scene == 'level_1_result_B':
    st.subheader("結果：社工魂爆發")
    st.write("你花了九牛二虎之力，耐心地安撫陳師奶的情緒，並答應下午幫她預留另一個黃金時段。")
    st.write("陳師奶最終被你的誠意打動，大方地讓給黃阿姨。兩人和好如初，中心氣氛變得非常融洽！")
    st.success("體力 -20 (說太多話口乾舌燥)。街坊信任度 +25 (展現極佳的同理心與人情味)！")
    if st.button("繼續下一關 ➡️"):
        st.session_state.trust = min(100, st.session_state.trust + 25)
        st.session_state.scene = 'level_2_intro'
        st.rerun()

# 【場景：第一關結局 C】
elif st.session_state.scene == 'level_1_result_C':
    st.subheader("結果：得罪全街坊")
    st.write("你的廣播一出，洗衣房瞬間安靜。但隨之而來的是全場的抱怨聲！")
    st.write("「搞錯啊，佢哋鬧交關我哋咩事？」「社工大哂啊？」結果不僅那兩位不開心，連後面排隊的街坊也跟著遭殃。")
    st.error("體力 -5 (迅速解決)。街坊信任度 -20 (引發群眾公憤)。")
    if st.button("繼續下一關 ➡️"):
        st.session_state.trust -= 20
        st.session_state.scene = 'level_2_intro'
        st.rerun()

# 【場景：準備進入第二關 (待開發)】
elif st.session_state.scene == 'level_2_intro':
    st.header("第一危機解除，但考驗才剛開始...")
    st.write("你喝了一口水，剛準備坐下看 Email，突然看見幾個小朋友在圖書角開始玩起了「扔書大戰」...")
    st.info("🚧 遊戲開發中：第二關劇本敬請期待！")
    
    if st.button("🔄 重新挑戰第一關"):
        reset_game()
        st.rerun()

# ==========================================
# 4. 遊戲結束判定 (Game Over)
# ==========================================
if st.session_state.energy <= 0:
    st.error("💥 體力透支！你暈倒在辦公室，被送往醫院。遊戲結束。")
    if st.button("🔄 重新開始"):
        reset_game()
        st.rerun()

if st.session_state.trust < 20:
    st.error("💥 投訴信如雪片般飛來！中心主任把你叫進房間「照肺」。遊戲結束。")
    if st.button("🔄 重新開始"):
        reset_game()
        st.rerun()
