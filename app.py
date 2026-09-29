
import streamlit as st
import requests
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

API_URL = "https://xosoapi.online/api/v1/vietnam/draws"
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# ============================================================
# TIÊU ĐỀ
# ============================================================

st.title("📈 HỆ THỐNG PHÂN TÍCH & DỰ ĐOÁN XỔ SỐ TỰ ĐỘNG (XSMB)")

st.caption(
    "Tự động lấy dữ liệu XSMB từ API, phân tích tần suất và tạo danh sách "
    "tham khảo dựa trên dữ liệu lịch sử."
)

# ============================================================
# LẤY API KEY
# ============================================================

def get_api_key():
    try:
        key = st.secrets.get("XOSO_API_KEY", "")
    except Exception:
        key = ""

    if not key:
        return ""

    return str(key).strip()


# ============================================================
# GỌI API
# ============================================================

@st.cache_data(ttl=1800, show_spinner=False)
def get_xsmb_data(limit=100):

    api_key = get_api_key()

    if not api_key:
        return {
            "success": False,
            "error": "Chưa cấu hình XOSO_API_KEY trong Streamlit Secrets.",
            "data": []
        }

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    params = {
        "region": "MB",
        "limit": limit
    }

    try:
        response = requests.get(
            API_URL,
            headers=headers,
            params=params,
            timeout=20
        )

        if response.status_code == 401:
            return {
                "success": False,
                "error": "API Key không hợp lệ hoặc đã hết hiệu lực.",
                "data": []
            }

        if response.status_code == 403:
            return {
                "success": False,
                "error": "API Key không có quyền truy cập dữ liệu này.",
                "data": []
            }

        if response.status_code == 429:
            return {
                "success": False,
                "error": "API đang giới hạn số lần gọi. Vui lòng thử lại sau.",
                "data": []
            }

        if response.status_code >= 500:
            return {
                "success": False,
                "error": "Máy chủ API đang gặp sự cố. Vui lòng thử lại sau.",
                "data": []
            }

        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            return {
                "success": False,
                "error": "API trả về dữ liệu không đúng định dạng.",
                "data": []
            }

        data = payload.get("data", [])

        if not isinstance(data, list):
            data = []

        return {
            "success": True,
            "error": "",
            "data": data
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Kết nối API quá thời gian chờ.",
            "data": []
        }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Không thể kết nối tới máy chủ API.",
            "data": []
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Lỗi kết nối API: {str(e)}",
            "data": []
        }

    except ValueError:
        return {
            "success": False,
            "error": "API không trả về JSON hợp lệ.",
            "data": []
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi không xác định: {str(e)}",
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
# BACKTEST WALK-FORWARD
# ============================================================

def backtest(history, test_days=30, top_n=5):

    if len(history) < 45:
        return {
            "tested_days": 0,
            "hits": 0,
            "hit_rate": 0,
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

        # Chuyển lại về mới nhất trước
        train = list(reversed(train))

        predictions = predict_numbers(
            train,
            top_n=top_n
        )

        actual = set(
            chronological[i]["loto"]
        )

        hits = [
            num for num in predictions
            if num in actual
        ]

        details.append({
            "Ngày": chronological[i]["date"],
            "Dự đoán": ", ".join(predictions),
            "Kết quả trúng": ", ".join(hits),
            "Số lượng trúng": len(hits)
        })

    tested_days = len(details)
    hit_days = sum(
        1 for x in details
        if x["Số lượng trúng"] > 0
    )

    hit_rate = (
        hit_days / tested_days * 100
        if tested_days
        else 0
    )

    return {
        "tested_days": tested_days,
        "hits": hit_days,
        "hit_rate": hit_rate,
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

    if st.button(
        "🔄 Làm mới dữ liệu API",
        use_container_width=True
    ):
        st.cache_data.clear()
        st.rerun()


# ============================================================
# KIỂM TRA API
# ============================================================

api_key = get_api_key()

if not api_key:

    st.error(
        "🔐 Chưa có API Key."
    )

    st.info(
        "Sau khi đưa app lên Streamlit, hãy cấu hình "
        "XOSO_API_KEY trong mục Secrets."
    )

    st.stop()


with st.spinner("🔄 Đang lấy dữ liệu XSMB từ API..."):

    api_result = get_xsmb_data(
        limit=max(history_days, 60)
    )


if not api_result["success"]:

    st.error(
        f"❌ {api_result['error']}"
    )

    st.warning(
        "Ứng dụng không sử dụng số giả hoặc dữ liệu thay thế "
        "khi API gặp lỗi."
    )

    st.stop()


records = parse_api_data(
    api_result["data"]
)

history = build_history(records)


if not history:

    st.error(
        "API đã phản hồi nhưng không tìm thấy dữ liệu XSMB "
        "đúng định dạng để phân tích."
    )

    st.stop()


history = history[:history_days]


# ============================================================
# TRẠNG THÁI
# ============================================================

latest_date = history[0]["date"]

st.success(
    f"✅ API hoạt động bình thường — dữ liệu mới nhất: {latest_date}"
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
    top_n=5
)

if backtest_result["tested_days"] > 0:

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

    detail_df = pd.DataFrame(
        backtest_result["details"]
    )

    st.dataframe(
        detail_df,
        use_container_width=True,
        hide_index=True
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
    "Hệ thống phân tích XSMB — dữ liệu được lấy từ API bên ngoài. "
    "Kết quả thống kê chỉ mang tính tham khảo."
)
