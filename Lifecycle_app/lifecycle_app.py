import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import plotly.express as px
from supabase import create_client, Client
import hashlib

# スマホ画面設定
st.set_page_config(page_title="ライフログ", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 🔑 Supabase（データベース）接続設定
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 💅 スマホ最適化デザイン ＆ 🚨キーボード完全ブロックCSS/JS
# ==========================================
st.markdown("""
<style>
    [data-testid="stHeader"] { visibility: hidden; }
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    div.stButton > button {
        border-radius: 12px !important;
        font-weight: bold !important;
    }
    
    .list-card {
        background-color: rgba(0, 0, 0, 0.03);
        padding: 15px; 
        border-radius: 15px; 
        margin-bottom: 10px;
        border: 1px solid rgba(0, 0, 0, 0.1);
    }
</style>

<script>
// 🚨 【魔改造】ページ内のすべてのプルダウンの文字入力を禁止し、スマホ本来のドラムロール（選択肢）だけを強制するスクリプト
function blockMobileKeyboardOnSelect() {
    // Streamlitのコンポーネントが生成されるのを待つため定期的に実行
    setInterval(() => {
        // Streamlitのselectboxの実体であるinputタグ（検索兼用入力欄）を探す
        const inputs = window.parent.document.querySelectorAll('div[data-testid="stSelectbox"] input');
        inputs.forEach(input => {
            if (!input.hasAttribute('data-keyboard-blocked')) {
                // 1. 読み取り専用にすることでキーボードの起動を完全に防ぐ
                input.setAttribute('readonly', 'true');
                // 2. スマホ特有のインプットフォーカスによるキーボード起動を無効化
                input.setAttribute('inputmode', 'none');
                // 処理済みマークをつける
                input.setAttribute('data-keyboard-blocked', 'true');
                
                // タップした時に確実に選択肢（ドロップダウン）が開くようにイベントを補正
                input.addEventListener('focus', function(e) {
                    input.blur(); // 入力フォーカスを一瞬ではずしてキーボードを完全に殺す
                });
            }
        });
    }, 500);
}
// スクリプトを実行
if (window.parent) {
    blockMobileKeyboardOnSelect();
}
</script>
""", unsafe_allow_html=True)

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
PASTEL_PALETTE = ["#B3E5FC", "#C8E6C9", "#FFF59D", "#FFE0B2", "#E1BEE7", "#FFCDD2", "#F8BBD0", "#CFD8DC", "#D7CCC8", "#FFE082"]

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================================
# 🔐 ログイン・サインアップ画面
# ==========================================
if "current_user" not in st.session_state: st.session_state.current_user = None

if st.session_state.current_user is None:
    st.markdown("<h2 style='text-align: center;'>時間管理表<br><small>ログイン</small></h2>", unsafe_allow_html=True)
    tab_login, tab_signup = st.tabs(["ログイン", "新規登録"])
    with tab_login:
        login_name = st.text_input("ユーザー名", key="login_name")
        login_pass = st.text_input("パスワード", type="password", key="login_pass")
        if st.button("ログイン", type="primary", use_container_width=True):
            res = supabase.table("users").select("*").eq("user_name", login_name).execute()
            if len(res.data) > 0 and res.data[0]["password"] == hash_password(login_pass):
                st.session_state.current_user = login_name
                st.rerun()
            else: st.error("ユーザー名かパスワードが違います。")
    with tab_signup:
        signup_name = st.text_input("好きなユーザー名", key="signup_name")
        signup_pass = st.text_input("好きなパスワード", type="password", key="signup_pass")
        if st.button("アカウントを作成する", type="primary", use_container_width=True):
            res = supabase.table("users").select("*").eq("user_name", signup_name).execute()
            if len(res.data) > 0: st.error("⚠️ その名前はすでに誰かに使われています。")
            elif signup_name and signup_pass:
                supabase.table("users").insert({"user_name": signup_name, "password": hash_password(signup_pass)}).execute()
                default_cats = ["睡眠 🛌", "大学（講義・研究） 📝", "自主学習 ✏️", "バイト 💼", "移動・通学 🚶", "趣味・娯楽 🎮", "食事・生活 🍳", "その他 💬"]
                cat_inserts = [{"user_name": signup_name, "category_name": c} for c in default_cats]
                supabase.table("timeline_categories").insert(cat_inserts).execute()
                st.success("🎉 アカウント完成！ログインしてください。")
    st.stop()

# ==========================================
# 🚀 メインアプリ
# ==========================================
user_name = st.session_state.current_user

def load_db_data():
    res_cats = supabase.table("timeline_categories").select("category_name").eq("user_name", user_name).execute()
    st.session_state.categories = [row["category_name"] for row in res_cats.data] if res_cats.data else ["未設定"]
    res_log = supabase.table("timeline_data").select("*").eq("user_name", user_name).execute()
    df_log = pd.DataFrame(res_log.data) if res_log.data else pd.DataFrame(columns=["id", "date", "start_time", "end_time", "category", "detail"])
    st.session_state.ui_log = df_log.rename(columns={"date": "日付", "start_time": "開始時刻", "end_time": "終了時刻", "category": "カテゴリ", "detail": "内容"})
    res_routine = supabase.table("timeline_routine").select("*").eq("user_name", user_name).execute()
    df_rt = pd.DataFrame(res_routine.data) if res_routine.data else pd.DataFrame(columns=["id", "weekday", "start_time", "end_time", "category", "detail"])
    st.session_state.ui_routine = df_rt.rename(columns={"weekday": "曜日", "start_time": "開始時刻", "end_time": "終了時刻", "category": "カテゴリ", "detail": "内容"})
    st.session_state.need_reload = False

if "need_reload" not in st.session_state or st.session_state.need_reload:
    load_db_data()

ui_log = st.session_state.ui_log
ui_routine = st.session_state.ui_routine
dynamic_colors = {cat: PASTEL_PALETTE[i % len(PASTEL_PALETTE)] for i, cat in enumerate(st.session_state.categories)}

def get_now_jst():
    return datetime.utcnow() + timedelta(hours=9)

if "target_date" not in st.session_state: st.session_state.target_date = get_now_jst().date()
if "app_mode" not in st.session_state: st.session_state.app_mode = "⏱️ 計測"
if "editing_log_id" not in st.session_state: st.session_state.editing_log_id = None 

# 時・分を分けたすっきりプルダウンUI（裏側のJSでキーボードを完全停止します）
def split_time_selectbox(label, default_h, default_m, key_suffix):
    st.markdown(f"<small style='color:#555;font-weight:bold;'>{label}</small>", unsafe_allow_html=True)
    
    hours_options = [f"{i:02d}" for i in range(24)]
    minutes_options = ["00", "15", "30", "45"]
    
    c_h, c_m = st.columns(2)
    with c_h:
        h_val = st.selectbox("時", hours_options, index=hours_options.index(f"{int(default_h):02d}"), key=f"sel_h_{key_suffix}", label_visibility="collapsed")
    with c_m:
        m_val = st.selectbox("分", minutes_options, index=minutes_options.index(f"{int(default_m):02d}") if f"{int(default_m):02d}" in minutes_options else 0, key=f"sel_m_{key_suffix}", label_visibility="collapsed")
        
    return f"{h_val}:{m_val}"

def check_overlap(date_str, start_str, end_str, df_check_log, exclude_id=None):
    if df_check_log.empty: return False, None
    df_check = df_check_log.copy()
    if exclude_id is not None: df_check = df_check[df_check["id"] != exclude_id]
    if df_check.empty: return False, None
    new_start = pd.to_datetime(f"{date_str} {start_str}")
    new_end = pd.to_datetime(f"{date_str} {end_str}")
    if new_end <= new_start: new_end += pd.Timedelta(days=1)
    df_check["Start_dt"] = pd.to_datetime(df_check["日付"] + " " + df_check["開始時刻"])
    df_check["End_dt"] = pd.to_datetime(df_check["日付"] + " " + df_check["終了時刻"])
    df_check.loc[df_check["End_dt"] < df_check["Start_dt"], "End_dt"] += pd.Timedelta(days=1)
    overlap = df_check[(new_start < df_check["End_dt"]) & (new_end > df_check["Start_dt"])]
    if not overlap.empty: return True, overlap.iloc[0]["カテゴリ"]
    return False, None

def round_to_15(dt):
    discard = timedelta(minutes=dt.minute % 15, seconds=dt.second, microseconds=dt.microsecond)
    dt -= discard
    if discard >= timedelta(minutes=7, seconds=30): dt += timedelta(minutes=15)
    return dt

def merge_continuous_logs(df_target):
    if df_target.empty: return df_target
    df_m = df_target.copy()
    df_m["Start_dt"] = pd.to_datetime(df_m["日付"] + " " + df_m["開始時刻"])
    df_m["End_dt"] = pd.to_datetime(df_m["日付"] + " " + df_m["終了時刻"])
    df_m.loc[df_m["End_dt"] < df_m["Start_dt"], "End_dt"] += pd.Timedelta(days=1)
    df_m = df_m.sort_values("Start_dt").reset_index(drop=True)
    merged_rows = []
    current_row = df_m.iloc[0].to_dict()
    for i in range(1, len(df_m)):
        next_row = df_m.iloc[i].to_dict()
        if current_row["End_dt"] == next_row["Start_dt"] and current_row["カテゴリ"] == next_row["カテゴリ"]:
            current_row["End_dt"] = next_row["End_dt"]
            current_row["終了時刻"] = next_row["終了時刻"]
            if current_row["内容"] != next_row["内容"] and next_row["内容"] != "（未入力）":
                if current_row["内容"] == "（未入力）": current_row["内容"] = next_row["内容"]
                else: current_row["内容"] += f", {next_row['内容']}"
        else:
            merged_rows.append(current_row)
            current_row = next_row
    merged_rows.append(current_row)
    return pd.DataFrame(merged_rows)

# ==========================================
# 🗓️ カレンダー＆ログアウト
# ==========================================
col_user, col_out = st.columns([3, 1])
with col_user: st.markdown(f"**👤 {user_name}** さん")
with col_out:
    if st.button("🚪 ログアウト", use_container_width=True):
        st.session_state.current_user = None
        st.rerun()

st.markdown("<h2 style='text-align: center; font-size: 1.5rem; margin-top: -10px; margin-bottom: 0;'>時間管理表</h2>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    if st.button("◀ 前日", use_container_width=True): st.session_state.target_date -= timedelta(days=1); st.rerun()
with c2:
    selected_date = st.date_input("日付", st.session_state.target_date, label_visibility="collapsed")
    if selected_date != st.session_state.target_date: st.session_state.target_date = selected_date; st.rerun()
with c3:
    if st.button("翌日 ▶", use_container_width=True): st.session_state.target_date += timedelta(days=1); st.rerun()

date_str = st.session_state.target_date.strftime("%Y-%m-%d")
current_weekday = WEEKDAYS[st.session_state.target_date.weekday()]
st.markdown(f"<div style='text-align: center; font-size: 0.95rem; font-weight: bold; margin-bottom: 10px;'>{date_str} ({current_weekday})</div>", unsafe_allow_html=True)

# ==========================================
# 📊 タイムラインエリア
# ==========================================
if not ui_log.empty:
    df_raw = ui_log.copy()
    df_day_raw = df_raw[df_raw["日付"] == date_str].copy()
    start_of_day = pd.to_datetime(f"{date_str} 00:00:00")
    end_of_day = start_of_day + pd.Timedelta(days=1)
    
    if not df_day_raw.empty:
        df_day = merge_continuous_logs(df_day_raw)
        df_day["時間（h）"] = (df_day["End_dt"] - df_day["Start_dt"]).dt.total_seconds() / 3600.0
        df_day["グラフ内文字"] = df_day.apply(lambda r: r["カテゴリ"] if ((r["End_dt"] - r["Start_dt"]).total_seconds() / 60.0) >= 45 else "", axis=1)
        
        fig = px.timeline(df_day, x_start="Start_dt", x_end="End_dt", y="日付", color="カテゴリ", text="グラフ内文字", hover_name="内容", height=180, color_discrete_map=dynamic_colors)
        fig.update_traces(textposition='inside', insidetextanchor='middle', textfont_size=15, textfont_color="#1C1E21", marker_line_width=0)
        
        annotations = []
        for i, (_, row) in enumerate(df_day.iterrows()):
            duration_minutes = (row["End_dt"] - row["Start_dt"]).total_seconds() / 60.0
            if duration_minutes < 45:
                mid_dt = row["Start_dt"] + (row["End_dt"] - row["Start_dt"]) / 2
                ay_val = 45 if (i % 2 == 0) else 75
                display_text = f"<b>{row['カテゴリ']}</b> <span style='font-size:11px; color:#666;'>{row['開始時刻']}~</span>"
                annotations.append(dict(x=mid_dt, y=date_str, xref="x", yref="y", text=display_text, showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.2, arrowcolor="#999999", ax=0, ay=ay_val, font=dict(size=12, color="#1C1E21"), bgcolor="rgba(255, 255, 255, 0.9)", bordercolor="rgba(0,0,0,0.1)", borderwidth=1, borderpad=3))
            
        fig.update_layout(xaxis=dict(tickformat="%H:%M", title="", range=[start_of_day, end_of_day], dtick=14400000, fixedrange=True, tickfont=dict(color="#555", size=13, weight="bold")), yaxis=dict(title="", showticklabels=False, fixedrange=True), bargap=0, showlegend=False, dragmode=False, margin=dict(l=10, r=10, t=10, b=85), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', annotations=annotations)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        day_total = df_day["時間（h）"].sum()
        st.info(f"✨ 記録済み: {round(day_total, 1)} 時間 （空き: {round(24.0 - day_total, 1)} 時間）")
    else:
        empty_df = pd.DataFrame({"日付": [date_str], "Start_dt": [start_of_day], "End_dt": [start_of_day], "カテゴリ": ["未記録"]})
        fig = px.timeline(empty_df, x_start="Start_dt", x_end="End_dt", y="日付", height=130)
        fig.update_layout(xaxis=dict(tickformat="%H:%M", title="", range=[start_of_day, end_of_day], dtick=14400000, fixedrange=True), yaxis=dict(title="", showticklabels=False, fixedrange=True), showlegend=False, dragmode=False, margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
st.markdown("---")

# ==========================================
# 📱 メニューボタン
# ==========================================
def change_mode(new_mode): st.session_state.app_mode = new_mode

m1, m2, m3 = st.columns(3)
with m1:
    if st.button("⏱️ 計測", type="primary" if st.session_state.app_mode == "⏱️ 計測" else "secondary", use_container_width=True): change_mode("⏱️ 計測"); st.rerun()
with m2:
    if st.button("📝 追加", type="primary" if st.session_state.app_mode == "📝 追加" else "secondary", use_container_width=True): change_mode("📝 追加"); st.rerun()
with m3:
    if st.button("📊 分析", type="primary" if st.session_state.app_mode == "📊 分析" else "secondary", use_container_width=True): change_mode("📊 分析"); st.rerun()

m4, m5, m6 = st.columns(3)
with m4:
    if st.button("⚙️ 固定", type="primary" if st.session_state.app_mode == "⚙️ 固定" else "secondary", use_container_width=True): change_mode("⚙️ 固定"); st.rerun()
with m5:
    if st.button("📜 編集・削除", type="primary" if st.session_state.app_mode == "📜 編集・削除" else "secondary", use_container_width=True): change_mode("📜 編集・削除"); st.rerun()
with m6:
    if st.button("🏷️ カテゴリ", type="primary" if st.session_state.app_mode == "🏷️ カテゴリ" else "secondary", use_container_width=True): change_mode("🏷️ カテゴリ"); st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
mode = st.session_state.app_mode

# ----------------------------
# 各種モードの処理
# ----------------------------
if mode == "⏱️ 計測":
    if st.session_state.tracking_start is None:
        if not st.session_state.categories: st.warning("カテゴリがありません。")
        else:
            rt_cat = st.selectbox("カテゴリを選ぶ", st.session_state.categories, key="rt_cat")
            if st.button("▶️ 今からスタート！", type="primary", use_container_width=True):
                st.session_state.tracking_cat = rt_cat
                st.session_state.tracking_start = get_now_jst() 
                st.rerun()
    else:
        st.success(f"⏳ {st.session_state.tracking_cat} 計測中\n\n開始: {st.session_state.tracking_start.strftime('%H:%M')}")
        rt_detail = st.text_input("メモ（任意）", key="rt_detail")
        
        if st.button("⏹️ 今終わった！（15分単位で記録）", type="primary", use_container_width=True):
            end_dt = get_now_jst() 
            start_rounded = round_to_15(st.session_state.tracking_start)
            end_rounded = round_to_15(end_dt)
            if start_rounded == end_rounded: end_rounded += timedelta(minutes=15)
            start_str = start_rounded.strftime('%H:%M')
            end_str = end_rounded.strftime('%H:%M')
            record_date_str = start_rounded.strftime('%Y-%m-%d') 
            
            is_overlap, overlap_cat = check_overlap(record_date_str, start_str, end_str, ui_log)
            if is_overlap:
                st.error(f"⚠️ 「{overlap_cat}」と重なっています。")
                st.session_state.tracking_cat = None; st.session_state.tracking_start = None
            else:
                supabase.table("timeline_data").insert({"user_name": user_name, "date": record_date_str, "start_time": start_str, "end_time": end_str, "category": st.session_state.tracking_cat, "detail": rt_detail if rt_detail else "（未入力）"}).execute()
                st.session_state.tracking_cat = None; st.session_state.tracking_start = None
                st.session_state.need_reload = True
                st.rerun()
        if st.button("❌ 計測をキャンセル", use_container_width=True):
            st.session_state.tracking_cat = None; st.session_state.tracking_start = None; st.rerun()

elif mode == "📝 追加":
    if not st.session_state.categories: st.warning("カテゴリがありません。")
    else:
        category = st.selectbox("カテゴリ", st.session_state.categories, key="man_cat")
        
        # 🚨 プルダウン形式（裏のJavaScriptでキーボード起動を完全阻止）
        start_str = split_time_selectbox("🛫 開始時刻", 9, 0, "add_start")
        end_str = split_time_selectbox("🛬 終了時刻", 10, 0, "add_end")
            
        detail = st.text_input("メモ", key="man_detail")
        
        if st.button("手動で追加する", use_container_width=True):
            if start_str == end_str: st.warning("開始と終了が同じです。")
            else:
                is_overlap, overlap_cat = check_overlap(date_str, start_str, end_str, ui_log)
                if is_overlap: st.error(f"⚠️ すでに「{overlap_cat}」が入っています！")
                else:
                    supabase.table("timeline_data").insert({"user_name": user_name, "date": date_str, "start_time": start_str, "end_time": end_str, "category": category, "detail": detail if detail else "（未入力）"}).execute()
                    st.session_state.need_reload = True
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(f"✨ {current_weekday}曜日のルーティンを一括追加", use_container_width=True):
        routine_for_day = ui_routine[ui_routine["曜日"] == current_weekday]
        if routine_for_day.empty: st.warning("ルーティンが設定されていません。")
        else:
            success_count = 0
            for _, row in routine_for_day.iterrows():
                is_overlap, _ = check_overlap(date_str, row["開始時刻"], row["終了時刻"], ui_log)
                if not is_overlap:
                    supabase.table("timeline_data").insert({"user_name": user_name, "date": date_str, "start_time": row["開始時刻"], "end_time": row["終了時刻"], "category": row["カテゴリ"], "detail": row["内容"]}).execute()
                    success_count += 1
            st.session_state.need_reload = True
            st.rerun()

elif mode == "📊 分析":
    st.markdown("#### 時間の使い方のバランス")
    period = st.selectbox("分析する期間", ["過去7日間", "過去30日間", "全期間", "今日"])
    if not ui_log.empty:
        df_analysis = ui_log.copy()
        df_analysis["Date_obj"] = pd.to_datetime(df_analysis["日付"]).dt.date
        today = get_now_jst().date() 
        if period == "今日": df_filtered_raw = df_analysis[df_analysis["Date_obj"] == today]
        elif period == "過去7日間": df_filtered_raw = df_analysis[df_analysis["Date_obj"] >= (today - timedelta(days=6))]
        elif period == "過去30日間": df_filtered_raw = df_analysis[df_analysis["Date_obj"] >= (today - timedelta(days=29))]
        else: df_filtered_raw = df_analysis
            
        if not df_filtered_raw.empty:
            df_list = []
            for d_str, sub_df in df_filtered_raw.groupby("日付"): df_list.append(merge_continuous_logs(sub_df))
            df_filtered = pd.concat(df_list)
            df_filtered["時間（h）"] = (df_filtered["End_dt"] - df_filtered["Start_dt"]).dt.total_seconds() / 3600.0
            sum_df = df_filtered.groupby("カテゴリ")["時間（h）"].sum().reset_index()
            total_hours = round(sum_df["時間（h）"].sum(), 1)
            
            fig_pie = px.pie(sum_df, values='時間（h）', names='カテゴリ', color='カテゴリ', color_discrete_map=dynamic_colors, hole=0.4)
            fig_pie.update_traces(textinfo='percent+label', textposition='outside', marker_line_width=0)
            fig_pie.add_annotation(text=f"<b>計 {total_hours}h</b>", x=0.5, y=0.5, font_size=18, showarrow=False)
            fig_pie.update_layout(showlegend=False, margin=dict(t=40, b=40, l=40, r=40), height=380, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(size=14))
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
            
            df_table = sum_df.sort_values(by="時間（h）", ascending=False).copy()
            df_table["割合"] = (df_table["時間（h）"] / total_hours * 100).round(1).astype(str) + " %"
            df_table["合計時間"] = df_table["時間（h）"].round(1).astype(str) + " 時間"
            st.dataframe(df_table[["カテゴリ", "合計時間", "割合"]], use_container_width=True, hide_index=True)
        else: st.warning("この期間の記録はありません。")
    else: st.write("データがありません。")

elif mode == "📜 編集・削除":
    st.markdown(f"#### {date_str} の記録・編集")
    if not ui_log.empty:
        df_edit_target = ui_log[ui_log["日付"] == date_str].copy()
        if df_edit_target.empty: st.write("今日の記録はありません。")
        else:
            df_edit_target = df_edit_target.sort_values("開始時刻")
            for _, row in df_edit_target.iterrows():
                is_editing = (st.session_state.editing_log_id == row["id"])
                st.markdown(f"<div class='list-card'>", unsafe_allow_html=True)
                
                if not is_editing:
                    c1, c2, c3 = st.columns([3.5, 1, 1])
                    with c1:
                        st.markdown(f"**{row['開始時刻']} 〜 {row['終了時刻']}**")
                        st.markdown(f"**{row['カテゴリ']}** <small>{row['内容']}</small>", unsafe_allow_html=True)
                    with c2:
                        if st.button("✏️", key=f"edit_btn_{row['id']}", use_container_width=True):
                            st.session_state.editing_log_id = row["id"]
                            st.rerun()
                    with c3:
                        if st.button("🗑️", key=f"del_l_{row['id']}", use_container_width=True):
                            supabase.table("timeline_data").delete().eq("id", row['id']).execute()
                            st.session_state.need_reload = True
                            st.rerun()
                else:
                    st.markdown("<p style='font-size:0.85rem; color:#f03e3e; font-weight:bold;'>📝 データを編集中...</p>", unsafe_allow_html=True)
                    edit_cat = st.selectbox("カテゴリ", st.session_state.categories, index=st.session_state.categories.index(row["カテゴリ"]) if row["カテゴリ"] in st.session_state.categories else 0, key=f"ed_cat_{row['id']}")
                    
                    try:
                        sh, sm = map(int, row["開始時刻"].split(":"))
                        eh, em = map(int, row["終了時刻"].split(":"))
                    except:
                        sh, sm, eh, em = 9, 0, 10, 0
                        
                    new_s_str = split_time_selectbox("🛫 変更後の開始時刻", sh, sm, f"edit_s_{row['id']}")
                    new_e_str = split_time_selectbox("🛬 変更後の終了時刻", eh, em, f"edit_e_{row['id']}")
                    
                    edit_detail = st.text_input("メモ内容", value=row["内容"], key=f"ed_det_{row['id']}")
                    
                    cb1, cb2 = st.columns(2)
                    with cb1:
                        if st.button("💾 変更を保存", type="primary", key=f"save_btn_{row['id']}", use_container_width=True):
                            if new_s_str == new_e_str: st.error("⚠️ 同じ時刻です。")
                            else:
                                is_overlap, overlap_cat = check_overlap(date_str, new_s_str, new_e_str, ui_log, exclude_id=row["id"])
                                if is_overlap: st.error(f"⚠️ 「{overlap_cat}」と重なっています！")
                                else:
                                    supabase.table("timeline_data").update({"start_time": new_s_str, "end_time": new_e_str, "category": edit_cat, "detail": edit_detail if edit_detail else "（未入力）"}).eq("id", row['id']).execute()
                                    st.session_state.editing_log_id = None 
                                    st.session_state.need_reload = True
                                    st.rerun()
                    with cb2:
                        if st.button("❌ キャンセル", key=f"cancel_btn_{row['id']}", use_container_width=True):
                            st.session_state.editing_log_id = None
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else: st.write("データがありません。")

elif mode == "⚙️ 固定":
    st.markdown("#### 新規追加")
    if not st.session_state.categories: st.warning("カテゴリがありません。")
    else:
        r_col1, r_col2 = st.columns(2)
        with r_col1: r_day = st.selectbox("曜日", WEEKDAYS)
        with r_col2: r_cat = st.selectbox("カテゴリ", st.session_state.categories)
        
        r_start_str = split_time_selectbox("🛫 開始", 9, 0, "rt_start")
        r_end_str = split_time_selectbox("🛬 終了", 10, 0, "rt_end")
            
        r_detail = st.text_input("メモ（任意）", key="r_detail")
        if st.button("➕ ルーティンを追加", use_container_width=True):
            supabase.table("timeline_routine").insert({"user_name": user_name, "weekday": r_day, "start_time": r_start_str, "end_time": r_end_str, "category": r_cat, "detail": r_detail if r_detail else "（未入力）"}).execute()
            st.session_state.need_reload = True
            st.rerun()

    st.markdown("#### 登録済み一覧")
    if ui_routine.empty: st.write("登録されていません。")
    else:
        for _, row in ui_routine.iterrows():
            st.markdown(f"<div class='list-card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{row['曜日']}** | {row['開始時刻']}〜{row['終了時刻']}")
                st.markdown(f"**{row['カテゴリ']}** {row['内容']}")
            with c2:
                if st.button("🗑️", key=f"del_r_{row['id']}", use_container_width=True):
                    supabase.table("timeline_routine").delete().eq("id", row['id']).execute()
                    st.session_state.need_reload = True
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

elif mode == "🏷️ カテゴリ":
    st.markdown("#### カテゴリの編集")
    df_cat = pd.DataFrame(st.session_state.categories, columns=["カテゴリ名"])
    edited_df_cat = st.data_editor(df_cat, num_rows="dynamic", use_container_width=True, key="cat_editor")
    if st.button("💾 変更を保存する", type="primary", use_container_width=True):
        new_cats = edited_df_cat["カテゴリ名"].dropna().astype(str).str.strip().tolist()
        new_cats = [c for c in new_cats if c != "" and c != "None"]
        new_cats = list(dict.fromkeys(new_cats)) 
        if len(new_cats) > 0:
            supabase.table("timeline_categories").delete().eq("user_name", user_name).execute()
            inserts = [{"user_name": user_name, "category_name": c} for c in new_cats]
            supabase.table("timeline_categories").insert(inserts).execute()
            st.session_state.need_reload = True
            st.rerun()
