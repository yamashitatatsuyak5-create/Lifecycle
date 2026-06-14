import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import plotly.express as px
from supabase import create_client, Client
import hashlib

# -------------------------------
# 画面基本設定
# -------------------------------
st.set_page_config(page_title="ライフログ",
                   layout="wide",
                   initial_sidebar_state="collapsed")

# -------------------------------
# Supabase 接続
# -------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# スタイル + キーボード殺し JS
# -------------------------------
st.markdown("""
<style>
[data-testid="stHeader"]{visibility:hidden;}
.block-container{padding-top:1rem;padding-bottom:5rem;}
div.stButton>button{
    border-radius:12px!important;
    font-weight:bold!important;
}
.list-card{
    background:rgba(0,0,0,.03);
    padding:15px;border-radius:15px;margin-bottom:10px;
    border:1px solid rgba(0,0,0,.1);
}
</style>

<!-- すべてのプルダウンに対してモバイルキーボードを抑止 -->
<script>
function killMobileKeyboard () {

  const lockAll = () => {
    const q =
    `div[data-testid^="stSelect"]    input,
     div[data-testid^="stDateInput"] input,
     div[data-testid^="stTimeInput"] input`;

    const inputs = window.parent.document.querySelectorAll(q);

    inputs.forEach(inp=>{
      if(inp.dataset.keyboardLocked) return;

      inp.readOnly  = true;          // 文字入力不可
      inp.inputMode = 'none';        // ソフトKB抑止
      inp.style.caretColor='transparent';

      inp.addEventListener('focus', ()=>inp.blur(), {passive:true});
      inp.dataset.keyboardLocked = 'true';
    });
  };

  // 初回実行
  lockAll();

  // 以後 DOM 変化のたびに実行
  const obs=new MutationObserver(lockAll);
  obs.observe(window.parent.document,{childList:true,subtree:true});
}

if(window.parent){
  if(document.readyState==='loading'){
    window.parent.addEventListener('DOMContentLoaded',killMobileKeyboard);
  }else{
    killMobileKeyboard();
  }
}
</script>
""", unsafe_allow_html=True)

# -------------------------------
# 定数／共通関数
# -------------------------------
WEEKDAYS = ["月","火","水","木","金","土","日"]
PASTEL_PALETTE = ["#B3E5FC","#C8E6C9","#FFF59D","#FFE0B2",
                  "#E1BEE7","#FFCDD2","#F8BBD0",
                  "#CFD8DC","#D7CCC8","#FFE082"]

def hash_password(pw): return hashlib.sha256(pw.encode()).hexdigest()
def get_now_jst():      return datetime.utcnow() + timedelta(hours=9)

# -------------------------------
# SessionState 初期化
# -------------------------------
defaults = {
    "current_user"   : None,
    "target_date"    : get_now_jst().date(),
    "app_mode"       : "⏱️ 計測",
    "editing_log_id" : None,
    "tracking_start" : None,   # ← 追加
    "tracking_cat"   : None,   # ← 追加
}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# -------------------------------
# 🔐 ログイン / サインアップ
# -------------------------------
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
                    # デフォルトカテゴリ
                    base = ["睡眠 🛌","大学（講義・研究） 📝","自主学習 ✏️","バイト 💼",
                            "移動・通学 🚶","趣味・娯楽 🎮","食事・生活 🍳","その他 💬"]
                    supabase.table("timeline_categories").insert(
                        [{"user_name":u,"category_name":c} for c in base]
                    ).execute()
                    st.success("🎉 アカウント作成完了！ログインしてください。")
    st.stop()

# -------------------------------
# データ読み込み
# -------------------------------
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

if "need_reload" not in st.session_state or st.session_state.need_reload:
    load_db()

ui_log     = st.session_state.ui_log
ui_routine = st.session_state.ui_routine
dynamic_colors = {c: PASTEL_PALETTE[i%len(PASTEL_PALETTE)]
                  for i,c in enumerate(st.session_state.categories)}

# -------------------------------
# 以降のアプリ本体
# -------------------------------
# ・・・この下はご質問のオリジナルコードをそのまま残して OK・・・
#     （編集・追加・分析等のロジックは変更無し）
# --------------------------------------------------------------------
# ここではサイズ削減のため省略しますが、上記 “読み込み” までを書き換えれば
# あとの UI・処理はそのまま動作します。
# --------------------------------------------------------------------
