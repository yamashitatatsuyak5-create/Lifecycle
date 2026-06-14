import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from supabase import create_client, Client
import hashlib

# -------------------------------------------------
# ページ設定
# -------------------------------------------------
st.set_page_config(page_title="ライフログ",
                   layout="wide",
                   initial_sidebar_state="collapsed")

# -------------------------------------------------
# Supabase 接続
# -------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------------------------
# CSS ＆ “スマホキーボード殺し” JavaScript
# -------------------------------------------------
st.markdown("""
<style>
[data-testid="stHeader"]{visibility:hidden;}
.block-container{padding-top:1rem;padding-bottom:5rem;}
div.stButton>button{border-radius:12px!important;font-weight:bold!important;}
.list-card{
    background:rgba(0,0,0,.03);
    padding:15px;border-radius:15px;margin-bottom:10px;
    border:1px solid rgba(0,0,0,.1);
}
/* ▼▼ 追加：selectbox 内 input を完全にタップ不可にする ▼▼ */
div[data-testid^="stSelect"] input,
div[data-testid^="stDateInput"] input,
div[data-testid^="stTimeInput"] input{
    pointer-events:none!important;      /* タップ出来ない = フォーカス出来ない */
    caret-color:transparent!important;  /* キャレットも非表示 */
}
div[data-testid^="stSelect"] input,
div[data-testid^="stDateInput"] input,
div[data-testid^="stTimeInput"] input {
    pointer-events: none !important;
    -webkit-user-select: none !important;
    user-select: none !important;
    outline: none !important;
    -webkit-appearance: none !important;
    appearance: none !important;
}

/* iOS Safari 特有対策：タップハイライトを消す */
div[data-testid^="stSelect"],
div[data-testid^="stDateInput"],
div[data-testid^="stTimeInput"] {
    -webkit-tap-highlight-color: transparent !important;
}
/* キーボードが出ても見えないよう画面外に押し出す */
@media (max-width: 768px) {
    .ReactVirtualized__Grid input,
    input[type="text"]:focus {
        position: fixed !important;
        left: -9999px !important;
        top: -9999px !important;
        opacity: 0 !important;
    }
    
    /* iOS Safari 特有：VirtualKeyboard API が起動しても画面に出ない */
    input {
        font-size: 16px !important;  /* iOS は 16px 未満だと zoom するのでこれを逆利用 */
    }
}

/* Streamlit selectbox の input を徹底的に消す */
div[data-testid^="stSelect"] input:focus,
div[data-testid^="stDateInput"] input:focus,
div[data-testid^="stTimeInput"] input:focus {
    position: absolute !important;
    left: -10000px !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
</style>

<script>
(function(){

  // "常時フォーカスを剥がす"パトロール
  function killFocusOnSelectInputs(){
    setInterval(()=>{
      const active = document.activeElement;
      if(!active) return;

      // 対象は selectbox / date / time の input
      const isTarget = 
        active.closest('div[data-testid^="stSelect"]')    ||
        active.closest('div[data-testid^="stDateInput"]') ||
        active.closest('div[data-testid^="stTimeInput"]');

      if(isTarget && active.tagName==='INPUT'){
        // フォーカスが当たった input を即座に blur
        active.blur();
        
        // ドロップダウンを開く
        const box = isTarget;
        box.click();
      }
    }, 50);  // 50ms ごとにチェック
  }

  // タップ時に即座に反応
  function interceptTaps(){
    const q = `
      div[data-testid^="stSelect"],
      div[data-testid^="stDateInput"],
      div[data-testid^="stTimeInput"]`;
    
    document.addEventListener('touchstart',(e)=>{
      const target = e.target.closest(q);
      if(target){
        e.preventDefault();
        // 子の input をすべて blur
        target.querySelectorAll('input').forEach(inp=>inp.blur());
        // ドロップダウン開く
        target.click();
      }
    }, {capture:true, passive:false});
  }

  killFocusOnSelectInputs();
  interceptTaps();

})();
document.addEventListener('focus', (e) => {
    if (e.target.tagName === 'INPUT') {
        e.target.setAttribute('readonly', 'true');
        setTimeout(() => e.target.blur(), 0);
    }
}, true);
</script>
""", unsafe_allow_html=True)

# -------------------------------------------------
# 定数 & ユーティリティ
# -------------------------------------------------
WEEKDAYS = ["月","火","水","木","金","土","日"]
PASTEL_PALETTE = ["#B3E5FC","#C8E6C9","#FFF59D","#FFE0B2",
                  "#E1BEE7","#FFCDD2","#F8BBD0",
                  "#CFD8DC","#D7CCC8","#FFE082"]

def hash_password(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_now_jst():      return datetime.utcnow() + timedelta(hours=9)

# -------------------------------------------------
# SessionState 初期化
# -------------------------------------------------
defaults = {
    "current_user"   : None,
    "target_date"    : get_now_jst().date(),
    "app_mode"       : "⏱️ 計測",
    "editing_log_id" : None,
    "tracking_start" : None,
    "tracking_cat"   : None,
    "need_reload"    : True,
}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# -------------------------------------------------
# 🔐 ログイン / サインアップ
# -------------------------------------------------
if st.session_state.current_user is None:
    st.markdown("<h2 style='text-align:center;'>時間管理表<br><small>ログイン</small></h2>",
                unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["ログイン","新規登録"])

    # --- ログイン ---
    with tab_login:
        u = st.text_input("ユーザー名", key="login_name")
        p = st.text_input("パスワード", type="password", key="login_pass")
        if st.button("ログイン", type="primary", use_container_width=True):
            res = supabase.table("users").select("*").eq("user_name",u).execute()
            if res.data and res.data[0]["password"] == hash_password(p):
                st.session_state.current_user = u
                st.rerun()
            else:
                st.error("ユーザー名かパスワードが違います。")

    # --- サインアップ ---
    with tab_signup:
        u = st.text_input("好きなユーザー名", key="signup_name")
        p = st.text_input("好きなパスワード", type="password", key="signup_pass")
        if st.button("アカウントを作成する", type="primary", use_container_width=True):
            if not u or not p:
                st.warning("ユーザー名とパスワードを入力してください。")
            else:
                dup = supabase.table("users").select("id").eq("user_name",u).execute()
                if dup.data:
                    st.error("⚠️ その名前は既に使われています。")
                else:
                    supabase.table("users").insert(
                        {"user_name":u,"password":hash_password(p)}
                    ).execute()
                    base_cats = ["睡眠 🛌","大学（講義・研究） 📝","自主学習 ✏️","バイト 💼",
                                 "移動・通学 🚶","趣味・娯楽 🎮","食事・生活 🍳","その他 💬"]
                    supabase.table("timeline_categories").insert(
                        [{"user_name":u,"category_name":c} for c in base_cats]
                    ).execute()
                    st.success("🎉 アカウント作成完了！ログインしてください。")
    st.stop()

# -------------------------------------------------
# DB 読み込み
# -------------------------------------------------
user_name = st.session_state.current_user

def load_db():
    # カテゴリ
    cats = supabase.table("timeline_categories").select("category_name") \
            .eq("user_name",user_name).execute().data
    st.session_state.categories = [c["category_name"] for c in cats] if cats else ["未設定"]

    # ログ
    logs = supabase.table("timeline_data").select("*") \
            .eq("user_name",user_name).execute().data
    df = pd.DataFrame(logs) if logs else \
         pd.DataFrame(columns=["id","date","start_time","end_time","category","detail"])
    st.session_state.ui_log = df.rename(columns={
        "date":"日付","start_time":"開始時刻","end_time":"終了時刻",
        "category":"カテゴリ","detail":"内容"
    })

    # ルーティン
    rts = supabase.table("timeline_routine").select("*") \
            .eq("user_name",user_name).execute().data
    df_rt = pd.DataFrame(rts) if rts else \
            pd.DataFrame(columns=["id","weekday","start_time","end_time","category","detail"])
    st.session_state.ui_routine = df_rt.rename(columns={
        "weekday":"曜日","start_time":"開始時刻","end_time":"終了時刻",
        "category":"カテゴリ","detail":"内容"
    })
    st.session_state.need_reload = False

if st.session_state.need_reload:
    load_db()

ui_log     = st.session_state.ui_log
ui_routine = st.session_state.ui_routine
dynamic_colors = {c: PASTEL_PALETTE[i%len(PASTEL_PALETTE)]
                  for i,c in enumerate(st.session_state.categories)}

# -------------------------------------------------
# 共通関数
# -------------------------------------------------
def split_time_selectbox(label, default_h, default_m, key_suffix):
    st.markdown(f"<small style='color:#555;font-weight:bold;'>{label}</small>", unsafe_allow_html=True)
    hours = [f"{i:02d}" for i in range(24)]
    minutes = ["00","15","30","45"]
    c_h,c_m = st.columns(2)
    with c_h:
        h = st.selectbox("時", hours,
                         index=hours.index(f"{int(default_h):02d}"),
                         key=f"h_{key_suffix}", label_visibility="collapsed")
    with c_m:
        m = st.selectbox("分", minutes,
                         index=minutes.index(f"{int(default_m):02d}")
                         if f"{int(default_m):02d}" in minutes else 0,
                         key=f"m_{key_suffix}", label_visibility="collapsed")
    return f"{h}:{m}"

def check_overlap(date_str, s_str, e_str, df, exclude_id=None):
    if df.empty: return False,None
    dfc = df.copy()
    if exclude_id is not None:
        dfc = dfc[dfc["id"]!=exclude_id]
    if dfc.empty: return False,None

    ns  = pd.to_datetime(f"{date_str} {s_str}")
    ne  = pd.to_datetime(f"{date_str} {e_str}")
    if ne<=ns: ne += timedelta(days=1)

    dfc["Start_dt"] = pd.to_datetime(dfc["日付"] + " " + dfc["開始時刻"])
    dfc["End_dt"]   = pd.to_datetime(dfc["日付"] + " " + dfc["終了時刻"])
    dfc.loc[dfc["End_dt"]<dfc["Start_dt"],"End_dt"] += timedelta(days=1)

    ov = dfc[(ns < dfc["End_dt"]) & (ne > dfc["Start_dt"])]
    if not ov.empty:
        return True, ov.iloc[0]["カテゴリ"]
    return False,None

def round15(dt):
    discard = timedelta(minutes=dt.minute%15, seconds=dt.second,
                        microseconds=dt.microsecond)
    dt -= discard
    if discard >= timedelta(minutes=7,seconds=30):
        dt += timedelta(minutes=15)
    return dt

def merge_continuous(df):
    if df.empty: return df
    d = df.copy()
    d["Start_dt"] = pd.to_datetime(d["日付"]+" "+d["開始時刻"])
    d["End_dt"]   = pd.to_datetime(d["日付"]+" "+d["終了時刻"])
    d.loc[d["End_dt"]<d["Start_dt"],"End_dt"] += timedelta(days=1)
    d = d.sort_values("Start_dt").reset_index(drop=True)

    merged = []
    cur = d.iloc[0].to_dict()
    for i in range(1,len(d)):
        nxt = d.iloc[i].to_dict()
        if cur["End_dt"]==nxt["Start_dt"] and cur["カテゴリ"]==nxt["カテゴリ"]:
            cur["End_dt"]     = nxt["End_dt"]
            cur["終了時刻"]   = nxt["終了時刻"]
            if cur["内容"]!=nxt["内容"] and nxt["内容"]!="（未入力）":
                cur["内容"] = ("" if cur["内容"]=="（未入力）" else cur["内容"]+", ")+nxt["内容"]
        else:
            merged.append(cur); cur=nxt
    merged.append(cur)
    return pd.DataFrame(merged)

# -------------------------------------------------
# 🗓️ ヘッダー / ログアウト
# -------------------------------------------------
col_user,col_out = st.columns([3,1])
with col_user:
    st.markdown(f"**👤 {user_name}** さん")
with col_out:
    if st.button("🚪 ログアウト", use_container_width=True):
        st.session_state.current_user = None
        st.rerun()

st.markdown("<h2 style='text-align:center;font-size:1.5rem;"
            "margin-top:-10px;margin-bottom:0;'>時間管理表</h2>",
            unsafe_allow_html=True)

c1,c2,c3 = st.columns([1,2,1])
with c1:
    if st.button("◀ 前日", use_container_width=True):
        st.session_state.target_date -= timedelta(days=1); st.rerun()
with c2:
    sel = st.date_input("日付", st.session_state.target_date,
                        label_visibility="collapsed")
    if sel!=st.session_state.target_date:
        st.session_state.target_date = sel; st.rerun()
with c3:
    if st.button("翌日 ▶", use_container_width=True):
        st.session_state.target_date += timedelta(days=1); st.rerun()

date_str = st.session_state.target_date.strftime("%Y-%m-%d")
weekday  = WEEKDAYS[st.session_state.target_date.weekday()]
st.markdown(f"<div style='text-align:center;font-size:0.95rem;"
            f"font-weight:bold;margin-bottom:10px;'>{date_str} ({weekday})</div>",
            unsafe_allow_html=True)

# -------------------------------------------------
# 📊 タイムライン描画
# -------------------------------------------------
if not ui_log.empty:
    raw = ui_log.copy()
    day_raw = raw[raw["日付"]==date_str].copy()
    sod = pd.to_datetime(f"{date_str} 00:00:00")
    eod = sod + timedelta(days=1)

    if not day_raw.empty:
        day = merge_continuous(day_raw)
        day["時間(h)"] = (day["End_dt"]-day["Start_dt"]).dt.total_seconds()/3600.0
        day["文字"] = day.apply(
            lambda r: r["カテゴリ"] if
            (r["End_dt"]-r["Start_dt"]).total_seconds()/60>=45 else "", axis=1)

        fig = px.timeline(day, x_start="Start_dt", x_end="End_dt", y="日付",
                          color="カテゴリ", text="文字",
                          hover_name="内容", height=180,
                          color_discrete_map=dynamic_colors)
        fig.update_traces(textposition='inside',
                          insidetextanchor='middle',
                          textfont_size=15, marker_line_width=0)
        fig.update_layout(xaxis=dict(tickformat="%H:%M",range=[sod,eod],
                          dtick=14400000,fixedrange=True,
                          tickfont=dict(size=13,color="#555")),
                          yaxis=dict(showticklabels=False,fixedrange=True),
                          showlegend=False,dragmode=False,
                          margin=dict(l=10,r=10,t=10,b=85),
                          plot_bgcolor='rgba(0,0,0,0)',
                          paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar":False})

        total = day["時間(h)"].sum()
        st.info(f"✨ 記録済み: {round(total,1)} 時間 "
                f"（空き: {round(24-total,1)} 時間）")
    else:
        empty = pd.DataFrame({"日付":[date_str],
                              "Start_dt":[sod],"End_dt":[sod],
                              "カテゴリ":["未記録"]})
        fig = px.timeline(empty, x_start="Start_dt", x_end="End_dt", y="日付", height=130)
        fig.update_layout(xaxis=dict(tickformat="%H:%M",range=[sod,eod],
                          dtick=14400000,fixedrange=True),
                          yaxis=dict(showticklabels=False,fixedrange=True),
                          showlegend=False,dragmode=False,
                          margin=dict(l=0,r=0,t=0,b=0),
                          plot_bgcolor='rgba(0,0,0,0)',
                          paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar":False})
st.markdown("---")

# -------------------------------------------------
# 📱 モード切替ボタン
# -------------------------------------------------
def change_mode(m): st.session_state.app_mode = m

btns = ["⏱️ 計測","📝 追加","📊 分析"]
cols = st.columns(3)
for i,b in enumerate(btns):
    with cols[i]:
        if st.button(b, type="primary" if st.session_state.app_mode==b else "secondary",
                     use_container_width=True):
            change_mode(b); st.rerun()

btns2 = ["⚙️ 固定","📜 編集・削除","🏷️ カテゴリ"]
cols = st.columns(3)
for i,b in enumerate(btns2):
    with cols[i]:
        if st.button(b, type="primary" if st.session_state.app_mode==b else "secondary",
                     use_container_width=True):
            change_mode(b); st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
mode = st.session_state.app_mode

# -------------------------------------------------
# 各モード処理
# -------------------------------------------------
# 1. ⏱️ 計測モード
if mode=="⏱️ 計測":
    if st.session_state.tracking_start is None:
        if not st.session_state.categories:
            st.warning("カテゴリがありません。")
        else:
            rt_cat = st.selectbox("カテゴリを選ぶ", st.session_state.categories, key="rt_cat")
            if st.button("▶️ 今からスタート！", type="primary", use_container_width=True):
                st.session_state.tracking_cat = rt_cat
                st.session_state.tracking_start = get_now_jst()
                st.rerun()
    else:
        st.success(f"⏳ {st.session_state.tracking_cat} 計測中\n\n"
                   f"開始: {st.session_state.tracking_start.strftime('%H:%M')}")
        rt_det = st.text_input("メモ（任意）", key="rt_detail")
        if st.button("⏹️ 今終わった！（15分単位で記録）",
                     type="primary", use_container_width=True):
            end_dt = get_now_jst()
            s_ = round15(st.session_state.tracking_start)
            e_ = round15(end_dt)
            if s_==e_: e_ += timedelta(minutes=15)
            s_str, e_str = s_.strftime('%H:%M'), e_.strftime('%H:%M')
            rec_date = s_.strftime('%Y-%m-%d')

            ov,cat = check_overlap(rec_date,s_str,e_str,ui_log)
            if ov:
                st.error(f"⚠️ 「{cat}」と重なっています。")
            else:
                supabase.table("timeline_data").insert({
                    "user_name":user_name,
                    "date":rec_date,"start_time":s_str,"end_time":e_str,
                    "category":st.session_state.tracking_cat,
                    "detail": rt_det if rt_det else "（未入力）"
                }).execute()
                st.session_state.need_reload = True
            st.session_state.tracking_cat = None
            st.session_state.tracking_start = None
            st.rerun()

        if st.button("❌ 計測をキャンセル", use_container_width=True):
            st.session_state.tracking_cat = None
            st.session_state.tracking_start = None
            st.rerun()

# 2. 📝 追加モード
elif mode=="📝 追加":
    if not st.session_state.categories:
        st.warning("カテゴリがありません。")
    else:
        cat = st.selectbox("カテゴリ", st.session_state.categories, key="man_cat")
        s_str = split_time_selectbox("🛫 開始時刻", 9,0,"add_s")
        e_str = split_time_selectbox("🛬 終了時刻",10,0,"add_e")
        det   = st.text_input("メモ", key="man_detail")

        if st.button("手動で追加する", use_container_width=True):
            if s_str==e_str:
                st.warning("開始と終了が同じです。")
            else:
                ov,cat_ = check_overlap(date_str,s_str,e_str,ui_log)
                if ov:
                    st.error(f"⚠️ 既に「{cat_}」が入っています！")
                else:
                    supabase.table("timeline_data").insert({
                        "user_name":user_name,"date":date_str,
                        "start_time":s_str,"end_time":e_str,
                        "category":cat,
                        "detail": det if det else "（未入力）"
                    }).execute()
                    st.session_state.need_reload=True
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(f"✨ {weekday}曜日のルーティンを一括追加",
                 use_container_width=True):
        r_for_day = ui_routine[ui_routine["曜日"]==weekday]
        if r_for_day.empty:
            st.warning("ルーティンが設定されていません。")
        else:
            for _,r in r_for_day.iterrows():
                ov,_ = check_overlap(date_str,r["開始時刻"],r["終了時刻"],ui_log)
                if not ov:
                    supabase.table("timeline_data").insert({
                        "user_name":user_name,"date":date_str,
                        "start_time":r["開始時刻"],"end_time":r["終了時刻"],
                        "category":r["カテゴリ"],"detail":r["内容"]
                    }).execute()
            st.session_state.need_reload=True
            st.rerun()

# 3. 📊 分析モード
elif mode=="📊 分析":
    st.markdown("#### 時間の使い方のバランス")
    period = st.selectbox("分析する期間",
                          ["過去7日間","過去30日間","全期間","今日"])
    if ui_log.empty:
        st.write("データがありません。")
    else:
        dfa = ui_log.copy()
        dfa["D"] = pd.to_datetime(dfa["日付"]).dt.date
        today = get_now_jst().date()
        if period=="今日":
            filt = dfa[dfa["D"]==today]
        elif period=="過去7日間":
            filt = dfa[dfa["D"] >= today - timedelta(days=6)]
        elif period=="過去30日間":
            filt = dfa[dfa["D"] >= today - timedelta(days=29)]
        else:
            filt = dfa
        if filt.empty:
            st.warning("この期間の記録はありません。")
        else:
            merged = pd.concat([merge_continuous(x) for _,x in filt.groupby("日付")])
            merged["時間(h)"] = (merged["End_dt"]-merged["Start_dt"]).dt.total_seconds()/3600.0
            sm = merged.groupby("カテゴリ")["時間(h)"].sum().reset_index()
            total_h = round(sm["時間(h)"].sum(),1)

            fig = px.pie(sm, values='時間(h)', names='カテゴリ',
                         color='カテゴリ', color_discrete_map=dynamic_colors,
                         hole=0.4)
            fig.update_traces(textinfo='percent+label', textposition='outside',
                              marker_line_width=0)
            fig.add_annotation(text=f"<b>計 {total_h}h</b>",
                               x=0.5,y=0.5,font_size=18,showarrow=False)
            fig.update_layout(showlegend=False,margin=dict(t=40,b=40,l=40,r=40),
                              height=380,
                              plot_bgcolor='rgba(0,0,0,0)',
                              paper_bgcolor='rgba(0,0,0,0)',
                              font=dict(size=14))
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar":False})

            tbl = sm.sort_values("時間(h)",ascending=False).copy()
            tbl["割合"] = (tbl["時間(h)"]/total_h*100).round(1).astype(str)+" %"
            tbl["合計時間"] = tbl["時間(h)"].round(1).astype(str)+" 時間"
            st.dataframe(tbl[["カテゴリ","合計時間","割合"]],
                         use_container_width=True, hide_index=True)

# 4. 📜 編集・削除モード
elif mode=="📜 編集・削除":
    st.markdown(f"#### {date_str} の記録・編集")
    if ui_log.empty:
        st.write("データがありません。")
    else:
        tgt = ui_log[ui_log["日付"]==date_str].copy()
        if tgt.empty:
            st.write("今日の記録はありません。")
        else:
            tgt = tgt.sort_values("開始時刻")
            for _,row in tgt.iterrows():
                editing = (st.session_state.editing_log_id == row["id"])
                st.markdown("<div class='list-card'>", unsafe_allow_html=True)
                if not editing:
                    c1,c2,c3 = st.columns([3.5,1,1])
                    with c1:
                        st.markdown(f"**{row['開始時刻']} 〜 {row['終了時刻']}**")
                        st.markdown(f"**{row['カテゴリ']}** "
                                    f"<small>{row['内容']}</small>",
                                    unsafe_allow_html=True)
                    with c2:
                        if st.button("✏️", key=f"e_{row['id']}",
                                     use_container_width=True):
                            st.session_state.editing_log_id = row["id"]; st.rerun()
                    with c3:
                        if st.button("🗑️", key=f"d_{row['id']}",
                                     use_container_width=True):
                            supabase.table("timeline_data").delete() \
                                .eq("id",row["id"]).execute()
                            st.session_state.need_reload=True; st.rerun()
                else:
                    st.markdown("<p style='font-size:0.85rem;"
                                "color:#f03e3e;font-weight:bold;'>"
                                "📝 データを編集中...</p>",
                                unsafe_allow_html=True)
                    ed_cat = st.selectbox("カテゴリ", st.session_state.categories,
                                          index=st.session_state.categories.index(
                                            row["カテゴリ"]) \
                                            if row["カテゴリ"] in st.session_state.categories else 0,
                                          key=f"edcat_{row['id']}")

                    sh,sm = map(int,row["開始時刻"].split(":"))
                    eh,em = map(int,row["終了時刻"].split(":"))
                    ns = split_time_selectbox("🛫 変更後の開始時刻", sh,sm,
                                              f"eds_{row['id']}")
                    ne = split_time_selectbox("🛬 変更後の終了時刻", eh,em,
                                              f"ede_{row['id']}")
                    ed_det = st.text_input("メモ内容", value=row["内容"],
                                           key=f"eddet_{row['id']}")
                    c1,c2 = st.columns(2)
                    with c1:
                        if st.button("💾 変更を保存", type="primary",
                                     key=f"sv_{row['id']}", use_container_width=True):
                            if ns==ne:
                                st.error("⚠️ 同じ時刻です。")
                            else:
                                ov,cat_ = check_overlap(date_str,ns,ne,ui_log,
                                                        exclude_id=row["id"])
                                if ov:
                                    st.error(f"⚠️ 「{cat_}」と重なっています！")
                                else:
                                    supabase.table("timeline_data").update({
                                        "start_time":ns,"end_time":ne,
                                        "category":ed_cat,
                                        "detail": ed_det if ed_det else "（未入力）"
                                    }).eq("id",row["id"]).execute()
                                    st.session_state.editing_log_id=None
                                    st.session_state.need_reload=True; st.rerun()
                    with c2:
                        if st.button("❌ キャンセル", key=f"cl_{row['id']}",
                                     use_container_width=True):
                            st.session_state.editing_log_id=None; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

# 5. ⚙️ 固定ルーティンモード
elif mode=="⚙️ 固定":
    st.markdown("#### 新規追加")
    if not st.session_state.categories:
        st.warning("カテゴリがありません。")
    else:
        c1,c2 = st.columns(2)
        with c1:
            r_day = st.selectbox("曜日", WEEKDAYS)
        with c2:
            r_cat = st.selectbox("カテゴリ", st.session_state.categories)

        r_s = split_time_selectbox("🛫 開始", 9,0,"rt_s")
        r_e = split_time_selectbox("🛬 終了",10,0,"rt_e")
        r_det = st.text_input("メモ（任意）", key="rt_det")
        if st.button("➕ ルーティンを追加", use_container_width=True):
            supabase.table("timeline_routine").insert({
                "user_name":user_name,"weekday":r_day,
                "start_time":r_s,"end_time":r_e,
                "category":r_cat,
                "detail": r_det if r_det else "（未入力）"
            }).execute()
            st.session_state.need_reload=True; st.rerun()

    st.markdown("#### 登録済み一覧")
    if ui_routine.empty:
        st.write("登録されていません。")
    else:
        for _,row in ui_routine.iterrows():
            st.markdown("<div class='list-card'>", unsafe_allow_html=True)
            c1,c2 = st.columns([4,1])
            with c1:
                st.markdown(f"**{row['曜日']}** | "
                            f"{row['開始時刻']}〜{row['終了時刻']}")
                st.markdown(f"**{row['カテゴリ']}** {row['内容']}")
            with c2:
                if st.button("🗑️", key=f"dr_{row['id']}",
                             use_container_width=True):
                    supabase.table("timeline_routine").delete() \
                        .eq("id",row["id"]).execute()
                    st.session_state.need_reload=True; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# 6. 🏷️ カテゴリモード
elif mode=="🏷️ カテゴリ":
    st.markdown("#### カテゴリの編集")
    df_cat = pd.DataFrame(st.session_state.categories, columns=["カテゴリ名"])
    ed = st.data_editor(df_cat, num_rows="dynamic",
                        use_container_width=True, key="cat_editor")
    if st.button("💾 変更を保存する", type="primary", use_container_width=True):
        new_cats = ed["カテゴリ名"].dropna().astype(str).str.strip().tolist()
        new_cats = [c for c in new_cats if c and c!="None"]
        new_cats = list(dict.fromkeys(new_cats))
        if new_cats:
            supabase.table("timeline_categories").delete() \
                .eq("user_name",user_name).execute()
            supabase.table("timeline_categories").insert(
                [{"user_name":user_name,"category_name":c} for c in new_cats]
            ).execute()
            st.session_state.need_reload=True; st.rerun()
