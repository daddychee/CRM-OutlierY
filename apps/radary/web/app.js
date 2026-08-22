// Radary dashboard — Preact + htm (React-compatible API, không cần build).
// Nói chuyện với backend FastAPI qua /api/* — hợp đồng dữ liệu là board JSON trong kv.
import { h, render } from 'preact';
import { useState, useEffect, useCallback } from 'preact/hooks';
import htm from 'htm';
const html = htm.bind(h);

// ---------- helpers ----------
async function api(method, path, body) {
  const r = await fetch('/api' + path, {
    method, headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = r.headers.get('content-type')?.includes('json') ? await r.json() : await r.text();
  if (!r.ok) throw new Error(typeof data === 'object' ? (data.detail || JSON.stringify(data)) : data);
  return data;
}
// trạng thái UI (tab/niche/báo cáo) lưu trong URL hash — F5 đứng yên tại chỗ, link chia sẻ được
const readHash = () => {
  const h = {};
  location.hash.replace(/^#/, '').split('&').forEach(p => {
    const [k, v] = p.split('='); if (k) h[k] = decodeURIComponent(v || '');
  });
  return h;
};
// RadarY chạy TRONG IFRAME khi vào qua cổng 9000 (giao diện "khung" của OUTLIERY).
// history.replaceState chỉ đổi URL của iframe, nên F5 trang cha là iframe tải lại src
// gốc và MẤT SẠCH hash -> luôn rơi về Board (user báo 21/08). Nhớ song song vào
// localStorage để khôi phục; hash vẫn giữ cho trường hợp mở thẳng cổng 9111 + chia sẻ link.
const NHO_KEY = 'radary_ui';
const nhoDoc = () => { try { return JSON.parse(localStorage.getItem(NHO_KEY) || '{}'); } catch (e) { return {}; } };
const nhoGhi = patch => {
  try { localStorage.setItem(NHO_KEY, JSON.stringify({ ...nhoDoc(), ...patch })); } catch (e) {}
};

const writeHash = patch => {
  const h = { ...readHash(), ...patch };
  Object.keys(h).forEach(k => (h[k] === '' || h[k] == null) && delete h[k]);
  const s = Object.entries(h).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
  history.replaceState(null, '', s ? '#' + s : location.pathname);
  nhoGhi(patch);                     // iframe mất hash khi F5 -> localStorage giữ hộ
};
const fmt = n => n == null ? '—' : Math.round(n).toLocaleString('vi-VN');
const fmtAge = h_ => h_ < 48 ? `${(h_/24).toFixed(1)}d` : `${Math.round(h_/24)}d`;
const ago = ts => {
  if (!ts) return 'chưa chạy';
  const s = Date.now()/1000 - ts;
  if (s < 90) return 'vừa xong';
  if (s < 3600) return `${Math.round(s/60)} phút trước`;
  if (s < 86400) return `${(s/3600).toFixed(1)} giờ trước`;
  return `${(s/86400).toFixed(1)} ngày trước`;
};
const fmtTs = ts => new Date(ts*1000).toLocaleString('vi-VN', { hour12:false });
const relTime = ts => { const s = Date.now()/1000 - ts;
  return s < 3600 ? Math.max(1, Math.round(s/60)) + 'ph trước' : s < 86400 ? Math.round(s/3600) + 'h trước' : Math.round(s/86400) + 'd trước'; };
const TIER = t => html`<span class="tier t${t}">${t ? 'T'+t : '—'}</span>`;

// ---------- Đăng nhập / Đăng ký ----------
function Login({ onDone }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [orgName, setOrgName] = useState('');
  const [invite, setInvite] = useState('');
  const [resetCode, setResetCode] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true); setErr('');
    try {
      const r = mode === 'reset'
        ? await api('POST', '/auth/reset', { email, code: resetCode.trim(), new_password: pw })
        : await api('POST', mode === 'login' ? '/auth/login' : '/auth/register',
            mode === 'login' ? { email, password: pw } : { email, password: pw, org_name: orgName, invite: invite.trim() });
      onDone(r);
    } catch (e) { setErr(String(e.message)); }
    setBusy(false);
  };
  return html`
    <div class="panel" style="max-width:400px;margin:60px auto">
      <h2 style="margin-bottom:14px">📡 RADAR<span style="color:var(--accent)">Y</span> — ${mode === 'login' ? 'Đăng nhập' : mode === 'reset' ? 'Đặt lại mật khẩu' : 'Tạo tài khoản'}</h2>
      <div class="formrow" style="grid-template-columns:1fr"><input type="text" placeholder="Email"
        value=${email} onInput=${e => setEmail(e.target.value)}/></div>
      ${mode === 'reset' && html`<div class="formrow" style="grid-template-columns:1fr">
        <input type="text" placeholder="Mã reset rs-… (xin từ owner)" value=${resetCode} onInput=${e => setResetCode(e.target.value)}/></div>`}
      <div class="formrow" style="grid-template-columns:1fr"><input type="password"
        placeholder=${mode === 'reset' ? 'Mật khẩu MỚI (≥8 ký tự)' : 'Mật khẩu (≥8 ký tự)'}
        value=${pw} onInput=${e => setPw(e.target.value)} onKeyDown=${e => e.key === 'Enter' && go()}/></div>
      ${mode === 'register' && !invite.trim() && html`<div class="formrow" style="grid-template-columns:1fr">
        <input type="text" placeholder="Tên team/org (tùy chọn)" value=${orgName} onInput=${e => setOrgName(e.target.value)}/></div>`}
      ${mode === 'register' && html`<div class="formrow" style="grid-template-columns:1fr">
        <input type="text" placeholder="Mã mời rdy-… (nếu được mời vào team)" value=${invite} onInput=${e => setInvite(e.target.value)}/></div>`}
      ${err && html`<div class="msg err">${err}</div>`}
      <button class="btn" style="width:100%" disabled=${busy} onClick=${go}>
        ${busy ? html`<span class="spin"></span>` : mode === 'login' ? 'Đăng nhập' : mode === 'reset' ? 'Đặt lại mật khẩu & đăng nhập' : 'Tạo tài khoản'}</button>
      <div class="note" style="text-align:center;margin-top:12px">
        <a href="#" onClick=${e => { e.preventDefault(); setMode(mode === 'login' ? 'register' : 'login'); setErr(''); }}>
          ${mode === 'login' ? 'Chưa có tài khoản? Đăng ký' : 'Đã có tài khoản? Đăng nhập'}</a>
        ${mode === 'login' && html` · <a href="#" onClick=${e => { e.preventDefault(); setMode('reset'); setErr(''); }}>Quên mật khẩu?</a>`}</div>
      ${mode === 'reset' && html`<div class="note">Chưa có mã? Nhờ owner của org vào tab Quản trị → bấm "reset MK" cạnh tên bạn rồi gửi mã cho bạn (hạn 24h, dùng 1 lần).</div>`}
      ${mode === 'register' && html`<div class="note">Tài khoản có sẵn từ trước (migrate) chưa có mật khẩu:
        đăng ký bằng đúng email đó để đặt mật khẩu lần đầu.</div>`}
    </div>`;
}

// ---------- API keys của org (Phase 5.1: gán theo niche + key dự phòng) ----------
function OrgKeys({ wss }) {
  const [orgs, setOrgs] = useState([]);
  const [keys, setKeys] = useState({});
  const [newKey, setNewKey] = useState('');
  const [newWs, setNewWs] = useState(0);
  const [newBackup, setNewBackup] = useState(false);
  const [msg, setMsg] = useState(null);
  const load = useCallback(async () => {
    const os_ = await api('GET', '/orgs'); setOrgs(os_);
    const m = {};
    for (const o of os_) m[o.id] = await api('GET', `/orgs/${o.id}/keys`).catch(() => []);
    setKeys(m);
  }, []);
  useEffect(() => { load(); }, [load]);
  const wsOf = orgId => (wss || []).filter(w => w.org_id === orgId);
  const add = async org => {
    if (newKey.trim().length < 20) return;
    try {
      await api('POST', `/orgs/${org}/keys`, { key: newKey.trim(), workspace_id: Number(newWs), backup: newBackup });
      setNewKey(''); setNewWs(0); setNewBackup(false); setMsg(null); load();
    } catch (e) { setMsg(String(e.message)); }
  };
  const del = async (org, k) => {
    if (!confirm(`Xóa API key ${k.masked} khỏi org?\nRadar sẽ không quét được nếu đây là key cuối cùng.`)) return;
    await api('DELETE', `/orgs/${org}/keys/${k.id}`); load();
  };
  const [tests, setTests] = useState({});
  const testKey = async (org, k) => {
    setTests(t => ({ ...t, [k.id]: { busy: true } }));
    try { const r = await api('POST', `/orgs/${org}/keys/${k.id}/test`); setTests(t => ({ ...t, [k.id]: r })); }
    catch (e) { setTests(t => ({ ...t, [k.id]: { ok: false, note: String(e.message) } })); }
  };
  const keyRow = (o, k) => { const t = tests[k.id]; return html`
    <div style="display:flex;gap:8px;align-items:center;margin:3px 0;flex-wrap:wrap">
      <span style="font-family:monospace">${k.backup ? '🛟 ' : ''}${k.masked}</span>
      ${k.note && html`<span class="note" style="margin:0">${k.note}</span>`}
      <button class="btn small ghost" onClick=${() => testKey(o.id, k)}>${t?.busy ? html`<span class="spin"></span>` : 'kiểm'}</button>
      ${t && !t.busy && html`<span class="note" style="margin:0;color:${t.ok ? 'var(--good, #0ca30c)' : 'var(--bad, #e66767)'}">
        ${t.ok ? '✅ còn quota' : `✗ ${t.reason || ''} ${t.note || ''}`}</span>`}
      <button class="btn small ghost danger" onClick=${() => del(o.id, k)}>xóa</button>
    </div>`; };
  const groupsOf = o => {
    const ks = keys[o.id] || [];
    const g = [{ wsId: 0, name: '🌐 Dùng chung toàn org', items: ks.filter(k => !k.workspace_id) }];
    for (const w of wsOf(o.id)) {
      const items = ks.filter(k => k.workspace_id === w.id);
      if (items.length) g.push({ wsId: w.id, name: `📁 ${w.name}`, items });
    }
    return g;
  };
  return html`
    <div class="panel">
      <h2>YouTube API key <small>· nhóm theo dự án · hết quota key chính → DỰ PHÒNG 🛟 tự lên thay</small></h2>
      ${orgs.map(o => html`
        <div style="margin-bottom:10px">
          ${groupsOf(o).map(g => html`
            <div class="keygroup">
              <b>${g.name}</b>
              <div class="formrow" style="margin-top:6px"><label>KEY CHÍNH</label><span>
                ${g.items.filter(k => !k.backup).map(k => keyRow(o, k))}
                ${!g.items.some(k => !k.backup) && html`<span class="note">chưa có — nhóm này đang chạy nhờ key nơi khác</span>`}
              </span></div>
              <div class="formrow"><label>DỰ PHÒNG</label><span>
                ${g.items.filter(k => k.backup).map(k => keyRow(o, k))}
                ${!g.items.some(k => k.backup) && html`<span class="note">chưa có</span>`}
              </span></div>
            </div>`)}
          <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center">
            <input type="text" style="min-width:240px" placeholder="Dán YouTube Data API key (AIza…)" value=${newKey}
              onInput=${e => setNewKey(e.target.value)}/>
            <select value=${newWs} onChange=${e => setNewWs(e.target.value)}>
              <option value="0">nhóm: toàn org</option>
              ${wsOf(o.id).map(w => html`<option value=${w.id}>nhóm: ${w.name}</option>`)}
            </select>
            <select value=${newBackup ? 1 : 0} onChange=${e => setNewBackup(Number(e.target.value) === 1)}>
              <option value="0">key chính</option><option value="1">dự phòng 🛟</option>
            </select>
            <button class="btn small" onClick=${() => add(o.id)}>Thêm key</button>
          </div>
        </div>`)}
      ${msg && html`<div class="msg err">${msg}</div>`}
      <div class="note">Quota 10K/ngày tính theo DỰ ÁN Google Cloud — key muốn cộng quota phải tạo từ project KHÁC NHAU.
        Dán key đã tồn tại sẽ bị từ chối (chống nhầm key cũ).</div>
    </div>`;
}

// ---------- Thành viên & mã mời (Phase 5 — chỉ owner thấy panel này) ----------
function OrgAdmin({ orgId, meEmail, wss }) {
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [invRole, setInvRole] = useState('viewer');
  const [invWs, setInvWs] = useState(0);        // 0 = toàn org; số = giới hạn 1 niche
  const [msg, setMsg] = useState(null);
  const scopeLabel = (wsId, wsName) => wsId ? `chỉ "${wsName || wsId}"` : 'toàn org';
  const load = useCallback(() => {
    api('GET', `/orgs/${orgId}/members`).then(setMembers).catch(() => setMembers([]));
    api('GET', `/orgs/${orgId}/invites`).then(setInvites).catch(() => setInvites([]));
  }, [orgId]);
  useEffect(() => { load(); }, [load]);
  const make = async () => {
    try {
      const r = await api('POST', `/orgs/${orgId}/invites`, { role: invRole, workspace_id: Number(invWs) });
      const scope = Number(invWs) ? ` (chỉ thấy niche "${(wss || []).find(w => w.id === Number(invWs))?.name}")` : '';
      setMsg({ ok: 1, t: `Mã mời ${r.role}${scope}: ${r.code} — gửi cho người được mời, hạn 7 ngày, dùng 1 lần.` });
      load();
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const revoke = async i => {
    if (!confirm(`Thu hồi mã mời ${i.code}?\nNgười đang giữ mã này sẽ không đăng ký được nữa.`)) return;
    await api('DELETE', `/orgs/${orgId}/invites/${i.id}`); load();
  };
  const removeM = async m => {
    if (!confirm(`Gỡ ${m.email} khỏi org? Người này sẽ mất quyền truy cập mọi workspace.`)) return;
    try { await api('DELETE', `/orgs/${orgId}/members/${m.id}`); load(); }
    catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const pwReset = async m => {
    if (!confirm(`Phát mã reset mật khẩu cho ${m.email}?`)) return;
    try {
      const r = await api('POST', `/orgs/${orgId}/members/${m.id}/pwreset`);
      setMsg({ ok: 1, t: `Mã reset cho ${r.email}: ${r.code} — gửi cho họ, vào "Quên mật khẩu?" ở màn đăng nhập để tự đặt lại. Hạn 24h, dùng 1 lần.` });
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const patchM = async (m, p) => {
    try {
      await api('PATCH', `/orgs/${orgId}/members/${m.id}`, { role: '', workspace_id: -1, ...p });
      setMsg({ ok: 1, t: `Đã cập nhật ${m.email}` }); load();
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); load(); }
  };
  const copy = code => { navigator.clipboard?.writeText(code); setMsg({ ok: 1, t: `Đã copy ${code}` }); };
  return html`
    <div class="panel">
      <h2>Thành viên & mã mời <small>· viewer chỉ xem · leader vận hành · owner toàn quyền</small></h2>
      <table>${members.map(m => {
        const editable = m.role !== 'owner' && m.email !== meEmail;
        return html`
        <tr><td>${m.email}</td>
        <td>${editable
          ? html`<select value=${m.role} onChange=${e => patchM(m, { role: e.target.value })}>
              <option value="viewer">viewer</option><option value="leader">leader</option></select>`
          : html`<span class="rolechip ${m.role}">${m.role}</span>`}</td>
        <td>${editable
          ? html`<select value=${m.workspace_id || 0} onChange=${e => patchM(m, { workspace_id: Number(e.target.value) })}>
              <option value="0">toàn bộ niche</option>
              ${(wss || []).map(w => html`<option value=${w.id}>chỉ: ${w.name}</option>`)}</select>`
          : html`<span class="note">${scopeLabel(m.workspace_id, m.workspace_name)}</span>`}</td>
        <td class="num">
          <button class="btn small ghost" title="Phát mã reset mật khẩu" onClick=${() => pwReset(m)}>reset MK</button>
          ${m.email !== meEmail && html`
          <button class="btn small ghost danger" onClick=${() => removeM(m)}>gỡ</button>`}</td></tr>`; })}
      </table>
      <div style="display:flex;gap:8px;margin-top:10px;align-items:center;flex-wrap:wrap">
        <select value=${invRole} onChange=${e => setInvRole(e.target.value)}>
          <option value="viewer">viewer — chỉ xem</option>
          <option value="leader">leader — vận hành pool/harvest/niche</option>
        </select>
        <select value=${invWs} onChange=${e => setInvWs(e.target.value)}>
          <option value="0">phạm vi: toàn bộ niche</option>
          ${(wss || []).map(w => html`<option value=${w.id}>chỉ niche: ${w.name}</option>`)}
        </select>
        <button class="btn small" onClick=${make}>Tạo mã mời</button>
      </div>
      ${invites.length > 0 && html`
        <div class="note" style="margin-top:10px">Mã đang chờ (chưa dùng, còn hạn):</div>
        <table>${invites.map(i => html`
          <tr><td style="font-family:monospace">${i.code}</td><td><span class="rolechip ${i.role}">${i.role}</span></td>
          <td class="note">${scopeLabel(i.workspace_id, i.workspace_name)}</td>
          <td class="note">hết hạn ${fmtTs(i.expires_ts)}</td>
          <td class="num"><button class="btn small ghost" onClick=${() => copy(i.code)}>copy</button>
            <button class="btn small ghost danger" onClick=${() => revoke(i)}>thu hồi</button></td></tr>`)}
        </table>`}
      ${msg && html`<div class="msg ${msg.ok ? '' : 'err'}" style="margin-top:10px">${msg.t}</div>`}
      <div class="note">Người được mời: vào trang đăng nhập → Đăng ký → dán mã — vào thẳng org này đúng vai.</div>
    </div>`;
}

// ---------- Niche của org (tab Quản trị — owner xóa niche tập trung) ----------
function OrgNiches({ wss, onChanged }) {
  const [msg, setMsg] = useState(null);
  const del = async w => {
    const name = prompt(`Xóa VĨNH VIỄN niche "${w.name}" và toàn bộ kênh/video/lịch sử của nó?\n\nGõ đúng tên niche để xác nhận:`);
    if (name == null) return;
    try {
      await api('DELETE', `/workspaces/${w.id}?confirm=${encodeURIComponent(name)}`);
      setMsg({ ok: 1, t: `Đã xóa niche "${w.name}".` });
      onChanged && onChanged(w.id);
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  return html`
    <div class="panel">
      <h2>Niche của org <small>· xóa = mất toàn bộ kênh/video/lịch sử của niche đó — phải gõ đúng tên</small></h2>
      <div class="tablewrap"><table>
        <tr><th>Niche</th><th class="num">Video đang theo dõi</th><th class="num"></th></tr>
        ${(wss || []).map(w => html`
          <tr><td>${w.name}</td><td class="num">${fmt(w.videos)}</td>
          <td class="num"><button class="btn small ghost danger" onClick=${() => del(w)}>xóa niche</button></td></tr>`)}
      </table></div>
      ${msg && html`<div class="msg ${msg.ok ? '' : 'err'}" style="margin-top:8px">${msg.t}</div>`}
    </div>`;
}

// ---------- Key YouTube của TỪNG niche (Phase 5.1 — 1 ô chính + N ô dự phòng, owner) ----------
function NicheKeys({ ws, orgId }) {
  const [list, setList] = useState([]);
  const [inMain, setInMain] = useState('');
  const [inBk, setInBk] = useState('');
  const [msg, setMsg] = useState(null);
  const load = useCallback(() => api('GET', `/orgs/${orgId}/keys`).then(setList).catch(() => setList([])), [orgId]);
  useEffect(() => { load(); }, [load]);
  const mine = list.filter(k => k.workspace_id === ws);
  const main = mine.find(k => !k.backup);
  const backups = mine.filter(k => k.backup);
  const orgWide = list.filter(k => !k.workspace_id);
  const saveMain = async () => {
    if (inMain.trim().length < 20) { setMsg({ ok: 0, t: 'Key quá ngắn.' }); return; }
    if (main && !confirm(`Thay KEY CHÍNH hiện tại (${main.masked}) của niche này?`)) return;
    try {
      if (main) await api('DELETE', `/orgs/${orgId}/keys/${main.id}`);
      await api('POST', `/orgs/${orgId}/keys`, { key: inMain.trim(), workspace_id: ws });
      setInMain(''); setMsg({ ok: 1, t: 'Đã lưu key chính cho niche.' }); load();
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const addBackup = async () => {
    if (inBk.trim().length < 20) { setMsg({ ok: 0, t: 'Key quá ngắn.' }); return; }
    try {
      await api('POST', `/orgs/${orgId}/keys`, { key: inBk.trim(), workspace_id: ws, backup: true });
      setInBk(''); setMsg({ ok: 1, t: 'Đã thêm key dự phòng.' }); load();
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const del = async k => {
    if (!confirm(`Xóa key ${k.masked} khỏi niche này?`)) return;
    await api('DELETE', `/orgs/${orgId}/keys/${k.id}`); load();
  };
  return html`
    <div class="panel">
      <h2>Key YouTube của niche này <small>· key riêng = quota riêng · hết quota key chính thì DỰ PHÒNG tự lên thay</small></h2>
      <div class="formrow"><label>KEY CHÍNH</label>
        <span style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          ${main && html`<span style="font-family:monospace">${main.masked}</span>
            <button class="btn small ghost danger" onClick=${() => del(main)}>xóa</button>`}
          <input type="text" style="min-width:200px" placeholder=${main ? 'dán key mới để THAY…' : 'dán key chính (AIza…)'}
            value=${inMain} onInput=${e => setInMain(e.target.value)}/>
          <button class="btn small" onClick=${saveMain}>${main ? 'Thay' : 'Lưu'}</button>
        </span></div>
      <div class="formrow"><label>KEY DỰ PHÒNG</label>
        <span>
          ${backups.map(k => html`<div style="display:flex;gap:8px;align-items:center;margin-bottom:6px">
            <span style="font-family:monospace">🛟 ${k.masked}</span>
            <button class="btn small ghost danger" onClick=${() => del(k)}>xóa</button></div>`)}
          <div style="display:flex;gap:8px;align-items:center">
            <input type="text" style="min-width:200px" placeholder="dán key dự phòng (AIza…)"
              value=${inBk} onInput=${e => setInBk(e.target.value)}/>
            <button class="btn small ghost" onClick=${addBackup}>+ Thêm ô dự phòng</button>
          </div>
        </span></div>
      ${msg && html`<div class="msg ${msg.ok ? '' : 'err'}">${msg.t}</div>`}
      <div class="note">Niche này cũng dùng chung ${orgWide.length} key toàn org (quản ở tab Quản trị).
        Key nên tạo từ các DỰ ÁN Google Cloud khác nhau thì quota mới cộng dồn.</div>
    </div>`;
}

// ---------- LLM diễn giải (Phase 7 — owner cấu hình provider/model/key) ----------
function LlmPanel({ orgId }) {
  const [cfg, setCfg] = useState(null);
  const [provider, setProvider] = useState('claude');
  const [model, setModel] = useState('');
  const [key, setKey] = useState('');
  const [msg, setMsg] = useState(null);
  const load = useCallback(() => api('GET', `/orgs/${orgId}/llm`)
    .then(r => { setCfg(r); setProvider(r.provider || 'claude'); setModel(r.model || ''); })
    .catch(() => {}), [orgId]);
  useEffect(() => { load(); }, [load]);
  const save = async () => {
    try {
      const r = await api('PUT', `/orgs/${orgId}/llm`, { provider, model: model.trim(), key: key.trim() });
      setMsg({ ok: 1, t: `Đã lưu — ${r.provider} / ${r.model}` }); setKey(''); load();
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const test = async () => {
    setMsg({ ok: 1, t: 'Đang gửi câu thử…' });
    try { const r = await api('POST', `/orgs/${orgId}/llm/test`); setMsg({ ok: 1, t: `✅ LLM trả lời: "${r.reply}"` }); }
    catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  return html`
    <div class="panel">
      <h2>LLM diễn giải <small>· viết tường thuật báo cáo ngách + trả lời "Hỏi Radar" · key mã hóa như YouTube key</small></h2>
      <div class="formrow"><label>Nhà cung cấp</label>
        <select value=${provider} onChange=${e => { setProvider(e.target.value); setModel(''); }}>
          <option value="claude">Claude (Anthropic)</option>
          <option value="glm">GLM (Zhipu)</option>
        </select></div>
      <div class="formrow"><label>Model</label>
        <input type="text" placeholder=${provider === 'glm' ? 'mặc định: glm-4-plus' : 'mặc định: claude-opus-4-8'}
          value=${model} onInput=${e => setModel(e.target.value)}/></div>
      <div class="formrow"><label>API key</label>
        <input type="password" placeholder=${cfg?.configured ? `đang dùng ${cfg.masked} — dán key mới để thay` : 'dán API key'}
          value=${key} onInput=${e => setKey(e.target.value)}/></div>
      <div style="display:flex;gap:8px">
        <button class="btn small" onClick=${save}>Lưu</button>
        ${cfg?.configured && html`<button class="btn small ghost" onClick=${test}>Gửi câu thử</button>`}
      </div>
      ${msg && html`<div class="msg ${msg.ok ? '' : 'err'}" style="margin-top:10px">${msg.t}</div>`}
      <div class="note">AI chỉ DIỄN GIẢI số liệu — bị cấm khuyên "đánh/không đánh" (nguyên tắc phân vai người–máy).
        Chưa có key thì mọi thứ vẫn chạy bình thường, chỉ thiếu phần tường thuật.</div>
    </div>`;
}

// ---------- Chart sóng video T2+ (SVG tự vẽ — spec dataviz: line 2px, band ~10%, grid hairline, tooltip) ----------
const kfmt = n => n >= 1e9 ? (n/1e9).toFixed(2)+'B' : n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(n >= 1e4 ? 0 : 1)+'K' : String(Math.round(n));
function niceTicks(max, n = 4) {
  if (max <= 0) return [0];
  const mag = Math.pow(10, Math.floor(Math.log10(max/n)));
  const step = [1, 2, 5, 10].map(m => m*mag).find(s => max/s <= n) || 10*mag;
  const out = []; for (let v = 0; v <= max + 1e-9; v += step) out.push(v);
  return out;
}
const pathOf = pts => pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
const MK_COLOR = { retitle: 'var(--viz-mk-title)', rethumb: 'var(--viz-mk-thumb)', dead: 'var(--viz-down)' };
const MK_LABEL = { retitle: 'Đổi title', rethumb: 'Đổi thumbnail', dead: 'Xóa/Ẩn' };

function LineChart({ title, pts, bands, markers, yfmt, height, xfmt, xstep, xtipfmt }) {
  // pts: [[age_h, value]] · bands: [{age_h,p25,p50,p75,p90}] (có thể rỗng) · markers: [{age_h,kind,old}]
  // xfmt/xstep (tùy chọn): nhãn trục X theo thời gian thật (Nhịp pool) thay vì tuổi video
  // Thẩm mỹ theo ngôn ngữ uPlot/Tremor/shadcn-charts: area gradient mờ dần + crosshair + grid chấm mảnh
  const [tip, setTip] = useState(null);
  const [gid] = useState(() => 'lg' + Math.random().toString(36).slice(2, 8));
  const W = 700, H = height || 240, L = 46, R = 12, T = 12, B = 24;
  const maxAge = Math.max(pts.length ? pts[pts.length-1][0] : 0, bands.length ? bands[bands.length-1].age_h : 0, 24);
  const maxV = Math.max(...pts.map(p => p[1]), ...bands.map(b => b.p90), 1) * 1.08;
  const x = a => L + (a / maxAge) * (W - L - R);
  const y = v => T + (1 - v / maxV) * (H - T - B);
  const xy = pts.map(p => [x(p[0]), y(p[1])]);
  const dayStep = xstep || (maxAge > 96 ? 48 : 24);
  const xticks = []; for (let h = 0; h <= maxAge; h += dayStep) xticks.push(h);
  // nhãn P50/P75/P90: kẹp trong mép phải + tách tối thiểu 11px khi các đường sát nhau
  // (giá trị càng cao nằm càng trên: P90 trên cùng, rồi P75, rồi P50)
  let labX = 0, labY50 = 0, labY75 = 0, labY90 = 0;
  if (bands.length > 0) {
    const lb = bands[bands.length - 1];
    labX = Math.min(x(lb.age_h) + 3, W - R - 24);
    labY50 = y(lb.p50) + 3; labY75 = y(lb.p75) + 3; labY90 = y(lb.p90) + 3;
    if (labY50 - labY75 < 11) labY75 = labY50 - 11;
    if (labY75 - labY90 < 11) labY90 = labY75 - 11;
  }
  const hover = e => {
    if (!pts.length) return;
    const r = e.currentTarget.getBoundingClientRect();
    const ax = ((e.clientX - r.left) / r.width) * W;
    let best = 0, bd = 1e18;
    xy.forEach((p, i) => { const d = Math.abs(p[0] - ax); if (d < bd) { bd = d; best = i; } });
    setTip({ px: (xy[best][0]/W)*100, py: (xy[best][1]/H)*100,
             yl: yfmt(pts[best][1]),
             xl: (xtipfmt || xfmt) ? (xtipfmt || xfmt)(pts[best][0]) : (pts[best][0]/24).toFixed(1) + 'd', i: best });
  };
  return html`
    <div class="vizwrap" style="margin-top:10px">
      <div class="note" style="margin:0 0 2px">${title}</div>
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;display:block" onMouseMove=${hover} onMouseLeave=${() => setTip(null)}>
        <defs><linearGradient id=${gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--viz-series)" stop-opacity="0.26"/>
          <stop offset="100%" stop-color="var(--viz-series)" stop-opacity="0.02"/>
        </linearGradient></defs>
        ${niceTicks(maxV).map(v => html`
          <line x1=${L} x2=${W-R} y1=${y(v)} y2=${y(v)} stroke="var(--viz-grid)" stroke-width="1" stroke-dasharray="2 4"/>
          <text x=${L-6} y=${y(v)+4} text-anchor="end" font-size="10" fill="var(--muted)">${yfmt(v)}</text>`)}
        ${xticks.map(h => html`
          <text x=${x(h)} y=${H-8} text-anchor="middle" font-size="10" fill="var(--muted)">${xfmt ? xfmt(h) : Math.round(h/24*10)/10 + 'd'}</text>`)}
        ${bands.length > 0 && html`
          <path d="${pathOf(bands.map(b => [x(b.age_h), y(b.p75)])) + ' ' +
                    bands.slice().reverse().map(b => 'L' + x(b.age_h).toFixed(1) + ',' + y(b.p25).toFixed(1)).join(' ') + ' Z'}"
                fill="var(--viz-band)" stroke="none"/>
          <path d=${pathOf(bands.map(b => [x(b.age_h), y(b.p50)]))} fill="none" stroke="var(--viz-ref)"
                stroke-width="1" stroke-dasharray="5 4" opacity="0.65"/>
          <path d=${pathOf(bands.map(b => [x(b.age_h), y(b.p75)]))} fill="none" stroke="var(--viz-p75)"
                stroke-width="1" stroke-dasharray="5 4" opacity="0.55"/>
          <path d=${pathOf(bands.map(b => [x(b.age_h), y(b.p90)]))} fill="none" stroke="var(--viz-p90)"
                stroke-width="1" stroke-dasharray="5 4" opacity="0.6"/>
          <text x=${labX} y=${labY50} font-size="9" fill="var(--muted)" opacity="0.8">P50</text>
          <text x=${labX} y=${labY75} font-size="9" fill="var(--viz-p75)" opacity="0.8">P75</text>
          <text x=${labX} y=${labY90} font-size="9" fill="var(--viz-p90)" opacity="0.85">P90</text>`}
        ${xy.length > 1 && html`
          <path d="${pathOf(xy)} L${xy[xy.length-1][0].toFixed(1)},${y(0).toFixed(1)} L${xy[0][0].toFixed(1)},${y(0).toFixed(1)} Z"
                fill="url(#${gid})" stroke="none"/>
          <path d=${pathOf(xy)} fill="none" stroke="var(--viz-series)" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>`}
        ${markers.map(m => html`
          <line x1=${x(m.age_h)} x2=${x(m.age_h)} y1=${T} y2=${H-B}
                stroke=${MK_COLOR[m.kind]} stroke-width="1.5"/>
          <circle cx=${x(m.age_h)} cy=${T+5} r="4.5" stroke="var(--panel)" stroke-width="2"
                  fill=${MK_COLOR[m.kind]}
                  style="cursor:help" onMouseMove=${e => { e.stopPropagation(); setTip({ px:(x(m.age_h)/W)*100, py:((T+5)/H)*100,
                    txt: MK_LABEL[m.kind] + ` @ ${(m.age_h/24).toFixed(1)}d` }); }}/>`)}
        ${tip && tip.i != null && html`
          <line x1=${xy[tip.i][0]} x2=${xy[tip.i][0]} y1=${T} y2=${H-B}
                stroke="var(--muted)" stroke-width="1" stroke-dasharray="3 3" opacity="0.5"/>
          <circle cx=${xy[tip.i][0]} cy=${xy[tip.i][1]} r="5.5" fill="var(--viz-series)" opacity="0.25"/>
          <circle cx=${xy[tip.i][0]} cy=${xy[tip.i][1]} r="3.5"
                  fill="var(--viz-series)" stroke="var(--panel)" stroke-width="2"/>`}
        <line x1=${L} x2=${W-R} y1=${y(0)} y2=${y(0)} stroke="var(--line)" stroke-width="1"/>
      </svg>
      ${tip && html`<div class="viztip" style="left:${tip.px}%;top:${tip.py}%">
        ${tip.txt ? tip.txt : html`<b>${tip.yl}</b><span style="color:var(--muted)"> · ${tip.xl}</span>`}</div>`}
    </div>`;
}

function VideoModal({ ws, ytId, canEdit, onClose }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState('');
  const [ai, setAi] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const explain = async () => {
    setAiBusy(true); setAi(null);
    try { const r = await api('POST', `/workspaces/${ws}/videos/${ytId}/explain`); setAi({ t: r.answer }); }
    catch (e) { setAi({ err: String(e.message) }); }
    setAiBusy(false);
  };
  useEffect(() => {
    setD(null); setErr(''); setAi(null);
    api('GET', `/workspaces/${ws}/videos/${ytId}/series`).then(setD).catch(e => setErr(String(e.message)));
  }, [ws, ytId]);
  useEffect(() => {
    const esc = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onClose]);
  const TREND = { up: ['↗', 'Đang tăng tốc'], flat: ['→', 'Đi ngang'], down: ['↘', 'Đang tàn'] };
  return html`
    <div class="modalback" onClick=${e => { if (e.target === e.currentTarget) onClose(); }}>
      <div class="modal">
        <button class="close" onClick=${onClose}>×</button>
        ${err && html`<div class="msg err">${err}</div>`}
        ${!d && !err && html`<div class="note"><span class="spin"></span> Đang tải chart…</div>`}
        ${d && html`
          <div style="padding-right:26px">
            ${TIER(d.video.tier)} ${d.video.dead && html`<span class="deadbadge">✕ XÓA/ẨN</span>`}
            <a href=${d.video.url} target="_blank"><b>${d.video.title}</b></a>
            <div class="note">${d.video.channel} · ${fmt(d.video.views)} views · tuổi ${(d.video.age_h/24).toFixed(1)}d
              ${d.video.dead && d.video.dead_age_h != null ? ` · không còn mở được từ ~${(d.video.dead_age_h/24).toFixed(1)}d tuổi` : ''}</div>
            <div class="trendbadge ${d.trend.dir}" style="margin-top:6px">
              ${TREND[d.trend.dir][0]} ${TREND[d.trend.dir][1]}
              ${d.trend.pct ? ` ${d.trend.pct > 0 ? '+' : ''}${Math.round(d.trend.pct*100)}%` : ''}
              ${d.trend.basis_h ? html`<span class="note" style="font-weight:400"> · so với ${d.trend.basis_h}h trước</span>` : ''}
            </div>
          </div>
          ${d.vph_series.length < 2
            ? html`<div class="note" style="margin-top:12px">Chưa đủ dữ liệu quét để vẽ VPH — quay lại sau vài chu kỳ.</div>`
            : html`
              <${LineChart} title="VPH theo tuổi video (views/giờ)" height=${250}
                pts=${d.vph_series.map(p => [p[0], p[1]])} bands=${d.reference.bands}
                markers=${d.markers} yfmt=${kfmt}/>
              <div class="mklegend">
                <span><span class="dot" style="background:var(--viz-series)"></span>VPH video này</span>
                ${d.reference.bands.length > 0
                  ? html`<span><span class="dot" style="background:var(--viz-band);border:1px solid var(--viz-ref)"></span>
                      Dải xám = hành lang P25–P75 của ${d.reference.n_waves} sóng T2+ tiền lệ cùng niche ·
                      <b>P50</b> (xám) = sóng trung vị — nằm TRÊN đường này là nhanh hơn nửa số sóng cũ ·
                      <b style="color:var(--viz-p75)">P75</b> (đỏ nhạt) = mốc top 25% ·
                      <b style="color:var(--viz-p90)">P90</b> (đỏ đậm) = mốc top 10% sóng mạnh nhất niche</span>`
                  : html`<span>Dải tham chiếu: chưa đủ sóng tiền lệ (có ${d.reference.n_waves}, cần ≥3) — sẽ tự hiện khi kho sóng dày lên</span>`}
                ${d.markers.some(m => m.kind === 'retitle') && html`<span><span class="dot" style="background:var(--viz-mk-title)"></span>Đổi title</span>`}
                ${d.markers.some(m => m.kind === 'rethumb') && html`<span><span class="dot" style="background:var(--viz-mk-thumb)"></span>Đổi thumbnail</span>`}
                ${d.markers.some(m => m.kind === 'dead') && html`<span><span class="dot" style="background:var(--viz-down)"></span>Xóa/Ẩn</span>`}
              </div>
              <${LineChart} title="Views tích lũy · mốc P50/P75/P90 = views của cùng bộ sóng tiền lệ ở cùng tuổi" height=${170}
                pts=${d.ticks} bands=${d.reference.views_bands || []} markers=${[]} yfmt=${kfmt}/>
              ${canEdit && html`<div style="margin-top:10px">
                <button class="btn small ghost" disabled=${aiBusy} onClick=${explain}>
                  ${aiBusy ? html`<span class="spin"></span> AI đang đọc biểu đồ…` : '🧠 AI đọc biểu đồ'}</button></div>`}
              ${ai && (ai.err
                ? html`<div class="msg err" style="margin-top:8px">${ai.err}</div>`
                : html`<div class="aska" style="margin-top:8px" dangerouslySetInnerHTML=${{ __html: mdHtml(ai.t) }}></div>`)}`}
        `}
      </div>
    </div>`;
}

// ---------- Nhịp pool (Phase 3.13) ----------
function PulsePanel({ ws }) {
  const RANGES = [['W', 7], ['M', 30], ['Y', 365]];   // user chốt 22/07/2026: chỉ W/M/Y + Tùy chọn
  const [days, setDays] = useState(7);
  const [custom, setCustom] = useState(false);
  const [c1, setC1] = useState(''); const [c2, setC2] = useState('');
  const [d, setD] = useState(null);
  const [err, setErr] = useState('');
  const q = custom && c1 ? `start=${c1}&end=${c2 || c1}` : `days=${days}`;
  useEffect(() => {
    const load = () => api('GET', `/workspaces/${ws}/pulse?${q}`).then(x => { setD(x); setErr(''); })
      .catch(e => setErr(String(e.message)));
    load();
    const t = setInterval(load, 60000);            // thời gian thực: dòng Hôm nay nhảy theo chu kỳ quét
    return () => clearInterval(t);
  }, [ws, q]);
  if (!d && !err) return null;
  const now = Date.now() / 1000;
  const pts = (d ? d.points : []).slice();
  // bucket đang mở (chưa trọn 6h/ngày) sẽ vẽ thành cú tụt giả ở mép phải — bỏ đi cho trung thực
  while (pts.length && pts[pts.length-1].ts + (d.res === 'day' ? 86400 : 21600) > now) pts.pop();
  const t0 = pts.length ? pts[0].ts : 0;
  const hx = p => (p.ts - t0) / 3600;
  const spanH = pts.length > 1 ? hx(pts[pts.length-1]) : 24;
  const step = Math.max(24, Math.ceil(spanH / 7 / 24) * 24);
  const long = spanH > 100 * 24;
  const xf = h => { const dt = new Date((t0 + h * 3600) * 1000);
    return long ? `${dt.getMonth()+1}/${String(dt.getFullYear()).slice(2)}` : `${dt.getDate()}/${dt.getMonth()+1}`; };
  // tooltip range W: mỗi điểm là một khung 6 tiếng — ghi rõ "22/7 · 06h–12h"
  const xtf = h => { const dt = new Date((t0 + h * 3600) * 1000);
    if (d.res !== '6h') return xf(h);
    const h0 = dt.getHours() - dt.getHours() % 6;
    return `${dt.getDate()}/${dt.getMonth()+1} · ${String(h0).padStart(2,'0')}h–${h0+6}h`; };
  const nAvg = pts.length ? Math.round(pts.reduce((a, p) => a + p.n, 0) / pts.length) : 0;
  // Điểm CUỐI đang chạy dở (bucket 6 giờ / ngày chưa trọn) KHÔNG vẽ lên đường: nó thấp
  // vì mới tích được một phần thời gian, vẽ vào là lần nào cũng thấy "pool đang tụt"
  // (user báo 22/08). Biểu đồ "Sóng views cả ngách" đã xử lý đúng cách này từ trước —
  // đây là áp lại cho Nhịp pool. Số vẫn hiện đầy đủ ở dòng ghi chú bên dưới.
  // Hai mức khác nhau, đều làm đường tụt giả:
  //   dang_chay = khung hiện tại, mới trôi được một phần thời gian
  //   chua_chot = còn thiếu phần views của nhóm video cũ (quét 1 lần/24h), sẽ được
  //               điền bù sau vòng quét toàn pool kế tiếp
  const dangChay = pts.length && pts[pts.length - 1].dang_chay ? pts[pts.length - 1] : null;
  const soChuaChot = pts.filter(p => p.chua_chot).length;
  const ptsVe = soChuaChot ? pts.slice(0, pts.length - soChuaChot) : pts;
  const ptsChuaChot = soChuaChot ? pts.slice(pts.length - soChuaChot) : [];
  return html`
    <div class="panel">
      <h2>Nhịp pool <small>· toàn pool gộp · ${d?.res === 'day' ? 'điểm theo ngày' : 'điểm 6 giờ'}</small></h2>
      <div class="chips" style="margin:4px 0 0">
        ${RANGES.map(([lb, n]) => html`
          <button class="btn small ${!custom && days === n ? '' : 'ghost'}"
                  onClick=${() => { setCustom(false); setDays(n); }}>${lb}</button>`)}
        <button class="btn small ${custom ? '' : 'ghost'}" onClick=${() => setCustom(true)}>Tùy chọn</button>
        ${custom && html`
          <input type="date" value=${c1} onChange=${e => setC1(e.target.value)}/>
          <input type="date" value=${c2} onChange=${e => setC2(e.target.value)}/>`}
      </div>
      ${err && html`<div class="msg err">${err}</div>`}
      ${pts.length < 2
        ? html`<div class="note" style="margin-top:8px">Chưa đủ dữ liệu nhịp trong khoảng này —
            dữ liệu tích lũy từ ${d?.since_ts ? fmtTs(d.since_ts) : 'chu kỳ quét đầu tiên'} và dày lên theo thời gian.</div>`
        : html`
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:0 14px">
            <${LineChart} title="Sóng views — views cộng thêm của cả pool mỗi ${d.res === 'day' ? 'ngày' : '6 giờ'}"
              height=${180} pts=${ptsVe.map(p => [hx(p), p.dviews])} bands=${[]} markers=${[]}
              yfmt=${kfmt} xfmt=${xf} xstep=${step} xtipfmt=${xtf}/>
            <${LineChart} title="Sóng VPH trung bình — views/giờ/video của video 0-6 ngày tuổi (TB ${nAvg} video)"
              height=${180} pts=${ptsVe.map(p => [hx(p), p.vph_avg])} bands=${[]} markers=${[]}
              yfmt=${kfmt} xfmt=${xf} xstep=${step} xtipfmt=${xtf}/>
          </div>
          ${ptsChuaChot.length ? html`<div class="note" style="margin-top:4px;padding:6px 8px;
            border-left:3px solid #ef6c00;background:rgba(239,108,0,.07)">
            <b>${ptsChuaChot.length} khung gần nhất chưa chốt — không vẽ lên đường</b> (tránh
            đọc nhầm thành sụt):
            ${ptsChuaChot.map(p => html`<span style="margin-right:10px">${xtf(hx(p))}:
              <b>${kfmt(p.dviews)}</b> views · VPH ${p.vph_avg}${p.dang_chay
                ? ` (mới qua ${p.phan_tram_da_troi}% khung)` : ''}</span>`)}
            <br/>Lý do: video cũ chỉ được quét 1 lần/24 giờ, nên phần views của chúng chỉ
            được phân bổ vào một khung SAU khi có lần quét kế tiếp. Các khung trong 24 giờ
            gần nhất vì thế còn thiếu và sẽ tự đầy lên — không phải pool đang tụt.</div>` : ''}
          <div class="note">Lịch sử tích lũy từ ${fmtTs(d.since_ts)} · range dài gộp theo ngày ·
            VPH TB chỉ tính video 0-6 ngày tuổi · views chia đều giữa 2 lần quét (ước lượng phân bổ —
            YouTube không có log từng view; khung giờ chính xác dựng được cho 14 ngày gần)</div>`}
    </div>
    <${MetricsPanel} ws=${ws}/>`;
}

// ---------- Metrics + Heatmap giờ đăng (user duyệt mockup kiểu vidIQ 23/07/2026 — thay Top kênh/ngày) ----------
function MetricsPanel({ ws }) {
  const DOWL = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
  const [days, setDays] = useState(90);
  const [tzu, setTzu] = useState('vn');
  const [ch, setCh] = useState('');
  const [d, setD] = useState(null);          // heatmap
  const [m, setM] = useState(null);          // tiles
  const [chans, setChans] = useState([]);    // dropdown giữ danh sách từ lần xem toàn pool
  const [tip, setTip] = useState(null);
  const [read, setRead] = useState(false);
  useEffect(() => {
    api('GET', `/workspaces/${ws}/metrics?channel=${encodeURIComponent(ch)}`)
      .then(setM).catch(() => setM(null));
  }, [ws, ch]);
  useEffect(() => {
    api('GET', `/workspaces/${ws}/heatmap?days=${days}&tz=${tzu}&channel=${encodeURIComponent(ch)}`)
      .then(x => { setD(x); if (!ch && x.channels) setChans(x.channels); })
      .catch(() => setD(null));
  }, [ws, days, tzu, ch]);
  useEffect(() => { setCh(''); setTip(null); }, [ws]);
  if (!d && !m) return null;
  const cellMap = {};
  ((d && d.cells) || []).forEach(([dw, h, n, list]) => { cellMap[dw + '-' + h] = { n, list }; });
  const hover = (e, dw, h) => {
    const c = cellMap[dw + '-' + h];
    const r = e.currentTarget.closest('.hmwrap').getBoundingClientRect();
    const b = e.currentTarget.getBoundingClientRect();
    setTip({ x: b.left - r.left + b.width / 2, y: b.top - r.top,
             dw, h, n: c ? c.n : 0, list: c ? c.list : [] });
  };
  const hh = h => String(h).padStart(2, '0');
  const pill = (pct, why) => pct == null
    ? html`<span class="pill gy" title=${(why ? why + ' — ' : '') + 'chưa đủ lịch sử để so, tự hiện khi dữ liệu dày lên'}>—%</span>`
    : html`<span class="pill ${pct >= 0 ? 'up' : 'dn'}" title=${why || ''}>${(pct > 0 ? '+' : '') + pct}%</span>`;
  const tile = (label, val, extra, rd, tt) => html`
    <div class="tile ${rd ? 'rd' : ''}" title=${tt || ''}><span>${label}</span><b>${val}${extra || ''}</b></div>`;
  const ol = m && m.outlier;
  const pk = d && d.peak;
  return html`
    <div class="panel">
      <h2>Metrics <small>· ${ch || 'toàn pool'} · đổi phạm vi là đổi cả chỉ số lẫn heatmap</small></h2>
      <div class="chips" style="margin:4px 0 10px">
        <select class="ws" style="margin:0" value=${ch} onChange=${e => setCh(e.target.value)}>
          <option value="">🌐 Entire pool · ${m ? m.n_channels : '…'} channels</option>
          ${chans.map(([c2, n2]) => html`<option value=${c2}>${c2} (${n2})</option>`)}
        </select>
        ${ch && m && m.scope === ch && m.channel_yt_id && html`
          <a class="btn small ghost" href="https://www.youtube.com/channel/${m.channel_yt_id}"
             target="_blank" rel="noopener" title="Mở kênh ${ch} trên YouTube (tab mới)">▶ Xem kênh trên YouTube ↗</a>`}
      </div>
      ${m && html`
        <div class="mtr1">
          ${tile('Total views', m.total_views == null ? '—' : kfmt(m.total_views),
                 pill(m.total_views_pct, 'so snapshot ~7 ngày trước'), false,
                 m.total_views == null ? 'chưa có snapshot ngày — tự có sau chu kỳ quét tới'
                                       : `${fmt(m.total_views)} views trọn đời (YouTube trả, snapshot ${m.snap_day})`)}
          ${tile('Views gained (7 days)', '+' + kfmt(m.gain7),
                 pill(m.gain7_pct, 'so 7 ngày liền trước — số đo thật qua API'), false,
                 `${fmt(m.gain7)} views mới đo được trong 7 ngày qua (hiệu số thật giữa các lần đọc API)`)}
          ${tile('Subscribers', m.subs == null ? '—' : kfmt(m.subs),
                 html`${pill(m.subs_pct, 'so snapshot ~7 ngày trước')}${m.rank && html`
                   <span class="pill gy" title="hạng theo views 7 ngày trong pool">Ranked #${m.rank.pos}/${m.rank.of}</span>`}`,
                 false, m.subs == null ? 'chưa có snapshot ngày — tự có sau chu kỳ quét tới' : fmt(m.subs) + ' subscribers')}
          ${tile('Top outlier (7 days)', ol ? 'T' + ol.tier : '—',
                 ol && (ol.pct_p50 != null
                   ? html`<span class="pill ${ol.pct_p50 >= 0 ? 'up' : 'dn'}"
                       title="VPH đỉnh so sóng trung vị (P50) của ${ol.n_waves} sóng T2+ tiền lệ cùng niche">
                       ${(ol.pct_p50 > 0 ? '+' : '') + ol.pct_p50}% vs P50</span>`
                   : html`<span class="pill gy" title="chưa đủ sóng tiền lệ để so (cần ≥3)">—% vs P50</span>`),
                 true, ol ? `${ol.title} — ${ol.ch} · VPH đỉnh ${fmt(ol.peak_vph)}` : 'chưa có video lên bậc trong 7 ngày')}
        </div>
        <div class="mtr2">
          ${tile('Current avg VPH', `${m.avg_vph || 0} v/h`, '', true,
                 `VPH trung bình của ${m.n_young} video 0-6 ngày tuổi — đo thật giữa 2 lần đọc API`)}
          ${tile('Surging T1+', String(m.surging), '', true, 'số video đang ở bậc T1 trở lên')}
          ${tile('Videos tracked', kfmt(m.videos_tracked), '', false, fmt(m.videos_tracked) + ' video radar đang theo dõi')}
          ${tile('Avg. video length', `${m.avg_len_m} minutes`, '', false, 'trung vị độ dài video >180s')}
          ${tile('Upload frequency', `~${m.upload_wk} /week`, '', false,
                 '~ = trung bình 30 ngày gần nhất' + (ch ? '' : ' tính trên mỗi kênh'))}
          ${pk
            ? tile('Most posted hours', `${hh((pk.h + 23) % 24)}–${hh((pk.h + 1) % 24)}h`,
                   pk.dows.length > 0 && html` <span class="pill gy">${pk.dows.join(', ')}</span>`, true,
                   `khung 3 giờ có nhiều video đăng nhất (${tzu === 'vn' ? 'giờ VN' : 'UTC'}) — mô tả nhịp đăng, không phải khuyến nghị`)
            : tile('Most posted hours', '—', '', true, 'chưa có dữ liệu giờ đăng trong phạm vi này')}
        </div>
        <div class="note" style="margin:2px 0 10px">Total views/Subscribers = số trọn đời kênh do YouTube trả
          (snapshot 1 lần/ngày, ~2 units) · % so ~7 ngày trước · '—' = chưa đủ lịch sử — Radary không ước đoán.</div>`}
      <h2 style="font-size:14px;margin:6px 0 6px">Giờ đăng <small>· giờ ĐĂNG theo publishedAt — không phải giờ xem · đậm = nhiều video · rê chuột vào ô để xem kênh</small></h2>
      <div class="chips" style="margin:4px 0 8px">
        ${[[30, '30 ngày'], [90, '90 ngày'], [0, 'Tất cả']].map(([v, lb]) => html`
          <button class="btn small ${days === v ? '' : 'ghost'}" onClick=${() => setDays(v)}>${lb}</button>`)}
        <button class="btn small ghost" onClick=${() => setTzu(t => (t === 'vn' ? 'utc' : 'vn'))}>
          giờ ${tzu === 'vn' ? 'VN' : 'UTC'} ⇄</button>
      </div>
      ${!d || d.total === 0
        ? html`<div class="note">Chưa có video nào có giờ đăng trong phạm vi này.</div>`
        : html`
      <div class="hmwrap" onMouseLeave=${() => setTip(null)}>
        <div class="hmrow hmhead"><span></span>
          ${Array.from({ length: 24 }, (_, h) => html`<span>${h % 3 === 0 ? h + 'h' : ''}</span>`)}</div>
        ${DOWL.map((lb, dw) => html`
          <div class="hmrow"><span class="hmlab">${lb}</span>
            ${Array.from({ length: 24 }, (_, h) => {
              const c = cellMap[dw + '-' + h];
              const a = c ? 0.18 + 0.82 * c.n / d.max : 0;
              return html`<div class="hmcell" style=${`--a:${a.toFixed(2)}`}
                onMouseEnter=${e => hover(e, dw, h)}></div>`;
            })}
          </div>`)}
        ${tip && html`<div class="hmtip" style="left:${tip.x}px;top:${tip.y}px">
          <b>${DOWL[tip.dw]} · ${hh(tip.h)}h–${hh((tip.h + 1) % 24)}h · ${tip.n} video</b>
          ${tip.list.map(([c2, n2]) => html`<div class="hmtr"><span>${c2}</span><span>${n2}</span></div>`)}
          ${tip.n === 0 && html`<div class="hmtr"><span>không có video nào đăng khung này</span></div>`}
        </div>`}
      </div>
      <div style="margin-top:8px"><button class="btn small ghost" onClick=${() => setRead(r => !r)}>📖 Đọc hộ</button></div>
      ${read && html`<div class="hmpop">${d.note}
        <div class="note" style="margin-top:4px">Tính trên ${fmt(d.total)} video radar đã bắt${d.oldest_ts
          ? ` (cũ nhất ${fmtTs(d.oldest_ts)})` : ''} — nhịp đăng gần đây, không phải lịch sử trọn đời kênh · 0 quota.</div>
      </div>`}`}
    </div>`;
}

// ---------- Board ----------
function Board({ ws, canEdit }) {
  const [board, setBoard] = useState(null);
  const [status, setStatus] = useState(null);
  const [err, setErr] = useState('');
  const [scanning, setScanning] = useState(false);
  const [sel, setSel] = useState(null);      // video đang mở chart — bấm lại là đóng
  const [cycles, setCycles] = useState([]);
  const [expand, setExpand] = useState({});  // day/'aa' -> true = xem tất cả thay vì top 15
  const load = useCallback(() => {
    api('GET', `/workspaces/${ws}/status`).then(setStatus).catch(e => setErr(String(e.message)));
    api('GET', `/workspaces/${ws}/cycles?limit=12`).then(setCycles).catch(() => setCycles([]));
    api('GET', `/workspaces/${ws}/board`).then(b => { setBoard(b); setErr(''); })
      .catch(e => { setBoard(null); setErr(String(e.message)); });
  }, [ws]);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);
  const scanNow = async () => {
    setScanning(true);
    try { await api('POST', `/workspaces/${ws}/run?budget=120`); load(); }
    catch (e) { setErr(String(e.message)); }
    setScanning(false);
  };
  const hbAge = status ? Date.now()/1000 - status.heartbeat_ts : 1e9;
  const hbCls = hbAge < 3900 ? 'ok' : hbAge < 4*3600 ? 'old' : 'dead';
  const alive = status ? Object.entries(status.tiers).reduce((a, [,n]) => a+n, 0) : 0;
  const hot = status ? Object.entries(status.tiers).filter(([t]) => t >= '1').reduce((a,[,n]) => a+n, 0) : 0;
  return html`
    <div class="chips">
      <div class="chip"><b><span class="hb ${hbCls}"></span>${ago(status?.heartbeat_ts)}</b><span>lần quét cuối (heartbeat)</span></div>
      <div class="chip"><b>${fmt(alive)}</b><span>video đang theo dõi</span></div>
      <div class="chip"><b>${hot}</b><span>video T1+</span></div>
      <div class="chip"><b>${board ? board.push_t2_today + '/' + board.push_t2_cap : '—'}</b><span>push T2 hôm nay</span></div>
      <div class="chip"><b>${board?.ntfy_enabled ? 'BẬT' : 'TẮT'}</b><span>push ntfy</span></div>
      ${canEdit && html`<div class="chip" style="margin-left:auto"><button class="btn" disabled=${scanning} onClick=${scanNow}>
        ${scanning ? html`<span class="spin"></span> đang quét…` : 'Quét ngay'}</button></div>`}
    </div>
    ${err && html`<div class="msg err">${err}</div>`}
    ${board && html`<${PulsePanel} ws=${ws}/>`}
    ${canEdit && html`<${AskRadar} ws=${ws}/>`}
    ${board && board.cohorts.map(co => html`
      <div class="panel">
        <h2>Cohort D${co.day} <small>· ${co.size} video · xếp theo VPH</small></h2>
        <div class="tablewrap"><table>
          <tr><th>#</th><th>Bậc</th><th class="num">VPH</th><th class="num">VPD</th><th class="num">Views</th><th>Tuổi</th><th>Kênh</th><th>Video</th></tr>
          ${co.videos.slice(0, expand[co.day] ? co.videos.length : 15).map(v => html`
            <tr class=${v.tier >= 2 ? 'clickable' : ''} title=${v.tier >= 2 ? 'Bấm để xem chart sóng' : ''}
                onClick=${e => { if (v.tier >= 2 && e.target.tagName !== 'A')
                  setSel(cur => cur === v.yt_id ? null : v.yt_id); }}>
              <td>${v.rank}</td><td>${TIER(v.tier)}</td>
              <td class="num">${v.est ? '~' : ''}${fmt(v.vph)}</td>
              <td class="num" title=${v.est_vpd ? 'VPD kỳ vọng = VPH×24 — video chưa đủ 24h dữ liệu' : ''}>${v.est_vpd ? '~' : ''}${fmt(v.vpd)}</td>
              <td class="num">${fmt(v.views)}</td><td>${fmtAge(v.age_h)}</td>
              <td>${v.fav ? html`<span class="favstar">★</span> ` : ''}${v.channel}</td>
              <td>${v.tier >= 2 ? '📈 ' : ''}<a href=${v.url} target="_blank">${v.title}</a></td></tr>`)}
        </table></div>
        ${co.videos.length > 15 && html`<div class="note" style="text-align:center;margin-top:6px">
          <a href="#" onClick=${e => { e.preventDefault(); setExpand(x => ({ ...x, [co.day]: !x[co.day] })); }}>
            ${expand[co.day] ? '▲ Thu gọn về top 15' : `▼ Xem tất cả ${co.videos.length} video`}</a></div>`}
      </div>`)}
    ${board && html`
      <div class="panel">
        <h2>VPD CAO MỌI TUỔI <small>· "còn VPD là còn đáng làm"</small></h2>
        <div class="tablewrap"><table>
          <tr><th class="num">VPD</th><th class="num">Views</th><th>Tuổi</th><th>Kênh</th><th>Video</th></tr>
          ${board.allages.slice(0, expand.aa ? board.allages.length : 15).map(v => html`
            <tr><td class="num">${v.est ? '~' : ''}${fmt(v.vpd)}</td><td class="num">${fmt(v.views)}</td>
              <td>${v.age_d}d</td><td>${v.fav ? html`<span class="favstar">★</span> ` : ''}${v.channel}</td>
              <td><a href=${v.url} target="_blank">${v.title}</a></td></tr>`)}
        </table></div>
        ${board.allages.length > 15 && html`<div class="note" style="text-align:center;margin-top:6px">
          <a href="#" onClick=${e => { e.preventDefault(); setExpand(x => ({ ...x, aa: !x.aa })); }}>
            ${expand.aa ? '▲ Thu gọn về top 15' : `▼ Xem tất cả ${board.allages.length} video`}</a></div>`}
        <div class="note">Cập nhật board: ${board ? fmtTs(board.generated_ts) : ''} · quota chu kỳ ~${board?.quota_used} units</div>
      </div>`}
    ${cycles.length > 0 && html`
      <div class="panel">
        <h2>Nhật ký quét <small>· mỗi dòng một chu kỳ · ⚠ bất ổn · ★ đặc biệt</small></h2>
        ${cycles.map(cy => html`
          <div class="cyclerow">
            <time>${fmtTs(cy.ts)}</time>
            <span class="note">${cy.ran && cy.ran.length ? cy.ran.join(', ') : 'không job đến hạn'}
              · ${cy.ran && cy.ran.includes('discover') ? `kênh ${cy.ch_scanned}/${cy.pool}` : `pool ${cy.pool} kênh`}
              · ${cy.refreshed} video quét · quota ~${cy.quota}${cy.tag === 'PAUSE' ? ' · PAUSE' : ''}</span>
            <span class="cystatus">
              ${(cy.notes || []).map(n => html`<span class="cywarn">⚠ ${n}</span>`)}
              ${(cy.special || []).map(sp => html`<span class="cyspec">★ ${sp}</span>`)}
              ${!(cy.notes || []).length && !(cy.special || []).length && html`<span class="cyok">✅ ổn định</span>`}
            </span>
          </div>`)}
      </div>`}
    ${!board && !err && html`<div class="panel">Đang tải…</div>`}
    ${sel && html`<${VideoModal} ws=${ws} ytId=${sel} canEdit=${canEdit} onClose=${() => setSel(null)}/>`}
  `;
}

// ---------- Tab Báo cáo (Phase 5) ----------
// Renderer md→HTML mini cho đúng tập cú pháp report engine sinh (#, ##, bảng, **, links, *ghi chú*).
// Escape HTML trước rồi mới biến đổi — title video là dữ liệu ngoài, không được tin.
function mdHtml(md) {
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = s => s
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  const out = []; let tbl = null; let ul = null;
  const flush = () => {
    if (tbl) { out.push(`<div class="tablewrap"><table>${tbl.join('')}</table></div>`); tbl = null; }
    if (ul) { out.push(`<ul>${ul.join('')}</ul>`); ul = null; }
  };
  for (const ln of esc(md).split('\n')) {
    if (ln.startsWith('|')) {
      if (ul) { out.push(`<ul>${ul.join('')}</ul>`); ul = null; }
      const cells = ln.replace(/^\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim());
      if (cells.every(c => /^:?-{3,}:?$/.test(c))) continue;          // dòng kẻ |---|
      const tag = tbl ? 'td' : 'th';
      (tbl = tbl || []).push('<tr>' + cells.map(c => `<${tag}>${inline(c)}</${tag}>`).join('') + '</tr>');
      continue;
    }
    if (/^\s*- /.test(ln)) {
      if (tbl) { out.push(`<div class="tablewrap"><table>${tbl.join('')}</table></div>`); tbl = null; }
      (ul = ul || []).push(`<li>${inline(ln.replace(/^\s*- /, ''))}</li>`);
      continue;
    }
    flush();
    const img = ln.trim().match(/^!\[([^\]]*)\]\((data:image\/svg\+xml;base64,[A-Za-z0-9+/=]+)\)$/);
    if (img) { out.push(`<img class="rptimg" alt="${img[1]}" src="${img[2]}"/>`); continue; }
    if (ln.startsWith('## ')) out.push(`<h2>${inline(ln.slice(3))}</h2>`);
    else if (ln.startsWith('# ')) out.push(`<h1>${inline(ln.slice(2))}</h1>`);
    else if (/^\*[^*].*\*$/.test(ln.trim())) out.push(`<div class="note">${inline(ln.trim().slice(1, -1))}</div>`);
    else if (ln.trim()) out.push(`<p>${inline(ln)}</p>`);
  }
  flush();
  return out.join('');
}

function Reports({ ws, canEdit }) {
  const [items, setItems] = useState(null);
  const [sel, setSel] = useState(readHash().r || null);
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const meta = items?.[0]?.meta;                 // trạng thái sinh báo cáo ngách
  const running = meta?.state === 'running';
  useEffect(() => { writeHash({ r: sel || '' }); }, [sel]);
  const loadList = useCallback(() =>
    api('GET', `/workspaces/${ws}/reports`)
      .then(l => {
        setItems(l);
        setSel(cur => (cur && l.some(i => i.id === cur)) ? cur : (l.length ? l[0].id : null));
        return l;
      })
      .catch(e => setErr(String(e.message))), [ws]);
  const loadDoc = useCallback(id =>
    api('GET', `/workspaces/${ws}/reports/${id}`).then(setDoc).catch(e => setErr(String(e.message))), [ws]);
  useEffect(() => { setItems(null); setDoc(null); setErr(''); setMsg(''); loadList(); }, [loadList]);
  // sel KHÔNG reset ở đây: giá trị từ URL hash cần sống qua mount; loadList tự kiểm tra hợp lệ
  useEffect(() => { if (sel) { setDoc(null); loadDoc(sel); } }, [sel, loadDoc]);
  useEffect(() => {                              // đang sinh → poll 5s; xong → nạp lại nội dung
    if (!running) return;
    const t = setInterval(async () => {
      const l = await loadList();
      const st = l?.[0]?.meta?.state;
      if (st !== 'running') { if (sel === 'overview' || !sel) loadDoc('overview'); }
    }, 5000);
    return () => clearInterval(t);
  }, [running, loadList, loadDoc, sel]);
  const refresh = async () => {
    setMsg(''); setErr('');
    try { const r = await api('POST', `/workspaces/${ws}/overview/refresh`); setMsg(r.note); loadList(); }
    catch (e) { setErr(String(e.message)); }
  };
  const exportPdf = () => {
    if (!doc?.md) return;
    const title = (items || []).find(i => i.id === sel)?.title || 'Báo cáo Radary';
    const w = window.open('', '_blank');
    w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${title}</title><style>
      body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;color:#111;background:#fff;max-width:840px;margin:24px auto;padding:0 18px}
      h1{font-size:20px} h2{font-size:15px;margin:18px 0 8px} p{font-size:13px;margin:6px 0}
      table{border-collapse:collapse;width:100%;font-size:11.5px;margin:8px 0}
      td,th{border:1px solid #ccc;padding:4px 6px;text-align:left;vertical-align:top} th{background:#f2f2f2}
      img{max-width:100%;margin:8px 0} ul{font-size:13px;padding-left:20px} li{margin:3px 0}
      .note{color:#666;font-size:11px} a{color:#111;text-decoration:none} .tablewrap{overflow:visible}
      @media print { body{margin:0 auto} }
      </style></head><body>${mdHtml(doc.md)}<script>window.onload=function(){setTimeout(function(){window.print()},400)}<\/script></body></html>`);
    w.document.close();
  };
  return html`
    ${err && html`<div class="msg err">${err}</div>`}
    ${msg && html`<div class="msg">${msg}</div>`}
    <div class="panel">
      <h2 style="display:flex;align-items:center;gap:10px">Báo cáo
        <small>· báo cáo ngách tự sinh từ pool, ghim đầu · báo cáo tuần mỗi CN 08:00</small>
        ${canEdit && html`<span style="margin-left:auto">
          <button class="btn small" disabled=${running} onClick=${refresh}>
            ${running ? html`<span class="spin"></span> đang sinh…` : '🔄 Sinh báo cáo ngách'}</button></span>`}
      </h2>
      ${running && html`<div class="note">⏳ ${meta.step || 'đang chạy'} — quét toàn pool mất vài phút, cứ rời tab thoải mái.</div>`}
      ${meta?.state === 'error' && html`<div class="msg err">Lần sinh trước lỗi: ${meta.error}</div>`}
      ${items === null && !err ? html`<div class="note"><span class="spin"></span> Đang tải…</div>`
        : (items || []).map(it => html`
          <div class=${'rptrow' + (sel === it.id ? ' on' : '')} onClick=${() => setSel(it.id)}>
            <span>${it.pinned ? '📌' : '📅'} ${it.title}${it.empty ? html` <span class="note">— chưa sinh lần nào</span>` : ''}</span>
            <span class="note" style="margin:0 0 0 auto">${it.pinned && meta?.state === 'done'
              ? `sinh ${fmtTs(meta.ts)} · ${meta.channels} kênh · ${meta.videos.toLocaleString('vi-VN')} video` : it.date}</span>
          </div>`)}
    </div>
    ${sel && html`
      <div class="panel rptdoc">
        ${doc?.md && html`<div style="float:right;margin-left:10px">
          <button class="btn small ghost" onClick=${exportPdf}>🖨 Xuất PDF</button></div>`}
        ${doc === null ? html`<div class="note"><span class="spin"></span> Đang tải báo cáo…</div>`
        : doc.md ? html`<div dangerouslySetInnerHTML=${{ __html: mdHtml(doc.md) }}></div>`
        : html`<div class="note">Chưa có báo cáo ngách. ${canEdit
            ? 'Bấm "🔄 Sinh báo cáo ngách" — tool sẽ quét pool đối thủ và tự viết báo cáo (OX v3, LIFT, bảng cược).'
            : 'Chờ leader/owner bấm sinh báo cáo.'}</div>`}
      </div>`}
  `;
}

// ---------- Hỏi Radar (Phase 7 — leader+, AI diễn giải chỉ số sống) ----------
function AskRadar({ ws }) {
  const [q, setQ] = useState('');
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const go = async () => {
    const question = q.trim();
    if (!question || busy) return;
    setBusy(true);
    try {
      const r = await api('POST', `/workspaces/${ws}/ask`, { q: question });
      setItems(l => [{ q: question, a: r.answer }, ...l]); setQ('');
    } catch (e) { setItems(l => [{ q: question, err: String(e.message) }, ...l]); }
    setBusy(false);
  };
  return html`
    <div class="panel">
      <h2>🧠 Hỏi Radar <small>· AI diễn giải chỉ số hiện tại — KHÔNG khuyên đánh/không đánh · 30 câu/ngày</small></h2>
      <div style="display:flex;gap:8px">
        <input type="text" placeholder="vd: Sóng nào đang tăng tốc mạnh nhất? Vì sao hôm nay ít alert?"
          value=${q} onInput=${e => setQ(e.target.value)} onKeyDown=${e => e.key === 'Enter' && go()}/>
        <button class="btn" disabled=${busy} onClick=${go}>${busy ? html`<span class="spin"></span>` : 'Hỏi'}</button>
      </div>
      ${items.map(it => html`
        <div class="askrow">
          <div class="askq">❓ ${it.q}</div>
          ${it.err ? html`<div class="msg err" style="margin:6px 0 0">${it.err}</div>`
                   : html`<div class="aska" dangerouslySetInnerHTML=${{ __html: mdHtml(it.a) }}></div>`}
        </div>`)}
    </div>`;
}

// ---------- Alerts: gom theo đơn vị hợp lý cho từng sub-tab (mockup user duyệt 24/07/2026) ----------
const SUBTABS = [['tier', 'Thăng/hạ bậc'], ['retitle', 'Đổi title'], ['rethumb', 'Đổi thumbnail'],
                 ['dead', 'Video Xóa/Ẩn'], ['channel_purge', 'Kênh ẩn hàng loạt'],
                 ['config_change', 'Đổi cấu hình'], ['pool_change', 'Đổi pool']];

// sparkline quỹ đạo bậc — thay chuỗi mũi tên dài
function TierSpark({ traj, peak }) {
  const tiers = traj && traj.length ? traj.map(e => e.to) : [0];
  const arr = tiers.length < 2 ? tiers.concat(tiers) : tiers, n = arr.length, W = 62, H = 15;
  const pts = arr.map((t, i) => `${(i / (n - 1) * (W - 2) + 1).toFixed(1)},${(H - 2 - (t / 4) * (H - 4)).toFixed(1)}`).join(' ');
  return html`<svg width=${W} height=${H} viewBox="0 0 ${W} ${H}" class=${'spark t' + peak}>
    <polyline points=${pts} fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>`;
}

// một video sóng = một thẻ (gộp mọi lần đổi bậc); verdict theo video qua event T2+ đại diện
function WaveCard({ w, canEdit, onChart, onVerdict }) {
  const [open, setOpen] = useState(false);
  const pkg = [];
  if (w.retitle) pkg.push('✏️' + w.retitle);
  if (w.rethumb) pkg.push('🖼' + w.rethumb);
  return html`
    <div class=${'wave' + (w.alive ? '' : ' ended')}>
      <span class=${'wpeak t' + w.peak} title="đỉnh đã đạt">T${w.peak}</span>
      <div class="wbody">
        <div class="wtitle"><a href=${'https://youtu.be/' + w.yt} target="_blank">${w.title}</a>
          ${w.dead && html`<span class="deadbadge">✕</span>`}</div>
        <div class="wmeta">Hiện ${TIER(w.cur)} <${TierSpark} traj=${w.traj} peak=${w.peak}/>
          <span class="wn" title="tổng số lần đổi bậc">${w.n_ev}↕</span> · ${w.ch}
          · ${kfmt(w.views)} · VPH ${kfmt(w.vph)} · ${Math.round(w.age_h / 24)}d · ${relTime(w.last_ts)}
          ${pkg.length > 0 && html` · <span class="pkg">${pkg.join(' ')}</span>`}
          ${w.pushed && html` · <span class="pushed" title="đã push điện thoại">📲</span>`}</div>
        ${open && html`<div class="wexp">${w.traj.slice().reverse().map(e => html`
          <div>${fmtTs(e.ts)} · ${TIER(e.from)}→${TIER(e.to)}${e.note ? ' · ' + e.note : ''}${e.pushed ? ' · 📲' : ''}</div>`)}</div>`}
      </div>
      <div class="wact">
        <button class="ib" title="Xem chart sóng" onClick=${() => onChart(w.yt)}>📈</button>
        <button class="ib" title=${'Bung ' + w.n_ev + ' sự kiện gốc'} onClick=${() => setOpen(o => !o)}>▾</button>
        ${w.verdict
          ? html`<span class="vd" title=${w.verdict === 'acted' ? 'đã đánh' : 'bỏ qua'}>${w.verdict === 'acted' ? '✅' : '⏭'}</span>
              ${canEdit && html`<button class="ib" title="đổi thẩm định"
                  onClick=${() => onVerdict(w.verdict_eid, w.verdict === 'acted' ? 'ignored' : 'acted')}>↺</button>`}`
          : canEdit ? html`
            <button class="ib ok" title="Đã đánh" onClick=${() => onVerdict(w.verdict_eid, 'acted')}>✅</button>
            <button class="ib" title="Bỏ qua" onClick=${() => onVerdict(w.verdict_eid, 'ignored')}>⏭</button>` : null}
      </div>
    </div>`;
}

// đổi title/thumbnail gom theo kênh — 1 kênh/dòng
function ChannelRow({ r, kind }) {
  const combined = r.retitle != null && r.rethumb != null;
  const parts = [];
  if (combined) {
    if (r.retitle) parts.push(`đổi title ${r.retitle} lần`);
    if (r.rethumb) parts.push(`đổi thumbnail ${r.rethumb} lần`);
  } else parts.push(`đổi ${kind === 'rethumb' ? 'thumbnail' : 'title'} ${r.count} lần`);
  const tag = combined ? 'PACKAGING' : (kind === 'rethumb' ? 'THUMB' : 'TITLE');
  return html`
    <div class="alertrow">
      <time>${relTime(r.last_ts)}</time>
      <div class="body">
        <span class="kindtag">${tag}</span><b>${r.ch}</b> · ${parts.join(' · ')}
        <span class="note">trên ${r.vids} video</span>
        ${r.last_new ? html`<div class="note">gần nhất 「${r.last_old}」 → 「${r.last_new}」</div>` : ''}
      </div>
    </div>`;
}

// sự kiện phẳng: dead / kênh ẩn loạt / pool / config
function EventRow({ e }) {
  return html`
    <div class="alertrow">
      <time>${fmtTs(e.ts)}</time>
      <div class="body">
        ${e.kind === 'dead' ? html`<span class="kindtag">XÓA/ẨN</span> Video không còn mở được: ${e.title}
            <span class="note">· ${e.ch} — đây cũng là tín hiệu</span>`
        : e.kind === 'channel_purge' ? html`<span class="kindtag">KÊNH ẨN HÀNG LOẠT</span>
            <b>${e.ch}</b> vừa Xóa/Ẩn <b>${e.count}</b> video trong một lần quét
            <div class="note">Tín hiệu dọn kho / đổi chiến lược / dính strike — đáng mở kênh xem thủ công.</div>`
        : e.kind === 'pool_change' ? html`<span class="kindtag">POOL</span>
            ${e.added ? 'Thêm kênh: ' + e.added.join(', ') : 'Gỡ kênh: ' + (e.removed || []).join(', ')}`
        : e.kind === 'config_change' ? html`<span class="kindtag">CONFIG</span> Đổi cấu hình
            <div class="note">${JSON.stringify(e.new || e)}</div>`
        : html`<span class="kindtag">${e.kind}</span>`}
      </div>
    </div>`;
}

function Alerts({ ws, canEdit }) {
  const [kind, setKind] = useState('tier');   // mặc định = Thăng/hạ bậc (user chốt 24/07/2026, không có tab Tất cả)
  const [d, setD] = useState(null);
  const [sel, setSel] = useState(null);      // chart sóng — bấm 📈 lần nữa là đóng
  const load = useCallback(() =>
    api('GET', `/workspaces/${ws}/alerts?kind=${kind}`).then(setD).catch(() => setD(null)), [ws, kind]);
  useEffect(() => { load(); }, [load]);
  const onVerdict = async (eid, action) => { if (eid) { await api('POST', `/workspaces/${ws}/alerts/${eid}/verdict`, { action }); load(); } };
  const onChart = yt => setSel(cur => cur === yt ? null : yt);
  const card = w => html`<${WaveCard} w=${w} canEdit=${canEdit} onChart=${onChart} onVerdict=${onVerdict}/>`;
  const body = () => {
    if (!d) return html`<div class="note">Đang tải…</div>`;
    if (d.mode === 'waves') return html`
      <div class="sechead"><h2>🌊 Đang sống</h2>
        <small>${d.alive.length} sóng còn T2+ hoặc mới cập nhật dưới 7 ngày · mỗi video một thẻ</small></div>
      ${d.alive.length === 0 && html`<div class="note">Chưa có sóng T2+ nào đang sống.</div>`}
      ${d.alive.map(card)}
      ${d.ended.length > 0 && html`
        <details class="ended-wrap"><summary>💤 Đã lắng — ${d.ended.length} sóng đã rớt T2+ & >7 ngày</summary>
          ${d.ended.map(card)}</details>`}`;
    if (d.mode === 'channels') return html`
      <div class="sechead"><h2>${d.kind === 'rethumb' ? 'Đổi thumbnail' : 'Đổi title'}</h2>
        <small>gom theo kênh · ${d.rows.length} kênh · mới nhất trước</small></div>
      ${d.rows.length === 0 && html`<div class="note">Chưa có kênh nào đổi ${d.kind === 'rethumb' ? 'thumbnail' : 'title'}.</div>`}
      ${d.rows.map(r => html`<${ChannelRow} r=${r} kind=${d.kind}/>`)}`;
    return html`
      ${d.rows.length === 0 && html`<div class="note">Chưa có sự kiện nào.</div>`}
      ${d.rows.map(e => html`<${EventRow} e=${e}/>`)}`;
  };
  return html`
    <div class="panel">
      <div class="filterbar">${SUBTABS.map(([k, label]) => html`
        <button class=${k === kind ? 'on' : ''} onClick=${() => setKind(k)}>${label}</button>`)}</div>
      ${body()}
      ${sel && html`<${VideoModal} ws=${ws} ytId=${sel} canEdit=${canEdit} onClose=${() => setSel(null)}/>`}
    </div>`;
}

// ---------- Hồ sơ kênh (modal) ----------
function ChannelModal({ ws, ytId, onClose }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    setD(null); setErr('');
    api('GET', `/workspaces/${ws}/channels/${ytId}/info`).then(setD).catch(e => setErr(String(e.message)));
  }, [ws, ytId]);
  useEffect(() => {
    const esc = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onClose]);
  const joined = d?.published_at ? new Date(d.published_at).toLocaleDateString('vi-VN') : '';
  return html`
    <div class="modalback" onClick=${e => { if (e.target === e.currentTarget) onClose(); }}>
      <div class="modal" style="max-width:620px">
        <button class="close" onClick=${onClose}>×</button>
        ${err && html`<div class="msg err">${err}</div>`}
        ${!d && !err && html`<div class="note"><span class="spin"></span> Đang tải hồ sơ kênh…</div>`}
        ${d && html`
          <div style="display:flex;gap:14px;align-items:center;padding-right:26px">
            ${d.avatar && html`<img src=${d.avatar} style="width:64px;height:64px;border-radius:50%"/>`}
            <div>
              <b style="font-size:16px">${d.title}</b>
              <div class="note"><a href=${'https://www.youtube.com/' + (d.handle || 'channel/' + d.yt_id)} target="_blank">
                www.youtube.com/${d.handle || d.yt_id}</a></div>
            </div>
          </div>
          <div class="chstats">
            <span><b>${d.subs_hidden ? 'ẩn' : kfmt(d.subs)}</b> subscribers</span>
            <span><b>${fmt(d.videos)}</b> videos</span>
            <span><b>${kfmt(d.views)}</b> views</span>
            ${d.country && html`<span><b>${d.country}</b></span>`}
            ${joined && html`<span>tham gia <b>${joined}</b></span>`}
          </div>
          ${d.description && html`
            <div class="note" style="margin-top:10px;font-weight:600;color:var(--text)">Description</div>
            <div class="chdesc">${d.description}</div>`}
          ${d.links_ok && d.links.length > 0 && html`
            <div class="note" style="margin-top:12px;font-weight:600;color:var(--text)">Links</div>
            <div class="linkrow">${d.links.map(l => html`
              <a class="linkchip" href=${l.href} target="_blank" rel="noopener" title=${l.url}>${l.title || l.url}</a>`)}</div>`}
          ${!d.links_ok && html`<div class="note" style="margin-top:12px">
            ⚠ Không đọc được mục Links (YouTube đổi cấu trúc trang About) — số liệu bên trên vẫn chuẩn từ API. Báo Claude để vá.</div>`}
          <div class="note" style="margin-top:12px">Cập nhật: ${fmtTs(d.fetched_ts)} · làm mới mỗi 24h · subs là số làm tròn công khai của YouTube</div>
        `}
      </div>
    </div>`;
}

// ---------- Pool ----------
function Pool({ ws, canEdit, role, wss, nganhs, onMoved }) {
  const [chans, setChans] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [sel, setSel] = useState(null);       // kênh đang mở hồ sơ — bấm lại là đóng
  const [picked, setPicked] = useState({});   // tách pool theo thị trường (18/08): yt_id -> true
  const [dest, setDest] = useState('');
  const [goiY, setGoiY] = useState('');       // ngách General gợi ý nhận cho workspace chưa nối
  // WORKSPACE = NGÁCH; pool thị trường chuyển bằng DẢI TAB CẤP APP (dưới header).
  // Pool tab chỉ còn: bảng kênh pool đang mở + chuyển kênh NỘI BỘ ngách + banner
  // nhận ngách cho workspace chưa nối General (nối bằng MÃ, tên theo General).
  const curW = (wss || []).find(w => w.id === ws) || {};
  const niche = (nganhs || []).find(n => n.ma === curW.ngach);
  const _bo = s => String(s || '').toLowerCase().normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim();
  useEffect(() => {
    if (niche || !(nganhs || []).length || !curW.id) return;
    const t = _bo(curW.name);
    const khop = nganhs.find(n => _bo(n.ten) === t)
      || nganhs.find(n => t.includes(_bo(n.ten)) || _bo(n.ten).includes(t));
    setGoiY((khop || nganhs[0]).ma);
  }, [ws, (nganhs || []).length]);
  const nhanNgach = async () => {
    setMsg(null);
    try {
      const r = await api('PATCH', `/workspaces/${ws}/market`, { ngach: goiY, market: '' });
      if (onMoved) await onMoved();
      setMsg({ ok: 1, t: `Đã nhận ngách${r.name ? ` — pool đổi tên "${r.name}" theo General` : ''}. Kênh hiện có nằm ở tab "Chưa phân loại", chuyển dần về các tab thị trường.` });
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const load = useCallback(() => api('GET', `/workspaces/${ws}/channels`).then(setChans), [ws]);
  useEffect(() => { load(); setPicked({}); setDest(''); setSel(null); }, [load]);
  const canMove = role === 'manager' || role === 'owner';   // dời dữ liệu lớn — cùng nấc xóa workspace
  // đích chuyển = pool ANH EM trong CÙNG ngách (gốc + các thị trường) — không chuyển chéo ngách
  const others = niche ? [
    { id: ((wss || []).find(w => w.ngach === niche.ma && !w.market) || {}).id, label: 'Chưa phân loại (gốc)' },
    ...niche.thi_truong
      .map(tt => ({ tt, w: (wss || []).find(x => x.ngach === niche.ma && x.market === tt.ma) }))
      .filter(s => s.w).map(s => ({ id: s.w.id, label: `${niche.ten} — ${s.tt.ten}` })),
  ].filter(o => o.id && o.id !== ws) : [];
  const nPicked = Object.values(picked).filter(Boolean).length;
  const move = async () => {
    const ids = Object.keys(picked).filter(k => picked[k]);
    const dw = others.find(o => o.id === Number(dest));
    if (!ids.length || !dw) return;
    if (!confirm(`Chuyển ${ids.length} kênh sang pool "${dw.label}"?\n\nLịch sử video/tick/nhịp kênh đi theo kênh; nhịp POOL của pool đích chỉ tính từ giờ trở đi. Alerts cũ ở lại pool nguồn (sổ cái).`)) return;
    setMsg(null);
    try {
      const r = await api('POST', `/workspaces/${ws}/channels/move`,
                          { to_ws: Number(dest), yt_ids: ids, confirm: true });
      setMsg({ ok: 1, t: `Đã chuyển ${r.moved.length} kênh (${r.moved_videos} video) sang "${dw.label}".` });
      setPicked({}); setDest(''); load(); onMoved && onMoved();
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const add = async () => {
    const items = text.split('\n').map(s => s.trim()).filter(Boolean);
    if (!items.length) return;
    setBusy(true); setMsg(null);
    try {
      const r = await api('POST', `/workspaces/${ws}/channels`, { items });
      const parts = [];
      if (r.added.length) parts.push(`✅ Đã thêm ${r.added.length} kênh mới`);
      if ((r.reactivated || []).length) parts.push(`↩ Khôi phục ${r.reactivated.length} kênh từng gỡ`);
      if ((r.existing || []).length) {
        const names = r.existing.slice(0, 5).map(c => c.title).join(', ');
        parts.push(`⚠ ${r.existing.length} kênh ĐÃ TỒN TẠI trong pool: ${names}${r.existing.length > 5 ? '…' : ''}`);
      }
      if (r.resolved < r.input) parts.push(`${r.input - r.resolved} dòng không resolve được`);
      const anyNew = r.added.length + (r.reactivated || []).length > 0;
      setMsg({ ok: anyNew ? 1 : 0, t: parts.join(' · ') || 'Không có gì thay đổi.' });
      if (anyNew) { setText(''); load(); }     // toàn kênh trùng → giữ nguyên ô nhập để user xem lại
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
    setBusy(false);
  };
  const remove = async ch => {
    if (!confirm(`Gỡ kênh "${ch.title}" khỏi pool?\n\n⚠ TOÀN BỘ video + lịch sử theo dõi của kênh này trong workspace sẽ bị XÓA (không hoàn tác được). Lịch sử alerts giữ nguyên.`)) return;
    try {
      const r = await api('DELETE', `/workspaces/${ws}/channels/${ch.yt_id}`);
      setMsg({ ok: 1, t: `Đã gỡ "${ch.title}" — xóa ${r.purged_videos} video khỏi radar. ${r.note}` });
      load();
    } catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const toggleFav = async c => {
    try { await api('POST', `/workspaces/${ws}/channels/${c.yt_id}/favorite`, { favorite: !c.favorite }); load(); }
    catch (e) { setMsg({ ok: 0, t: String(e.message) }); }
  };
  const active = chans.filter(c => c.active);
  const download = () => {           // tải danh sách pool — CSV UTF-8 BOM (mở được Excel/Sheets),
    const esc = s => '"' + String(s ?? '').replace(/"/g, '""') + '"';   // cột URL dán lại được vào Radary/Harvest
    const rows = [['Tên kênh', 'URL', 'Channel ID', 'Yêu thích'],
      ...active.map(c => [c.title, 'https://www.youtube.com/channel/' + c.yt_id, c.yt_id, c.favorite ? '⭐' : ''])];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\ufeff' + rows.map(r => r.map(esc).join(',')).join('\n')],
                                          { type: 'text/csv;charset=utf-8' }));
    a.download = `radary_pool_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click(); URL.revokeObjectURL(a.href);
  };
  return html`
    <div class="grid2">
      <div class="panel">
        <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:10px">
          <h2 style="margin-bottom:0">Pool kênh đối thủ <small>· ${active.length} kênh đang theo dõi · ⭐ = kênh yêu thích, video của kênh hiện sao trên Board</small></h2>
          ${active.length > 0 && html`<button class="btn small ghost" style="margin-left:auto"
            onClick=${download}>⬇ Tải danh sách (.csv)</button>`}
        </div>
        ${!niche && nganhs.length > 0 && curW.id && html`<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
          <span class="note">Niche này chưa nối với General —</span>
          <select value=${goiY} onChange=${e => setGoiY(e.target.value)}>
            ${nganhs.map(n => html`<option value=${n.ma}>${n.ten}</option>`)}
          </select>
          <button class="btn small" disabled=${!canEdit || !goiY} onClick=${nhanNgach}>Nhận "${curW.name}" là ngách này</button>
          <span class="note">(chưa có trong danh sách → Owner tạo niche ở General › Niches trước)</span>
        </div>`}
        ${curW.ngach && !curW.market && html`<div class="note" style="margin-bottom:8px">
          🕐 Hàng chờ phân loại — radar KHÔNG tự quét pool này (không tốn quota); kênh chỉ được tracking khi chuyển vào pool thị trường.</div>`}
        ${canMove && others.length > 0 && html`<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
          <span class="note">Chuyển kênh giữa các pool — tích chọn kênh rồi:</span>
          <select value=${dest} onChange=${e => setDest(e.target.value)}>
            <option value="">— pool đích —</option>
            ${others.map(o => html`<option value=${o.id}>${o.label}</option>`)}
          </select>
          <button class="btn small" disabled=${!dest || !nPicked} onClick=${move}>Chuyển ${nPicked || ''} kênh đã chọn</button>
        </div>`}
        <div class="tablewrap"><table>
          ${active.map(c => html`<tr class="clickable" title="Bấm để xem hồ sơ kênh"
              onClick=${e => { if (e.target.tagName !== 'A' && e.target.tagName !== 'BUTTON' && e.target.tagName !== 'INPUT')
                setSel(cur => cur === c.yt_id ? null : c.yt_id); }}>
            ${canMove && others.length > 0 && html`<td style="width:22px"><input type="checkbox" checked=${!!picked[c.yt_id]}
              onChange=${e => setPicked(p => ({ ...p, [c.yt_id]: e.target.checked }))}/></td>`}
            <td style="width:26px"><button class=${'starbtn' + (c.favorite ? ' on' : '')}
              title=${c.favorite ? 'Bỏ yêu thích' : 'Đánh dấu yêu thích'} disabled=${!canEdit}
              onClick=${() => canEdit && toggleFav(c)}>${c.favorite ? '★' : '☆'}</button></td>
            <td>${c.title}</td>
            <td class="num"><a href=${'https://youtube.com/channel/' + c.yt_id} target="_blank">mở</a></td>
            <td class="num">${canEdit && html`<button class="btn small ghost danger" onClick=${() => remove(c)}>gỡ</button>`}</td></tr>`)}
        </table></div>
        <div class="note">Bấm vào kênh để xem hồ sơ (subs, description, links). Gỡ = ngừng theo dõi video mới; dữ liệu lịch sử giữ lại.</div>
      </div>
      ${sel && html`<${ChannelModal} ws=${ws} ytId=${sel} onClose=${() => setSel(null)}/>`}
      ${canEdit && html`<div class="panel">
        <h2>Thêm kênh</h2>
        <textarea placeholder=${'Mỗi dòng một kênh — nhận cả 3 dạng:\nhttps://youtube.com/channel/UCxxxx\n@tenkenh\nUCxxxxxxxxxxxxxxxxxxxx'}
          value=${text} onInput=${e => setText(e.target.value)}></textarea>
        <div style="margin-top:10px"><button class="btn" disabled=${busy} onClick=${add}>
          ${busy ? html`<span class="spin"></span> đang resolve…` : 'Thêm vào pool'}</button></div>
        ${msg && html`<div class="msg ${msg.ok ? '' : 'err'}" style="margin-top:10px">${msg.t}</div>`}
      </div>`}
    </div>`;
}

// ---------- Settings ----------
const NUMS = [['T1_vph', 'Sàn VPH — T1 Quan sát'], ['T2_vph', 'Sàn VPH — T2 Ứng viên (push)'],
              ['T3_vph', 'Sàn VPH — T3 Sóng (xác nhận rồi push)'], ['T4_vph', 'Sàn VPH — T4 Bùng nổ (push tức thì)'],
              ['T2_daily_cap', 'Trần push T2 / ngày'], ['allages_vpd_floor', 'Sàn VPD bảng mọi-tuổi'],
              ['min_duration_s', 'Video tối thiểu (giây, lọc Shorts)']];
function Settings({ ws, role, orgId }) {
  // Ngách/thị trường KHÔNG chỉnh ở đây (user chốt 18/08): ngách sinh ở General,
  // pool sinh từ tab Pool theo cấu trúc ngách × thị trường — Tuning chỉ lo ngưỡng.
  const vw = role === 'viewer';
  const [cfg, setCfg] = useState(null);
  const [cal, setCal] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    api('GET', `/workspaces/${ws}/config`).then(setCfg);
    api('GET', `/workspaces/${ws}/calibration`).then(setCal).catch(() => setCal(null));
  }, [ws]);
  const save = async patch => {
    setMsg(null);
    try { setCfg(await api('PUT', `/workspaces/${ws}/config`, patch)); setMsg({ ok:1, t:'Đã lưu — có ghi vết trong Alerts.' }); }
    catch (e) { setMsg({ ok:0, t:String(e.message) }); }
  };
  const saveForm = () => {
    const patch = {};
    NUMS.forEach(([k]) => { patch[k] = Number(document.getElementById('f_' + k).value); });
    patch.ntfy_topic = document.getElementById('f_topic').value.trim();
    patch.ntfy_enabled = document.getElementById('f_ntfy').checked;
    save(patch);
  };
  const applySuggest = () => cal && save(Object.fromEntries(Object.entries(cal.suggested).map(([k,v]) => [k, Math.round(v)])));
  if (!cfg) return html`<div class="panel">Đang tải…</div>`;
  return html`
    ${msg && html`<div class="msg ${msg.ok ? '' : 'err'}">${msg.t}</div>`}
    <div class="grid2">
      <div class="panel">
        <h2>Ngưỡng bậc T1-T4 <small>· chỉnh theo dữ liệu, không theo cảm giác</small></h2>
        ${NUMS.map(([k, label]) => html`
          <div class="formrow"><label>${label}</label><input type="number" id=${'f_' + k} value=${cfg[k]} disabled=${vw}/></div>`)}
        <div class="formrow"><label>ntfy topic (bí mật)</label><input type="text" id="f_topic" value=${cfg.ntfy_topic} disabled=${vw}/></div>
        <div class="formrow"><label>Push điện thoại (ntfy)</label>
          <span><input type="checkbox" id="f_ntfy" checked=${cfg.ntfy_enabled} disabled=${vw}/> bật</span></div>
        ${vw ? html`<div class="note">Bạn là viewer — chỉ xem, không sửa được cấu hình.</div>` : html`<div style="display:flex;gap:8px">
          <button class="btn" onClick=${saveForm}>Lưu cấu hình</button>
          <button class="btn ghost" onClick=${async () => {
            try { await api('POST', `/workspaces/${ws}/push-test`);
                  setMsg({ ok:1, t:'Đã gửi tin thử — điện thoại phải kêu trong vài giây. Không kêu = app ntfy subscribe sai topic.' }); }
            catch (e) { setMsg({ ok:0, t:String(e.message) }); }
          }}>Gửi thử 📲</button>
        </div>`}
      </div>
      <div>
        <div class="panel">
          <h2>Căn cứ hiệu chỉnh <small>· phân phối VPH quan sát được</small></h2>
          ${cal ? html`
            <div class="tablewrap"><table>
              <tr><th></th><th class="num">P50</th><th class="num">P80</th><th class="num">P90</th><th class="num">P95</th><th class="num">P99</th><th class="num">Max</th></tr>
              <tr><td>VPH thực (n=${cal.n})</td><td class="num">${fmt(cal.p50)}</td><td class="num">${fmt(cal.p80)}</td>
                <td class="num">${fmt(cal.p90)}</td><td class="num">${fmt(cal.p95)}</td><td class="num">${fmt(cal.p99)}</td><td class="num">${fmt(cal.max)}</td></tr>
              <tr><td>Sàn hiện tại</td><td class="num" colspan="6">T1 ${fmt(cal.current.T1_vph)} · T2 ${fmt(cal.current.T2_vph)} · T3 ${fmt(cal.current.T3_vph)} · T4 ${fmt(cal.current.T4_vph)}</td></tr>
              <tr><td>Đề xuất (P80/P95/P99/3×P99)</td><td class="num" colspan="6">T1 ${fmt(cal.suggested.T1_vph)} · T2 ${fmt(cal.suggested.T2_vph)} · T3 ${fmt(cal.suggested.T3_vph)} · T4 ${fmt(cal.suggested.T4_vph)}</td></tr>
            </table></div>
            <div class="note">${cal.reliable
              ? `Đã có ${cal.days_of_data} ngày dữ liệu — đề xuất dùng được.`
              : `Mới ${cal.days_of_data} ngày dữ liệu — spec yêu cầu ≥14 ngày mới đáng tin. Đề xuất chỉ để tham khảo.`}</div>
            ${!vw && html`<div style="margin-top:10px"><button class="btn ghost" onClick=${applySuggest}>Áp dụng đề xuất</button></div>`}`
          : html`<div class="note">Chưa đủ dữ liệu để hiệu chỉnh.</div>`}
        </div>
        ${role === 'owner' && html`<${NicheKeys} ws=${ws} orgId=${orgId}/>`}
        ${role === 'owner' && html`<div class="note">API key toàn org, thành viên, mã mời và <b>xóa niche</b> nằm ở tab <b>Quản trị</b>.</div>`}
      </div>
    </div>`;
}

// ---------- App ----------
// ---------- HARVEST (spec_harvest_1 — read-only advisory, 1 job hiện hành/org) ----------
function Harvest({ orgId, canEdit }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState('');
  const [text, setText] = useState('');
  const [aud, setAud] = useState(true);
  const [merge, setMerge] = useState(false);
  const [picked, setPicked] = useState({});
  const [open, setOpen] = useState({});      // gkey -> true: mở danh sách kênh
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api('GET', `/orgs/${orgId}/harvest`)
    .then(x => { setD(x); setErr(''); }).catch(e => setErr(String(e.message))), [orgId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {                          // job đang chạy → poll 5s
    if (!d?.running && !['RESOLVING', 'SNOWBALL'].includes(d?.job?.status)) return;
    const t = setInterval(load, 5000); return () => clearInterval(t);
  }, [d?.running, d?.job?.status, load]);
  const job = d?.job;
  const start = async () => {
    if (job && !['DONE', 'ERROR'].includes(job.status)
        && !confirm('Đang có job chưa xong — chạy job mới sẽ BỎ DỞ job cũ. Tiếp tục?')) return;
    setBusy(true);
    try {
      const r = await api('POST', `/orgs/${orgId}/harvest`,
        { text, audience: aud, confirm: true });
      if (r.bad_lines?.length) alert('Bỏ qua ' + r.bad_lines.length + ' dòng không nhận diện được:\n' + r.bad_lines.slice(0, 5).join('\n'));
      setText(''); load();
    } catch (e) { setErr(String(e.message)); }
    setBusy(false);
  };
  const select = async () => {
    const gks = Object.keys(picked).filter(k => picked[k]);
    if (!gks.length) return;
    setBusy(true);
    try { await api('POST', `/orgs/${orgId}/harvest/select`, { groups: gks, merge }); setPicked({}); load(); }
    catch (e) { setErr(String(e.message)); }
    setBusy(false);
  };
  const removeCh = async (gkey, chId) => {
    try { await api('POST', `/orgs/${orgId}/harvest/remove-channel`, { gkey, ch_id: chId }); load(); }
    catch (e) { setErr(String(e.message)); }
  };
  // stepper: chạy đến đâu xanh đến đó
  const st = job?.status;
  const seed = job?.mode === 'SEED';
  const stepAt = st === 'RESOLVING' ? 0 : st === 'CLASSIFIED' ? 2 : st === 'SNOWBALL' ? 3
    : st === 'DONE' ? 5 : (d?.groups || []).some(g => g.selected) ? 3 : 0;
  const STEP_NAMES = ['Đọc kênh', 'Phân loại', 'Chọn nhóm', 'Tìm kênh mới', 'Kết quả'];
  const byG = {};
  (d?.results || []).forEach(r => (byG[r.gkey] = byG[r.gkey] || []).push(r));
  return html`
    ${err && html`<div class="msg err">${err}</div>`}
    ${job && html`
      <div class="panel">
        <h2>Harvest <small>· job #${job.id} · ${job.mode} · quota đã tiêu ${fmt(job.quota_used)} units</small></h2>
        <div class="hsteps">
          ${STEP_NAMES.map((nm, i) => {
            const skip = seed && (i === 1 || i === 2);
            const cls = skip ? 'skip' : i < stepAt ? 'done' : i === stepAt && st !== 'DONE' ? 'now' : '';
            return html`<span class="hstep ${cls}">${i < stepAt && !skip ? '✓ ' : ''}${nm}</span>`;
          })}
          ${d?.running && html`<span class="spin"></span>`}
        </div>
        ${st === 'PAUSED' && html`<div class="msg err" style="margin-top:8px">${job.note}
          ${canEdit && html` <button class="btn small" onClick=${async () => { await api('POST', `/orgs/${orgId}/harvest/resume`); load(); }}>▶ Chạy tiếp</button>`}</div>`}
        ${st === 'ERROR' && html`<div class="msg err" style="margin-top:8px">${job.note}
          ${canEdit && html` <button class="btn small" onClick=${async () => { await api('POST', `/orgs/${orgId}/harvest/resume`); load(); }}>▶ Thử lại từ chỗ dừng</button>`}
          <div class="note" style="margin-top:4px">Thử lại chạy tiếp từ tiến độ đã lưu (không tốn lại quota phần đã làm) — hoặc dán lại bên dưới để làm mới từ đầu.</div></div>`}
      </div>`}
    ${(!job || ['DONE', 'ERROR'].includes(st)) && html`
      <div class="panel">
        <h2>1 · Nhập liệu <small>· dán link kênh (@handle / channel/UC… / link video) — mỗi dòng một mục</small></h2>
        <textarea rows="6" style="font-family:ui-monospace,monospace;font-size:12.5px" value=${text}
          onInput=${e => setText(e.target.value)}
          placeholder=${'https://youtube.com/@kenh1\nhttps://youtube.com/channel/UC…\nhttps://youtube.com/watch?v=…'}></textarea>
        <div style="display:flex;gap:14px;align-items:center;margin-top:8px;flex-wrap:wrap">
          <label class="note" style="margin:0" title="Chỉ chạy ở bước tìm kênh mới, không chạy lúc dán link">
            <input type="checkbox" checked=${aud} onChange=${e => setAud(e.target.checked)}/>
            Phân tích trùng khán giả — xếp hạng kênh CHÍNH XÁC HƠN nhưng tốn quota gấp ~10 lần. Không chắc thì cứ để BẬT.</label>
          ${canEdit && html`<button class="btn" disabled=${busy || !text.trim()} onClick=${start}>
            ${busy ? html`<span class="spin"></span>` : 'Chạy nền ngay'}</button>`}
        </div>
        <div class="note">Dán ≤5 kênh → tự đi tìm thêm kênh tương tự ngay. Dán >5 kênh → phân nhóm trước để anh/chị chọn nhóm nào đáng mở rộng.</div>
      </div>`}
    ${st === 'CLASSIFIED' && html`
      <div class="panel">
        <h2>2 · Phân loại Workspace <small>· bấm tên nhóm để xem kênh bên trong, ✕ loại kênh lạc — rồi tick chọn nhóm muốn mở rộng</small></h2>
        <div class="htree">
          ${(d.groups || []).map(g => html`
            <div class="hleaf ${picked[g.gkey] ? 'sel' : ''}">
              <h3><input type="checkbox" checked=${!!picked[g.gkey]}
                    onChange=${e => setPicked(p => ({ ...p, [g.gkey]: e.target.checked }))}/>
                <a href="#" onClick=${e => { e.preventDefault(); setOpen(o => ({ ...o, [g.gkey]: !o[g.gkey] })); }}>
                  ${g.gkey}</a> ${g.small && html`<span class="hwarn">⚠ nhóm nhỏ</span>`}</h3>
              <div class="note" style="margin:2px 0 0">${g.n} kênh · subs ${kfmt(g.subs_min)}–${kfmt(g.subs_max)}
                · ${(g.keywords || []).slice(0, 5).join(', ')}</div>
              ${open[g.gkey] && html`<div class="hchl">
                ${(g.channels || []).map(ch => html`<div>
                  <span>${ch.title} · ${kfmt(ch.subs)} · long ${Math.round((ch.long_ratio || 0) * 100)}%</span>
                  ${canEdit && html`<span class="hx" title="Loại khỏi workspace (chỉ sửa bản nháp Harvest)"
                    onClick=${() => removeCh(g.gkey, ch.id)}>✕</span>`}</div>`)}
              </div>`}
            </div>`)}
        </div>
        ${canEdit && html`<div style="display:flex;gap:14px;align-items:center;margin-top:10px;flex-wrap:wrap">
          <button class="btn" disabled=${busy || !Object.values(picked).some(Boolean)} onClick=${select}>
            Tìm thêm kênh tương tự cho nhóm đã chọn</button>
          <label class="note" style="margin:0"><input type="checkbox" checked=${merge}
            onChange=${e => setMerge(e.target.checked)}/> Gộp các nhóm đã tick thành MỘT pool rồi mới tìm</label>
        </div>`}
      </div>`}
    ${st === 'DONE' && Object.keys(byG).map(gk => {
      const rows = byG[gk];
      const grp = (d.groups || []).find(g => gk.includes(g.gkey));
      return html`
      <div class="panel">
        <h2>3 · Report — ${gk} <small>· ${rows.length} kênh đề xuất · UI hiện tóm tắt, chi tiết trong file tải về</small></h2>
        ${grp?.rounds?.length > 0 && html`<div class="note">Đà hội tụ (kênh mới đạt chuẩn/vòng): ${grp.rounds.join(' → ')}</div>`}
        <div class="tablewrap"><table>
          <tr><th>Hạng</th><th>Kênh</th><th class="num">Subs</th><th class="num">voc</th>
            <th class="num">long%</th><th class="num">core/broad</th><th>Vòng</th><th>Vì sao / Rủi ro</th></tr>
          ${rows.slice(0, 15).map(r => html`<tr>
            <td><span class="htier ${r.tier}">${r.tier}</span></td>
            <td><a href=${'https://youtube.com/channel/' + r.ch_id} target="_blank">${r.title}</a></td>
            <td class="num">${kfmt(r.subs)}</td><td class="num">${r.voc}</td>
            <td class="num">${Math.round(r.long_ratio * 100)}%</td>
            <td class="num">${r.core}/${r.broad}${r.n_auth < 30 && job.audience ? ' ⚠' : ''}</td>
            <td>${r.round === 0 ? 'seed' : r.round}</td>
            <td class="note" style="margin:0">${r.why}${r.risk !== '—' ? html` · <span style="color:var(--viz-down)">${r.risk}</span>` : ''}</td></tr>`)}
        </table></div>
        ${rows.length > 15 && html`<div class="note">… ${rows.length - 15} kênh nữa trong file tải về</div>`}
      </div>`;
    })}
    ${st === 'DONE' && html`
      <div class="panel">
        <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
          <a class="btn" href=${`/api/orgs/${orgId}/harvest/report.md`} download>⬇ Tải báo cáo đầy đủ (.md)</a>
          <button class="btn ghost small" onClick=${() => {
            const a = (d.results || []).filter(r => r.tier === 'A').map(r => 'https://youtube.com/channel/' + r.ch_id);
            navigator.clipboard.writeText(a.join('\n')); alert('Đã copy ' + a.length + ' kênh hạng A — dán vào tab Pool của niche.');
          }}>📋 Copy kênh hạng A</button>
          <span class="note" style="margin:0">Harvest không tự thêm kênh — anh/chị tự áp dụng qua tab Pool (NP5).</span>
        </div>
      </div>`}
  `;
}

function HarvestKeys({ orgId }) {
  const [keys, setKeys] = useState([]);
  const [bulk, setBulk] = useState('');
  const [msg, setMsg] = useState('');
  const load = useCallback(() => api('GET', `/orgs/${orgId}/keys`)
    .then(ks => setKeys(ks.filter(k => k.harvest))).catch(() => {}), [orgId]);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    try {
      const r = await api('POST', `/orgs/${orgId}/keys/harvest-bulk`, { keys_text: bulk });
      setMsg(`Đã thêm ${r.added} key · trùng ${r.duplicate} · không hợp lệ ${r.invalid}`);
      setBulk(''); load();
    } catch (e) { setMsg(String(e.message)); }
  };
  const del = async k => {
    if (!confirm(`Xóa key ${k.masked} khỏi kho Harvest?`)) return;
    await api('DELETE', `/orgs/${orgId}/keys/${k.id}`); load();
  };
  return html`
    <div class="panel">
      <h2>Key Harvest <small>· kho TÁCH RIÊNG — radar không đụng, Harvest không tiêu key niche · mỗi key phải từ một dự án Google Cloud KHÁC nhau</small></h2>
      ${keys.map(k => html`<div class="cyclerow"><span>${k.masked}</span>
        <button class="btn small ghost" onClick=${async () => {
          const r = await api('POST', `/orgs/${orgId}/keys/${k.id}/test`); alert(r.ok ? '✓ Key sống' : '✗ ' + r.error);
        }}>kiểm</button>
        <button class="btn small ghost" onClick=${() => del(k)}>xóa</button></div>`)}
      ${keys.length === 0 && html`<div class="note">Chưa có key nào — Harvest sẽ không chạy được.</div>`}
      <textarea rows="4" style="font-family:ui-monospace,monospace;font-size:12px;margin-top:8px" value=${bulk}
        onInput=${e => setBulk(e.target.value)} placeholder="Dán NHIỀU key một lần — mỗi dòng một key"></textarea>
      <div style="margin-top:8px"><button class="btn small" disabled=${!bulk.trim()} onClick=${add}>Thêm cả loạt</button>
        ${msg && html` <span class="note">${msg}</span>`}</div>
    </div>`;
}

// ---------- Volume cả ngách (user 18/08: 'xem được cả volume của niche') ----------
function NicheVolume({ ma, ten }) {
  const [days, setDays] = useState(30);
  const [d, setD] = useState(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    setD(null);
    api('GET', `/ngach/${ma}/volume?days=${days}`)
      .then(x => { setD(x); setErr(''); }).catch(e => setErr(String(e.message)));
  }, [ma, days]);
  // ngày ĐANG DỞ (hôm nay) không vẽ lên đường — điểm ngày-dở cạnh ngày-trọn
  // nhìn như "cắm đầu" (user bắt 19/08); hiện thành ghi chú số đang tích
  const ptsTron = d ? d.pts.filter(p => !p.dang_do) : [];
  const homNay = d ? d.pts.find(p => p.dang_do) : null;
  const pts = ptsTron;
  // LineChart nói thang GIỜ (trục ép sàn 24): mỗi NGÀY = 24 đơn vị, nhãn trục
  // hoành = NGÀY dd/mm (không còn '0.1666d' — bug user bắt 19/08)
  const xf = h => { const p = pts[Math.round(h / 24)]; return p ? p.ngay.slice(8) + '/' + p.ngay.slice(5, 7) : ''; };
  return html`
    <div class="panel">
      <h2>Volume cả ngách — ${ten} <small>· cộng mọi pool thị trường trong phạm vi của bạn · số đo thật từ nhịp quét</small></h2>
      <div class="chips" style="margin:4px 0 0">
        ${[['30 ngày', 30], ['90 ngày', 90], ['1 năm', 365]].map(([lb, n]) => html`
          <button class="btn small ${days === n ? '' : 'ghost'}" onClick=${() => setDays(n)}>${lb}</button>`)}
      </div>
      ${err && html`<div class="msg err" style="margin-top:8px">${err}</div>`}
      ${!d && !err ? html`<div class="note" style="margin-top:8px"><span class="spin"></span> Đang tải…</div>`
        : d && pts.length < 2 ? html`<div class="note" style="margin-top:8px">Chưa đủ dữ liệu nhịp trong khoảng này —
            volume dày lên theo thời gian quét; pool mới tách tích từ lúc tách.</div>`
        : d && html`<${LineChart} title="Sóng views cả ngách — trục ngang: NGÀY (dd/mm) · trục dọc: views CỘNG THÊM trong ngày TRỌN, gộp mọi pool thị trường" height=${200}
            pts=${pts.map((p, i) => [i * 24, p.dviews])} bands=${[]} markers=${[]}
            yfmt=${kfmt} xfmt=${xf} xstep=${24 * Math.max(1, Math.ceil(pts.length / 8))} xtipfmt=${xf}/>`}
      ${homNay && html`<div class="note" style="margin-top:4px">Hôm nay (${homNay.ngay.slice(8)}/${homNay.ngay.slice(5, 7)}) đang tích:
        <b>${kfmt(homNay.dviews)}</b> views — ngày chưa trọn nên không vẽ lên đường (tránh đọc nhầm thành sụt).</div>`}
      ${d && html`
        <div class="tablewrap" style="margin-top:10px"><table>
          <tr><th>Thị trường</th><th class="num">Kênh</th><th class="num">Video</th>
            <th class="num">Views 7 ngày</th><th class="num">Views 28 ngày</th></tr>
          ${d.pools.map(b => html`<tr><td>${b.nhan}</td><td class="num">${fmt(b.kenh)}</td>
            <td class="num">${fmt(b.video)}</td><td class="num">${kfmt(b.views_7d)}</td>
            <td class="num">${kfmt(b.views_28d)}</td></tr>`)}
          <tr><td><b>Cả ngách</b></td><td class="num"><b>${fmt(d.tong.kenh)}</b></td>
            <td class="num"><b>${fmt(d.tong.video)}</b></td><td class="num"><b>${kfmt(d.tong.views_7d)}</b></td>
            <td class="num"><b>${kfmt(d.tong.views_28d)}</b></td></tr>
        </table></div>
        <div class="note" style="margin-top:8px">Nhịp pool đích tính từ lúc tách kênh — quá khứ pool trộn nằm ở
          "Chưa phân loại" (trung thực, không bịa lại lịch sử theo thị trường).</div>`}
    </div>`;
}

// '+ New Niche' ĐÃ BỎ (user 19/08): niche sinh ở General, pool dựng từ nút ＋
// trên dải tab thị trường, kênh nhập ở Data Pool — không còn cửa tạo tự do.
// ---------- Mapping: TRA CỨU MỘT TỪ KHOÁ (21/08/2026, bản 3) ----------
// Bản 1 (bản đồ 4 ô) đã bỏ. Bản 3 sửa 4 điểm user nêu:
//   1) state reset khi đổi pool — trước đó tra ở US rồi sang Spain vẫn thấy kết quả cũ
//   2) mọi kênh/video click ra được YouTube
//   3) truy vấn đang lên vẽ thành biểu đồ, không còn là dòng chữ
//   4) thêm nguồn ngoài Google Trends: Google News + Wikipedia (Reddit .json/.rss đều
//      403 từ IP này; X cần bản trả phí)
const soGon = n => n == null ? '—' : (n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : String(Math.round(n)));
const ngayVN = ts => ts ? new Date(ts * 1000).toISOString().slice(0, 10) : '—';
const linkKenh = id => id ? `https://www.youtube.com/channel/${id}` : null;
const linkVideo = id => id ? `https://youtu.be/${id}` : null;

// Đường xu hướng: interest (Trends) hoặc lượt xem (Wikipedia)
function DuongXuHuong({ diem, nhan }) {
  if (!diem || diem.length < 2) return null;
  const w = 640, h = 90, pad = 4;
  const gt = diem.map(p => p.gia_tri), max = Math.max(...gt) || 1;
  const x = i => pad + (i / (diem.length - 1)) * (w - 2 * pad);
  const y = v => h - pad - (v / max) * (h - 2 * pad);
  const duong = diem.map((p, i) => `${x(i)},${y(p.gia_tri)}`).join(' ');
  const nen = `${x(0)},${h - pad} ${duong} ${x(diem.length - 1)},${h - pad}`;
  const moc = [0, Math.floor(diem.length / 2), diem.length - 1];
  return html`<div style="margin:4px 0">
    <svg viewBox=${`0 0 ${w} ${h + 16}`} style="width:100%;height:106px" preserveAspectRatio="none">
      <polygon points=${nen} fill="var(--accent,#4C8FE0)" opacity="0.12"/>
      <polyline points=${duong} fill="none" stroke="var(--accent,#4C8FE0)" stroke-width="2"/>
      ${moc.map(i => html`<text x=${x(i)} y=${h + 12} font-size="10" fill="currentColor" opacity="0.6"
        text-anchor=${i === 0 ? 'start' : i === diem.length - 1 ? 'end' : 'middle'}>${diem[i].ngay}</text>`)}
    </svg>
    <div class="note" style="margin:0">${nhan} · đỉnh ${soGon(max)}</div></div>`;
}

// LƯỚI CHUNG cho mọi hàng thanh ngang (Trends đang lên / phổ biến / biến thể người
// ta gõ). Trước đây mỗi khối tự khai flex riêng — 44% vs 46% cho cột nhãn, 82px vs
// 92px cho cột số — nên thanh và số không thẳng hàng giữa các khối (user báo 22/08).
// Sửa hằng số ở đây là cả ba khối đổi theo, không khối nào lệch lại được.
const COT_NHAN = '46%', COT_SO = '92px';
function HangThanh({ nhan, tieu_de, phan_tram, mau, phai, phaiStyle, phaiClass }) {
  return html`
    <div style="display:flex;align-items:center;gap:8px;padding:1px 0">
      <div style=${`flex:0 0 ${COT_NHAN};overflow:hidden;text-overflow:ellipsis;white-space:nowrap`}
        title=${tieu_de}>${nhan}</div>
      <div style="flex:1;background:rgba(127,127,127,.15);border-radius:3px;height:14px">
        <div style=${`width:${phan_tram}%;height:14px;border-radius:3px;background:${mau}`}></div>
      </div>
      <div class=${phaiClass || ''} style=${`flex:0 0 ${COT_SO};text-align:right;`
        + 'white-space:nowrap;font-variant-numeric:tabular-nums' + (phaiStyle || '')}>${phai}</div>
    </div>`;
}

// THẺ KÊNH — kênh nào đẩy chủ đề này, và họ đẩy BẰNG VIDEO GÌ.
// Trước đây chỉ liệt kê "tên · N video · X view": biết kênh nào đang làm nhưng muốn
// xem họ làm bài gì thì phải tự mở YouTube dò từng kênh (user báo 22/08). Video đã
// có sẵn trong dữ liệu pool nên đính vào không tốn thêm quota nào.
function TheKenh({ k, maxView }) {
  const [mo, setMo] = useState(false);
  const vids = k.video || [];
  const hien = mo ? vids : vids.slice(0, 3);
  const ten = linkKenh(k.kenh_yt)
    ? html`<a href=${linkKenh(k.kenh_yt)} target="_blank" rel="noopener">${k.kenh}</a>`
    : html`<span>${k.kenh}</span>`;
  return html`<div style="border:1px solid var(--line);border-radius:10px;padding:10px 12px">
    <div style="display:flex;align-items:baseline;gap:8px">
      <div style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
        title=${k.kenh}>${ten}</div>
      <div class="note" style="margin:0 0 0 auto;white-space:nowrap"
        title=${`${k.so_video} video về từ khoá này trong 12 tháng · ${(k.views || 0).toLocaleString('vi-VN')} view`
          + (k.view_tb != null ? ` · trung bình ${(k.view_tb).toLocaleString('vi-VN')} view/video` : '')}>
        ${k.so_video} video · ${soGon(k.views)} view${k.view_tb != null ? ` · TB ${soGon(k.view_tb)}/video` : ''}</div>
    </div>
    <div style="height:4px;border-radius:2px;background:rgba(127,127,127,.15);margin:7px 0 8px">
      <div style=${`width:${Math.max(3, Math.round(100 * (k.views || 0) / (maxView || 1)))}%;`
        + 'height:4px;border-radius:2px;background:var(--accent,#4C8FE0)'}></div>
    </div>
    ${vids.length ? html`<div>
      ${hien.map(v => html`<div style="display:flex;gap:8px;padding:2px 0;align-items:baseline">
        <span style="flex:0 0 46px;text-align:right;font-weight:600;font-variant-numeric:tabular-nums">
          ${soGon(v.views)}</span>
        <a href=${linkVideo(v.yt_id)} target="_blank" rel="noopener" title=${v.title}
          style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${v.title}</a>
        <span class="note" style="margin:0 0 0 auto;white-space:nowrap">${ngayVN(v.pub_ts)}</span>
      </div>`)}
      ${vids.length > 3 ? html`<a href="#" class="note" style="display:inline-block;margin-top:4px"
        onClick=${e => { e.preventDefault(); setMo(!mo); }}>
        ${mo ? '▴ Thu gọn' : `▾ ${vids.length - 3} video nữa`}</a>` : ''}
    </div>` : html`<div class="note" style="margin:0">Bản lưu cũ chưa kèm video — tra lại để có</div>`}
  </div>`;
}

// Truy vấn đang lên: thanh ngang, dài theo mức tăng — yêu cầu 3 của user
function ThanhTruyVan({ muc, mau, ghi }) {
  if (!muc || !muc.length) return null;
  const BUNG_NO = 5000;
  const thuong = muc.map(m => Number(m.gia_tri) || 0).filter(v => v < BUNG_NO);
  const max = Math.max(...(thuong.length ? thuong : [1]), 1);
  return html`<div style="margin:6px 0 10px">
    <div class="note" style="margin:0 0 3px">${ghi}</div>
    ${muc.map(m => { const v = Number(m.gia_tri) || 0, no = v >= BUNG_NO; return html`
      <${HangThanh} nhan=${m.cum} tieu_de=${m.cum}
        phan_tram=${no ? 100 : Math.max(4, Math.min(100, (v / max) * 100))}
        mau=${no ? '#c62828' : mau}
        phai=${no ? '🔥 bùng nổ' : '+' + v + '%'}
        phaiStyle=${no ? ';color:#c62828;font-weight:600' : ''}/>`; })}
    ${thuong.length !== muc.length ? html`<div class="note" style="margin:2px 0 0">
      Thanh đỏ = mức tăng vượt 5.000% (Google gọi là "breakout") — không so tỉ lệ được
      với các truy vấn còn lại nên vẽ riêng.</div>` : ''}
  </div>`;
}

// BẢN ĐỒ BONG BÓNG cho từ khoá trong pool (user 21/08 gửi mẫu "beachhead map").
// X = số video trong pool (mức cạnh tranh, thang log vì lệch hàng trăm lần)
// Y = % thay đổi 30 ngày (xu hướng)   ·   cỡ bong bóng = số video mới 30 ngày
// Góc TRÊN-TRÁI = đang lên mà ít người làm = chỗ đáng nhìn trước.
function BanDoCum({ cum, onChon }) {
  const d = (cum || []).filter(r => r.phan_tram != null && r.tong_video > 0);
  if (d.length < 2) return null;
  const w = 720, h = 360, L = 66, R = 30, T = 22, B = 40;
  // TRUC NGANG = PHAN VI TRONG LOAI, khong phai so tuyet doi (user 22/08: "cac tab
  // dang cung 1 he quy chieu ve tran muc canh tranh"). Mau cau von nhieu video gap
  // hang chuc lan doi tuong ("life in" ~1.500 vs nuoc ~vai chuc) -> tran chung o tab
  // Tat ca lam doi tuong bep trai het, doc nham thanh "it canh tranh"; va moi tab tu
  // lay tran rieng nen cung mot bong bong nhay vi tri khi doi tab. Phan vi tinh TRONG
  // loai: vi tri on dinh giua cac tab, hai loai so cong bang, dung le "so voi chinh
  // phien". So tuyet doi van o tooltip + bang duoi.
  // Canh tranh do trong CUA SO 180 ngay (video_cua_so), khong phai tong tron doi —
  // user 22/08: "chia cho lifetime thi nong do pha loang qua lon" (cum chet 5 nam
  // truoc van hien "dong nguoi lam"). Fallback tong_video cho du lieu cu thieu truong.
  const canhTranh = r => r.video_cua_so ?? r.tong_video;
  const theoLoai = {};
  d.forEach(r => (theoLoai[r.loai] = theoLoai[r.loai] || []).push(canhTranh(r)));
  Object.values(theoLoai).forEach(a => a.sort((x2, y2) => x2 - y2));
  const pv = r => { const a = theoLoai[r.loai] || [];
    return a.length < 2 ? 50 : 100 * a.indexOf(canhTranh(r)) / (a.length - 1); };
  const ys = d.map(r => r.phan_tram);
  const yHi = Math.max(20, ...ys), yLo = Math.min(-20, ...ys);
  const X = v => L + (v / 100) * (w - L - R);
  const Y = v => T + (1 - (v - yLo) / (yHi - yLo || 1)) * (h - T - B);
  const rMax = Math.max(...d.map(r => r.video_30n), 1);
  const bk = n => 5 + 17 * Math.sqrt(Math.max(0, n) / rMax);
  const y0 = Y(0);
  const cotX = [0, 25, 50, 75, 100];
  // Nhãn: chỉ những cụm ĐÁNG NHÌN (3 lên mạnh + 2 giảm mạnh + 2 nhiều video nhất) —
  // 30 bong bóng mà gắn hết thì chữ chồng nhau, đúng lỗi user báo. Còn lại rê chuột.
  const theoPt = [...d].sort((a2, b2) => b2.phan_tram - a2.phan_tram);
  const theoSo = [...d].sort((a2, b2) => b2.tong_video - a2.tong_video);
  const ten = new Set([...theoPt.slice(0, 3), ...theoPt.slice(-2), ...theoSo.slice(0, 2)]
                      .filter(Boolean).map(r => r.cum));
  const daDung = [];
  return html`<div style="margin:8px 0 4px">
    <svg viewBox=${`0 0 ${w} ${h}`} style="width:100%;height:360px">
      <rect x=${L} y=${T} width=${w - L - R} height=${h - T - B} fill="currentColor" opacity="0.03"/>
      ${cotX.map(v => html`<line x1=${X(v)} y1=${T} x2=${X(v)} y2=${h - B}
        stroke="currentColor" opacity="0.10"/>`)}
      <line x1=${L} y1=${y0} x2=${w - R} y2=${y0} stroke="currentColor" opacity="0.45" stroke-dasharray="5,4"/>
      <text x=${L + 4} y=${y0 - 5} font-size="11" fill="currentColor" opacity="0.65">0% — đi ngang</text>
      ${cotX.map(v => html`<text x=${X(v)} y=${h - B + 15} font-size="11" fill="currentColor"
        opacity="0.7" text-anchor="middle">${v === 0 ? 'ít nhất loại' : v === 100 ? 'đông nhất loại' : v + '%'}</text>`)}
      <text x=${(w + L) / 2} y=${h - 6} font-size="11" fill="currentColor" opacity="0.75" text-anchor="middle">
        TRỤC NGANG — MỨC CẠNH TRANH 180 NGÀY: phân vị số-video SO VỚI CÁC CỤM CÙNG LOẠI → càng phải càng đông người làm gần đây</text>
      <text x="12" y=${(h - B + T) / 2} font-size="11" fill="currentColor" opacity="0.75"
        text-anchor="middle" transform=${`rotate(-90 12 ${(h - B + T) / 2})`}>
        TRỤC DỌC — XU HƯỚNG: % video mới so kỳ trước</text>
      <text x=${L - 4} y=${T + 10} font-size="11" fill="#2e7d32" text-anchor="end" font-weight="600">+${Math.round(yHi)}%</text>
      <text x=${L - 4} y=${T + 22} font-size="10" fill="#2e7d32" text-anchor="end">đang lên</text>
      <text x=${L - 4} y=${h - B - 12} font-size="10" fill="#c62828" text-anchor="end">đang giảm</text>
      <text x=${L - 4} y=${h - B} font-size="11" fill="#c62828" text-anchor="end" font-weight="600">${Math.round(yLo)}%</text>

      ${d.map(r => { const len = r.phan_tram > 15, xuong = r.phan_tram < -15;
        // Cụm TĂNG tách màu theo LOẠI (user 22/08): mở tab "Tất cả" là nhìn ra ngay
        // cặp kết hợp đối-tượng × mẫu-câu cùng đang lên ở góc trên-trái. Tím = cùng
        // màu sparkline mật-độ của mẫu câu, sẵn trong hệ. Giảm giữ MỘT màu đỏ —
        // ngữ nghĩa cảnh báo mạnh hơn nhu cầu phân loại.
        const mau = len ? (r.loai === 'mau_cau' ? '#7e57c2' : '#2e7d32')
                        : xuong ? '#c62828' : '#5b6b7c';
        return html`<g style="cursor:pointer" onClick=${() => onChon && onChon(r.cum)}>
          <circle cx=${X(pv(r))} cy=${Y(r.phan_tram)} r=${bk(r.video_30n)}
            style="transition:cx .6s ease,cy .6s ease,r .6s ease"
            fill=${mau} fill-opacity="0.55" stroke=${mau} stroke-width="1.8" stroke-opacity="0.95"/>
          <title>${r.cum} · ${r.loai === 'mau_cau' ? 'mẫu câu' : 'đối tượng'} · ${r.video_cua_so ?? '?'} video 180 ngày (${r.tong_video} trọn đời) · ${r.phan_tram > 0 ? '+' : ''}${r.phan_tram}% (${r.video_30n_truoc}→${r.video_30n})${r.view_moi_ngay ? ` · ${r.view_moi_ngay} view/ngày` : ''}</title>
        </g>`; })}

      ${d.filter(r => ten.has(r.cum)).map(r => {
        const cx = X(pv(r)), cy = Y(r.phan_tram), b2 = bk(r.video_30n);
        const phai = cx > (w + L) / 2;
        let y = cy + 4;
        while (daDung.some(v => Math.abs(v - y) < 14)) y += 14;
        daDung.push(y);
        const x = phai ? cx - b2 - 6 : cx + b2 + 6;
        // vẽ 2 lần: bản nền dày cùng màu nền để chữ không dính vào bong bóng/nhau
        return html`<g>
          <text x=${x} y=${y} font-size="12" font-weight="600" text-anchor=${phai ? 'end' : 'start'}
            stroke="var(--panel,#fff)" stroke-width="3.5" stroke-linejoin="round">${r.cum}</text>
          <text x=${x} y=${y} font-size="12" font-weight="600" fill="currentColor"
            text-anchor=${phai ? 'end' : 'start'}>${r.cum}</text></g>`;
      })}
    </svg>
    <div class="note" style="margin:0">${d.length} cụm · cỡ bong bóng = số video mới 30 ngày ·
      <b style="color:#2e7d32">xanh</b> đối tượng đang lên · <b style="color:#7e57c2">tím</b> mẫu
      câu đang lên · <b style="color:#c62828">đỏ</b> đang giảm ·
      góc TRÊN-TRÁI = đang lên mà còn ít người làm SO VỚI LOẠI CỦA NÓ — mỗi loại một thước
      riêng (mẫu câu vốn nhiều video hơn đối tượng hàng chục lần, đo chung một trần là đối
      tượng bẹp hết về trái); ở tab Tất cả, một cặp xanh + tím cùng góc này là một
      CẶP KẾT HỢP đáng thử. Số video thật xem ở tooltip và bảng dưới. Bấm để tra cứu cụm đó.</div>
  </div>`;
}

function Sparkline({ chuoi, mau }) {
  const d = (chuoi || []).filter(p => p);
  if (d.length < 2) return null;
  const w = 110, h = 22, max = Math.max(...d.map(p => p.gia_tri)) || 1;
  const pts = d.map((p, i) => `${(i / (d.length - 1)) * w},${h - (p.gia_tri / max) * (h - 2) - 1}`).join(' ');
  return html`<svg viewBox=${`0 0 ${w} ${h}`} style="width:110px;height:22px">
    <polyline points=${pts} fill="none" stroke=${mau} stroke-width="1.6"/></svg>`;
}

function CotVaDuong({ lua }) {
  const d = (lua || []).slice(-12).filter(x => x.thang);
  if (d.length < 2) return null;
  const w = 640, h = 120, pad = 6, bw = (w - 2 * pad) / d.length;
  const maxV = Math.max(...d.map(x => x.so_video)) || 1;
  const co = d.filter(x => x.du_mau);
  const maxR = Math.max(...co.map(x => x.view_moi_ngay), 1);
  const x = i => pad + i * bw;
  const yV = v => h - (v / maxV) * (h - 18);
  const yR = v => h - (v / maxR) * (h - 18);
  const duong = d.map((p, i) => p.du_mau ? `${x(i) + bw / 2},${yR(p.view_moi_ngay)}` : null)
                 .filter(Boolean).join(' ');
  return html`<div style="margin:6px 0 10px">
    <svg viewBox=${`0 0 ${w} ${h + 18}`} style="width:100%;height:138px">
      ${d.map((p, i) => html`<rect x=${x(i) + 2} y=${yV(p.so_video)} width=${bw - 4}
        height=${h - yV(p.so_video)} fill="var(--accent,#4C8FE0)" opacity="0.55"
        ><title>${p.thang}: ${p.so_video} video</title></rect>`)}
      ${d.map((p, i) => p.so_video === maxV ? html`<text x=${x(i) + bw / 2} y=${yV(p.so_video) - 3}
        font-size="10" font-weight="600" fill="var(--accent,#4C8FE0)" text-anchor="middle">${p.so_video}</text>` : '')}
      ${duong ? html`<polyline points=${duong} fill="none" stroke="#2e7d32" stroke-width="2"
        stroke-dasharray=${d.some(p => !p.du_mau) ? '5,3' : ''}/>` : ''}
      ${d.map((p, i) => p.du_mau ? html`<circle cx=${x(i) + bw / 2} cy=${yR(p.view_moi_ngay)} r="3"
        fill="#2e7d32"><title>${p.thang}: ${p.view_moi_ngay} view/ngày</title></circle>` : '')}
      ${d.map((p, i) => (i % 2 === 0 || d.length <= 6) ? html`<text x=${x(i) + bw / 2} y=${h + 14}
        font-size="9" fill="currentColor" opacity="0.6" text-anchor="middle">${p.thang.slice(2)}</text>` : '')}
    </svg>
    <div class="note" style="margin:0">
      <span style="color:var(--accent,#4C8FE0)">▮</span> số video ra mỗi tháng (đỉnh ${maxV})
      · <span style="color:#2e7d32">▬</span> view/ngày của lứa đó (đỉnh ${soGon(maxR)})
      ${d.some(p => !p.du_mau) ? html`· <span class="note">đường đứt nét vì có tháng dưới 2 video,
        không lấy trung vị được</span>` : ''}</div>
  </div>`;
}

function Mapping({ ws, canEdit }) {
  const [cum, setCum] = useState('');
  const [A, setA] = useState(null);
  const [B, setB] = useState(null);
  const [pool, setPool] = useState({});
  const [goiY, setGoiY] = useState([]);
  const [noi, setNoi] = useState(null);
  const [nong, setNong] = useState(null);     // Hot Topic — tải ngay khi mở tab
  const [nongMo, setNongMo] = useState(false); // Hot Topic: 5 dòng đầu hay cả danh sách
  const [luiThang, setLuiThang] = useState(0); // bản đồ tại quá khứ: 0 = hôm nay
  const [loaiCum, setLoaiCum] = useState('doi_tuong');   // đối tượng trước — thứ quyết định làm video về CÁI GÌ
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const [lichSu, setLichSu] = useState([]);
  const [xemLai, setXemLai] = useState(null);   // mốc thời gian nếu đang xem bản đã lưu

  // ĐỔI POOL = xoá sạch kết quả cũ. Thiếu chỗ này thì tra ở US xong sang Spain vẫn
  // thấy số của US — user báo 21/08 ("từ khoá thị trường US lọt sang Spain").
  useEffect(() => {
    setA(null); setB(null); setCum(''); setErr(''); setBusy(''); setXemLai(null);
    setLichSu([]); setNoi(null); setNong(null); setNongMo(false); setLuiThang(0);
    api('GET', `/workspaces/${ws}/discovery/goi-y-seed`).then(r => setGoiY(r.seed || [])).catch(() => setGoiY([]));
    const nnLuu = (() => { try { return localStorage.getItem('mapping_nn_' + ws) || ''; } catch (e) { return ''; } })();
    api('GET', `/workspaces/${ws}/discovery/tu-khoa-noi`
      + (nnLuu ? `?ngon_ngu=${encodeURIComponent(nnLuu)}` : '')).then(setNoi).catch(() => setNoi(null));
    // Hot Topic nam trong Overview (duyet mockup v2) nen tai NGAY khi mo tab —
    // truoc day tai luoi khi bam chip "Dang nong".
    api('GET', `/workspaces/${ws}/discovery/tu-khoa-nong`).then(setNong)
      .catch(() => setNong({ co_du_lieu: false, ly_do: 'không tải được' }));
    api('GET', `/workspaces/${ws}/mapping`).then(d => setPool(d.pool || {})).catch(() => setPool({}));
    // Lịch sử phải có NGAY khi mở tab: trước đây chỉ tải kèm kết quả tra cứu nên F5
    // xong là trắng bảng, đúng lỗi user báo 21/08.
    api('GET', `/workspaces/${ws}/tra-cuu/lich-su`).then(r => setLichSu(r.lich_su || []))
      .catch(() => setLichSu([]));
    // Từ khoá đang xem nằm trong URL (#q=...) -> F5 mở lại đúng chỗ, đọc từ lịch sử,
    // 0 quota. Chỉ tự mở khi hash thuộc ĐÚNG pool này.
    const h0 = readHash(), nho = nhoDoc();
    const q0 = h0.q || nho.q || '';
    // `qws` = pool SINH RA từ khoá này, không phải pool đang mở. Trước đây so với
    // `h0.ws` — mà đổi pool thì chính `ws` trong hash vừa bị ghi thành pool MỚI, nên
    // phép so luôn đúng và từ khoá của pool cũ tự được tra lại trong pool mới, ghi
    // thẳng vào lịch sử pool đó (user báo 22/08: dấu vết UZBEKISTAN ws1 10:05 -> ws20
    // 10:06, áfrica ws18 10:35 -> ws20 10:43).
    const wsCuaQ = String(h0.qws || nho.qws || '');
    if (q0 && wsCuaQ === String(ws)) traCuu(q0, true);
    else if (q0) writeHash({ q: '', qws: '' });   // đổi pool -> bỏ từ khoá của pool cũ
  }, [ws]);

  // `lai` = xem lại bản đã lưu: KHÔNG gọi lại nguồn ngoài (mỗi lần hỏi tốn 102 units).
  const traCuu = async (tu, lai) => {
    const q = (tu || cum).trim();
    if (!q) return;
    const wsLucDo = ws;
    setCum(q); setErr(''); setB(null); setXemLai(null);
    setBusy(lai ? 'Đang mở lại bản đã lưu…' : 'Đang đọc pool…');
    try {
      const a = await api('GET', `/workspaces/${ws}/tra-cuu?cum=${encodeURIComponent(q)}`
        + (lai ? '&xem_lai=1' : ''));
      if (wsLucDo !== ws) return;               // người dùng đã đổi pool giữa chừng
      if (a.khong_co_ban_luu) {                 // pool này chưa từng tra từ khoá đó
        setLichSu(a.lich_su || []); setPool(a.pool || {});
        setCum(''); setBusy(''); writeHash({ q: '', qws: '' });
        return;
      }
      setA(a); setPool(a.pool || {}); setLichSu(a.lich_su || []);
      writeHash({ q, qws: String(ws) });       // F5 giữ nguyên từ khoá đang xem
      if (a.ngoai) setB(a.ngoai);               // kết quả ngoài đã lưu từ lần trước
      if (lai) { setXemLai(a.ts || null); setBusy(''); return; }
      if (!canEdit) { setBusy(''); return; }
      if (a.ngoai) {                            // đã có bản cũ -> hỏi lại là quyết định của người
        setXemLai(a.ngoai.ts || null); setBusy(''); return;
      }
      setBusy('Đang hỏi YouTube · Google Trends · News · Wikipedia (~20 giây)…');
      const b = await api('POST', `/workspaces/${ws}/tra-cuu/ngoai`, { cum: q });
      if (wsLucDo !== ws) return;
      setB(b); setLichSu(b.lich_su || []); setBusy('');
    } catch (e) { setErr(String(e.message)); setBusy(''); }
  };
  const hoiLaiNgoai = async () => {
    setBusy('Đang hỏi lại nguồn ngoài (~20 giây, 102 units)…'); setXemLai(null);
    try {
      const b = await api('POST', `/workspaces/${ws}/tra-cuu/ngoai`, { cum });
      setB(b); setLichSu(b.lich_su || []); setBusy('');
    } catch (e) { setErr(String(e.message)); setBusy(''); }
  };

  const tp = A && A.trong_pool || {};
  const yt = B && B.youtube || {};
  const tr = B && B.trends || {};
  const nw = B && B.news || {};
  // Wikipedia: BAN LUU CU con thang-dang-chay trong chuoi (server da va 22/08 cho lan
  // hoi moi, nhung ban luu thi dong bang) -> loc + tinh lai xu huong o day de ban cu
  // het bao "xuong -42%" gia. Cung cong thuc voi server (mean quy dau vs quy cuoi).
  const wkTho = B && B.wiki || {};
  const wk = (() => {
    if (!wkTho.co_du_lieu || !(wkTho.diem || []).length) return wkTho;
    const nay = new Date(), thangNay = `${nay.getUTCFullYear()}${String(nay.getUTCMonth() + 1).padStart(2, '0')}`;
    const diem = wkTho.diem.filter(d => d.ngay !== thangNay);
    if (diem.length === wkTho.diem.length) return wkTho;      // bản mới — server đã lọc
    if (diem.length < 4) return { ...wkTho, diem };
    const n = Math.max(1, Math.floor(diem.length / 4));
    const tb = a => a.reduce((x, y) => x + y.gia_tri, 0) / a.length;
    const dau = tb(diem.slice(0, n)), cuoi = tb(diem.slice(-n));
    const lech = dau ? Math.round(100 * (cuoi - dau) / dau) : 0;
    return { ...wkTho, diem, xem_thang_cuoi: diem[diem.length - 1].gia_tri,
             xu_huong: { phan_tram: lech, chieu: lech > 15 ? 'lên' : lech < -15 ? 'xuống' : 'đi ngang' } };
  })();

  return html`
    <div class="panel" style="border-left:4px solid var(--accent,#4C8FE0)">
      <div class="eyebrow" style="margin-top:0">Overview${pool.ngach ? ` · ngách ${pool.ngach}` : ''}
        ${pool.ngon_ngu ? html`<span style="color:var(--accent,#4C8FE0)"> · mọi số liệu đo theo thị trường ${pool.market} / ${pool.ngon_ngu}</span>` : ''}</div>
      <b style="font-size:18px">${pool.ten || '—'}</b>
      <div class="chips" style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 0">
        <div class="chip"><b>${(pool.so_video || 0).toLocaleString()}</b><span>video</span></div>
        <div class="chip"><b>${pool.so_kenh || 0}</b><span>kênh</span></div>
        <div class="chip"><b>${pool.video_moi_30_ngay || 0}</b><span>video mới 30 ngày</span></div>
        ${pool.view_giua_moi ? html`<div class="chip"><b>${soGon(pool.view_giua_moi)}</b><span>view/video mới (mốc pool)</span></div>` : ''}
        ${pool.vph_giua_pool != null ? html`<div class="chip"><b>${pool.vph_giua_pool}</b><span>view/giờ trung vị pool</span></div>` : ''}
        ${nong && nong.co_du_lieu ? html`<div class="chip"><b>${soGon(nong.nguong_no_view_ngay)}</b><span>ngưỡng video nổ (view/ngày)</span></div>` : ''}
      </div>
      ${!pool.market ? html`<div style="margin-top:8px;padding:8px 10px;border-radius:8px;
        border:1px solid #ef6c00;background:rgba(239,108,0,.08);font-size:13px">
        ⚠ Pool chưa gắn thị trường — không ép được vùng khi hỏi YouTube/Trends, kết quả sẽ
        theo IP máy chủ (Việt Nam). Mở pool theo thị trường (US/Spain…) ở dải tab.</div>` : ''}
      <div class="eyebrow" style="margin-top:14px">Hot Topic
        ${nong && nong.co_du_lieu ? html`<span class="note" style="text-transform:none;letter-spacing:0;font-weight:400">
          · video "nổ" = top ${100 - (nong.phan_vi || 90)}% view/ngày của ${nong.so_video_moi}
          video 2-${nong.cua_so_ngay} ngày tuổi (nền ${Math.round((nong.nen || 0) * 100)}%)
          · cụm nóng = tỉ lệ nổ ≥ 2× nền · xếp theo HIỆU SUẤT VIEW
          ${nong.duoc_soi ? ` · tự soi External tối đa ${nong.ngan_sach_ngay} cụm/ngày (hôm nay ${nong.da_soi_hom_nay})` : ''}</span>` : ''}</div>
      ${!nong ? html`<div class="note">Đang tải…</div>`
        : !nong.co_du_lieu ? html`<div class="note">${nong.ly_do}</div>`
        : html`<div>
          <table class="tbl"><thead><tr><th>Cụm</th><th>Loại</th>
            <th title="video 2-60 ngày tuổi chứa cụm">Video mới</th>
            <th title="bao nhiêu trong số đó là video nổ">Nổ</th>
            <th>Video nổ nhất</th><th>External</th></tr></thead>
            <tbody>${(nong.cum || []).slice(0, nongMo ? undefined : 5).map(m => html`<tr>
              <td><a href="#" onClick=${e => { e.preventDefault(); traCuu(m.cum); }}>${m.cum}</a></td>
              <td class="note">${m.loai === 'doi_tuong' ? 'đối tượng' : 'công thức'}</td>
              <td>${m.so_moi}</td>
              <td style="white-space:nowrap"><b>${m.so_no}/${m.so_moi}</b>
                <span class="note"> = ${Math.round(m.ti_le_no * 100)}%</span></td>
              <td>${m.vi_du ? html`<a href=${linkVideo(m.vi_du.yt_id)} target="_blank"
                  rel="noopener" title=${m.vi_du.title}
                  style="display:inline-block;max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom">
                  ${m.vi_du.title}</a>
                <span class="note"> ${soGon(m.vi_du.views)}</span>` : html`<span class="note">—</span>`}</td>
              <td class="note" style="white-space:nowrap">${m.ngoai
                ? `${m.ngoai.tong_view_90n != null ? soGon(m.ngoai.tong_view_90n) + ' view 90n' : 'đã soi'}`
                : m.dang_soi ? 'đang soi…' : '—'}</td>
            </tr>`)}</tbody></table>
          ${(nong.cum || []).length > 5 ? html`<a href="#" class="note" style="display:inline-block;margin-top:4px"
            onClick=${e => { e.preventDefault(); setNongMo(!nongMo); }}>
            ${nongMo ? '▴ Thu gọn' : `▾ Xem cả ${nong.cum.length} cụm`}</a>` : ''}
        </div>`}
    </div>

    <div class="panel">
      <div class="eyebrow" style="margin-top:0">Keyword</div>
      <div class="row" style="gap:6px;flex-wrap:wrap">
        <button class=${'ktab' + (loaiCum === 'doi_tuong' ? ' on' : '')}
          onClick=${() => setLoaiCum('doi_tuong')}>Đối tượng<small>nước / địa danh</small></button>
        <button class=${'ktab' + (loaiCum === 'mau_cau' ? ' on' : '')}
          onClick=${() => setLoaiCum('mau_cau')}>Mẫu câu<small>cụm lặp lại</small></button>
        <button class=${'ktab' + (loaiCum === '' ? ' on' : '')}
          onClick=${() => setLoaiCum('')}>Tất cả<small>gộp hai loại</small></button>
      </div>
      <div class="ksearch">
        <input type="text" placeholder="tra MỘT từ khoá bất kỳ, ví dụ: life in alaska" value=${cum}
          onInput=${e => setCum(e.target.value)}
          onKeyDown=${e => { if (e.key === 'Enter') traCuu(); }}/>
        <button class="btn primary" onClick=${() => traCuu()} disabled=${!!busy}>Tra cứu</button>
        <span class="note" style="margin:0">${busy}${err ? html`<span style="color:#c62828">${err}</span>` : ''}</span>
        ${lichSu.length ? html`<select value=""
          title="Mỗi từ khoá là một phiên riêng, đo tại thời điểm ghi bên cạnh — không so số giữa các phiên (chúng đo ở những thời điểm khác nhau)"
          onChange=${e => { if (e.target.value) traCuu(e.target.value, true); e.target.value = ''; }}>
          <option value="">Lịch sử tra cứu (${lichSu.length}) — chọn để mở lại, 0 quota</option>
          ${lichSu.map(l => html`<option value=${l.cum}>${l.cum} · ${new Date(l.ts * 1000).toLocaleString('vi-VN')} · ${l.co_ngoai ? 'đã hỏi External' : 'chưa hỏi External'}</option>`)}
        </select>` : ''}
      </div>

      ${(noi && (noi.cum || []).length) ? html`<div style="margin-top:10px">
        <div class="note" style="margin:0 0 3px">Từ khoá trong pool — đang lên / đang giảm
          (so ${noi.cua_so_ngay} ngày qua với ${noi.cua_so_ngay} ngày liền trước; cập nhật theo
          mỗi vòng quét pool)

          ${!noi.tu_de ? html`<span> · lọc ngôn ngữ:
            <select value=${noi.ngon_ngu_loc || ''} onChange=${e => {
              try { localStorage.setItem('mapping_nn_' + ws, e.target.value); } catch (err) {}
              api('GET', `/workspaces/${ws}/discovery/tu-khoa-noi?ngon_ngu=${encodeURIComponent(e.target.value)}`)
                .then(setNoi).catch(() => {});
            }}>
              <option value="">(không lọc — pool trộn ngôn ngữ)</option>
              <option value="English">English</option>
              <option value="Spanish">Spanish</option>
              <option value="Vietnamese">Tiếng Việt</option>
            </select>
            ${(noi.ngon_ngu_trong_pool || []).length ? html`<span> · pool có:
              ${(noi.ngon_ngu_trong_pool || []).map(([ma, n]) => `${ma} ${n}`).join(' · ')}</span>` : ''}
          </span>` : ''}</div>
        ${noi.cach_lay ? html`<div class="note" style="margin:2px 0 6px">
          <b>Từ khoá lấy ở đâu ra:</b> ${noi.cach_lay}</div>` : ''}
        <div class="row" style="gap:10px;align-items:center;flex-wrap:wrap;margin-top:8px">
          <span class="note" style="margin:0">Bản đồ tại thời điểm:</span>
          <input type="range" min="0" max="12" step="1" value=${12 - luiThang}
            style="width:220px;accent-color:var(--accent,#4C8FE0)"
            onChange=${e => {
              const lui = 12 - Number(e.target.value);
              setLuiThang(lui);
              const nn = noi.ngon_ngu_loc || '';
              api('GET', `/workspaces/${ws}/discovery/tu-khoa-noi?lui_thang=${lui}`
                + (nn ? `&ngon_ngu=${encodeURIComponent(nn)}` : ''))
                .then(setNoi).catch(() => {});
            }}/>
          <b style="font-variant-numeric:tabular-nums">${luiThang
            ? new Date((noi.moc_ts || 0) * 1000).toLocaleDateString('vi-VN') + ` (lùi ${luiThang} tháng)`
            : 'hôm nay'}</b>
          ${luiThang ? html`<span class="note" style="margin:0">· dựng lại từ ngày đăng video —
            cột View/ngày tắt (views là của hôm nay, không có lịch sử theo cụm)</span>` : ''}
        </div>
        <${BanDoCum} cum=${(noi.cum || []).filter(r => !loaiCum || r.loai === loaiCum)}
          onChon=${c => traCuu(c)}/>
        <table class="tbl"><thead><tr><th>Cụm</th><th>Xu hướng</th>
          <th>Video ${noi.cua_so_ngay}n</th><th>View/ngày</th>
          <th title="số video mới mỗi tháng — khoảng thời gian khác cột Xu hướng">Mật độ theo tháng</th></tr></thead>
          <tbody>${(noi.cum || []).filter(r => !loaiCum || r.loai === loaiCum)
            .map(r => { const len = r.chieu === 'lên', xuong = r.chieu === 'xuống';
            return html`<tr>
            <td><a href="#" onClick=${e => { e.preventDefault(); traCuu(r.cum); }}>${r.cum}</a>
              <span class="note"> ${r.tong_video}</span></td>
            <td style=${`white-space:nowrap;font-weight:600;color:${len ? '#2e7d32' : xuong ? '#c62828' : 'inherit'}`}>
              ${r.phan_tram == null ? html`<span class="note" style="font-weight:400">ít mẫu</span>`
                : `${len ? '↑' : xuong ? '↓' : '→'} ${r.phan_tram > 0 ? '+' : ''}${r.phan_tram}%`}</td>
            <td style="white-space:nowrap">${r.video_30n_truoc} → <b>${r.video_30n}</b></td>
            <td>${r.view_moi_ngay ?? '—'}</td>
            <td style="width:120px" title="mật độ theo THÁNG — khác cột xu hướng (30 ngày)">
              <${Sparkline} chuoi=${r.chuoi} mau="#7e57c2"/></td>
          </tr>`; })}</tbody></table>
      </div>` : (goiY.length ? html`<div style="margin-top:6px">
        <span class="note">Từ khoá phổ biến trong pool này:</span>
        ${goiY.map(g => html`<button class="btn small ghost" style="margin:2px 4px 2px 0"
          onClick=${() => traCuu(g.seed)}>${g.seed} <span class="note">${g.so_video}</span></button>`)}
      </div>` : '')}
    </div>

    ${A ? html`<div class="panel">
      <div class="eyebrow" style="margin-top:0">Keyword Analytics — “${A.cum}”
        <span class="note" style="text-transform:none;letter-spacing:0;font-weight:400">
          ${xemLai ? ` · phiên đo ${new Date(xemLai * 1000).toLocaleString()}` : ''}
          ${B && B.quota_da_tieu ? ` · ${B.quota_da_tieu} units` : ''}</span>
        ${xemLai && canEdit ? html`<button class="btn small ghost" style="margin-left:8px"
          onClick=${hoiLaiNgoai} disabled=${!!busy}>↻ Hỏi lại (102 units)</button>` : ''}</div>

      <div class="eyebrow" style="color:var(--accent,#4C8FE0)">A · In pool — ${pool.ten}</div>
      ${!tp.co_du_lieu ? html`<div class="note">${tp.ly_do}</div>` : html`
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
          <div class="chip"><b>${tp.so_video}</b><span>video</span></div>
          <div class="chip"><b>${tp.so_kenh}</b><span>kênh</span></div>
          <div class="chip"><b>${tp.ti_trong_video}%</b><span>số video của pool</span></div>
          <div class="chip"><b>${tp.ti_trong_view}%</b><span>view của pool</span></div>
          <div class="chip"><b>${tp.vph_giua ?? '—'}</b><span>view/giờ${
            tp.vph_giua && tp.vph_giua_pool ? html` · <b style=${`color:${tp.vph_giua >= tp.vph_giua_pool ? '#2e7d32' : '#c62828'}`}>${(tp.vph_giua / tp.vph_giua_pool).toFixed(1)}× pool</b>` : ''}</span></div>
        </div>`}

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:14px">
        ${tp.co_du_lieu ? html`<div>
          <div class="note" style="margin:0 0 4px">Xu hướng theo lứa đăng — mỗi tháng ra bao
          nhiêu video, lứa đó ăn bao nhiêu view/ngày</div>
          <${CotVaDuong} lua=${tp.lua}/>
          <details><summary class="note" style="cursor:pointer">Xem số chi tiết</summary>
          <table class="tbl"><thead><tr><th>Tháng</th><th>Video mới</th><th>View/ngày (trung vị)</th></tr></thead>
            <tbody>${(tp.lua || []).slice(-12).map(l => html`<tr>
              <td>${l.thang}</td><td>${l.so_video}</td>
              <td>${l.du_mau ? l.view_moi_ngay : html`<span class="note">— ít mẫu</span>`}</td></tr>`)}
            </tbody></table></details>
        </div>` : ''}

        <div>
          <div class="eyebrow" style="margin-top:0;color:var(--accent,#4C8FE0)">B · YouTube market — ${pool.market || '(chưa gắn)'}
            <span class="note" style="text-transform:none;letter-spacing:0;font-weight:400"> · ngoài pool, trong YouTube</span></div>
          ${!B ? html`<div class="note">Chưa hỏi thị trường cho từ khoá này${canEdit ? ' — bấm ↻ Hỏi lại phía trên' : ''}.</div>`
            : yt.co_du_lieu ? html`<div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
              <div class="chip"><b>${soGon(yt.tong_view_90n)}</b><span>view 90 ngày (top ${yt.so_ket_qua} video)</span></div>
              <div class="chip"><b>${soGon(yt.view_giua)}</b><span>view giữa</span></div>
              <div class="chip"><b>${(yt.kenh_moi_noi || []).length}</b><span>kênh nhỏ lọt top</span></div>
            </div>
            <div class="note" style="margin:0 0 6px">Không nền tảng nào công bố số lần tìm kiếm
              của YouTube (API trả 1.000.000 cho mọi truy vấn — số giả). Đây là <b>view thật</b>
              thị trường đang trả${(yt.da_bo && (yt.da_bo.khac_ngon_ngu || yt.da_bo.shorts))
                ? ` · đã bỏ ${yt.da_bo.khac_ngon_ngu} video khác ngôn ngữ, ${yt.da_bo.shorts} Shorts` : ''}.</div>
            ${(yt.top_video || []).slice(0, 6).map(v => html`<div style="padding:2px 0">
              <span style="font-weight:600;min-width:52px;display:inline-block">${soGon(v.views)}</span>
              <a href=${linkVideo(v.yt_id)} target="_blank" rel="noopener">${v.title}</a>
              <span class="note"> · ${v.subs == null ? 'subs ẩn' : soGon(v.subs) + ' subs'}
                · ${v.tuoi_ngay} ngày · ${soGon(v.view_moi_ngay)}/ngày</span></div>`)}
            ${(yt.kenh_moi_noi || []).length ? html`<div style="margin-top:8px">
              <div><b>Kênh nhỏ đang thắng chủ đề này</b> <span class="note">(dưới 50k subs mà vẫn lọt top view)</span></div>
              ${(yt.kenh_moi_noi || []).map(k => html`<div style="padding:2px 0">
                ${linkKenh(k.kenh_id) ? html`<a href=${linkKenh(k.kenh_id)} target="_blank" rel="noopener">${k.kenh}</a>` : k.kenh}
                <span class="note"> · ${soGon(k.subs)} subs · ${k.so_video_top} video trong top · bài tốt nhất </span>
                ${k.video_tot_nhat ? html`<a href=${linkVideo(k.video_tot_nhat)} target="_blank" rel="noopener">${soGon(k.view_tot_nhat)} view</a>`
                  : html`<span class="note">${soGon(k.view_tot_nhat)} view</span>`}
                <span class="note">${k.lap_luc ? ` · lập ${k.lap_luc}` : ''}</span></div>`)}
            </div>` : ''}
          </div>` : html`<div class="note">YouTube: ${yt.ly_do || 'không có dữ liệu'}</div>`}
          ${B && (B.bien_the || []).length ? html`<div style="margin-top:10px">
            <div><b>Biến thể người ta gõ</b> <span class="note">· YouTube autocomplete (thanh dài
              = lọt ra từ nhiều hướng gõ) + Bing (gợi ý tìm kiếm web, cụm YouTube không có)</span></div>
            ${(B.bien_the || []).map(m => { const max = Math.max(...B.bien_the.map(x => x.do_phu || 0)) || 1;
              return html`<${HangThanh} tieu_de=${m.cum}
                nhan=${html`<a href="#" onClick=${e => { e.preventDefault(); traCuu(m.cum); }}>${m.cum}</a>`}
                phan_tram=${m.nguon === 'bing' ? 26 : Math.max(4, (m.do_phu / max) * 100)}
                mau=${m.nguon === 'bing' ? '#8d6e63' : '#7e57c2'}
                phaiClass="note" phai=${m.nguon === 'bing' ? 'Bing' : m.do_phu + ' hướng'}/>`; })}
          </div>` : ''}
        </div>
      </div>

      ${tp.co_du_lieu && (tp.top_kenh || []).length ? html`<div style="margin-top:14px">
        <div class="eyebrow">Kênh đẩy mạnh chủ đề này (12 tháng) ${' '}
          <span class="note">· thanh = view của kênh so với kênh mạnh nhất · bấm tiêu đề mở video</span></div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:10px">
          ${(tp.top_kenh || []).map(k => html`<${TheKenh} k=${k}
            maxView=${Math.max(...tp.top_kenh.map(x => x.views || 0), 1)}/>`)}
        </div>
      </div>` : ''}
      ${tp.co_du_lieu && tp.moi_nhat ? html`<div class="note" style="margin-top:6px">Bài gần nhất trong pool: ${' '}
        <a href=${linkVideo(tp.moi_nhat.yt_id)} target="_blank" rel="noopener">${tp.moi_nhat.title}</a>
        · ${linkKenh(tp.moi_nhat.kenh_yt) ? html`<a href=${linkKenh(tp.moi_nhat.kenh_yt)} target="_blank" rel="noopener">${tp.moi_nhat.kenh}</a>` : tp.moi_nhat.kenh}
        · ${soGon(tp.moi_nhat.views)} view · ${ngayVN(tp.moi_nhat.pub_ts)}</div>` : ''}

      ${B ? html`<div>
        <div class="eyebrow" style="margin-top:14px;color:var(--accent,#4C8FE0)">C · External traffic
          <span class="note" style="text-transform:none;letter-spacing:0;font-weight:400">
          · sự quan tâm NGOÀI nền tảng YouTube — Google Trends · Google News · Wikipedia · 0 quota</span></div>
        <div class="exgrid">
          <div class="excard">
            <h3>Google Trends <span class="note">· ${tr.geo || ''} · ${tr.timeframe || '12 tháng'}${tr.tu_cache ? ' · từ cache hôm nay' : ''}</span></h3>
            ${tr.co_du_lieu ? html`<div>
              ${tr.xu_huong ? html`<div class="big" style=${`color:${tr.xu_huong.chieu === 'lên' ? '#2e7d32' : tr.xu_huong.chieu === 'xuống' ? '#c62828' : 'inherit'}`}>
                ${tr.xu_huong.chieu === 'lên' ? '↑' : tr.xu_huong.chieu === 'xuống' ? '↓' : '→'}
                ${tr.xu_huong.phan_tram > 0 ? '+' : ''}${tr.xu_huong.phan_tram}%</div>` : ''}
              <${DuongXuHuong} diem=${tr.diem} nhan="Mức quan tâm tương đối (0–100)"/>
              <${ThanhTruyVan} muc=${tr.rising} mau="#2e7d32" ghi="Truy vấn ĐANG LÊN (so kỳ trước)"/>
              <${ThanhTruyVan} muc=${tr.top} mau="var(--accent,#4C8FE0)" ghi="Truy vấn phổ biến nhất (0–100)"/>
              ${!(tr.rising || []).length && !(tr.top || []).length ? html`<div class="note">
                Không có truy vấn liên quan (từ khoá hẹp) — xem "biến thể người ta gõ" ở khối B.</div>` : ''}
            </div>` : html`<div class="note">${tr.rate_limit ? '⏳ ' : ''}${tr.ly_do || 'không có dữ liệu'}</div>`}
          </div>
          <div class="excard">
            <h3>Google News <span class="note">· tin gần nhất</span></h3>
            ${nw.co_du_lieu ? html`<div>
              <div class="big">${nw.so_bai}<span style="font-size:13px;font-weight:400;color:var(--muted,#8B96A8)"> bài liên quan</span></div>
              ${(nw.bai || []).map(b => html`<div style="padding:3px 0;border-bottom:1px solid var(--line,#243149)">
                <a href=${b.link} target="_blank" rel="noopener">${b.tieu_de}</a>
                <span class="note" style="display:block;margin:0">${b.nguon} · ${b.ngay}</span></div>`)}
            </div>` : html`<div class="note">${nw.ly_do || 'không có dữ liệu'}</div>`}
          </div>
          <div class="excard">
            <h3>Wikipedia <span class="note">· lượt xem bài/tháng</span></h3>
            ${wk.co_du_lieu ? html`<div>
              ${wk.xu_huong ? html`<div class="big" style=${`color:${wk.xu_huong.chieu === 'lên' ? '#2e7d32' : wk.xu_huong.chieu === 'xuống' ? '#c62828' : 'inherit'}`}>
                ${wk.xu_huong.chieu === 'lên' ? '↑' : wk.xu_huong.chieu === 'xuống' ? '↓' : '→'}
                ${wk.xu_huong.phan_tram > 0 ? '+' : ''}${wk.xu_huong.phan_tram}%</div>` : ''}
              <${DuongXuHuong} diem=${wk.diem} nhan=${`Bài "${wk.bai}" · tháng chốt gần nhất ${soGon(wk.xem_thang_cuoi)} (tháng đang chạy không vẽ)`}/>
              ${(wk.bai_lien_quan || []).length ? html`<div class="note">Bài liên quan: ${(wk.bai_lien_quan || []).join(' · ')}</div>` : ''}
            </div>` : html`<div class="note">${wk.ly_do || 'không có dữ liệu'}${wk.bai ? ` (bài: ${wk.bai})` : ''}</div>`}
          </div>
        </div>
      </div>` : ''}
    </div>` : ''}`;
}

const TABS = [['board', 'Board'], ['alerts', 'Alerts'], ['mapping', 'Mapping'], ['reports', 'Report'],
              ['pool', 'Data Pool'], ['harvest', 'Harvest'], ['settings', 'Tuning'], ['admin', 'Setting']];
function App() {
  const h0 = readHash();
  const [me, setMe] = useState(undefined);       // undefined = đang kiểm tra, null = chưa đăng nhập
  const [wss, setWss] = useState([]);
  const nho0 = nhoDoc();
  const [ws, setWs] = useState(h0.ws ? Number(h0.ws) : (nho0.ws ? Number(nho0.ws) : null));
  const [tab, setTab] = useState(h0.tab || nho0.tab || 'board');
  const [nganhs, setNganhs] = useState([]);      // ngách + thị trường CỦA ngách — sinh ở General (18/08)
  const [nicheView, setNicheView] = useState(false);   // Board: xem VOLUME CẢ NGÁCH thay vì 1 pool
  useEffect(() => { api('GET', '/auth/me').then(setMe).catch(() => setMe(null)); }, []);
  useEffect(() => { if (me) api('GET', '/ngach').then(setNganhs).catch(() => setNganhs([])); }, [me]);
  useEffect(() => { writeHash({ tab, ws: ws ?? '' }); }, [tab, ws]);
  useEffect(() => {                              // tab trong hash không hợp lệ với vai → về board
    if (!me) return;
    const cur0 = wss.find(w => w.id === ws);
    const orgId0 = cur0 ? cur0.org_id : (me.orgs || [])[0]?.id;
    const role0 = (me.orgs || []).find(o => o.id === orgId0)?.role || 'viewer';
    // 21/08: 'mapping' phải có trong whitelist này — thiếu là bấm tab xong bị đá về
    // Board ngay (guard chạy sau setTab). Viewer xem được, như Board.
    const ok = ['board', 'alerts', 'mapping', 'reports', 'settings'].includes(tab)
      || (['pool', 'harvest'].includes(tab) && role0 !== 'viewer')   // 23/07: leader trở lên
      || (tab === 'admin' && role0 === 'owner');
    if (!ok) setTab('board');
  }, [me, wss, ws, tab]);
  const loadWs = useCallback(async keep => {
    const list = await api('GET', '/workspaces');
    setWss(list);
    if (!keep && list.length && !list.find(w => w.id === ws)) setWs(list[0].id);
    return list;
  }, [ws]);
  useEffect(() => { if (me) loadWs(); }, [me]);
  const logout = async () => { await api('POST', '/auth/logout'); setMe(null); setWss([]); setWs(null); };
  if (me === undefined) return html`<div class="panel" style="max-width:300px;margin:80px auto;text-align:center"><span class="spin"></span> Đang tải…</div>`;
  if (me === null) return html`<${Login} onDone=${r => setMe(r)}/>`;
  const cur = wss.find(w => w.id === ws);
  const orgId = cur ? cur.org_id : (me.orgs || [])[0]?.id;
  const role = (me.orgs || []).find(o => o.id === orgId)?.role || 'viewer';
  const canEdit = role !== 'viewer';
  // V3 (lam gon 16/08): SSO qua OUTLIERY -> tab Quan tri AN HAN ke ca owner —
  // khoa nhap o General > API Keys, quyen o General > Permissions (server cung 404).
  const tabs = TABS.filter(([k]) => (['pool', 'harvest'].includes(k) ? canEdit
    : k === 'admin' ? (!me.sso && (role === 'owner' || role === 'manager')) : true));
  // 23/07: Data Pool/Harvest/New Niche = leader trở lên. 04/08: manager vào tab Quản trị
  // CHỈ thấy khối xóa niche (vận hành) — key/thành viên/LLM vẫn riêng owner (server chặn thật).
  // DẢI TAB THỊ TRƯỜNG CỦA NGÁCH (user 18/08): Board/Alerts/Report/Pool/Tuning đều
  // xem theo thị trường — bấm tab = chuyển sang pool thị trường đó (đếm theo SỐ KÊNH,
  // Data Pool quản kênh); tab chưa có pool = nút ＋ dựng ngay (leader trở lên).
  const niche = cur && nganhs.find(n => n.ma === cur.ngach);
  const goc = niche && wss.find(w => w.ngach === niche.ma && !w.market);
  // thứ tự ưu tiên user 19/08: US trước → Tây Ban Nha → thị trường khác;
  // "Chưa phân loại" sau các thị trường; Σ Cả ngách xếp CUỐI dải
  const _uu = ma => ma === 'TT-US' ? 0 : ma === 'TT-SPAIN' ? 1 : 2;
  const dai = niche ? niche.thi_truong.map(tt => ({
    tt, w: wss.find(x => x.ngach === niche.ma && x.market === tt.ma) }))
    .sort((a, b) => _uu(a.tt.ma) - _uu(b.tt.ma)) : [];
  const taoPoolTT = async tt => {
    try {
      const w = await api('POST', '/workspaces', { name: `${niche.ten} — ${tt.ten}`, ngach: niche.ma, market: tt.ma });
      await loadWs(true); setWs(w.id);
    } catch (e) { alert(String(e.message)); }
  };
  return html`
    <header class="top">
      <h1>📡 RADAR<span>Y</span></h1>
      <nav class="tabs">${tabs.map(([k, label]) => html`
        <button class=${tab === k ? 'on' : ''} onClick=${() => setTab(k)}>${label}</button>`)}</nav>
      <select class="ws" value=${cur && cur.market ? ((wss.find(x => x.ngach === cur.ngach && !x.market) || cur).id) : ws}
        onChange=${async e => {
          const v = e.target.value;
          if (v.startsWith('ng:')) {              // ngách MỚI từ General chưa có pool (19/08) → dựng pool gốc
            const n = nganhs.find(x => x.ma === v.slice(3));
            if (!n || !canEdit) return;
            try {
              const w = await api('POST', '/workspaces', { name: n.ten, ngach: n.ma, market: '' });
              await loadWs(true); setWs(w.id); setNicheView(true);
            } catch (err) { alert(String(err.message)); }
            return;
          }
          const w = wss.find(x => x.id === Number(v)); if (!w) return;
          setWs(w.id); setNicheView(!!w.ngach);
        }}>
        ${wss.filter(w => !w.market).map(w => html`<option value=${w.id}>${w.name}</option>`)}
        ${nganhs.filter(n => !wss.some(w => w.ngach === n.ma)).map(n => html`
          <option value=${'ng:' + n.ma} disabled=${!canEdit}>＋ ${n.ten} (ngách mới — dựng pool)</option>`)}
      </select>
      ${me.sso ? '' : html`
        <span class="note" title=${me.email}>${me.email.split('@')[0]}${role !== 'owner' ? html` · <span class="rolechip ${role}">${role}</span>` : ''}</span>
        <button class="btn small ghost" onClick=${logout}>Thoát</button>`}
    </header>
    ${niche && !['harvest', 'admin'].includes(tab) && html`
      <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:0 0 12px">
        <span class="note">${niche.ten}:</span>
        ${dai.map(s => s.w
          ? html`<button class=${'btn small' + (!nicheView && ws === s.w.id ? '' : ' ghost')}
              onClick=${() => { setNicheView(false); setWs(s.w.id); }}>${s.tt.ten} <small>· ${s.w.channels} kênh</small></button>`
          : html`<button class="btn small ghost" disabled=${!canEdit}
              title=${'Thị trường ' + s.tt.ten + ' chưa có pool' + (canEdit ? ' — bấm để dựng' : '')}
              onClick=${() => canEdit && taoPoolTT(s.tt)}>＋ ${s.tt.ten}</button>`)}
        ${goc && tab === 'pool' && html`<button class=${'btn small' + (ws === goc.id ? '' : ' ghost')}
          onClick=${() => { setNicheView(false); setWs(goc.id); }}>Chưa phân loại <small>· ${goc.channels} kênh</small></button>`}
        ${tab === 'board' && html`<button class=${'btn small' + (nicheView || !(cur && cur.market) ? '' : ' ghost')}
          title="Volume cộng gộp mọi pool thị trường của ngách"
          onClick=${() => setNicheView(true)}>Σ Cả ngách</button>`}
        ${dai.length === 0 && html`<span class="note">ngách chưa khai thị trường — gắn ở General › Niches</span>`}
      </div>`}
    ${tab === 'admin' && !me.sso && (role === 'owner' || role === 'manager') ? html`
        ${role === 'owner' && html`<${OrgAdmin} orgId=${orgId} meEmail=${me.email} wss=${wss.filter(w => w.org_id === orgId)}/>`}
        <${OrgNiches} wss=${wss.filter(w => w.org_id === orgId)}
          onChanged=${async deletedId => { const l = await loadWs(true); if (ws === deletedId) setWs(l[0]?.id ?? null); }}/>
        ${role === 'owner' && html`<${OrgKeys} wss=${wss}/>`}
        ${role === 'owner' && html`<${HarvestKeys} orgId=${orgId}/>`}
        ${role === 'owner' && html`<${LlmPanel} orgId=${orgId}/>`}`
      : tab === 'harvest' ? html`<${Harvest} orgId=${orgId} canEdit=${canEdit}/>`
      : !cur ? html`<div class="panel">${canEdit ? 'Chưa có pool nào — tạo niche + thị trường ở General › Niches rồi dựng pool bằng nút ＋ trên dải tab.'
                                                 : 'Org chưa có workspace nào — chờ owner/leader tạo.'}</div>`
      : tab === 'board' && niche && (nicheView || !(cur && cur.market)) ? html`<${NicheVolume} ma=${niche.ma} ten=${niche.ten}/>`
      : tab === 'board' ? html`<${Board} ws=${ws} canEdit=${canEdit}/>`
      : tab === 'alerts' ? html`<${Alerts} ws=${ws} canEdit=${canEdit}/>`
      : tab === 'mapping' ? html`<${Mapping} ws=${ws} canEdit=${canEdit}/>`
      : tab === 'reports' ? html`<${Reports} ws=${ws} canEdit=${canEdit}/>`
      : tab === 'pool' ? html`<${Pool} ws=${ws} canEdit=${canEdit} role=${role} nganhs=${nganhs}
          wss=${wss.filter(w => w.org_id === orgId)} onMoved=${() => loadWs(true)}/>`
      : html`<${Settings} ws=${ws} role=${role} orgId=${orgId}/>`}
  `;
}
render(html`<${App}/>`, document.getElementById('app'));
