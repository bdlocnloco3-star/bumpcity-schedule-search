import time
import re
from datetime import date, timedelta
from urllib.parse import urlencode

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="ライブスケジュール文字列検索", layout="wide")
st.title("ライブスケジュール文字列検索")
st.write("指定期間の日別ページを取得し、入力した任意の文字列を検索します。")

st.info(
    "文字化け対策として、文字コードを自動判定しつつ Shift_JIS / CP932 / EUC-JP / UTF-8 を候補にして解析します。"
    "それでも文字化けする場合は、下の「文字コードを指定」で切り替えてください。"
)

with st.sidebar:
    st.header("取得設定")
    base_url = st.text_input("日別ページURL", value="http://tomo-kaz.com/calendar/schedule.cgi")
    fixed_params = st.text_input("固定パラメータ", value="form=2")
    
    # 検索モードの選択（AND / OR）
    search_mode = st.selectbox(
        "複数ワードの検索方法（スペース区切り）",
        ["AND検索（すべて含む）", "OR検索（いずれかを含む）", "完全一致（スペース含む文字列）"],
        index=0
    )

    encoding_choice = st.selectbox(
        "文字コード",
        ["自動判定", "cp932", "shift_jis", "euc_jp", "utf-8", "iso-2022-jp"],
        index=0,
        help="検索結果が文字化けする場合は cp932 または shift_jis を試してください。"
    )
    timeout = st.number_input("タイムアウト（秒）", min_value=3, max_value=60, value=20)
    delay = st.number_input("ページ間の待ち時間（秒）", min_value=0.5, max_value=10.0, value=1.0, step=0.5)
    max_days = st.number_input("1回の検索で確認する最大日数", min_value=1, max_value=1000, value=120)

c1, c2 = st.columns(2)
with c1:
    start_date = st.date_input("開始日", value=date(2026, 11, 1))
with c2:
    end_date = st.date_input("終了日", value=date(2026, 11, 30))

query = st.text_input(
    "検索する文字列", 
    value="", 
    placeholder="例：ギター セッション（複数ワード可）、Hall & Oats、曲名の一部など"
)
case_sensitive = st.checkbox("英字の大文字・小文字を区別する", value=False)
show_page_text = st.checkbox("検索結果にページ本文も表示する", value=False)

def make_url(base, fixed, d):
    params = {}
    for piece in fixed.split("&"):
        piece = piece.strip()
        if not piece:
            continue
        if "=" in piece:
            k, v = piece.split("=", 1)
            params[k] = v
        else:
            params[piece] = ""
    params.update({"year": str(d.year), "mon": str(d.month), "day": str(d.day)})
    return base + ("&" if "?" in base else "?") + urlencode(params)

def decode_html(response, forced):
    if forced != "自動判定":
        return response.content.decode(forced, errors="replace"), forced

    raw = response.content
    head = raw[:8192].lower()
    declared = None
    m = re.search(br'<meta[^>]+charset\s*=\s*["\']?([a-z0-9._-]+)', head)
    if m:
        declared = m.group(1).decode("ascii", errors="ignore")

    candidates = ([declared] if declared else []) + [
        "cp932", "shift_jis", "euc_jp", "utf-8", "iso-2022-jp"
    ]
    seen = set()
    valid = []
    for enc in candidates:
        if not enc or enc.lower() in seen:
            continue
        seen.add(enc.lower())
        try:
            decoded = raw.decode(enc, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
        if not decoded or "\ufffd" in decoded:
            continue
        japanese = sum(1 for ch in decoded if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
        mojibake = sum(decoded.count(mark) for mark in ["Ã", "Â", "縺", "繧", "譁", "ï¿½"])
        valid.append((japanese - mojibake * 20, enc, decoded))
    if valid:
        valid.sort(key=lambda x: x[0], reverse=True)
        _, enc, decoded = valid[0]
        return decoded, enc
    return raw.decode("cp932", errors="replace"), "cp932 (置換あり)"

def fetch(url, timeout_seconds, forced_encoding):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()
    html, enc = decode_html(response, forced_encoding)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = "\n".join(s.strip() for s in soup.get_text("\n").splitlines() if s.strip())
    return text, title, enc, response.status_code

if st.button("検索開始", type="primary", use_container_width=True):
    if start_date > end_date:
        st.error("開始日は終了日以前にしてください。")
    elif not query.strip():
        st.error("検索する文字列を入力してください。")
    elif (end_date - start_date).days + 1 > max_days:
        st.error(f"検索期間が上限の{max_days}日を超えています。")
    elif not base_url.strip().startswith(("http://", "https://")):
        st.error("日別ページURLは http:// または https:// で始めてください。")
    else:
        days = (end_date - start_date).days + 1
        results, errors = [], []
        progress = st.progress(0, text="検索準備中…")
        current = st.empty()
        
        # 検索ワードの分解・準備（全角・半角スペースで分割）
        raw_query = query if case_sensitive else query.casefold()
        # スペースで分割（空文字を除外）
        tokens = [t for t in re.split(r'[\s ]+', raw_query) if t]

        for i in range(days):
            d = start_date + timedelta(days=i)
            url = make_url(base_url.strip(), fixed_params.strip(), d)
            current.write(f"確認中：{d.isoformat()}（{i+1}/{days}）")
            try:
                text, title, encoding, status = fetch(url, timeout, encoding_choice)
                haystack = text if case_sensitive else text.casefold()
                
                # 検索判定ロジック
                is_matched = False
                match_pos = -1
                match_length = len(query.strip())

                if search_mode == "完全一致（スペース含む文字列）" or len(tokens) <= 1:
                    # そのままの部分一致（スペースを含む語句もそのまま探す）
                    pos = haystack.find(raw_query)
                    if pos >= 0:
                        is_matched = True
                        match_pos = pos
                        match_length = len(raw_query)
                elif search_mode == "AND検索（すべて含む）":
                    # すべての単語が含まれているかチェック
                    if all(token in haystack for token in tokens):
                        is_matched = True
                        # 最初に見つかったトークンの位置をスニペットの基準にする
                        match_pos = haystack.find(tokens[0])
                        match_length = len(tokens[0])
                elif search_mode == "OR検索（いずれかを含む）":
                    # いずれかの単語が含まれているかチェック
                    matched_tokens = [t for t in tokens if t in haystack]
                    if matched_tokens:
                        is_matched = True
                        match_pos = haystack.find(matched_tokens[0])
                        match_length = len(matched_tokens[0])

                if is_matched:
                    left = max(0, match_pos - 120)
                    right = min(len(text), match_pos + match_length + 120)
                    snippet = text[left:right].replace("\n", " / ")
                    if left:
                        snippet = "…" + snippet
                    if right < len(text):
                        snippet += "…"
                    results.append({
                        "日付": d.isoformat(),
                        "ページタイトル": title,
                        "該当箇所": snippet,
                        "詳細ページ": url,
                        "文字コード": encoding,
                        "本文": text,
                    })
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else "HTTP error"
                errors.append({"日付": d.isoformat(), "URL": url, "エラー": f"HTTP {code}: {e}"})
            except Exception as e:
                errors.append({"日付": d.isoformat(), "URL": url, "エラー": f"{type(e).__name__}: {e}"})
            progress.progress((i+1)/days, text=f"{i+1}/{days}日確認済み")
            if i < days - 1:
                time.sleep(float(delay))

        progress.empty()
        current.empty()
        st.session_state["results_v2"] = results
        st.session_state["errors_v2"] = errors
        st.session_state["show_text_v2"] = show_page_text
        st.session_state["range_v2"] = f"{start_date.isoformat()} ～ {end_date.isoformat()}"
        st.session_state["query_v2"] = query.strip()

if "results_v2" in st.session_state:
    results = st.session_state["results_v2"]
    errors = st.session_state["errors_v2"]
    st.subheader("検索結果")
    st.write(f"検索語：**{st.session_state['query_v2']}** ／ 対象期間：{st.session_state['range_v2']} ／ 該当ページ：{len(results)}件")

    if results:
        df = pd.DataFrame([{k: r[k] for k in ["日付", "ページタイトル", "該当箇所", "詳細ページ"]} for r in results])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("検索結果をCSVで保存", df.to_csv(index=False).encode("utf-8-sig"),
                           "schedule_search_results.csv", "text/csv")
        for r in results:
            with st.expander(f"{r['日付']} — {r['ページタイトル'] or '詳細'}"):
                st.markdown(f"[詳細ページを開く]({r['詳細ページ']})")
                st.write(r["該当箇所"])
                st.caption(f"文字コード：{r['文字コード']}")
                if st.session_state["show_text_v2"]:
                    st.text_area("ページ本文", r["本文"], height=300, key=f"body_{r['日付']}")
    else:
        st.warning("検索語に一致するページはありませんでした。")

    if errors:
        st.subheader(f"取得エラー（{len(errors)}件）")
        st.warning("エラーになった日付は確認できていません。「該当なし」とは判定できません。")
        err_df = pd.DataFrame(errors)
        st.dataframe(err_df, use_container_width=True, hide_index=True)
        st.download_button("エラー一覧をCSVで保存", err_df.to_csv(index=False).encode("utf-8-sig"),
                           "schedule_search_errors.csv", "text/csv")

