# DoJa NDS Port – Changelog

## v37 — Native Viewport + Game-Independent Preparation

- Gỡ bộ scale cưỡng bức 240×240 → 256×192; blitter giữ nguyên pixel gốc.
- Mặc định căn khung 240×240 tại X=8, Y=-24, hiển thị vùng giữa 240×192 và cắt phần vượt màn hình.
- Sinh `DOJA_SCREEN_X/Y` theo metadata thay vì khóa vị trí trong Java.
- Bỏ giới hạn ScratchPad đúng 409.600 byte; kích thước và CRC32 được sinh từ từng game.
- Bỏ logic slot lưu Corpse Party khỏi runtime chung.
- Chỉ áp dụng bản vá `j.class`/HTTP cũ khi JAR khớp chữ ký Corpse Party chính xác.
- Bộ kiểm tra chấp nhận lớp chính, tham số, tên game, mã ROM và ScratchPad khác nhau sau mỗi lần chuẩn bị.
- Đã kiểm tra đổi metadata liên tiếp giữa ScratchPad 512.000 byte và 778.240 byte mà không giữ cấu hình cũ.

## v36 — Sửa lỗi biên dịch bộ scale 256×192

- Sửa lỗi `KNI_EndHandles()` bị gọi trong nhánh scale, làm đóng scope macro giữa hàm và khiến `alpha`, `clipX`, `dstX`, `srcW` cùng nhiều biến khác bị báo chưa khai báo.
- Nhánh scale giờ nhảy tới một epilogue chung duy nhất bằng `goto blit_done`, sau đó mới đóng KNI handles và trả về.
- Thêm kiểm tra tự động để không tái xuất hiện lỗi đóng handle scope trong nhánh.
- Giữ nguyên font CP932 12×12, sửa nét Latin, scale 240×240 → 256×192 và save `.sav` đang hoạt động.

## v35 — Original CP932 Font + Latin Stroke Fix + Forced 256×192

- Loại bỏ hoàn toàn font lai NFTR của v34.
- Khôi phục font CP932 12×12 đầy đủ như v33.
- Raster chữ Latin vào ô 6×12 riêng, không còn lấy cách một cột gây mất nét.
- Giữ hệ tọa độ game 240×240, scale khung hình cuối sang toàn màn hình NDS 256×192.
- Đặt khung hình tại X=0, Y=0; không còn crop bằng offset Y=-24.
- Giữ nguyên save `.sav` đang hoạt động, ba slot, write-through, CRC, icon mặc định, input, ScratchPad zero-copy và heap 2432 KiB.
