# Điện vận hành máy chủ OUTLIERY — tắt 20:00 / bật 9:00

> Chốt 24/08/2026. Máy: HUANANZHI, BIOS AMI 5.11 (2023), RAM 32GB, Windows Server 2025.
> Nối tiếp mục 6 "Phương án điện B1" trong `KE_HOACH_THAY_THE.md`.

## Trạng thái hiện tại

| Việc | Cơ chế | Ghi chú |
|---|---|---|
| **Tắt 20:00** | ~~Tác vụ `OUTLIERY-TatMay`~~ — **ĐÃ TẮT 24/08/2026 theo lệnh Owner** | Tác vụ đặt `Disabled`, script và tác vụ vẫn còn nguyên. Bật lại: `Enable-ScheduledTask -TaskName 'OUTLIERY-TatMay'`. **Từ nay máy KHÔNG tự tắt — ra về phải Shut down tay** |
| **Bật 9:00** | **BIOS RTC Alarm** (xem hướng dẫn dưới) | KHÔNG làm được bằng phần mềm — máy tắt hẳn thì Task Scheduler đã chết |
| **App tự lên** | Tác vụ `OUTLIERY-V3` (SYSTEM, At startup + lặp 30 phút) → `start-all.ps1` idempotent | Không cần đăng nhập Windows. Lặp 30 phút = lưới tự chữa nếu dịch vụ chết |

**Vì sao không dùng phần mềm để bật máy** (đã đo 24/08):
- `powercfg /a`: chỉ còn Standby S3, Hibernate đã tắt (23/08 lấy lại 17GB ổ C)
- `powercfg /devicequery wake_from_any_S3_supported`: **rỗng** — không thiết bị nào được phép đánh thức
- NIC Realtek: `WakeOnMagicPacket = Unsupported` → **Wake-on-LAN không dùng được** (mà dùng được cũng cần một máy khác thức lúc 9:00 để bắn gói)

## Hướng dẫn bật RTC Alarm trong BIOS (làm 1 lần)

1. Khởi động lại máy. Ngay khi màn hình vừa sáng, **bấm liên tục phím `Delete`** (một số bản là `F2`) cho tới khi vào màn hình BIOS xanh/xám.
2. Dùng phím mũi tên sang tab **`Advanced`**.
3. Tìm mục **`ACPI Settings`** hoặc **`APM Configuration`** → Enter.
4. Tìm một trong các dòng sau (mỗi hãng gọi một kiểu, cùng một thứ):
   - `Wake system from S5`
   - `Wake System with Fixed Time`
   - `RTC Alarm Power On`
   - `Resume By RTC Alarm`
5. Đổi thành **`Enabled`** → sẽ hiện thêm mấy dòng con:
   - **`Wake up day`** → đặt **`0`** ⚠️ số 0 nghĩa là **MỌI NGÀY**; đặt 1–31 là chỉ bật đúng ngày đó trong tháng
   - **`Wake up hour`** → **`9`**
   - **`Wake up minute`** → **`0`**
   - **`Wake up second`** → **`0`**
6. *(Khuyến nghị)* Ở cùng khu vực, tìm **`Restore AC Power Loss`** / `AC Back Function` → đặt **`Power On`**. Đêm mất điện rồi có lại thì máy tự lên, không phải chờ sáng.
7. Bấm **`F4`** (hoặc tab `Save & Exit` → `Save Changes and Reset`) → chọn `Yes`. Máy khởi động lại.

**Kiểm giờ BIOS trước khi thoát:** trên màn hình chính BIOS có đồng hồ `System Date/Time`. Nó phải trùng giờ Việt Nam đang chạy trên Windows. Lệch thì sửa ngay tại đó, vì alarm chạy theo đồng hồ BIOS chứ không theo Windows.

## Nghiệm thu

**Cách nhanh (làm cuối giờ, ~5 phút):** vào BIOS đặt tạm `Wake up hour/minute` = thời điểm 5 phút sau → Save & Exit → `shutdown /s /t 0` → chờ. Máy tự lên đúng giờ là xong; vào lại BIOS đổi về 9:00.

**Cách tự nhiên:** sáng hôm sau tới xem máy đã lên chưa. Kiểm bằng lệnh:

```powershell
(Get-CimInstance Win32_OperatingSystem).LastBootUpTime      # phải là ~09:00
Get-ScheduledTaskInfo -TaskName 'OUTLIERY-V3' | fl LastRunTime,LastTaskResult   # Result = 0
```

Rồi mở `http://192.168.1.250:9000` xem hệ đã lên chưa.

## Nếu BIOS máy này KHÔNG có mục RTC Alarm

Quay lại phương án dự phòng, tôi làm được bằng phần mềm:
- **B**: đổi `tat-may.ps1` từ shutdown sang **Sleep (S3)** + tác vụ `OUTLIERY-BatMay` 9:00 có `WakeToRun=True`
- **C**: bật lại **Hibernate** (`powercfg /h on`, tốn ~32GB ổ C — hiện còn trống 110GB) + wake timer như trên

Cả hai phải **thử đánh thức thật một lần** (máy ngủ 1–2 phút, dịch vụ team gián đoạn) vì `wake_from_any_S3_supported` đang rỗng — chưa chắc board này cho đánh thức từ S3.

## Lưu ý vận hành

- Máy **đang bật sẵn** lúc 9:00 thì alarm không làm gì cả — vô hại, không cần tắt lịch cuối tuần.
- Alarm BIOS chạy **cả T7/CN**. Muốn nghỉ cuối tuần thì phải vào BIOS tắt tay — hoặc chấp nhận máy chạy không (ít điện hơn là quên bật sáng thứ Hai).
- **Vault chưa có trong V3** — cần thì Enable tạm tác vụ `OUTLIERY` (V2), xong Disable lại.
- **Máy không còn tự tắt** (24/08 Owner tắt lưới an toàn 20:00) — ra về nhớ Shut down tay,
  không thì máy chạy suốt đêm. Backup 19:00 (`OUTLIERY-V3-Backup`) vẫn chạy bình thường.
- Sự cố đã gặp 23/08: sau khi tắt 20:02 có người bật máy lại lúc 20:40 → tác vụ TatMay chạy bù lúc 20:45 và bị hủy (mã `0x800710E0`, không ghi log). Không phải lỗi hệ, nhưng nếu bật lại máy trước 20:00 hôm sau thì kịch bản lặp.
