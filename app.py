


import streamlit as st
import requests
import re
from html.parser import HTMLParser
import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ============================================================
# CẤU HÌNH
# ============================================================

st.set_page_config(
    page_title="Hệ Thống Phân Tích & Dự Đoán XSMB",
    page_icon="📈",
    layout="wide"
)

FREE_DATA_URLS = {
    30: "https://ketqua.vn/so-ket-qua-30-ngay",
    60: "https://ketqua.vn/so-ket-qua-60-ngay",
    90: "https://ketqua.vn/so-ket-qua-90-ngay",
    100: "https://ketqua.vn/so-ket-qua-100-ngay",
}
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# ============================================================
# TIÊU ĐỀ
# ============================================================

st.title("📈 HỆ THỐNG PHÂN TÍCH & DỰ ĐOÁN XỔ SỐ TỰ ĐỘNG (XSMB)")

st.caption(
    "Tự động lấy dữ liệu XSMB từ nguồn web công khai, phân tích tần suất "
    "và tạo danh sách tham khảo dựa trên dữ liệu lịch sử."
)

# ============================================================
# LẤY DỮ LIỆU MIỄN PHÍ - KHÔNG CẦN API KEY
# ============================================================

class VisibleTextParser(HTMLParser):
    """Chuyển HTML thành phần văn bản nhìn thấy để phân tích."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            text = data.strip()
            if text:
                self.parts.append(text)


def html_to_text(html_text):
    parser = VisibleTextParser()
    parser.feed(html_text)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def choose_source_url(history_days):
    """Chọn trang miễn phí có phạm vi gần nhất nhưng không nhỏ hơn nhu cầu."""
    for days in (30, 60, 90, 100):
        if history_days <= days:
            return FREE_DATA_URLS[days], days
    return FREE_DATA_URLS[100], 100


@st.cache_data(ttl=1800, show_spinner=False)
def get_xsmb_data(limit=100):
    """
    Lấy XSMB từ trang kết quả công khai, không cần API Key.

    Hàm trả về cấu trúc tương thích với parser cũ:
    [{"date": "YYYY-MM-DD", "draws": [{"results": [...]}]}]
    """

    source_url, source_days = choose_source_url(limit)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }

    try:
        response = requests.get(
            source_url,
            headers=headers,
            timeout=25
        )
        response.raise_for_status()

        text = html_to_text(response.text)

        # Các trang có thể lặp tên XSMB trong tiêu đề/breadcrumb.
        # Chỉ giữ những mốc ngày mà phần sau thực sự chứa giải ĐB.
        date_matches = list(
            re.finditer(
                r"XSMB.*?(\d{2}/\d{2}/\d{4})",
                text,
                flags=re.IGNORECASE
            )
        )

        records = []
        seen_dates = set()

        for index, match in enumerate(date_matches):
            date_text = match.group(1)

            try:
                date_obj = datetime.strptime(date_text, "%d/%m/%Y")
                iso_date = date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue

            # Bỏ các đoạn không phải bảng kết quả.
            next_pos = (
                date_matches[index + 1].start()
                if index + 1 < len(date_matches)
                else len(text)
            )
            block = text[match.end():next_pos]

            db_pos = block.find("ĐB")
            if db_pos < 0:
                continue

            result_block = block[db_pos:]

            # Chỉ lấy phần kết quả giải thưởng, không lấy thống kê phía dưới.
            stop_positions = [
                pos for marker in ("Bảng loto", "Đầu", "Thống kê")
                for pos in [result_block.find(marker)]
                if pos > 0
            ]
            if stop_positions:
                result_block = result_block[:min(stop_positions)]

            numbers = re.findall(r"(?<!\d)\d{2,5}(?!\d)", result_block)

            # Một ngày XSMB có 27 giải thưởng/giá trị số. Cho phép sai lệch
            # nhỏ vì từng trang có thể trình bày khác nhau.
            if len(numbers) < 20:
                continue

            if iso_date in seen_dates:
                continue

            seen_dates.add(iso_date)
            records.append({
                "date": iso_date,
                "draws": [{"results": numbers}]
            })

            if len(records) >= source_days:
                break

        records.sort(
            key=lambda x: x["date"],
            reverse=True
        )

        if not records:
            return {
                "success": False,
                "error": "Không đọc được dữ liệu XSMB từ nguồn miễn phí.",
                "data": []
            }

        return {
            "success": True,
            "error": "",
            "data": records[:limit],
            "source_url": source_url,
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Nguồn dữ liệu miễn phí phản hồi quá chậm.",
            "data": []
        }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Không thể kết nối tới nguồn dữ liệu XSMB miễn phí.",
            "data": []
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Lỗi khi lấy dữ liệu XSMB: {str(e)}",
            "data": []
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi xử lý dữ liệu XSMB: {str(e)}",
            "data": []
        }


# ============================================================
# CHUẨN HÓA KẾT QUẢ API
# ============================================================

def normalize_number(value):
    """
    Chuyển một giá trị về chuỗi số.
    Ví dụ:
    12345 -> "12345"
    "12345" -> "12345"
    """

    if value is None:
        return None

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

    text = str(value).strip()

    if not text:
        return None

    # Chỉ giữ số
    digits = "".join(ch for ch in text if ch.isdigit())

    if not digits:
        return None

    return digits


def extract_numbers_from_draw(draw):
    """
    Lấy danh sách tất cả giải thưởng trong một kỳ quay.
    """

    numbers = []

    if not isinstance(draw, dict):
        return numbers

    results = draw.get("results", [])

    if isinstance(results, list):
        for item in results:

            # Trường hợp API trả trực tiếp chuỗi số
            if isinstance(item, (str, int, float)):
                num = normalize_number(item)

                if num:
                    numbers.append(num)

            # Trường hợp API trả object
            elif isinstance(item, dict):
                for key in [
                    "number",
                    "value",
                    "result",
                    "code"
                ]:
                    if key in item:
                        num = normalize_number(item[key])

                        if num:
                            numbers.append(num)
                        break

    elif isinstance(results, dict):

        for value in results.values():

            if isinstance(value, list):
                for item in value:

                    num = normalize_number(item)

                    if num:
                        numbers.append(num)

            else:
                num = normalize_number(value)

                if num:
                    numbers.append(num)

    return numbers


def parse_api_data(raw_data):
    """
    Chuyển dữ liệu API thành:
    [
        {
            date: YYYY-MM-DD,
            numbers: [...]
        }
    ]
    """

    records = []

    if not isinstance(raw_data, list):
        return records

    for item in raw_data:

        if not isinstance(item, dict):
            continue

        date_text = item.get("date")

        if not date_text:
            continue

        draws = item.get("draws", [])

        if not isinstance(draws, list):
            continue

        all_numbers = []

        for draw in draws:
            all_numbers.extend(
                extract_numbers_from_draw(draw)
            )

        # Loại các giá trị rỗng
        all_numbers = [
            x for x in all_numbers
            if x
        ]

        if all_numbers:
            records.append({
                "date": str(date_text)[:10],
                "numbers": all_numbers
            })

    # Loại ngày trùng
    unique = {}

    for record in records:
        unique[record["date"]] = record

    records = list(unique.values())

    # Mới nhất trước
    records.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return records


# ============================================================
# CHUYỂN SANG LÔ 2 SỐ
# ============================================================

def get_two_digit_numbers(numbers):
    result = []

    for number in numbers:

        number = str(number).strip()

        if not number:
            continue

        # Lấy 2 số cuối
        if len(number) >= 2:
            result.append(number[-2:].zfill(2))

    return result


def build_history(records):
    history = []

    for record in records:

        loto = get_two_digit_numbers(
            record["numbers"]
        )

        history.append({
            "date": record["date"],
            "loto": loto
        })

    return history


# ============================================================
# THỐNG KÊ
# ============================================================

def calculate_frequency(history):
    counter = Counter()

    for day in history:
        counter.update(day["loto"])

    return counter


def calculate_recent_frequency(history, days=30):

    selected = history[:days]

    counter = Counter()

    for day in selected:
        counter.update(day["loto"])

    return counter


def calculate_gap(history):

    gap = {}

    for number in range(100):

        num = f"{number:02d}"

        found = False

        for index, day in enumerate(history):

            if num in day["loto"]:
                gap[num] = index
                found = True
                break

        if not found:
            gap[num] = len(history)

    return gap


# ============================================================
# THUẬT TOÁN ĐIỂM
# ============================================================

def calculate_scores(history):

    if not history:
        return pd.DataFrame()

    freq_all = calculate_frequency(history)
    freq_30 = calculate_recent_frequency(history, 30)
    freq_14 = calculate_recent_frequency(history, 14)
    gap = calculate_gap(history)

    rows = []

    for number in range(100):

        num = f"{number:02d}"

        f_all = freq_all.get(num, 0)
        f_30 = freq_30.get(num, 0)
        f_14 = freq_14.get(num, 0)
        g = gap.get(num, len(history))

        # Trọng số giảm dần theo thời gian
        score_frequency = (
            f_all * 0.5
            + f_30 * 1.5
            + f_14 * 2.0
        )

        # Điểm theo độ trễ.
        # Chỉ dùng ở mức nhỏ, không coi "gan" là quy luật chắc chắn.
        gap_score = min(g, 30) * 0.05

        total_score = (
            score_frequency
            + gap_score
        )

        rows.append({
            "Số": num,
            "Tần suất": f_all,
            "30 ngày": f_30,
            "14 ngày": f_14,
            "Độ trễ": g,
            "Điểm": round(total_score, 3)
        })

    df = pd.DataFrame(rows)

    df = df.sort_values(
        by=["Điểm", "14 ngày", "30 ngày"],
        ascending=False
    ).reset_index(drop=True)

    df.insert(
        0,
        "Hạng",
        range(1, len(df) + 1)
    )

    return df


# ============================================================
# DỰ ĐOÁN
# ============================================================

def predict_numbers(history, top_n=10):

    scores = calculate_scores(history)

    if scores.empty:
        return []

    return scores.head(top_n)["Số"].tolist()


# ============================================================
# BACKTEST WALK-FORWARD + TÍNH LÃI/LỖ
# ============================================================

def backtest(
    history,
    test_days=30,
    top_n=5,
    cost_per_point=23000,
    payout_per_hit=80000
):
    """
    Backtest walk-forward cho top_n số.

    Quan trọng:
    - "Số lượng trúng" = số dự đoán khác nhau có xuất hiện ít nhất 1 lần.
    - "Tổng nháy" = tổng số lần các số dự đoán thực sự xuất hiện trong
      toàn bộ bảng loto của ngày đó. Một số xuất hiện 2 hoặc 3 lần được
      tính 2 hoặc 3 nháy.
    """

    if len(history) < 45:
        return {
            "tested_days": 0,
            "hits": 0,
            "hit_rate": 0,
            "total_bets": 0,
            "total_stake": 0,
            "total_nhay": 0,
            "total_payout": 0,
            "profit_loss": 0,
            "roi": 0,
            "details": []
        }

    # history mới nhất -> cũ nhất
    chronological = list(reversed(history))

    start_index = max(
        30,
        len(chronological) - test_days
    )

    details = []

    for i in range(start_index, len(chronological)):

        train = chronological[:i]

        # Chuyển lại về mới nhất trước khi chấm điểm
        train = list(reversed(train))

        predictions = predict_numbers(
            train,
            top_n=top_n
        )

        # Giữ nguyên toàn bộ loto của ngày thực tế, KHÔNG dùng set,
        # để có thể đếm đúng số lần xuất hiện (nháy).
        actual_loto = chronological[i]["loto"]
        actual_counter = Counter(actual_loto)

        hits = [
            num for num in predictions
            if actual_counter.get(num, 0) > 0
        ]

        nhay_by_number = {
            num: actual_counter.get(num, 0)
            for num in predictions
            if actual_counter.get(num, 0) > 0
        }

        total_nhay_day = sum(nhay_by_number.values())
        stake_day = len(predictions) * cost_per_point
        payout_day = total_nhay_day * payout_per_hit
        profit_day = payout_day - stake_day

        details.append({
            "Ngày": chronological[i]["date"],
            "Dự đoán": ", ".join(predictions),
            "Kết quả trúng": ", ".join(hits),
            "Số lượng trúng": len(hits),
            "Nháy": total_nhay_day,
            "Tiền cược": stake_day,
            "Tiền trả": payout_day,
            "Lãi/Lỗ": profit_day
        })

    tested_days = len(details)
    hit_days = sum(
        1 for x in details
        if x["Số lượng trúng"] > 0
    )

    # Mỗi ngày thực tế đánh đúng top_n số; nếu mô hình không trả đủ số
    # thì tính theo số dự đoán thực tế trong từng dòng.
    total_bets = sum(
        len([x for x in row["Dự đoán"].split(", ") if x])
        for row in details
    )

    total_stake = total_bets * cost_per_point
    total_nhay = sum(row["Nháy"] for row in details)
    total_payout = total_nhay * payout_per_hit
    profit_loss = total_payout - total_stake

    hit_rate = (
        hit_days / tested_days * 100
        if tested_days
        else 0
    )

    roi = (
        profit_loss / total_stake * 100
        if total_stake
        else 0
    )

    return {
        "tested_days": tested_days,
        "hits": hit_days,
        "hit_rate": hit_rate,
        "total_bets": total_bets,
        "total_stake": total_stake,
        "total_nhay": total_nhay,
        "total_payout": total_payout,
        "profit_loss": profit_loss,
        "roi": roi,
        "details": details
    }


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Cài đặt")

    history_days = st.slider(
        "Số ngày dữ liệu sử dụng",
        min_value=30,
        max_value=100,
        value=60,
        step=10
    )

    top_n = st.slider(
        "Số lượng số tham khảo",
        min_value=3,
        max_value=20,
        value=10,
        step=1
    )

    st.divider()

    st.subheader("💰 Cài đặt tính lãi/lỗ")

    cost_per_point = st.number_input(
        "Tiền cược mỗi số (đồng)",
        min_value=0,
        value=23000,
        step=1000
    )

    payout_per_hit = st.number_input(
        "Tiền trả mỗi nháy (đồng)",
        min_value=0,
        value=80000,
        step=1000
    )

    backtest_top_n = 5

    st.caption("Backtest lãi/lỗ: cố định 5 số/ngày theo lựa chọn của bạn.")

    if st.button(
        "🔄 Làm mới dữ liệu",
        use_container_width=True
    ):
        st.cache_data.clear()
        st.rerun()


# ============================================================
# LẤY DỮ LIỆU
# ============================================================

with st.spinner("🔄 Đang lấy dữ liệu XSMB miễn phí..."):

    data_result = get_xsmb_data(
        limit=history_days
    )


if not data_result["success"]:

    st.error(
        f"❌ {data_result['error']}"
    )

    st.info(
        "Ứng dụng đang dùng nguồn dữ liệu XSMB công khai, không cần API Key. "
        "Nếu nguồn tạm thời không phản hồi, hãy thử nút Làm mới dữ liệu."
    )

    st.stop()


records = parse_api_data(
    data_result["data"]
)

history = build_history(records)


if not history:

    st.error(
        "Nguồn dữ liệu đã phản hồi nhưng không tìm thấy dữ liệu XSMB "
        "đúng định dạng để phân tích."
    )

    st.stop()


history = history[:history_days]


# ============================================================
# TRẠNG THÁI
# ============================================================

latest_date = history[0]["date"]

st.success(
    f"✅ Đã tải dữ liệu XSMB miễn phí — dữ liệu mới nhất: {latest_date}"
)


# ============================================================
# TỔNG QUAN
# ============================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "📅 Số ngày dữ liệu",
        len(history)
    )

with col2:
    st.metric(
        "📌 Ngày mới nhất",
        latest_date
    )

with col3:
    total_results = sum(
        len(x["loto"])
        for x in history
    )

    st.metric(
        "🔢 Lượt số phân tích",
        total_results
    )

with col4:
    unique_numbers = len(
        calculate_frequency(history)
    )

    st.metric(
        "🔢 Số 2 chữ số xuất hiện",
        unique_numbers
    )


st.divider()


# ============================================================
# DỰ ĐOÁN
# ============================================================

st.subheader("🎯 Danh sách số tham khảo")

scores = calculate_scores(history)

prediction_numbers = predict_numbers(
    history,
    top_n=top_n
)

if prediction_numbers:

    cols = st.columns(
        min(len(prediction_numbers), 10)
    )

    for i, number in enumerate(prediction_numbers):

        with cols[i % len(cols)]:

            row = scores[
                scores["Số"] == number
            ]

            score = (
                row.iloc[0]["Điểm"]
                if not row.empty
                else 0
            )

            st.metric(
                f"#{i + 1}",
                number,
                f"Điểm {score:.2f}"
            )

else:

    st.warning(
        "Chưa đủ dữ liệu để tạo danh sách tham khảo."
    )


st.caption(
    "⚠️ Đây là kết quả thống kê/tham khảo từ dữ liệu lịch sử, "
    "không phải bảo đảm kết quả tương lai."
)


# ============================================================
# BẢNG XẾP HẠNG THỐNG KÊ
# ============================================================

st.subheader("📊 Bảng phân tích 00–99")

display_df = scores.head(30).copy()

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# BIỂU ĐỒ TẦN SUẤT
# ============================================================

st.subheader("📈 Top 20 số theo tần suất")

frequency_df = scores.copy()

frequency_df = frequency_df.sort_values(
    "Tần suất",
    ascending=False
).head(20)

chart_df = frequency_df[
    ["Số", "Tần suất"]
].set_index("Số")

st.bar_chart(chart_df)


# ============================================================
# ĐẦU / ĐUÔI
# ============================================================

st.subheader("🔢 Phân tích đầu và đuôi")

freq_counter = calculate_frequency(history)

head_counter = Counter()
tail_counter = Counter()

for num, count in freq_counter.items():

    if len(num) == 2:

        head_counter[num[0]] += count
        tail_counter[num[1]] += count

head_df = pd.DataFrame(
    {
        "Đầu": list(head_counter.keys()),
        "Tần suất": list(head_counter.values())
    }
).sort_values(
    "Đầu"
)

tail_df = pd.DataFrame(
    {
        "Đuôi": list(tail_counter.keys()),
        "Tần suất": list(tail_counter.values())
    }
).sort_values(
    "Đuôi"
)

col1, col2 = st.columns(2)

with col1:
    st.write("**Đầu 0–9**")
    st.dataframe(
        head_df,
        use_container_width=True,
        hide_index=True
    )

with col2:
    st.write("**Đuôi 0–9**")
    st.dataframe(
        tail_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# KẾT QUẢ MỚI NHẤT
# ============================================================

st.subheader("🗓️ Dữ liệu các ngày gần nhất")

recent_rows = []

for day in history[:10]:

    recent_rows.append(
        {
            "Ngày": day["date"],
            "Số lượng giải": len(day["loto"]),
            "Các số 2 chữ số": " ".join(day["loto"])
        }
    )

recent_df = pd.DataFrame(
    recent_rows
)

st.dataframe(
    recent_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# BACKTEST
# ============================================================

st.divider()

st.subheader("🧪 Kiểm tra mô hình bằng dữ liệu lịch sử")

st.write(
    "Mô hình được kiểm tra theo kiểu walk-forward: "
    "mỗi ngày chỉ sử dụng dữ liệu của các ngày trước đó "
    "để tạo danh sách tham khảo."
)

backtest_result = backtest(
    history,
    test_days=min(30, max(1, len(history) - 30)),
    top_n=backtest_top_n,
    cost_per_point=cost_per_point,
    payout_per_hit=payout_per_hit
)

if backtest_result["tested_days"] > 0:

    st.info(
        f"💡 Backtest đang giả định đánh {backtest_top_n} số/ngày | "
        f"{cost_per_point:,.0f}đ/số | {payout_per_hit:,.0f}đ/nháy."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Số ngày kiểm tra",
            backtest_result["tested_days"]
        )

    with c2:
        st.metric(
            "Ngày có ít nhất 1 số trúng",
            backtest_result["hits"]
        )

    with c3:
        st.metric(
            "Tỷ lệ ngày có trúng",
            f"{backtest_result['hit_rate']:.1f}%"
        )

    m1, m2, m3 = st.columns(3)

    with m1:
        st.metric(
            "🎯 Tổng số nháy",
            f"{backtest_result['total_nhay']:,}"
        )

    with m2:
        st.metric(
            "💰 Tổng tiền cược",
            f"{backtest_result['total_stake']:,} đ"
        )

    with m3:
        st.metric(
            "💵 Tổng tiền trả",
            f"{backtest_result['total_payout']:,} đ"
        )

    profit = backtest_result["profit_loss"]
    profit_label = "🟢 Lãi" if profit >= 0 else "🔴 Lỗ"

    p1, p2 = st.columns(2)

    with p1:
        st.metric(
            profit_label,
            f"{profit:+,} đ"
        )

    with p2:
        st.metric(
            "📊 ROI",
            f"{backtest_result['roi']:+.2f}%"
        )

    detail_df = pd.DataFrame(
        backtest_result["details"]
    )

    st.dataframe(
        detail_df,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "⚠️ 'Số lượng trúng' là số dự đoán khác nhau có xuất hiện. "
        "'Nháy' là tổng số lần xuất hiện thực tế của các số dự đoán trong ngày, "
        "nên dùng 'Nháy' để tính tiền trả. Đây chỉ là phép tính lịch sử, "
        "không phải bảo đảm kết quả tương lai."
    )

else:

    st.info(
        "Cần thêm dữ liệu lịch sử để thực hiện backtest."
    )


# ============================================================
# TẢI DỮ LIỆU
# ============================================================

st.divider()

st.subheader("⬇️ Xuất dữ liệu")

csv_data = scores.to_csv(
    index=False
).encode("utf-8-sig")

st.download_button(
    label="📥 Tải bảng phân tích CSV",
    data=csv_data,
    file_name="phan_tich_xsmb.csv",
    mime="text/csv"
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Hệ thống phân tích XSMB — dữ liệu được lấy từ nguồn web công khai. "
    "Kết quả thống kê chỉ mang tính tham khảo."
)
