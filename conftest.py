# conftest.py ở ROOT — pytest tự thêm root vào sys.path để import được `nen.*`.
# LƯU Ý TÊN PACKAGE: thư mục tầng nền tên `nen` (KHÔNG phải `platform`) vì
# `platform` trùng module chuẩn Python — đặt trùng là che stdlib, vỡ thư viện khác.
