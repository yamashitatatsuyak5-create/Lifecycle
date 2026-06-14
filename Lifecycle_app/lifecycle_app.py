import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, timedelta, time
import plotly.express as px

# スマホ画面設定
st.set_page_config(page_title="ライフログ", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 💅 アプリをかわいく、見やすくする魔法のCSS
# ==========================================
st.markdown("""
<style>
    /* 🌟 文字をくっきり濃く、背景は明るく清潔感のあるグレーに */
    .stApp {
        background-color: #F4F7F8;
        font-family: 'Helvetica Neue', 'Hiragino Kaku Gothic ProN', 'Meiryo', sans-serif;
    }
    
    /* 基本の文字色を全体的に「濃い黒」にして視認性MAXに！ */
    h1, h2, h3, h4, h5, h6, p, span, label, div {
        color: #1C1E21 !important; 
    }

    /* 上部の邪魔なメニューや余白を消してアプリっぽく */
    [data-testid="stHeader"] { visibility: hidden; }
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    /* 🌟 入力セル（時間、テキスト、カテゴリ）を超おしゃれに！ */
    div[data-baseweb="input"] > div, 
    div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        border: 2px solid #EAECEF !important;
        border-radius: 12px !important;
        padding: 2px 5px;
        transition: all 0.3s ease;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    
    /* 👆 入力セルをタップ（選択）した時に可愛くピンクに光る！ */
    div[data-baseweb="input"] > div:focus-within, 
    div[data-baseweb="select"] > div:focus-within {
        border-color: #FFB6C1 !important; 
        box-shadow: 0 0 8px rgba(255, 182, 193, 0.6) !important;
    }
    
    /* 🌟 データ一覧の表（セル）も、おしゃれなカード風に！ */
    [data-testid="stDataFrame"] {
        background-color: #FFFFFF;
        border: 2px solid #EAECEF;
        border-radius: 15px;
        padding: 5px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.03);
    }
    
    /* 🌟 ボタンの角丸と立体感 */
    div.stButton > button {
        border-radius: 20px !important;
        font-weight: bold !important;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.08);
        transition: all 0.2s ease-in-out;
        background-color: #FFFFFF !important;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.12);
    }
    div.stButton > button:active {
        transform: translateY(1px);
    }
    
    /* 目立つボタン（スタート等）は白文字がくっきり見える濃いめのピンクに！ */
    div.stButton > button[kind="primary"] {
        background-color: #FF69B4 !important; 
        color: #FFFFFF !important;
    }
    
    /* 🌟 タブのスタイル（選択中のタブをくっきり太字に） */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 15px 15px 0 0 !important;
        background-color: #EAECEF;
        padding: 10px 15px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        border-bottom: 4px solid #FF69B4 !important;
        color: #1C1E21 !important;
        font-weight: 900 !important;
    }
    
    /* メッセージボックスを角丸に */
    .stAlert { border-radius: 15px; border: none; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

DATA_FILE = "timeline_data.csv"
ROUTINE_FILE = "timeline_routine.csv"
TRACKING_FILE = "timeline_tracking.json"

CATEGORIES = ["睡眠 🛌", "大学（講義・研究） 📝", "自主学習 ✏️", "バイト 💼", "移動・通学 🚶", "趣味・娯楽 🎮", "食事・生活 🍳", "その他 💬"]
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

# グラフ用のパステルカラー設定
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

st.markdown(f"<div style='text-align: center; font-size: 0.95rem; font-weight: bold; margin-bottom: 10px;'>{date_str} ({current_weekday}) のスケジュール</div>", unsafe_allow_html=True)

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
        fig.update_layout(
            xaxis=dict(tickformat="%H:%M", title="", range=[start_of_day, end_of_day], dtick=14400000, fixedrange=True, tickfont=dict(color="#555", weight="bold")),
            yaxis=dict(title="", showticklabels=False, fixedrange=True),
            showlegend=False, dragmode=False, margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        st.warning("この日の記録はまだありません 🌱")
else:
    st.info("まずは下のメニューから記録を追加してみましょう！ 🎈")

st.markdown("---")

# ==========================================
# 📝 入力・編集エリア（タブ）
# ==========================================
tab_timer, tab_manual, tab_routine, tab_data = st.tabs(["⏱️ 計測", "📝 追加", "⚙️ 固定", "📜 編集"])

with tab_timer:
    if current_start is None:
        rt_cat = st.selectbox("カテゴリを選ぶ", CATEGORIES, key="rt_cat")
        if st.button("▶️ 今からスタート！", type="primary", use_container_width=True):
            set_tracking_state(rt_cat, datetime.now())
            st.rerun()
    else:
        st.success(f"⏳ 現在 **{current_cat}** を計測中です！\n\n開始: {current_start.strftime('%H:%M')}")
        rt_detail = st.text_input("メモ（任意）", key="rt_detail")
        
        if st.button("⏹️ 今終わった！（記録）", type="primary", use_container_width=True):
            end_dt = datetime.now()
            start_str = current_start.strftime("%H:%M")
            end_str = end_dt.strftime("%H:%M")
            record_date_str = current_start.strftime("%Y-%m-%d") 
            
            is_overlap, overlap_cat = check_overlap(record_date_str, start_str, end_str, st.session_state.df_log)
            if is_overlap:
                st.error(f"⚠️ すでに「{overlap_cat}」と重なっています。")
                clear_tracking_state()
            else:
                new_row = pd.DataFrame([{"日付": record_date_str, "開始時刻": start_str, "終了時刻": end_str, "カテゴリ": current_cat, "内容": rt_detail if rt_detail else "（未入力）"}])
                st.session_state.df_log = pd.concat([st.session_state.df_log, new_row], ignore_index=True)
                save_data(st.session_state.df_log, DATA_FILE)
                clear_tracking_state()
                st.rerun()
                
        if st.button("❌ キャンセル", use_container_width=True):
            clear_tracking_state()
            st.rerun()

with tab_manual:
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

with tab_routine:
    st.write("曜日ごとの決まった予定を登録できます。")
    edited_routine = st.data_editor(
        st.session_state.df_routine,
        column_config={
            "曜日": st.column_config.SelectboxColumn("曜日", options=WEEKDAYS, required=True),
            "開始時刻": st.column_config.TimeColumn("開始", format="HH:mm", required=True),
            "終了時刻": st.column_config.TimeColumn("終了", format="HH:mm", required=True),
            "カテゴリ": st.column_config.SelectboxColumn("カテゴリ", options=CATEGORIES, required=True),
            "内容": st.column_config.TextColumn("内容")
        },
        num_rows="dynamic", use_container_width=True
    )
    if not edited_routine.equals(st.session_state.df_routine):
        st.session_state.df_routine = edited_routine
        save_data(edited_routine, ROUTINE_FILE)
        st.rerun()

with tab_data:
    if not st.session_state.df_log.empty:
        df_edit_target = st.session_state.df_log[st.session_state.df_log["日付"] == date_str]
        display_df = df_edit_target[["開始時刻", "終了時刻", "カテゴリ", "内容"]]
        edited_df = st.data_editor(display_df, num_rows="dynamic", use_container_width=True, key="data_editor")
        if not edited_df.equals(display_df):
            df_others = st.session_state.df_log[st.session_state.df_log["日付"] != date_str]
            edited_df["日付"] = date_str
            st.session_state.df_log = pd.concat([df_others, edited_df], ignore_index=True)
            save_data(st.session_state.df_log, DATA_FILE)
            st.rerun()
    else:
        st.write("データがありません。")