import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, timedelta, time
import plotly.express as px

# スマホ画面設定
st.set_page_config(page_title="ライフログ", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 💅 スマホに特化した見やすいデザイン（CSS）
# ==========================================
st.markdown("""
<style>
    .stApp {
        background-color: #F4F7F8;
        font-family: 'Helvetica Neue', 'Hiragino Kaku Gothic ProN', 'Meiryo', sans-serif;
    }
    h1, h2, h3, h4, h5, h6, p, span, label, div { color: #1C1E21 !important; }
    [data-testid="stHeader"] { visibility: hidden; }
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    /* 入力セルをおしゃれに */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        border: 2px solid #EAECEF !important;
        border-radius: 12px !important;
        padding: 2px 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within {
        border-color: #FFB6C1 !important; 
        box-shadow: 0 0 8px rgba(255, 182, 193, 0.6) !important;
    }
    
    /* ボタンの角丸と立体感 */
    div.stButton > button {
        border-radius: 20px !important;
        font-weight: bold !important;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.08);
        background-color: #FFFFFF !important;
        transition: all 0.2s ease;
    }
    div.stButton > button:active { transform: translateY(2px); }
    div.stButton > button[kind="primary"] {
        background-color: #FF69B4 !important; 
        color: #FFFFFF !important;
    }
    
    /* カード風のリスト表示用 */
    .list-card {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #EAECEF;
    }
</style>
""", unsafe_allow_html=True)

DATA_FILE = "timeline_data.csv"
ROUTINE_FILE = "timeline_routine.csv"
TRACKING_FILE = "timeline_tracking.json"

CATEGORIES = ["睡眠 🛌", "大学（講義・研究） 📝", "自主学習 ✏️", "バイト 💼", "移動・通学 🚶", "趣味・娯楽 🎮", "食事・生活 🍳", "その他 💬"]
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
CUTE_COLORS = {
    "睡眠 🛌": "#B3E5FC", "大学（講義・研究） 📝": "#C8E6C9", "自主学習 ✏️": "#FFF59D", 
    "バイト 💼": "#FFE0B2", "移動・通学 🚶": "#E1BEE7", "趣味・娯楽 🎮": "#FFCDD2", 
    "食事・生活 🍳": "#F8BBD0", "その他 💬": "#CFD8DC"
}

def load_data(file_path, default_columns):
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if "日付" in df.columns: df["日付"] = df["日付"].astype(str)
        return df
    return pd.DataFrame(columns=default_columns)

def save_data(df, file_path):
    df.to_csv(file_path, index=False, encoding="utf-8-sig")

if "df_log" not in st.session_state: st.session_state.df_log = load_data(DATA_FILE, ["日付", "開始時刻", "終了時刻", "カテゴリ", "内容"])
if "df_routine" not in st.session_state: st.session_state.df_routine = load_data(ROUTINE_FILE, ["曜日", "開始時刻", "終了時刻", "カテゴリ", "内容"])
if "target_date" not in st.session_state: st.session_state.target_date = datetime.now().date()

def get_tracking_state():
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["category"], datetime.fromisoformat(data["start_time"])
    return None, None

def set_tracking_state(category, start_time):
    with open(TRACKING_FILE, "w", encoding="utf-8") as f:
        json.dump({"category": category, "start_time": start_time.isoformat()}, f)

def clear_tracking_state():
    if os.path.exists(TRACKING_FILE): os.remove(TRACKING_FILE)

def check_overlap(date_str, start_str, end_str, df_log):
    if df_log.empty: return False, None
    new_start = pd.to_datetime(f"{date_str} {start_str}")
    new_end = pd.to_datetime(f"{date_str} {end_str}")
    if new_end <= new_start: new_end += pd.Timedelta(days=1)
        
    df_check = df_log.copy()
    df_check["Start_dt"] = pd.to_datetime(df_check["日付"] + " " + df_check["開始時刻"])
    df_check["End_dt"] = pd.to_datetime(df_check["日付"] + " " + df_check["終了時刻"])
    mask = df_check["End_dt"] < df_check["Start_dt"]
    df_check.loc[mask, "End_dt"] += pd.Timedelta(days=1)
    
    overlap = df_check[(new_start < df_check["End_dt"]) & (new_end > df_check["Start_dt"])]
    if not overlap.empty: return True, overlap.iloc[0]["カテゴリ"]
    return False, None

# 💡 新機能：時間を15分単位に自動で丸める（四捨五入）関数
def round_to_15(dt):
    discard = timedelta(minutes=dt.minute % 15, seconds=dt.second, microseconds=dt.microsecond)
    dt -= discard
    # 余りが7分30秒以上なら切り上げ（次の15分へ）、それ未満なら切り捨て
    if discard >= timedelta(minutes=7, seconds=30):
        dt += timedelta(minutes=15)
    return dt

# ==========================================
# 🗓️ 画面上部：メイン・カレンダーナビゲーション
# ==========================================
st.markdown("<h2 style='text-align: center; font-size: 1.5rem; margin-bottom: 0;'>🧸 ライフログ</h2>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    if st.button("◀ 前日", use_container_width=True):
        st.session_state.target_date -= timedelta(days=1)
        st.rerun()
with c2:
    selected_date = st.date_input("日付", st.session_state.target_date, label_visibility="collapsed")
    if selected_date != st.session_state.target_date:
        st.session_state.target_date = selected_date
        st.rerun()
with c3:
    if st.button("翌日 ▶", use_container_width=True):
        st.session_state.target_date += timedelta(days=1)
        st.rerun()

date_str = st.session_state.target_date.strftime("%Y-%m-%d")
current_weekday = WEEKDAYS[st.session_state.target_date.weekday()]
st.markdown(f"<div style='text-align: center; font-size: 0.95rem; font-weight: bold; margin-bottom: 10px;'>{date_str} ({current_weekday})</div>", unsafe_allow_html=True)

current_cat, current_start = get_tracking_state()

# ==========================================
# 📊 タイムライン・グラフエリア
# ==========================================
if not st.session_state.df_log.empty:
    df = st.session_state.df_log.copy()
    df["Start_dt"] = pd.to_datetime(df["日付"] + " " + df["開始時刻"])
    df["End_dt"] = pd.to_datetime(df["日付"] + " " + df["終了時刻"])
    df.loc[df["End_dt"] < df["Start_dt"], "End_dt"] += pd.Timedelta(days=1)
    df["時間（h）"] = (df["End_dt"] - df["Start_dt"]).dt.total_seconds() / 3600.0
    
    df_day = df[df["日付"] == date_str].copy()
    start_of_day = pd.to_datetime(f"{date_str} 00:00:00")
    end_of_day = start_of_day + pd.Timedelta(days=1)
    
    if not df_day.empty:
        fig = px.timeline(
            df_day, x_start="Start_dt", x_end="End_dt", y="日付", color="カテゴリ", 
            text="カテゴリ", hover_name="内容", height=130, color_discrete_map=CUTE_COLORS
        )
        fig.update_traces(textposition='inside', insidetextanchor='middle', textfont_color="#333", marker_line_width=0)
        fig.update_layout(
            xaxis=dict(tickformat="%H:%M", title="", range=[start_of_day, end_of_day], dtick=14400000, fixedrange=True, tickfont=dict(color="#555", weight="bold")),
            yaxis=dict(title="", showticklabels=False, fixedrange=True),
            showlegend=False, dragmode=False, margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        day_total = df_day["時間（h）"].sum()
        st.info(f"✨ 記録済み: {round(day_total, 1)} 時間 （空き: {round(24.0 - day_total, 1)} 時間）")
    else:
        empty_df = pd.DataFrame({"日付": [date_str], "Start_dt": [start_of_day], "End_dt": [start_of_day], "カテゴリ": ["未記録"]})
        fig = px.timeline(empty_df, x_start="Start_dt", x_end="End_dt", y="日付", height=130)
        fig.update_layout(xaxis=dict(tickformat="%H:%M", title="", range=[start_of_day, end_of_day], dtick=14400000, fixedrange=True), yaxis=dict(title="", showticklabels=False, fixedrange=True), showlegend=False, dragmode=False, margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
else:
    st.info("まずは下のメニューから記録を追加してみましょう！ 🎈")

st.markdown("---")

# ==========================================
# 📱 モード切り替え（画面切り替えで広く使う！）
# ==========================================
# タブをやめて、スマホで押しやすいラジオボタン式の「メニュー」にしました
mode = st.radio("メニュー", ["⏱️ 計測", "📝 追加", "⚙️ ルーティン", "📜 削除"], horizontal=True, label_visibility="collapsed")
st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------
# ⏱️ 計測モード
# ----------------------------
if mode == "⏱️ 計測":
    if current_start is None:
        rt_cat = st.selectbox("カテゴリを選ぶ", CATEGORIES, key="rt_cat")
        if st.button("▶️ 今からスタート！", type="primary", use_container_width=True):
            set_tracking_state(rt_cat, datetime.now())
            st.rerun()
    else:
        st.success(f"⏳ 現在 **{current_cat}** を計測中です！\n\n実際の開始: {current_start.strftime('%H:%M')}")
        rt_detail = st.text_input("メモ（任意）", key="rt_detail")
        
        if st.button("⏹️ 今終わった！（15分単位で記録）", type="primary", use_container_width=True):
            # 💡 開始時刻と終了時刻をそれぞれ15分単位に丸める
            end_dt = datetime.now()
            start_rounded = round_to_15(current_start)
            end_rounded = round_to_15(end_dt)
            
            # もし丸めた結果、開始と終了が同じ時間になってしまったら、最低15分として記録する
            if start_rounded == end_rounded:
                end_rounded += timedelta(minutes=15)
                
            start_str = start_rounded.strftime('%H:%M')
            end_str = end_rounded.strftime('%H:%M')
            record_date_str = start_rounded.strftime('%Y-%m-%d') 
            
            is_overlap, overlap_cat = check_overlap(record_date_str, start_str, end_str, st.session_state.df_log)
            if is_overlap:
                st.error(f"⚠️ 丸められた時間（{start_str}〜{end_str}）が、すでに「{overlap_cat}」と重なっています。手動で追加してください。")
                clear_tracking_state()
            else:
                new_row = pd.DataFrame([{"日付": record_date_str, "開始時刻": start_str, "終了時刻": end_str, "カテゴリ": current_cat, "内容": rt_detail if rt_detail else "（未入力）"}])
                st.session_state.df_log = pd.concat([st.session_state.df_log, new_row], ignore_index=True)
                save_data(st.session_state.df_log, DATA_FILE)
                clear_tracking_state()
                st.success(f"丸め処理を行い {start_str} 〜 {end_str} で記録しました！")
                st.rerun()
                
        if st.button("❌ 計測をキャンセル", use_container_width=True):
            clear_tracking_state()
            st.rerun()

# ----------------------------
# 📝 追加モード
# ----------------------------
elif mode == "📝 追加":
    category = st.selectbox("カテゴリ", CATEGORIES, key="man_cat")
    col3, col4 = st.columns(2)
    with col3: start_time = st.time_input("開始", time(9, 0))
    with col4: end_time = st.time_input("終了", time(10, 0))
    detail = st.text_input("メモ", key="man_detail")
    
    if st.button("手動で追加する", use_container_width=True):
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")
        if start_str == end_str: st.warning("開始と終了が同じです。")
        else:
            is_overlap, overlap_cat = check_overlap(date_str, start_str, end_str, st.session_state.df_log)
            if is_overlap: st.error(f"⚠️ すでに「{overlap_cat}」が入っています！")
            else:
                new_row = pd.DataFrame([{"日付": date_str, "開始時刻": start_str, "終了時刻": end_str, "カテゴリ": category, "内容": detail if detail else "（未入力）"}])
                st.session_state.df_log = pd.concat([st.session_state.df_log, new_row], ignore_index=True)
                save_data(st.session_state.df_log, DATA_FILE)
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(f"✨ {current_weekday}曜日のルーティンを一括追加", use_container_width=True):
        routine_for_day = st.session_state.df_routine[st.session_state.df_routine["曜日"] == current_weekday]
        if routine_for_day.empty: st.warning("ルーティンが設定されていません。")
        else:
            success_count = 0
            new_rows = []
            for _, row in routine_for_day.iterrows():
                is_overlap, _ = check_overlap(date_str, row["開始時刻"], row["終了時刻"], st.session_state.df_log)
                if not is_overlap:
                    new_rows.append({"日付": date_str, "開始時刻": row["開始時刻"], "終了時刻": row["終了時刻"], "カテゴリ": row["カテゴリ"], "内容": row["内容"]})
                    success_count += 1
            if new_rows:
                st.session_state.df_log = pd.concat([st.session_state.df_log, pd.DataFrame(new_rows)], ignore_index=True)
                save_data(st.session_state.df_log, DATA_FILE)
                st.rerun()

# ----------------------------
# ⚙️ 固定ルーティン（追加・削除）モード
# ----------------------------
elif mode == "⚙️ ルーティン":
    st.markdown("#### 新規追加")
    r_col1, r_col2 = st.columns(2)
    with r_col1: r_day = st.selectbox("曜日", WEEKDAYS)
    with r_col2: r_cat = st.selectbox("カテゴリ", CATEGORIES)
    r_col3, r_col4 = st.columns(2)
    with r_col3: r_start = st.time_input("開始", time(9,0), key="r_start")
    with r_col4: r_end = st.time_input("終了", time(10,0), key="r_end")
    r_detail = st.text_input("メモ（任意）", key="r_detail")
    
    if st.button("➕ ルーティンを追加", use_container_width=True):
        new_routine = pd.DataFrame([{"曜日": r_day, "開始時刻": r_start.strftime("%H:%M"), "終了時刻": r_end.strftime("%H:%M"), "カテゴリ": r_cat, "内容": r_detail if r_detail else "（未入力）"}])
        st.session_state.df_routine = pd.concat([st.session_state.df_routine, new_routine], ignore_index=True)
        save_data(st.session_state.df_routine, ROUTINE_FILE)
        st.success("追加しました！")
        st.rerun()

    st.markdown("#### 登録済みルーティン一覧")
    if st.session_state.df_routine.empty:
        st.write("まだ登録されていません。")
    else:
        # 💡 スマホで操作しやすい「カード型」のリスト表示！
        for idx, row in st.session_state.df_routine.iterrows():
            st.markdown(f"<div class='list-card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{row['曜日']}** | {row['開始時刻']}〜{row['終了時刻']}")
                st.markdown(f"**{row['カテゴリ']}** {row['内容']}")
            with c2:
                # 押しやすい大きなゴミ箱ボタン！
                if st.button("🗑️", key=f"del_r_{idx}", use_container_width=True):
                    st.session_state.df_routine = st.session_state.df_routine.drop(idx).reset_index(drop=True)
                    save_data(st.session_state.df_routine, ROUTINE_FILE)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# 📜 削除（今日の記録）モード
# ----------------------------
elif mode == "📜 削除":
    st.markdown("#### 今日の記録一覧")
    st.info("時間を修正したい場合は、一度ここで削除してから「📝 追加」タブで新しく入れ直してください。")
    
    if not st.session_state.df_log.empty:
        df_edit_target = st.session_state.df_log[st.session_state.df_log["日付"] == date_str]
        
        if df_edit_target.empty:
            st.write("今日の記録はありません。")
        else:
            for idx, row in df_edit_target.iterrows():
                st.markdown(f"<div class='list-card'>", unsafe_allow_html=True)
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{row['開始時刻']} 〜 {row['終了時刻']}**")
                    st.markdown(f"**{row['カテゴリ']}** <small>{row['内容']}</small>", unsafe_allow_html=True)
                with c2:
                    if st.button("🗑️", key=f"del_l_{idx}", use_container_width=True):
                        st.session_state.df_log = st.session_state.df_log.drop(idx).reset_index(drop=True)
                        save_data(st.session_state.df_log, DATA_FILE)
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.write("データがありません。")
