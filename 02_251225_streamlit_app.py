import streamlit as st
import re
import requests
import pandas as pd
import os
import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- 設定 ---
CATEGORY_LIST = ["小説", "AI", "Stoicism", "語学", "ノンフィクション", "エッセイ", "その他"]
LANGUAGE_LIST = ["日本語", "英語", "スペイン語"]
STATUS_LIST = ["読了", "読書中", "読みたい", "断念"]

# --- ページの設定 ---
st.set_page_config(page_title="Reading Log", page_icon="📚", layout="wide")

# --- パスワード認証 ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state.authenticated:
        return True
    
    st.title("🔒 読書記録ログイン")
    pw = st.text_input("パスワードを入力してください", type="password")
    if pw == "251225": # デフォルトパスワード
        st.session_state.authenticated = True
        st.rerun()
    elif pw != "":
        st.error("パスワードが違います")
    return False

if not check_password():
    st.stop()

# --- 初期化 (Session State) ---
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None
if 'active_detail_index' not in st.session_state:
    st.session_state.active_detail_index = None
if 'filter_reset_key' not in st.session_state:
    st.session_state.filter_reset_key = 0

# --- デザイン（スマホ対応CSS） ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    
    /* スマホ（画面幅600px以下）の時の2列表示設定 */
    @media (max-width: 600px) {
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 10px !important;
        }
        div[data-testid="column"] {
            width: calc(50% - 5px) !important;
            flex: 1 1 calc(50% - 5px) !important;
            min-width: 140px !important;
        }
        .book-card {
            height: 220px !important; /* スマホではカードを少し低く */
        }
        .book-image-container {
            height: 140px !important; /* 画像エリアも縮小 */
        }
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📚 読書記録")

# --- Google Sheets 接続 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_books = conn.read(ttl=0) 
except Exception as e:
    st.error(f"スプレッドシートへの接続に失敗しました: {e}")
    st.stop()

# --- 関数 ---
def get_book_info(url):
    isbn_pattern = r"/(?:dp|product|ASID|ASIN)/([A-Z0-9]{10,13})"
    match = re.search(isbn_pattern, url)
    isbn = match.group(1) if match else None
    
    if isbn:
        api_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "items" in data:
                    return parse_google_books_item(data["items"][0], isbn)
        except: pass

    slug_pattern = r"amazon\.co\.jp/([^/]+)/dp/"
    slug_match = re.search(slug_pattern, url)
    if slug_match:
        keyword = slug_match.group(1).replace("-", " ").replace("ebook", "").strip()
        api_url = f"https://www.googleapis.com/books/v1/volumes?q={keyword}&maxResults=1"
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "items" in data:
                    return parse_google_books_item(data["items"][0], isbn)
        except: pass
    return None

def parse_google_books_item(item, isbn_fallback):
    v = item["volumeInfo"]
    thumbnail = v.get("imageLinks", {}).get("thumbnail", "")
    if thumbnail:
        thumbnail = thumbnail.replace("zoom=1", "zoom=0").replace("http://", "https://")
    return {
        "title": v.get("title", "不明"),
        "authors": ", ".join(v.get("authors", ["不明"])),
        "thumbnail": thumbnail,
        "isbn": isbn_fallback if isbn_fallback else ""
    }

def update_gsheet(df_all):
    try:
        conn.update(worksheet="Sheet1", data=df_all)
        return True
    except Exception as e:
        st.error(f"書き込みエラー: {e}")
        return False

@st.dialog("📖 本の詳細", width="large")
def show_detail_dialog(row, index):
    col1, col2 = st.columns([1, 2])
    img_url = row["画像URL"]
    has_image = isinstance(img_url, str) and img_url.strip() != "" and str(img_url) != "nan"
    
    with col1:
        if has_image: st.image(img_url, use_container_width=True)
        else: st.warning("🖼️ 画像未登録")
            
    with col2:
        st.title(row["タイトル"])
        st.write(f"🖊️ **著者:** {row['著者']}")
        
        stat = row['ステータス'] if 'ステータス' in row and str(row['ステータス']) != 'nan' else "読了"
        stat_color = "#28a745" if stat == "読了" else ("#007bff" if stat == "読書中" else ("#6c757d" if stat == "断念" else "#ffc107"))
        st.markdown(f"**ステータス:** <span style='background-color:{stat_color}; color:white; padding:2px 8px; border-radius:10px; font-size:0.8em;'>{stat}</span>", unsafe_allow_html=True)
        
        st.write(f"🏷️ **カテゴリ:** {row['カテゴリ']} | 🌐 **言語:** {row['言語']}")
        st.write(f"📅 **読書期間:** {row['開始日']} 〜 {row['読了日']}")
        
        try:
            r_box = str(int(float(row['評価']))) if str(row['評価']) != 'nan' else "0"
            r_val = int(r_box)
            st.subheader('★' * r_val if r_val > 0 else '評価なし')
        except: st.subheader('評価なし')
        
        st.info(f"💬 **コメント:**\n\n{row['コメント'] if str(row['コメント']) != 'nan' else 'なし'}")
        
        st.divider()
        if st.button("✏️ 情報を修正する", use_container_width=True):
            st.session_state.edit_index = index
            st.session_state.active_detail_index = None
            st.rerun()

        with st.popover("🗑️ この本を削除する", use_container_width=True):
            st.error("⚠️ 本当に削除しますか？")
            if st.button("🔴 はい、削除します", use_container_width=True, type="primary"):
                updated_df = df_books.drop(index)
                if update_gsheet(updated_df):
                    st.session_state.active_detail_index = None
                    st.toast("削除しました", icon="🗑️")
                    time.sleep(0.5)
                    st.rerun()

# --- メイン UI (登録・編集) ---
is_edit = st.session_state.edit_index is not None

if is_edit:
    st.warning("現在、既存の記録を編集しています")
    if st.session_state.edit_index in df_books.index:
        edit_data = df_books.loc[st.session_state.edit_index]
        st.subheader(f"✏️ 編集: {edit_data['タイトル']}")
        book_data = {"title": edit_data["タイトル"], "authors": edit_data["著者"], "thumbnail": edit_data["画像URL"], "isbn": ""}
        url_input = None
    else: is_edit = False
else:
    st.subheader("🔍 本の登録")
    url_input = st.text_input("AmazonのURLを貼り付けてください", key="url_in")
    book_data = get_book_info(url_input) if url_input else None

if book_data:
    st.success("本の情報を読み込みました")
    manual_image_url = st.text_input("🖼️ 画像URLの修正（任意）", value=book_data["thumbnail"])
    display_url = manual_image_url if manual_image_url else book_data["thumbnail"]

    col_img, col_txt = st.columns([1, 2])
    with col_img:
        if display_url: st.image(display_url, width=150)
    with col_txt:
        title_box = st.text_input("📖 タイトル", value=book_data["title"])
        author_box = st.text_input("🖊️ 著者", value=book_data["authors"])
        
    st.divider()
    try:
        def_rating = str(int(float(edit_data["評価"]))) if is_edit and str(edit_data["評価"]) != 'nan' else "3"
    except: def_rating = "3"
    
    def_cat = edit_data["カテゴリ"] if is_edit else "小説"
    def_lang = edit_data["言語"] if is_edit and "言語" in edit_data else "日本語"
    def_status = edit_data["ステータス"] if is_edit and "ステータス" in edit_data else "読了"
    def_comment = edit_data["コメント"] if is_edit else ""
    
    if is_edit:
        try:
            d1 = datetime.datetime.strptime(str(edit_data["開始日"]), "%Y-%m-%d").date()
            d2 = datetime.datetime.strptime(str(edit_data["読了日"]), "%Y-%m-%d").date()
            def_dates = [d1, d2]
        except: def_dates = [datetime.date.today(), datetime.date.today()]
    else: def_dates = [datetime.date.today(), datetime.date.today()]

    rating = st.select_slider("評価", options=["1", "2", "3", "4", "5"], value=def_rating)
    c1, c2, c3 = st.columns(3)
    with c1: category = st.selectbox("カテゴリ", CATEGORY_LIST, index=CATEGORY_LIST.index(def_cat) if def_cat in CATEGORY_LIST else 0)
    with c2: language = st.selectbox("言語", LANGUAGE_LIST, index=LANGUAGE_LIST.index(def_lang) if def_lang in LANGUAGE_LIST else 0)
    with c3: status = st.selectbox("ステータス", STATUS_LIST, index=STATUS_LIST.index(def_status) if def_status in STATUS_LIST else 0)
    
    comment = st.text_area("一言コメント", value=def_comment if str(def_comment) != 'nan' else "")
    dates = st.date_input("読書期間", def_dates)
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("🆕 保存する" if not is_edit else "✅ 更新する"):
            start_date = dates[0].strftime("%Y-%m-%d") if len(dates) > 0 else ""
            end_date = dates[1].strftime("%Y-%m-%d") if len(dates) > 1 else start_date
            record = {"タイトル": title_box, "著者": author_box, "評価": rating, "カテゴリ": category, "言語": language, "ステータス": status, "コメント": comment, "開始日": start_date, "読了日": end_date, "画像URL": display_url}
            
            if is_edit:
                df_books.loc[st.session_state.edit_index] = record
            else:
                df_books = pd.concat([df_books, pd.DataFrame([record])], ignore_index=True)
            
            if update_gsheet(df_books):
                st.session_state.edit_index = None
                st.toast("保存しました！", icon="✅")
                time.sleep(1)
                st.rerun()
    with btn_col2:
        if is_edit and st.button("❌ キャンセル"):
            st.session_state.edit_index = None
            st.rerun()

# --- 本棚表示 ---
st.divider()

if not df_books.empty:
    df_books['読了日_dt'] = pd.to_datetime(df_books['読了日'], errors='coerce')
    
    # --- フィルタ (サイドバー) ---
    st.sidebar.title("🔍 検索・フィルタ")
    reset_prefix = f"filter_{st.session_state.filter_reset_key}_"

    search_query = st.sidebar.text_input("キーワード検索", key=f"{reset_prefix}search")
    selected_cat = st.sidebar.selectbox("カテゴリ", ["すべて"] + CATEGORY_LIST, key=f"{reset_prefix}cat")
    selected_lang = st.sidebar.selectbox("言語", ["すべて"] + LANGUAGE_LIST, key=f"{reset_prefix}lang")
    selected_status = st.sidebar.selectbox("ステータス", ["すべて"] + STATUS_LIST, key=f"{reset_prefix}status")
    min_rating = st.sidebar.slider("最低評価", 1, 5, value=1, key=f"{reset_prefix}rating")
    
    years = ["すべて"] + sorted(df_books['読了日_dt'].dt.year.dropna().unique().astype(int).astype(str).tolist(), reverse=True)
    selected_year = st.sidebar.selectbox("記録された年", years, key=f"{reset_prefix}year")
    sort_order = st.sidebar.selectbox("並び替え", ["新しい順", "古い順"], key=f"{reset_prefix}sort")
    
    if st.sidebar.button("🧹 フィルタをクリア"):
        st.session_state.filter_reset_key += 1
        st.rerun()
    
    # フィルタ適用
    df_f = df_books.copy()
    if search_query:
        df_f = df_f[df_f['タイトル'].str.contains(search_query, case=False, na=False) | df_f['著者'].str.contains(search_query, case=False, na=False)]
    if selected_cat != "すべて": df_f = df_f[df_f['カテゴリ'] == selected_cat]
    if selected_lang != "すべて": df_f = df_f[df_f['言語'] == selected_lang]
    if selected_status != "すべて": df_f = df_f[df_f['ステータス'] == selected_status] if 'ステータス' in df_f.columns else df_f
    df_f = df_f[df_f['評価'].fillna(0).astype(int) >= min_rating] if '評価' in df_f.columns else df_f
    if selected_year != "すべて": df_f = df_f[df_f['読了日_dt'].dt.year == int(selected_year)]
    
    is_asc = (sort_order == "古い順")
    df_f = df_f.sort_values(['読了日_dt', 'タイトル'], ascending=[is_asc, True])

    # --- 本棚グリッド ---
    st.subheader(f"📖 私の本棚 ({len(df_f)} 冊)")
    
    # グリッドの描画
    cols = st.columns(5)
    for i, (idx, row) in enumerate(df_f.iterrows()):
        with cols[i % 5]:
            stat = row['ステータス'] if 'ステータス' in row and str(row['ステータス']) != 'nan' else "読了"
            s_color = "#28a745" if stat == "読了" else ("#007bff" if stat == "読書中" else ("#6c757d" if stat == "断念" else "#ffc107"))
            r_img = row['画像URL']
            img_disp = f'<img src="{r_img}" style="max-height: 100%; max-width: 100%; object-fit: contain;">' if isinstance(r_img, str) and r_img.strip() != "" and str(r_img) != "nan" else '<div style="color:#ccc; font-size:0.8em;">No Image</div>'

            st.markdown(f"""
            <div class="book-card" style="background-color: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; height: 260px; margin-bottom: 5px;">
                <div class="book-image-container" style="height: 180px; width: 100%; border-radius: 4px; margin-bottom: 8px; overflow: hidden; background-color: white; display: flex; align-items: center; justify-content: center; position: relative;">
                    {img_disp}
                    <div style="position: absolute; top: 5px; right: 5px; background-color: {s_color}; width: 10px; height: 10px; border-radius: 50%; border: 1px solid white;"></div>
                </div>
                <div style="font-weight: bold; font-size: 0.75em; height: 2.8em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.4; margin-bottom: 2px;">
                    {row['タイトル']}
                </div>
                <div style="font-size: 0.65em; color: #555;">{row['著者']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("📖 詳細を表示", key=f"btn_{idx}", use_container_width=True):
                st.session_state.active_detail_index = idx
                st.rerun()

    if st.session_state.active_detail_index is not None:
        if st.session_state.active_detail_index in df_books.index:
            detail_row = df_books.loc[st.session_state.active_detail_index]
            show_detail_dialog(detail_row, st.session_state.active_detail_index)
        else: st.session_state.active_detail_index = None
else: st.info("まだ登録された本がありません")
