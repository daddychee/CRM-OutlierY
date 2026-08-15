// Markdown → HTML an toàn (escape trước, format sau) — TRÍCH NGUYÊN VĂN từ khối <script> của
// hoi_dap.html (đã kiểm chứng ở đó, xem CLAUDE.md mục "khối <script> giữ nguyên TỪNG BYTE").
// Tách ra file dùng chung để các trang khác (vd _bang_phan_quyet.html) không phải chép lại hàm —
// hoi_dap.html CHỦ Ý không đổi sang nạp file này (đang chạy tốt, không sờ).
function dinhDangMarkdown(text) {
  const escHtml = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = s => escHtml(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  let html = '';
  let dsMo = null;             // <ul>/<ol> đang mở, nếu có
  let khoiVuaXong = false;     // dòng trước là thẻ khối (h*/list) — né <br> trống dư ngay sau nó
  const dongDs = () => { if (dsMo) { html += '</' + dsMo + '>'; dsMo = null; khoiVuaXong = true; } };
  for (const dongTho of text.split('\n')) {
    const dong = dongTho.trim();
    let m;
    if ((m = dong.match(/^(#{1,4})\s+(.+)$/))) {
      dongDs();
      const c = m[1].length + 2;                // # → h3 ... #### → h6
      html += `<h${c}>${inline(m[2])}</h${c}>`;
      khoiVuaXong = true;
    } else if ((m = dong.match(/^[-*]\s+(.+)$/))) {
      if (dsMo !== 'ul') { dongDs(); html += '<ul>'; dsMo = 'ul'; }
      html += `<li>${inline(m[1])}</li>`;
      khoiVuaXong = false;
    } else if ((m = dong.match(/^\d+[.)]\s+(.+)$/))) {
      if (dsMo !== 'ol') { dongDs(); html += '<ol>'; dsMo = 'ol'; }
      html += `<li>${inline(m[1])}</li>`;
      khoiVuaXong = false;
    } else if (dong === '') {
      dongDs();
      if (!khoiVuaXong) html += '<br>';          // ngay sau khối thì bỏ, tránh khoảng trắng đúp
      khoiVuaXong = false;
    } else {
      dongDs();
      html += inline(dong) + '<br>';
      khoiVuaXong = false;
    }
  }
  dongDs();
  return html;
}
