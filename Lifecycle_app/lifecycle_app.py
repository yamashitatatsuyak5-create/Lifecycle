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
    .stApp { background-color: #F4F7F8; font-family: 'Helvetica Neue', sans-serif; }
    h1, h2, h3, h4, h5, h6, p, span, label, div { color: #1C1E21 !important; }
    [data-testid="stHeader"] { visibility: hidden; }
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important; border: 2px solid #EAECEF !important;
        border-radius: 12px !important; padding: 2px 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within {
        border-color: #FFB6C1 !important; box-shadow: 0 0 8px rgba(255, 182, 193, 0.6) !important;
    }
    
    div.stButton > button {
        border-radius: 20px !important; font-weight: bold !important; padding: 10px 0 !important; 
        border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.08); background-color: #FFFFFF !important; transition: all 0.2s ease;
    }
    div.stButton > button:active { transform: translateY(2px); }
    div.stButton > button[kind="primary"] { background-color: #FF69B4 !important; color: #FFFFFF !important; }
    
    .list-card {
        background-color: #FFFFFF; padding: 15px; border-radius: 15px; margin-bottom: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #EAECEF;
    }
</style>
""", unsafe_allow_html=True)

# --- 保存ファイル ---
DATA_FILE = "timeline_data.csv"
ROUTINE_FILE = "timeline_routine.csv"
TRACKING_FILE = "timeline_tracking.json"
CATEGORIES_FILE = "timeline_categories.json" # 💡 新規：カテゴリ保存用

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
DEFAULT_CATEGORIES = ["睡眠 🛌", "大学（講義・研究） 📝", "自主学習 ✏️", "バイト 💼", "移動・通学 🚶", "趣味・娯楽 🎮", "食事・生活 🍳", "その他 💬"]

# 💡 カテゴリを自動で可愛く色分けするためのカラーパレット（無限に使い回せます）
PASTEL_PALETTE = [
    "#B3E5FC", "#C8E6C9", "#FFF59D", "#FFE0B2", "#E1BEE7", 
    "#FFCDD2", "#F8BBD0", "#CFD8DC", "#D7CCC8", "#FFE082", 
    "#80DEEA", "#A5D6A7", "#CE93D8", "#F48FB1", "#90CAF9"
]

# --- データの読み書き関数 ---
def load_categories():
    if os.path.exists(CATEGORIES_FILE):
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CATEGORIES.copy()

def save_categories(cats):
    with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cats, f, ensure_ascii=False)

def load_data(file_path, default_columns):
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if "日付" in df.columns: df["日付"] = df["日付"].astype(str)
        return df
    return pd.DataFrame(columns=default_columns)

def save_data(df, file_path):
    df.to_csv(file_path, index=False, encoding="utf-8-sig")

# --- セッションステート初期化 ---
if "categories" not in st.session_state: st.session_state.categories = load_categories()
if "df_log" not in st.session_state: st.session_state.df_log = load_data(DATA_FILE, ["日付", "開始時刻", "終了時刻", "カテゴリ", "内容"])
if "df_routine" not in st.session_state: st.session_state.df_routine = load_data(ROUTINE_FILE, ["曜日", "開始時刻", "終了時刻", "カテゴリ", "内容"])
if "target_date" not in st.session_state: st.session_state.target_date = datetime.now().date()
if "app_mode" not in st.session_state: st.session_state.app_mode = "⏱️ 計測"

# 💡 現在のカテゴリリストに合わせて動的にカラーマップを作成
dynamic_colors = {cat: PASTEL_PALETTE[i % len(PASTEL_PALETTE)] for i, cat in enumerate(st.session_state.categories)}

# --- ストップウォッチ・重複チェック関数 ---
def get_tracking_state():
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["category"], datetime.fromisoformat(data["start_time"])
    return None, None

def set_tracking_state(category, start_time):
    with open(TRACKING_FILE, "w", encoding="utf-8") as f: json.dump({"category": category, "start_time": start_time.isoformat()}, f)

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

def round_to_15(dt):
    discard = timedelta(minutes=dt.minute % 15, seconds=dt.second, microseconds=dt.microsecond)
    dt -= discard
    if discard >= timedelta(minutes=7, seconds=30): dt += timedelta(minutes=15)
    return dt

# ==========================================
# 🗓️ 画面上部：メイン・カレンダー
# ==========================================
st.markdown("<h2 style='text-align: center; font-size: 1.5rem; margin-bottom: 0;'>🧸 ライフログ</h2>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    if st.button("◀ 前日", use_container_width=True):
        st.session_state.target_date -= timedelta(days=1); st.rerun()
with c2:
    selected_date = st.date_input("日付", st.session_state.target_date, label_visibility="collapsed")
    if selected_date != st.session_state.target_date:
        st.session_state.target_date = selected_date; st.rerun()
with c3:
    if st.button("翌日 ▶", use_container_width=True):
        st.session_state.target_date += timedelta(days=1); st.rerun()

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
            text="カテゴリ", hover_name="内容", height=130, color_discrete_map=dynamic_colors # 💡 動的カラーマップを使用
        )
        fig.update_traces(textposition='inside', insidetextanchor='middle', textfont_color="#333", marker_line_width=0)
        fig.update_layout(
            xaxis=dict(tickformat="%H:%M", title="", range=[start_of_day, end_of_day], dtick=14400000, fixedrange=True, tickfont=dict(color="#555", weight="bold")),
            yaxis=dict(title="", showticklabels=False, fixedrange=True),
            showlegend=False, dragmode=False, margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
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
# 📱 6つの特大ボタン・メニュー
# ==========================================
def change_mode(new_mode): st.session_state.app_mode = new_mode

m1, m2, m3 = st.columns(3)
with m1:
    if st.button("⏱️ 計測", type="primary" if st.session_state.app_mode == "⏱️ 計測" else "secondary", use_container_width=True): change_mode("⏱️ 計測"); st.rerun()
with m2:
    if st.button("📝 追加", type="primary" if st.session_state.app_mode == "📝 追加" else "secondary", use_container_width=True): change_mode("📝 追加"); st.rerun()
with m3:
    if st.button("📊 分析", type="primary" if st.session_state.app_mode == "📊 分析" else "secondary", use_container_width=True): change_mode("📊 分析"); st.rerun()

# 💡 新機能「🏷️ カテゴリ」を追加し、2段目も綺麗に3つに揃えました！
m4, m5, m6 = st.columns(3)
with m4:
    if st.button("⚙️ 固定", type="primary" if st.session_state.app_mode == "⚙️ 固定" else "secondary", use_container_width=True): change_mode("⚙️ 固定"); st.rerun()
with m5:
    if st.button("📜 削除", type="primary" if st.session_state.app_mode == "📜 削除" else "secondary", use_container_width=True): change_mode("📜 削除"); st.rerun()
with m6:
    if st.button("🏷️ カテゴリ", type="primary" if st.session_state.app_mode == "🏷️ カテゴリ" else "secondary", use_container_width=True): change_mode("🏷️ カテゴリ"); st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
mode = st.session_state.app_mode

# ----------------------------
# ⏱️ 計測モード
# ----------------------------
if mode == "⏱️ 計測":
    if current_start is None:
        if not st.session_state.categories:
            st.warning("カテゴリがありません。「🏷️ カテゴリ」から追加してください。")
        else:
            rt_cat = st.selectbox("カテゴリを選ぶ", st.session_state.categories, key="rt_cat")
            if st.button("▶️ 今からスタート！", type="primary", use_container_width=True):
                set_tracking_state(rt_cat, datetime.now())
                st.rerun()
    else:
        st.success(f"⏳ 現在 **{current_cat}** を計測中です！\n\n実際の開始: {current_start.strftime('%H:%M')}")
        rt_detail = st.text_input("メモ（任意）", key="rt_detail")
        
        if st.button("⏹️ 今終わった！（15分単位で記録）", type="primary", use_container_width=True):
            end_dt = datetime.now()
            start_rounded = round_to_15(current_start)
            end_rounded = round_to_15(end_dt)
            if start_rounded == end_rounded: end_rounded += timedelta(minutes=15)
                
            start_str = start_rounded.strftime('%H:%M')
            end_str = end_rounded.strftime('%H:%M')
            record_date_str = start_rounded.strftime('%Y-%m-%d') 
            
            is_overlap, overlap_cat = check_overlap(record_date_str, start_str, end_str, st.session_state.df_log)
            if is_overlap:
                st.error(f"⚠️ 丸められた時間が「{overlap_cat}」と重なっています。手動で追加してください。")
                clear_tracking_state()
            else:
                new_row = pd.DataFrame([{"日付": record_date_str, "開始時刻": start_str, "終了時刻": end_str, "カテゴリ": current_cat, "内容": rt_detail if rt_detail else "（未入力）"}])
                st.session_state.df_log = pd.concat([st.session_state.df_log, new_row], ignore_index=True)
                save_data(st.session_state.df_log, DATA_FILE)
                clear_tracking_state()
                st.success(f"{start_str} 〜 {end_str} で記録しました！")
                st.rerun()
                
        if st.button("❌ 計測をキャンセル", use_container_width=True):
            clear_tracking_state()
            st.rerun()

# ----------------------------
# 📝 追加モード
# ----------------------------
elif mode == "📝 追加":
    if not st.session_state.categories:
        st.warning("カテゴリがありません。「🏷️ カテゴリ」から追加してください。")
    else:
        category = st.selectbox("カテゴリ", st.session_state.categories, key="man_cat")
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
# 📊 分析モード
# ----------------------------
elif mode == "📊 分析":
    st.markdown("#### 時間の使い方のバランス")
    period = st.selectbox("分析する期間", ["過去7日間", "過去30日間", "全期間", "今日"])
    
    if not st.session_state.df_log.empty:
        df_analysis = st.session_state.df_log.copy()
        df_analysis["Date_obj"] = pd.to_datetime(df_analysis["日付"]).dt.date
        today = datetime.now().date()
        
        if period == "今日": df_filtered = df_analysis[df_analysis["Date_obj"] == today]
        elif period == "過去7日間": df_filtered = df_analysis[df_analysis["Date_obj"] >= (today - timedelta(days=6))]
        elif period == "過去30日間": df_filtered = df_analysis[df_analysis["Date_obj"] >= (today - timedelta(days=29))]
        else: df_filtered = df_analysis
            
        if not df_filtered.empty:
            sum_df = df_filtered.groupby("カテゴリ")["時間（h）"].sum().reset_index()
            total_hours = round(sum_df["時間（h）"].sum(), 1)
            
            fig_pie = px.pie(
                sum_df, values='時間（h）', names='カテゴリ', color='カテゴリ', 
                color_discrete_map=dynamic_colors, hole=0.4 # 💡 動的カラーマップを使用
            )
            fig_pie.update_traces(textinfo='percent+label', textposition='inside', insidetextorientation='horizontal', marker_line_width=0)
            fig_pie.add_annotation(text=f"<b>計 {total_hours}h</b>", x=0.5, y=0.5, font_size=18, showarrow=False)
            fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
            st.info(f"💡 「{period}」の合計記録時間は **{total_hours} 時間** です。")
        else:
            st.warning("この期間の記録はありません。")
    else:
        st.write("データがありません。")

# ----------------------------
# ⚙️ 固定モード
# ----------------------------
elif mode == "⚙️ 固定":
    st.markdown("#### 新規追加")
    if not st.session_state.categories:
        st.warning("カテゴリがありません。「🏷️ カテゴリ」から追加してください。")
    else:
        r_col1, r_col2 = st.columns(2)
        with r_col1: r_day = st.selectbox("曜日", WEEKDAYS)
        with r_col2: r_cat = st.selectbox("カテゴリ", st.session_state.categories)
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

    st.markdown("#### 登録済み一覧")
    if st.session_state.df_routine.empty: st.write("登録されていません。")
    else:
        for idx, row in st.session_state.df_routine.iterrows():
            st.markdown(f"<div class='list-card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{row['曜日']}** | {row['開始時刻']}〜{row['終了時刻']}")
                st.markdown(f"**{row['カテゴリ']}** {row['内容']}")
            with c2:
                if st.button("🗑️", key=f"del_r_{idx}", use_container_width=True):
                    st.session_state.df_routine = st.session_state.df_routine.drop(idx).reset_index(drop=True)
                    save_data(st.session_state.df_routine, ROUTINE_FILE)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# 📜 削除モード
# ----------------------------
elif mode == "📜 削除":
    st.markdown(f"#### {date_str} の記録")
    
    if not st.session_state.df_log.empty:
        df_edit_target = st.session_state.df_log[st.session_state.df_log["日付"] == date_str]
        if df_edit_target.empty: st.write("今日の記録はありません。")
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

# ----------------------------
# 🏷️ カテゴリ編集モード（💡完全新機能！）
# ----------------------------
elif mode == "🏷️ カテゴリ":
    st.markdown("#### カテゴリの編集")
    st.info("💡 グラフの色は自動で可愛く割り当てられます。\n表の下の「＋」で追加、行を選択して「Delete」で削除できます。")
    
    # リストを編集しやすいようにDataFrameに変換
    df_cat = pd.DataFrame(st.session_state.categories, columns=["カテゴリ名"])
    
    edited_df_cat = st.data_editor(
        df_cat,
        num_rows="dynamic",
        use_container_width=True,
        key="cat_editor"
    )
    
    # 変更があったら保存してアプリ全体に反映！
    if not edited_df_cat.equals(df_cat):
        # 空白を消したり、重複を整理してリストに戻す
        new_cats = edited_df_cat["カテゴリ名"].dropna().str.strip().tolist()
        new_cats = [c for c in new_cats if c != ""]
        new_cats = list(dict.fromkeys(new_cats)) # 重複を削除
        
        st.session_state.categories = new_cats
        save_categories(new_cats)
        st.rerun()
