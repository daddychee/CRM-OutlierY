"""Gợi ý TỪ KHÓA NHẤT QUÁN khi nhập tài liệu — Ý 2 Đợt 3.

Vấn đề: ô keywords gõ tự do → mỗi người một kiểu ("ngâm kênh"/"nuôi kênh") → mất
hệ quy chiếu metadata. Giải: gom từ khóa ĐÃ DÙNG từ payload Qdrant làm gợi ý
autocomplete — người nhập THẤY từ có sẵn trước khi tự đặt từ mới. Chỉ đổi UI nhập,
KHÔNG đổi search, không bắt buộc.
"""

import re
from collections import Counter, defaultdict

# Chế độ mock (chưa có Qdrant thật) — vài từ mẫu khớp kho mock để test UI
TU_KHOA_MAU = ["đăng video", "SEO", "ngâm kênh"]


def lay_tu_khoa_da_co(rag) -> list[str]:
    """Mọi từ khóa đã dùng trong kho, xếp theo số TÀI LIỆU dùng (hay dùng lên đầu).

    - keywords là chuỗi "a, b; c" → tách từng từ theo dấu phẩy/chấm phẩy, trim.
    - Bỏ trùng không phân biệt hoa thường, GIỮ cách viết phổ biến nhất (đếm theo
      tài liệu — mỗi doc_code tính 1 lần dù tài liệu có nhiều chunk cùng payload)."""
    if rag.mock:
        return list(TU_KHOA_MAU)

    from src.vector_client import ALIAS

    points, _ = rag.client.scroll(ALIAS, limit=5000,
                                  with_payload=["keywords", "doc_code"])
    da_dem: set[tuple] = set()               # (doc, từ-thường) — chunk trùng không đếm thêm
    dem: Counter = Counter()                 # tần suất theo số tài liệu
    cach_viet: dict = defaultdict(Counter)   # từ-thường → đếm từng cách viết gốc
    for p in points:
        payload = p.payload or {}
        doc = payload.get("doc_code") or ""
        for tk in re.split(r"[,;]", payload.get("keywords") or ""):
            tk = tk.strip()
            khoa = tk.lower()
            if khoa and (doc, khoa) not in da_dem:
                da_dem.add((doc, khoa))
                dem[khoa] += 1
                cach_viet[khoa][tk] += 1
    return [cach_viet[khoa].most_common(1)[0][0] for khoa, _ in dem.most_common()]
