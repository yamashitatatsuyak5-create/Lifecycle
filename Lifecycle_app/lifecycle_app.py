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

# Supabaseに接続
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 💅 スマホに特化した見やすいデザイン（超シンプル・安全版）
# ==========================================
st.markdown("""
<style>
    /* ヘッダーの非表示と画面の余白調整だけを行う */
    [data-testid="stHeader"] { visibility: hidden; }
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    /* ボタンのカドを少し丸くしてスマホっぽくする */
    div.stButton > button {
        border-radius: 15px !important;
        font-weight: bold !important;
    }
    
    /* 履歴カード（削除・固定タブ）の見た目調整 */
    .list-card {
        background-color: rgba(0, 0, 0, 0.03); /* どのモードでも薄く見える背景 */
        padding: 15px; 
        border-radius: 15px; 
        margin-bottom: 10px;
        border: 1px solid rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
PASTEL_PALETTE = ["#B3E5FC", "#C8E6C9", "#FFF59D", "#FFE0B2", "#E1BEE7", "#FFCDD2", "#F8BBD0", "#CFD8DC", "#D7CCC8", "#FFE082"]

# パスワードを暗号化する関数（セキュリティ対策）
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
        st.write("アカウントを持っている方はこちら👇")
        login_name = st.text_input("ユーザー名", key="login_name")
        login_pass = st.text_input("パスワード", type="password", key="login_pass")
        if st.button("ログイン", type="primary", use_container_width=True):
            res = supabase.table("users").select("*").eq("user_name", login_name).execute()
            if len(res.data) > 0 and res.data[0]["password"] == hash_password(login_pass):
                st.session_state.current_user = login_name
                st.rerun()
            else:
                st.error("ユーザー名かパスワードが違います。")
                
    with tab_signup:
        st.write("初めての方はこちら👇（友達もここから作れます！）")
        signup_name = st.text_input("好きなユーザー名", key="signup_name")
        signup_pass = st.text_input("好きなパスワード", type="password", key="signup_pass")
        if st.button("アカウントを作成する", type="primary", use_container_width=True):
            res = supabase.table("users").select("*").eq("user_name", signup_name).execute()
            if len(res.data) > 0:
                st.error("⚠️ その名前はすでに誰かに使われています。")
            elif signup_name and signup_pass:
                # ユーザーを登録
                supabase.table("users").insert({"user_name": signup_name, "password": hash_password(signup_pass)}).execute()
                # デフォルトのカテゴリを登録
                default_cats = ["睡眠 🛌", "大学（講義・研究） 📝", "自主学習 ✏️", "バイト 💼", "移動・通学 🚶", "趣味・娯楽 🎮", "食事・生活 🍳", "その他 💬"]
                cat_inserts = [{"user_name": signup_name, "category_name": c} for c in default_cats]
                supabase.table("timeline_categories").insert(cat_inserts).execute()
                st.success("🎉 アカウントが完成しました！左のタブからログインしてください。")
            else:
                st.warning("ユーザー名とパスワードを入力してください。")
    st.stop() # ログインしていない場合はここで画面を止める

# ==========================================
# 🚀 ログイン成功後（メインアプリ）
# ==========================================
user_name = st.session_state.current_user

# --- データベースから読み込む関数 ---
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

# 最新のデータを読み込む
if "need_reload" not in st.session_state or st.session_state.need_reload:
    load_db_data()

ui_log = st.session_state.ui_log
ui_routine = st.session_state.ui_routine
dynamic_colors = {cat: PASTEL_PALETTE[i % len(PASTEL_PALETTE)] for i, cat in enumerate(st.session_state.categories)}

# アプリ状態の初期化
if "target_date" not in st.session_state: st.session_state.target_date = datetime.now().date()
if "app_mode" not in st.session_state: st.session_state.app_mode = "⏱️ 計測"
if "tracking_cat" not in st.session_state: st.session_state.tracking_cat = None
if "tracking_start" not in st.session_state: st.session_state.tracking_start = None

def check_overlap(date_str, start_str, end_str, df_check_log):
    if df_check_log.empty: return False, None
    new_start = pd.to_datetime(f"{date_str} {start_str}")
    new_end = pd.to_datetime(f"{date_str} {end_str}")
    if new_end <= new_start: new_end += pd.Timedelta(days=1)
    df_check = df_check_log.copy()
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

# ==========================================
# 🗓️ 画面上部：カレンダー＆ログアウト
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
# 📊 タイムライン・グラフエリア（棒グラフ拡大版）
# ==========================================
if not ui_log.empty:
    df = ui_log.copy()
    df["Start_dt"] = pd.to_datetime(df["日付"] + " " + df["開始時刻"])
    df["End_dt"] = pd.to_datetime(df["日付"] + " " + df["終了時刻"])
    df.loc[df["End_dt"] < df["Start_dt"], "End_dt"] += pd.Timedelta(days=1)
    df["時間（h）"] = (df["End_dt"] - df["Start_dt"]).dt.total_seconds() / 3600.0
    
    df_day = df[df["日付"] == date_str].copy()
    start_of_day = pd.to_datetime(f"{date_str} 00:00:00")
    end_of_day = start_of_day + pd.Timedelta(days=1)
    
    if not df_day.empty:
        # 開始時刻順に並び替え
        df_day = df_day.sort_values("開始時刻")
        
        # 45分未満の予定は、棒グラフ内の文字をはじめから「空っぽ」にする
        df_day["グラフ内文字"] = df_day.apply(
            lambda r: r["カテゴリ"] if ((pd.to_datetime(r["日付"] + " " + r["終了時刻"]) - pd.to_datetime(r["日付"] + " " + r["開始時刻"])).total_seconds() / 60.0) >= 45 else "",
            axis=1
        )
        
        # 🚨 修正：heightを 150 から 180 に大きくしました
        fig = px.timeline(
            df_day, x_start="Start_dt", x_end="End_dt", y="日付", color="カテゴリ", 
            text="グラフ内文字", hover_name="内容", height=180, color_discrete_map=dynamic_colors
        )
        
        fig.update_traces(
            textposition='inside', 
            insidetextanchor='middle', 
            textfont_size=15,         # 🚨 文字サイズも少し大きく（14→15）して見やすくしました
            textfont_color="#1C1E21",  
            marker_line_width=0
        )
        
        # 短すぎる項目だけを判定して、引き出し線を伸ばす
        annotations = []
        for i, (_, row) in enumerate(df_day.iterrows()):
            duration_minutes = (row["End_dt"] - row["Start_dt"]).total_seconds() / 60.0
            
            # 45分未満の短い予定は引き出し線を出す
            if duration_minutes < 45:
                mid_dt = row["Start_dt"] + (row["End_dt"] - row["Start_dt"]) / 2
                
                # 🚨 グラフが太くなったので、引き出し線の出発点を調整（少し深めに伸ばす）
                ay_val = 45 if (i % 2 == 0) else 75
                display_text = f"<b>{row['カテゴリ']}</b> <span style='font-size:11px; color:#666;'>{row['開始時刻']}~</span>"
                
                annotations.append(dict(
                    x=mid_dt,
                    y=date_str,
                    xref="x", yref="y",
                    text=display_text,
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=1.2,
                    arrowcolor="#999999",
                    ax=0,
                    ay=ay_val,
                    font=dict(size=12, color="#1C1E21"),
                    bgcolor="rgba(255, 255, 255, 0.9)",
                    bordercolor="rgba(0,0,0,0.1)",
                    borderwidth=1,
                    borderpad=3
                ))
            
        fig.update_layout(
            xaxis=dict(tickformat="%H:%M", title="", range=[start_of_day, end_of_day], dtick=14400000, fixedrange=True, tickfont=dict(color="#555", size=13, weight="bold")),
            yaxis=dict(title="", showticklabels=False, fixedrange=True),
            bargap=0, # 🚨 修正：棒の上下の無駄な隙間をゼロにして、限界まで太くします！
            showlegend=False, 
            dragmode=False, 
            margin=dict(l=10, r=10, t=10, b=85), # 下側の引き出し線用の余白
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            annotations=annotations 
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
# 各種モードの処理（データベース連携版）
# ----------------------------
if mode == "⏱️ 計測":
    if st.session_state.tracking_start is None:
        if not st.session_state.categories: st.warning("カテゴリがありません。「🏷️ カテゴリ」から追加してください。")
        else:
            rt_cat = st.selectbox("カテゴリを選ぶ", st.session_state.categories, key="rt_cat")
            if st.button("▶️ 今からスタート！", type="primary", use_container_width=True):
                st.session_state.tracking_cat = rt_cat
                st.session_state.tracking_start = datetime.now()
                st.rerun()
    else:
        st.success(f"⏳ 現在 **{st.session_state.tracking_cat}** を計測中です！\n\n実際の開始: {st.session_state.tracking_start.strftime('%H:%M')}")
        rt_detail = st.text_input("メモ（任意）", key="rt_detail")
        
        if st.button("⏹️ 今終わった！（15分単位で記録）", type="primary", use_container_width=True):
            end_dt = datetime.now()
            start_rounded = round_to_15(st.session_state.tracking_start)
            end_rounded = round_to_15(end_dt)
            if start_rounded == end_rounded: end_rounded += timedelta(minutes=15)
                
            start_str = start_rounded.strftime('%H:%M')
            end_str = end_rounded.strftime('%H:%M')
            record_date_str = start_rounded.strftime('%Y-%m-%d') 
            
            is_overlap, overlap_cat = check_overlap(record_date_str, start_str, end_str, ui_log)
            if is_overlap:
                st.error(f"⚠️ 丸められた時間が「{overlap_cat}」と重なっています。手動で追加してください。")
                st.session_state.tracking_cat = None; st.session_state.tracking_start = None
            else:
                supabase.table("timeline_data").insert({"user_name": user_name, "date": record_date_str, "start_time": start_str, "end_time": end_str, "category": st.session_state.tracking_cat, "detail": rt_detail if rt_detail else "（未入力）"}).execute()
                st.session_state.tracking_cat = None; st.session_state.tracking_start = None
                st.session_state.need_reload = True
                st.success(f"{start_str} 〜 {end_str} で記録しました！")
                st.rerun()
                
        if st.button("❌ 計測をキャンセル", use_container_width=True):
            st.session_state.tracking_cat = None; st.session_state.tracking_start = None; st.rerun()

elif mode == "📝 追加":
    if not st.session_state.categories: st.warning("カテゴリがありません。「🏷️ カテゴリ」から追加してください。")
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
            st.success(f"🎉 {success_count}件追加しました！")
            st.rerun()

elif mode == "📊 分析":
    st.markdown("#### 時間の使い方のバランス")
    period = st.selectbox("分析する期間", ["過去7日間", "過去30日間", "全期間", "今日"])
    
    if not ui_log.empty:
        df_analysis = ui_log.copy()
        df_analysis["Date_obj"] = pd.to_datetime(df_analysis["日付"]).dt.date
        today = datetime.now().date()
        
        if period == "今日": df_filtered = df_analysis[df_analysis["Date_obj"] == today]
        elif period == "過去7日間": df_filtered = df_analysis[df_analysis["Date_obj"] >= (today - timedelta(days=6))]
        elif period == "過去30日間": df_filtered = df_analysis[df_analysis["Date_obj"] >= (today - timedelta(days=29))]
        else: df_filtered = df_analysis
            
        if not df_filtered.empty:
            # 「時間（h）」の計算（深夜またぎも考慮）
            df_filtered["Start_dt"] = pd.to_datetime(df_filtered["日付"] + " " + df_filtered["開始時刻"])
            df_filtered["End_dt"] = pd.to_datetime(df_filtered["日付"] + " " + df_filtered["終了時刻"])
            df_filtered.loc[df_filtered["End_dt"] < df_filtered["Start_dt"], "End_dt"] += pd.Timedelta(days=1)
            df_filtered["時間（h）"] = (df_filtered["End_dt"] - df_filtered["Start_dt"]).dt.total_seconds() / 3600.0

            sum_df = df_filtered.groupby("カテゴリ")["時間（h）"].sum().reset_index()
            total_hours = round(sum_df["時間（h）"].sum(), 1)
            
            # 割合の小さな項目でも潰れないように円グラフの設定を大幅に強化しました！
            fig_pie = px.pie(sum_df, values='時間（h）', names='カテゴリ', color='カテゴリ', color_discrete_map=dynamic_colors, hole=0.4)
            
            # 文字の位置を「外側（outside）」に強制し、勝手に文字が小さくなるのをストップ
            fig_pie.update_traces(
                textinfo='percent+label', 
                textposition='outside', 
                marker_line_width=0
            )
            
            # 真ん中の合計時間表示
            fig_pie.add_annotation(text=f"<b>計 {total_hours}h</b>", x=0.5, y=0.5, font_size=18, showarrow=False)
            
            # 外側の文字が画面からはみ出さないように、余白（margin）とグラフ全体の高さ（height）をゆったり広げ、全体の文字サイズを14pxに固定しました
            fig_pie.update_layout(
                showlegend=False, 
                margin=dict(t=40, b=40, l=40, r=40), 
                height=380, 
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=14)
            )
            
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
            
            # 🚨【新設】円グラフの下に表示する詳細データ表の作成
            st.markdown(f"<p style='font-size:1.0rem; font-weight:bold; color:#555; margin-bottom:5px;'>📋 「{period}」のカテゴリ別詳細</p>", unsafe_allow_html=True)
            
            # 合計時間が長い順（降順）に並び替える
            df_table = sum_df.sort_values(by="時間（h）", ascending=False).copy()
            
            # パーセント（％）を計算して文字にする
            df_table["割合"] = (df_table["時間（h）"] / total_hours * 100).round(1).astype(str) + " %"
            # 時間の表示を綺麗にする（例: 42.5 時間）
            df_table["合計時間"] = df_table["時間（h）"].round(1).astype(str) + " 時間"
            
            # 列の整理
            df_table = df_table[["カテゴリ", "合計時間", "割合"]]
            
            # 綺麗なテーブル形式でStreamlitに表示（インデックスは非表示）
            st.dataframe(df_table, use_container_width=True, hide_index=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.info(f"💡 「{period}」の合計記録時間は **{total_hours} 時間** です。")
        else: st.warning("この期間の記録はありません。")
    else: st.write("データがありません。")

elif mode == "⚙️ 固定":
    st.markdown("#### 新規追加")
    if not st.session_state.categories: st.warning("カテゴリがありません。「🏷️ カテゴリ」から追加してください。")
    else:
        r_col1, r_col2 = st.columns(2)
        with r_col1: r_day = st.selectbox("曜日", WEEKDAYS)
        with r_col2: r_cat = st.selectbox("カテゴリ", st.session_state.categories)
        r_col3, r_col4 = st.columns(2)
        with r_col3: r_start = st.time_input("開始", time(9,0), key="r_start")
        with r_col4: r_end = st.time_input("終了", time(10,0), key="r_end")
        r_detail = st.text_input("メモ（任意）", key="r_detail")
        
        if st.button("➕ ルーティンを追加", use_container_width=True):
            supabase.table("timeline_routine").insert({"user_name": user_name, "weekday": r_day, "start_time": r_start.strftime("%H:%M"), "end_time": r_end.strftime("%H:%M"), "category": r_cat, "detail": r_detail if r_detail else "（未入力）"}).execute()
            st.session_state.need_reload = True
            st.success("追加しました！"); st.rerun()

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

elif mode == "📜 削除":
    st.markdown(f"#### {date_str} の記録")
    if not ui_log.empty:
        df_edit_target = ui_log[ui_log["日付"] == date_str]
        if df_edit_target.empty: st.write("今日の記録はありません。")
        else:
            for _, row in df_edit_target.iterrows():
                st.markdown(f"<div class='list-card'>", unsafe_allow_html=True)
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{row['開始時刻']} 〜 {row['終了時刻']}**")
                    st.markdown(f"**{row['カテゴリ']}** <small>{row['内容']}</small>", unsafe_allow_html=True)
                with c2:
                    if st.button("🗑️", key=f"del_l_{row['id']}", use_container_width=True):
                        supabase.table("timeline_data").delete().eq("id", row['id']).execute()
                        st.session_state.need_reload = True
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else: st.write("データがありません。")

elif mode == "🏷️ カテゴリ":
    st.markdown("#### カテゴリの編集")
    st.info("💡 表の下の「＋」で追加できます。\n⚠️ 編集が終わったら、必ず下の**「保存ボタン」**を押してください。")
    
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
            st.success("カテゴリを保存しました！")
            st.rerun()
        else:
            st.error("⚠️ 最低1つのカテゴリが必要です。")
