import streamlit as st
import re
import requests
import pandas as pd
import os
import datetime
import time
import urllib.parse
from streamlit_gsheets import GSheetsConnection

# --- 設定 ---
CATEGORY_LIST = ["小説", "Stoicism", "語学", "キャリア", "AI", "ビジネス", "ノンフィクション", "エッセイ", "その他"]
LANGUAGE_LIST = ["日本語", "英語", "スペイン語"]
STATUS_LIST = ["読了", "読書中", "読みたい", "断念"]

# --- ページの設定 ---
st.set_page_config(page_title="Reading Log", page_icon="📚", layout="wide")

# --- 初期化 (Session State) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None
if 'active_detail_index' not in st.session_state:
    st.session_state.active_detail_index = None
if 'filter_reset_key' not in st.session_state:
    st.session_state.filter_reset_key = 0

# --- デザイン ---
st.markdown("""
<style>
/* フォントと全体背景 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Outfit:wght@500;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3, h4 { font-family: 'Outfit', sans-serif; }
.stApp { background: linear-gradient(135deg, #f8fafd 0%, #e8edf3 100%); }

/* 既存ボタンのスタイル（管理画面等） */
.stButton>button { 
    border-radius: 10px; border: 1px solid #cbd5e1; background-color: white; color: #475569;
    transition: all 0.3s ease; font-weight: 500;
}
.stButton>button:hover { border-color: #94a3b8; background-color: #f8fafc; color: #1e293b; }

/* --- 本棚ギャラリーのCSS --- */
/* 書影のスタイル */
.book-cover {
    width: 100%;
    aspect-ratio: 2/3;
    object-fit: cover;
    border-radius: 8px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    transition: all 0.4s ease;
    display: block;
}
.book-cover:hover {
    transform: translateY(-5px);
    box-shadow: 0 15px 30px rgba(0,0,0,0.2);
}

/* グリッド内のボタンを「豆アイコン」にする */
.grid-btn button {
    width: 32px !important;
    height: 32px !important;
    min-height: 32px !important;
    padding: 0 !important;
    border-radius: 50% !important;
    background: rgba(255,255,255,0.9) !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
    font-size: 14px !important;
    line-height: 32px !important;
    margin-top: -40px !important;
    margin-left: auto !important;
    margin-right: 5px !important;
    display: block !important;
    position: relative !important;
    z-index: 10 !important;
}
.grid-btn button:hover {
    background: white !important;
    transform: scale(1.1) !important;
}

/* サイドバーをコンパクトに */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0.3rem !important;
}
[data-testid="stSidebar"] .stSelectbox, 
[data-testid="stSidebar"] .stTextInput {
    margin-bottom: 0 !important;
}
[data-testid="stSidebar"] {
    font-size: 0.85rem !important;
}
[data-testid="stSidebar"] h1 {
    font-size: 1.3rem !important;
    margin-bottom: 0.5rem !important;
}
[data-testid="stSidebar"] .stButton > button {
    padding: 0.3rem 0.8rem !important;
    font-size: 0.85rem !important;
}
[data-testid="stSidebar"] .stRadio > div {
    gap: 0.2rem !important;
}
[data-testid="stSidebar"] .stRadio label {
    font-size: 0.85rem !important;
}
[data-testid="stSidebar"] [data-testid="stAlert"] {
    padding: 0.4rem 0.6rem !important;
    font-size: 0.8rem !important;
}
[data-testid="stSidebar"] hr {
    margin: 0.5rem 0 !important;
}
/* --- Notion風リストのCSS --- */
.notion-list-item {
    display: flex;
    align-items: flex-start;
    background: white;
    padding: 12px;
    border-radius: 12px;
    margin-bottom: 15px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    transition: transform 0.2s ease;
    border: 1px solid #edf2f7;
}
.notion-list-item:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.notion-cover {
    width: 80px;
    height: 110px;
    object-fit: cover;
    border-radius: 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    margin-right: 15px;
    flex-shrink: 0;
}
.notion-content {
    flex-grow: 1;
    min-width: 0; /* 折り返しを正常にするため */
}
.notion-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 2px;
    line-height: 1.3;
}
.notion-author {
    font-size: 0.9rem;
    color: #64748b;
    margin-bottom: 8px;
}
.notion-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
}
.notion-tag {
    font-size: 0.75rem;
    padding: 2px 8px;
    border-radius: 4px;
    background: #f1f5f9;
    color: #475569;
}
.notion-rating {
    color: #f59e0b;
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: 6px;
}
.notion-comment {
    font-size: 0.85rem;
    color: #475569;
    line-height: 1.4;
    border-left: 3px solid #e2e8f0;
    padding-left: 8px;
    margin-top: 5px;
}
.notion-footer {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 8px;
    text-align: right;
}
</style>
""", unsafe_allow_html=True)

# --- サイドバー (管理・設定) ---
st.sidebar.markdown(
    "<h1 style='font-size: 1.5rem; margin-bottom: 0px; margin-top: -30px;'>📚 読書記録</h1>", 
    unsafe_allow_html=True
)

# 1. 認証セクション
if not st.session_state.authenticated:
    with st.sidebar.expander("🔐 管理ログイン"):
        pw = st.text_input("パスワードを入力", type="password")
        if pw == "251225":
            st.session_state.authenticated = True
            st.rerun()
        elif pw != "":
            st.error("× パスワードが違います")
else:
    # ログイン状態のUI
    st.sidebar.markdown(
        "<div style='background-color: #dcfce7; padding: 5px 10px; border-radius: 5px; font-size: 0.8rem; color: #166534; margin-bottom: 10px;'>✅ 編集モード：有効</div>", 
        unsafe_allow_html=True
    )
    
    if st.sidebar.button("ログアウト", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.edit_index = None
        st.rerun()
    st.sidebar.markdown("---")

# --- 関数 ---
def update_gsheet(df_all):
    try:
        conn.update(worksheet="Sheet1", data=df_all)
        return True
    except Exception as e:
        st.error(f"書き込みエラー: {e}")
        return False

def get_search_results(query):
    # ASIN/ISBNの抽出（URLの場合）
    asin_match = re.search(r"/(?:dp|product|ASID|ASIN|ebook)/([A-Z0-9]{10,13})", query)
    search_q = query
    if asin_match:
        search_q = asin_match.group(1)
    else:
        # URLからキーワードを抽出
        slug_match = re.search(r"jp/([^/]+)/(?:dp|product|ebook|ASID|ASIN)", query)
        if slug_match:
            decoded = urllib.parse.unquote(slug_match.group(1))
            raw_words = re.findall(r"[\wéàèùâêîôûëïü]+", decoded)
            search_q = " ".join([w for w in raw_words if w.lower() not in ["novel", "english", "ebook", "kindle", "edition", "paperback", "hardcover"]])

    safe_q = urllib.parse.quote(search_q)
    # 地域制限を回避するため、country=JPパラメータを追加
    api_url = f"https://www.googleapis.com/books/v1/volumes?q={safe_q}&country=JP&maxResults=5"
    results = []
    try:
        # より詳細なヘッダーを追加して、正規のブラウザからのアクセスに見せる
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Referer": "https://www.google.com/"
        }
        res = requests.get(api_url, headers=headers, timeout=10).json()
        if "items" in res:
            for item in res["items"]:
                v = item.get("volumeInfo", {})
                img = v.get("imageLinks", {}).get("thumbnail", "").replace("zoom=1", "zoom=0")
                if img:
                     img = img.replace("http://", "https://")
                results.append({
                    "title": v.get("title", "不明なタイトル"),
                    "authors": ", ".join(v.get("authors", ["不明な著者"])),
                    "thumbnail": img
                })
        elif "error" in res:
            st.error(f"APIエラー: {res['error'].get('message')}")
    except Exception as e:
        st.error(f"検索中にエラーが発生しました: {e}")
    return results

    # ダイアログではなく、メイン画面にexpanderで展開する方式に変更（動作安定化のため）
    pass

def render_registration_ui():
    """メイン画面に表示する登録フォーム"""
    if 'new_book' not in st.session_state:
        st.session_state.new_book = {"title": "", "authors": "", "thumbnail": "", "url": ""}
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    
    with st.expander("➕ 新しい本を登録する", expanded=st.session_state.get('show_reg_ui', False)):
        # 登録画面を開くときは詳細を閉じておく
        st.session_state.active_detail_index = None
        st.markdown("##### 1. 本を検索")
        col_s1, col_s2 = st.columns([4, 1])
        with col_s1:
            search_input_val = st.text_input("Amazon URL または タイトル", value=st.session_state.new_book["url"], placeholder="例: 夏目漱石 こころ", key="search_input_main")
        with col_s2:
            st.write("")
            if st.button("検索", use_container_width=True, key="search_btn_main"):
                if search_input_val:
                    st.session_state.new_book["url"] = search_input_val
                    with st.spinner("検索中..."):
                        res = get_search_results(search_input_val)
                        st.session_state.search_results = res
                        if not res:
                            st.warning("見つかりませんでした")
                        else:
                            st.success(f"{len(res)}件見つかりました！下から選択してください")
                else:
                    st.warning("検索キーワードを入力してください")

        # 検索候補
        if st.session_state.search_results:
            st.markdown("##### 候補から選択:")
            cols = st.columns(len(st.session_state.search_results))
            for i, res in enumerate(st.session_state.search_results):
                with cols[i]:
                    if res["thumbnail"]: st.image(res["thumbnail"], use_container_width=True)
                    else: st.write("No Image")
                    # タイトルが長い場合は切り詰める
                    short_title = res['title'][:15] + "..." if len(res['title']) > 15 else res['title']
                    st.caption(f"{short_title}")
                    
                    if st.button("選択", key=f"sel_{i}", use_container_width=True):
                        st.session_state.new_book.update(res)
                        st.session_state.search_results = [] # 候補をクリア
                        st.rerun()
            st.divider()

        st.markdown("##### 2. 詳細を入力して登録")
        with st.form("new_book_main_form"):
            f_title = st.text_input("タイトル (必須)", value=st.session_state.new_book["title"])
            f_author = st.text_input("著者", value=st.session_state.new_book["authors"])
            f_img = st.text_input("画像URL", value=st.session_state.new_book["thumbnail"])
            
            c1, c2, c3 = st.columns(3)
            with c1: f_cat = st.selectbox("カテゴリ", CATEGORY_LIST)
            with c2: f_lang = st.selectbox("言語", LANGUAGE_LIST)
            with c3: f_stat = st.selectbox("ステータス", STATUS_LIST)
            
            f_rate = st.select_slider("評価", options=["1", "2", "3", "4", "5"], value="3")
            f_comment = st.text_area("コメント", placeholder="感想などを入力")
            f_dates = st.date_input("読書期間", [datetime.date.today(), datetime.date.today()])
            
            st.markdown("---")
            confirm = st.checkbox("内容を確認しました（誤操作防止）", key="reg_confirm")
            
            if st.form_submit_button("保存する", type="primary", use_container_width=True):
                if not f_title:
                    st.error("タイトルは必須です")
                elif not confirm:
                    st.error("⚠️ 保存するにはチェックボックスを入れてください")
                else:
                    sd = f_dates[0].strftime("%Y-%m-%d") if len(f_dates) > 0 else ""
                    ed = f_dates[1].strftime("%Y-%m-%d") if len(f_dates) > 1 else sd
                    # 既存のdf_booksを参照するためにglobal宣言は避け、引数かst.session_stateから取得する設計が望ましいが
                    # 簡易対応としてst.connectionから再取得して追記する
                    record = {"タイトル": f_title, "著者": f_author, "評価": f_rate, "カテゴリ": f_cat, "言語": f_lang, "ステータス": f_stat, "コメント": f_comment, "開始日": sd, "読了日": ed, "画像URL": f_img}
                    
                    # 読み書き用コネクション再取得
                    conn_w = st.connection("gsheets", type=GSheetsConnection)
                    current_df = conn_w.read()
                    updated_df = pd.concat([current_df, pd.DataFrame([record])], ignore_index=True)
                    try:
                        conn_w.update(worksheet="Sheet1", data=updated_df)
                        st.toast("登録しました！")
                        # フォームリセット
                        st.session_state.new_book = {"title": "", "authors": "", "thumbnail": "", "url": ""}
                        st.session_state.show_reg_ui = False # 閉じる
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存エラー: {e}")

@st.dialog("✏️ 本の情報を編集", width="large")
def show_edit_dialog(index):
    edit_data = df_books.loc[index]
    with st.form("edit_form"):
        f_title = st.text_input("タイトル", value=str(edit_data.get("タイトル", "")) if str(edit_data.get("タイトル", "")) != 'nan' else "")
        f_author = st.text_input("著者", value=str(edit_data.get("著者", "")) if str(edit_data.get("著者", "")) != 'nan' else "")
        
        # 画像URLの処理（nanチェック）
        img_val = edit_data.get("画像URL", "")
        img_val = str(img_val) if str(img_val) != 'nan' else ""
        f_img = st.text_input("画像URL", value=img_val)
        if f_img and f_img.startswith("http"):
            st.image(f_img, width=100)
        
        c1, c2, c3 = st.columns(3)
        with c1: 
            d_cat = str(edit_data.get("カテゴリ", "")) if str(edit_data.get("カテゴリ", "")) != 'nan' else "その他"
            f_cat = st.selectbox("カテゴリ", CATEGORY_LIST, index=CATEGORY_LIST.index(d_cat) if d_cat in CATEGORY_LIST else 0)
        with c2:
            d_lang = str(edit_data.get("言語", "")) if str(edit_data.get("言語", "")) != 'nan' else "日本語"
            f_lang = st.selectbox("言語", LANGUAGE_LIST, index=LANGUAGE_LIST.index(d_lang) if d_lang in LANGUAGE_LIST else 0)
        with c3:
            d_stat = str(edit_data.get("ステータス", "")) if str(edit_data.get("ステータス", "")) != 'nan' else "読了"
            f_stat = st.selectbox("ステータス", STATUS_LIST, index=STATUS_LIST.index(d_stat) if d_stat in STATUS_LIST else 0)
        
        try:
            rate_val = edit_data.get("評価", "3")
            # 安全に数値化し、1〜5の範囲に収める
            if str(rate_val) == 'nan' or str(rate_val) == '':
                val_int = 3
            else:
                val_int = int(float(rate_val))
            
            if val_int < 1: val_int = 1
            if val_int > 5: val_int = 5
            d_rate = str(val_int)
        except: d_rate = "3"
        f_rate = st.select_slider("評価", options=["1", "2", "3", "4", "5"], value=d_rate)
        
        comment_val = edit_data.get("コメント", "")
        f_comment = st.text_area("コメント", value=str(comment_val) if str(comment_val) != 'nan' else "")
        
        # 日付の処理を修正
        try:
            sd_val = str(edit_data.get("開始日", ""))
            ed_val = str(edit_data.get("読了日", ""))
            if sd_val and sd_val != 'nan':
                start_date = datetime.datetime.strptime(sd_val, "%Y-%m-%d").date()
            else:
                start_date = datetime.date.today()
            if ed_val and ed_val != 'nan':
                end_date = datetime.datetime.strptime(ed_val, "%Y-%m-%d").date()
            else:
                end_date = datetime.date.today()
        except:
            start_date = datetime.date.today()
            end_date = datetime.date.today()
        f_dates = st.date_input("読書期間", value=(start_date, end_date))
        
        st.divider()
        confirm = st.checkbox("内容を確認しました（誤操作防止）")
        
        if st.form_submit_button("💾 更新を保存する", use_container_width=True):
            if not confirm:
                st.error("⚠️ 保存するにはチェックボックスを入れてください")
            else:
                # f_datesがタプルかリストかを確認
                if isinstance(f_dates, (list, tuple)) and len(f_dates) >= 2:
                    sd = f_dates[0].strftime("%Y-%m-%d")
                    ed = f_dates[1].strftime("%Y-%m-%d")
                else:
                    sd = f_dates.strftime("%Y-%m-%d") if hasattr(f_dates, 'strftime') else str(datetime.date.today())
                    ed = sd
                record = {"タイトル": f_title, "著者": f_author, "評価": f_rate, "カテゴリ": f_cat, "言語": f_lang, "ステータス": f_stat, "コメント": f_comment, "開始日": sd, "読了日": ed, "画像URL": f_img}
                df_books.loc[index] = record
                if update_gsheet(df_books):
                    st.toast("データが正常に更新されました！", icon="✅")
                    time.sleep(1.5)
                    st.session_state.edit_index = None
                    st.cache_data.clear()
                    st.rerun()
    
    if st.button("❌ 編集をキャンセル", use_container_width=True):
        st.session_state.edit_index = None
        st.rerun()

@st.dialog("📖 本の詳細", width="large")
def show_detail_dialog(row, index):
    col1, col2 = st.columns([1, 2])
    with col1:
        img_url = row["画像URL"]
        if isinstance(img_url, str) and img_url != "" and str(img_url) != 'nan':
            st.image(img_url, use_container_width=True)
        else: st.warning("画像なし")
    with col2:
        st.title(row["タイトル"])
        st.write(f"🖊️ **著者:** {row['著者']}")
        # ステータスを追加
        status_val = row.get('ステータス', '読了') if str(row.get('ステータス', '')) != 'nan' else '読了'
        st.write(f"🏷️ **カテゴリ:** {row['カテゴリ']} | 🌐 **言語:** {row['言語']} | 📌 **ステータス:** {status_val}")
        st.write(f"📅 **読書期間:** {row['開始日']} 〜 {row['読了日']}")
        try:
            r_val = int(float(row['評価'])) if str(row['評価']) != 'nan' else 0
            st.subheader('★' * r_val if r_val > 0 else '評価なし')
        except: pass
        st.info(f"💬 **コメント:**\n\n{row['コメント'] if str(row['コメント']) != 'nan' else 'なし'}")
        
        # 編集・削除ボタン（ログイン時のみ）
        if st.session_state.authenticated:
            st.divider()
            if st.button("✏️ この情報を更新する", use_container_width=True):
                st.session_state.edit_index = index
                st.session_state.active_detail_index = None # 詳細を閉じる
                st.rerun()
            with st.popover("🗑️ 本を削除する", use_container_width=True):
                st.error("⚠️ 本当に削除しますか？")
                if st.button("🔴 削除を実行", use_container_width=True):
                    # indexを使って行を削除
                    updated_df = df_books.drop(index)
                    if update_gsheet(updated_df):
                        st.session_state.active_detail_index = None
                        st.cache_data.clear() # キャッシュを消して即反映
                        st.toast("削除しました")
                        time.sleep(1)
                        st.rerun()

# --- メイン画面 ---
st.title("📚 読書記録")

# ログイン中のみ「新規登録」UIを表示
if st.session_state.authenticated:
    render_registration_ui()

st.divider()

# --- Google Sheets 接続 ---
df_books = pd.DataFrame() # 初期化
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_books = conn.read(ttl=60) 
except Exception as e:
    st.error(f"接続エラー: {e}")
    st.stop()

# --- サイドバー (表示・フィルタ) ---
def clear_all_states():
    st.session_state.active_detail_index = None
    st.session_state.edit_index = None

if not df_books.empty:
    df_books['読了日_dt'] = pd.to_datetime(df_books['読了日'], errors='coerce')
    
    # --- フィルタと設定の順序整理 ---
    # 1. ホーム (フィルタクリア & データ更新)
    if st.sidebar.button("🏠 ホーム", use_container_width=True):
        st.session_state.filter_reset_key += 1
        st.cache_data.clear()
        clear_all_states()
        st.rerun()
    
    st.sidebar.divider()
    
    # リセットキーを全フィルタに適用
    reset_prefix = f"filter_{st.session_state.filter_reset_key}_"

    # 2. 表示スタイル
    display_mode_raw = st.sidebar.radio("🖼️ 表示スタイル", ["PC向け", "スマホ向け"], key=f"{reset_prefix}display_mode")
    display_mode = "本棚 (グリッド)" if display_mode_raw == "PC向け" else "リスト (一覧表)"
    
    if 'last_display_mode' not in st.session_state:
        st.session_state.last_display_mode = display_mode
    if st.session_state.last_display_mode != display_mode:
        clear_all_states()
        st.session_state.last_display_mode = display_mode

    st.sidebar.write("") # 余白調整

    # 3. 表示切替
    status_group = st.sidebar.radio(
        "📚 表示切替",
        ["読了", "読みたい・読書中"],
        key=f"{reset_prefix}status_group",
        on_change=clear_all_states
    )

    st.sidebar.write("") # 余白調整

    # 4. 読了年
    years = ["すべて"] + sorted(df_books['読了日_dt'].dt.year.dropna().unique().astype(int).astype(str).tolist(), reverse=True)
    f_year = st.sidebar.selectbox("読了年", years, key=f"{reset_prefix}year", on_change=clear_all_states)

    # 5. 言語
    f_lang = st.sidebar.selectbox("言語", ["すべて"] + LANGUAGE_LIST, key=f"{reset_prefix}lang", on_change=clear_all_states)

    # 6. カテゴリ
    f_cat = st.sidebar.selectbox("カテゴリ", ["すべて"] + CATEGORY_LIST, key=f"{reset_prefix}cat", on_change=clear_all_states)

    # 7. キーワード検索
    q = st.sidebar.text_input("キーワード検索", key=f"{reset_prefix}search", on_change=clear_all_states)

    # 8. 並び替え
    sort_order = st.sidebar.selectbox("並び替え", ["新しい順", "古い順"], key=f"{reset_prefix}sort", on_change=clear_all_states)
    
    # フィルタ条件の適用
    df_f = df_books.copy()
    
    # ステータスグループによるフィルタ
    if status_group == "読了":
        df_f = df_f[df_f['ステータス'] == '読了']
    else:  # 「読みたい・読書中」
        df_f = df_f[df_f['ステータス'].isin(['読みたい', '読書中'])]
    
    if q:
        df_f = df_f[df_f['タイトル'].str.contains(q, case=False, na=False) | df_f['著者'].str.contains(q, case=False, na=False)]
    if f_cat != "すべて": df_f = df_f[df_f['カテゴリ'] == f_cat]
    if f_lang != "すべて": df_f = df_f[df_f['言語'] == f_lang] if '言語' in df_f.columns else df_f
    if f_year != "すべて": df_f = df_f[df_f['読了日_dt'].dt.year == int(f_year)]
    
    is_asc = (sort_order == "古い順")
    df_f = df_f.sort_values(['読了日_dt'], ascending=is_asc)

    st.write(f"全 {len(df_f)} 冊の記録がヒットしました")

    if display_mode == "本棚 (グリッド)":
        current_month = None
        for idx, row in df_f.iterrows():
            month_label = row['読了日_dt'].strftime('%Y年 %m月') if pd.notnull(row['読了日_dt']) else "日付なし"
            if month_label != current_month:
                current_month = month_label
                st.markdown(f"### 🗓️ {current_month}")
                cols = st.columns(7)
                col_idx = 0
            
            with cols[col_idx % 7]:
                img = row["画像URL"]
                if isinstance(img, str) and img != "" and str(img) != 'nan':
                    st.markdown(f'<img src="{img}" class="book-cover">', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="book-cover" style="background:#f1f5f9; display:flex; align-items:center; justify-content:center; color:#94a3b8; font-size:0.7em;">No Cover</div>', unsafe_allow_html=True)
                
                # 豆アイコンボタン（画像の右下に浮く）
                st.markdown('<div class="grid-btn">', unsafe_allow_html=True)
                if st.button("➕", key=f"v_{idx}"):
                    st.session_state.active_detail_index = idx
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            col_idx += 1
            if col_idx % 7 == 0 and month_label == current_month:
                cols = st.columns(7)
    else:
        # 改良版リスト表示（Notion風カード形式）
        current_month = None
        for idx, row in df_f.iterrows():
            month_label = row['読了日_dt'].strftime('%Y年 %m月') if pd.notnull(row['読了日_dt']) else "日付なし"
            if month_label != current_month:
                current_month = month_label
                st.markdown(f"#### 🗓️ {current_month}")

            # 表示データの準備
            img = row["画像URL"]
            if not (isinstance(img, str) and img != "" and str(img) != 'nan'):
                img = "https://via.placeholder.com/80x110?text=No+Cover" # ダミー画像
            
            title = row['タイトル']
            author = row['著者'] if str(row['著者']) != 'nan' else '不明な著者'
            cat = row['カテゴリ']
            lang = row.get('言語', '日本語') if str(row.get('言語', '')) != 'nan' else '日本語'
            stat = row.get('ステータス', '読了') if str(row.get('ステータス', '')) != 'nan' else '読了'
            comm = str(row['コメント']) if str(row['コメント']) != 'nan' else ""
            date_val = row['読了日']
            
            try:
                r_val = int(float(row['評価'])) if str(row['評価']) != 'nan' else 0
                stars = '★' * r_val + '☆' * (5 - r_val)
            except:
                stars = ""

            # HTMLの構築
            list_item_html = f"""<div class="notion-list-item">
<img src="{img}" class="notion-cover">
<div class="notion-content">
<div class="notion-title">{title}</div>
<div class="notion-author">{author}</div>
<div class="notion-rating">{stars}</div>
<div class="notion-meta-row">
<span class="notion-tag">{cat}</span>
<span class="notion-tag">{lang}</span>
<span class="notion-tag">{stat}</span>
</div>"""
            
            if comm:
                # コメントは60文字で切り詰め
                short_comm = comm[:60] + ("..." if len(comm) > 60 else "")
                list_item_html += f'<div class="notion-comment">{short_comm}</div>'
            
            list_item_html += f"""<div class="notion-footer">📅 {date_val}</div>
</div>
</div>"""
            
            # コンテナを使って表示（ボタンとの整合性のため）
            with st.container():
                # カードとボタンを一つの枠に収める
                inner_container = st.container(border=True)
                with inner_container:
                    # HTMLを表示
                    st.markdown(list_item_html, unsafe_allow_html=True)
                    # 詳細ボタン（右下に「＋」のみ配置）
                    c_btn1, c_btn2 = st.columns([8, 1])
                    with c_btn2:
                        if st.button("➕", key=f"lbtn_{idx}", use_container_width=True):
                            st.session_state.active_detail_index = idx
                            st.rerun()
            st.write("") 

# 新規登録UIは上部で既に表示済み（render_registration_ui）

# 詳細ダイアログの起動
if st.session_state.active_detail_index is not None:
    if st.session_state.active_detail_index in df_books.index:
        show_detail_dialog(df_books.loc[st.session_state.active_detail_index], st.session_state.active_detail_index)

# 編集ダイアログの起動
if st.session_state.edit_index is not None:
    if st.session_state.edit_index in df_books.index:
        show_edit_dialog(st.session_state.edit_index)
