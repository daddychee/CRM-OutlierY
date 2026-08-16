// Chọn theme sáng/tối cho cả hệ OUTLIERY (mọi app qua cổng 8000 cùng origin
// nên cùng đọc một khóa localStorage). Ưu tiên: ?theme= > localStorage > OS.
// Trang nào nạp file này phải đặt nó TRONG <head> (chạy trước khi vẽ, khỏi chớp).
(function () {
  var d = document.documentElement, t = null;
  try {
    t = new URLSearchParams(location.search).get("theme") || localStorage.getItem("outliery_theme");
  } catch (e) {}
  if (t !== "light" && t !== "dark") {
    t = (window.matchMedia && matchMedia("(prefers-color-scheme: light)").matches) ? "light" : "dark";
  }
  d.setAttribute("data-theme", t);
})();
