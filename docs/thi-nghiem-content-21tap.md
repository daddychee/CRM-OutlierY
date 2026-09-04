# Thí nghiệm content 21 tập Outland (04/09/2026)

Mục đích: kiểm tiêu chí đánh giá KỊCH BẢN trên nhóm đối chứng TRƯỚC khi xây tầng
review content (bài học burstiness Content Ultimate: ngưỡng tự đặt phải đo nhóm
đối chứng trước khi tin). Dữ liệu: 21 tập đã đăng của kênh Outland
(UCqRE8oB1qzZqxEpSo_857ww), APV/AVD/hook30 đọc từ Studio, transcript lấy bằng
youtube-transcript-api (0 đồng). Kết quả thô: thi-nghiem-content-21tap.json.

## Bẫy đã bắt được (suýt kết luận sai)

So 7 tập APV cao nhất với 7 thấp nhất ra tín hiệu ảo: nhóm tốt toàn video CŨ có
phụ đề tay (~250 cue), nhóm kém toàn video MỚI phụ đề tự động (600+ cue). Tuổi
video + loại phụ đề trộn vào phép so → mọi kết luận vòng 1 phải kiểm lại
TRONG CÙNG LỨA 12 video mới (đều auto-caption).

Phát hiện cấu trúc kèm theo: APV p50 lứa CŨ 24,6% vs lứa MỚI 18,5% — dây chuyền
sản xuất hiện tại (các tập LI0xx) đang thấp hơn lứa cũ ~6 điểm APV.

## Tiêu chí SỐNG SÓT sau kiểm trong-lứa (6 vs 6)

| Tiêu chí | TOP p50 | ĐÁY p50 | Tỉ lệ | Chồng lấn |
|---|---|---|---|---|
| Mật độ lời 60 giây đầu (từ) | 126 | 78,5 | 1,61 | 2/6 |
| Tốc độ nói cả bài (từ/phút) | 143 | 116 | 1,23 | 3/6 |
| Câu hỏi tương tác /phút | 1,49 | 1,16 | 1,28 | 2/6 |
| Lặng voice >2s /phút (cờ đỏ) | 0,00 | 0,14 | — | 4/6* |

*lang_2s yếu ở trung vị nhưng 2 tập tệ nhất nhì (Palau 2,96 · Indonesia 1,83)
đều vượt xa 1/phút → dùng làm CỜ ĐỎ ngưỡng >1/phút, không dùng làm thang đo.

Ca đối chứng đẹp: Indonesia (LI083) — wpm 107 (chậm nhì), 67 từ/60s đầu (kém
nhì), lặng 1,83/phút (nhì) và APV 13,9% (kém nhì). Khớp chẩn đoán mạch dựng
"mở đầu chậm, lời vào muộn" đã đo độc lập bằng ffmpeg.

## Tiêu chí CHẾT trong kiểm — KHÔNG được đưa vào bộ đánh giá

- Mật độ số liệu /100 từ và quãng-đọc-số dài nhất: tưởng "đọc số làm người bỏ đi"
  — đo ra KHÔNG phân biệt hai nhóm (giả thuyết từ ca LI083 7:10 không khái quát được).
- Cụm sáo AI /1000 từ (deai_en.csv): chồng lấn 6/6 — vẫn đáng giữ cho VĂN PHONG,
  nhưng không dự báo retention.
- Lặp 4-gram, listicle marker, từ-mới/phút: đều không phân biệt.

## Giới hạn

n=6 vs 6 trong lứa — đây là GỢI Ý MẠNH, chưa phải kết luận; mỗi tập mới có hậu
kiểm sẽ nối dài mẫu. wpm đo từ auto-caption là cận dưới nhưng cùng hệ quy chiếu
giữa hai nhóm. Script chạy lại được: scratchpad tn_content/ (tai_transcript.py +
do_dac_trung.py + kiem_lai.py).
