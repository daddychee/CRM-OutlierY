# conftest.py ở ROOT — pytest tự thêm root vào sys.path để import được `nen.*`.
# LƯU Ý TÊN PACKAGE: thư mục tầng nền tên `nen` (KHÔNG phải `platform`) vì
# `platform` trùng module chuẩn Python — đặt trùng là che stdlib, vỡ thư viện khác.
import os

# NAS (nen/common/nas_sync.py, nối vào gateway lúc đăng nhập): TẮT CỨNG trong test
# — suite tuyệt đối không được gọi PowerShell/tạo-đổi tài khoản Windows thật (cùng
# họ bài học nas_sync hệ cũ). Test riêng của nas_sync tự bật qua monkeypatch + mock
# subprocess (tests/test_nas_sync.py); test gateway mock thẳng dong_bo_nen.
os.environ["NAS_DONG_BO"] = "false"
