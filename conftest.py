# conftest.py ở ROOT — pytest tự thêm root vào sys.path để import được `nen.*`.
# LƯU Ý TÊN PACKAGE: thư mục tầng nền tên `nen` (KHÔNG phải `platform`) vì
# `platform` trùng module chuẩn Python — đặt trùng là che stdlib, vỡ thư viện khác.
import os

# NAS (nen/common/nas_sync.py, nối vào gateway lúc đăng nhập): TẮT CỨNG trong test
# — suite tuyệt đối không được gọi PowerShell/tạo-đổi tài khoản Windows thật (cùng
# họ bài học nas_sync hệ cũ). Test riêng của nas_sync tự bật qua monkeypatch + mock
# subprocess (tests/test_nas_sync.py); test gateway mock thẳng dong_bo_nen.
os.environ["NAS_DONG_BO"] = "false"

# SỔ GỌI: ép về thư mục TẠM cho CẢ suite. Không có dòng này thì test nào chạm
# so_goi.ghi() sẽ ghi thẳng vào data/logs/so-goi/ THẬT — đã dính 03/09: một test
# két ghi 28 dòng "viec-log-*" vào sổ đang chạy, làm bẩn số liệu quota Owner đọc
# trên Command Center. Fixture cách ly LOGS_DIR không đỡ được vì so_goi đọc biến
# RIÊNG (SO_GOI_DIR). Đặt ở conftest ROOT để test mới quên cách ly vẫn an toàn.
_SO_GOI_TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "test-tmp", "so-goi")
os.environ.setdefault("SO_GOI_DIR", _SO_GOI_TMP)
# Dọn đầu phiên: sổ là append thô nên dòng của lần chạy TRƯỚC sẽ cộng dồn vào
# phép đếm của lần này (test "7 dòng → show more (2)" hỏng ngay lần chạy thứ hai).
if os.environ["SO_GOI_DIR"] == _SO_GOI_TMP and os.path.isdir(_SO_GOI_TMP):
    import shutil
    shutil.rmtree(_SO_GOI_TMP, ignore_errors=True)
