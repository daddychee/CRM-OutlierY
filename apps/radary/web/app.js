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
const writeHash = patch => {
  const h = { ...readHash(), ...patch };
  Object.keys(h).forEach(k => (h[k] === '' || h[k] == null) && delete h[k]);
  const s = Object.entries(h).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
  history.replaceState(null, '', s ? '#' + s : location.pathname);
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
          <text x=${x(h)} y=${H-8} text-anchor="middle" font-size="10" fill="var(--muted)">${h/24}d</text>`)}
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
              height=${180} pts=${pts.map(p => [hx(p), p.dviews])} bands=${[]} markers=${[]}
              yfmt=${kfmt} xfmt=${xf} xstep=${step} xtipfmt=${xtf}/>
            <${LineChart} title="Sóng VPH trung bình — views/giờ/video của video 0-6 ngày tuổi (TB ${nAvg} video)"
              height=${180} pts=${pts.map(p => [hx(p), p.vph_avg])} bands=${[]} markers=${[]}
              yfmt=${kfmt} xfmt=${xf} xstep=${step} xtipfmt=${xtf}/>
          </div>
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
function Pool({ ws, canEdit }) {
  const [chans, setChans] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [sel, setSel] = useState(null);       // kênh đang mở hồ sơ — bấm lại là đóng
  const load = useCallback(() => api('GET', `/workspaces/${ws}/channels`).then(setChans), [ws]);
  useEffect(() => { load(); }, [load]);
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
        <div class="tablewrap"><table>
          ${active.map(c => html`<tr class="clickable" title="Bấm để xem hồ sơ kênh"
              onClick=${e => { if (e.target.tagName !== 'A' && e.target.tagName !== 'BUTTON')
                setSel(cur => cur === c.yt_id ? null : c.yt_id); }}>
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

// ---------- Onboarding niche mới ----------
function NewNiche({ onCreated, role }) {
  const [name, setName] = useState('');
  const [chans, setChans] = useState('');
  const [keyMain, setKeyMain] = useState('');
  const [keyBk, setKeyBk] = useState('');
  const [step, setStep] = useState('');
  const [err, setErr] = useState('');
  const create = async () => {
    const items = chans.split('\n').map(s => s.trim()).filter(Boolean);
    if (!name.trim() || !items.length) { setErr('Cần tên niche và ít nhất 1 kênh.'); return; }
    setErr('');
    try {
      setStep('Tạo workspace…');
      const w = await api('POST', '/workspaces', { name: name.trim() });
      if (role !== 'viewer' && keyMain.trim().length >= 20) {
        setStep('Gắn key cho niche…');
        await api('POST', `/orgs/${w.org_id}/keys`, { key: keyMain.trim(), workspace_id: w.id });
        if (keyBk.trim().length >= 20)
          await api('POST', `/orgs/${w.org_id}/keys`, { key: keyBk.trim(), workspace_id: w.id, backup: true });
      }
      setStep(`Resolve ${items.length} kênh…`);
      const r = await api('POST', `/workspaces/${w.id}/channels`, { items });
      setStep(`Đã nhận ${r.added.length} kênh — quét lần đầu (có thể mất 1-2 phút)…`);
      await api('POST', `/workspaces/${w.id}/run?budget=300`);
      setStep(''); onCreated(w.id);
    } catch (e) { setErr(String(e.message)); setStep(''); }
  };
  return html`
    <div class="panel" style="max-width:640px">
      <h2>Niche mới — dán pool kênh đối thủ là chạy</h2>
      <div class="formrow"><label>Tên niche</label>
        <input type="text" placeholder="vd: Xe điện Việt Nam" value=${name} onInput=${e => setName(e.target.value)}/></div>
      ${role !== 'viewer' && html`
        <div class="formrow"><label>Key chính của niche</label>
          <input type="text" placeholder="AIza… (bỏ trống nếu dùng key toàn org)" value=${keyMain}
            onInput=${e => setKeyMain(e.target.value)}/></div>
        <div class="formrow"><label>Key dự phòng (tùy chọn)</label>
          <input type="text" placeholder="AIza… — tự lên thay khi key chính hết quota" value=${keyBk}
            onInput=${e => setKeyBk(e.target.value)}/></div>`}
      <div class="formrow"><label>Pool kênh (mỗi dòng 1 kênh)</label>
        <textarea placeholder=${'https://youtube.com/channel/UCxxxx\n@tenkenh\n…'}
          value=${chans} onInput=${e => setChans(e.target.value)}></textarea></div>
      <div class="note">Báo cáo ngách KHÔNG cần nhập tay — sau khi tạo, vào tab Báo cáo bấm
        "🔄 Sinh báo cáo ngách" khi pool đủ lớn.</div>
      ${err && html`<div class="msg err">${err}</div>`}
      ${step ? html`<div class="msg"><span class="spin"></span> ${step}</div>`
             : html`<button class="btn" onClick=${create}>Tạo niche & quét lần đầu</button>`}
      <div class="note">48h đầu là kỳ hiệu chỉnh sống (cold start theo spec): radar gắn cờ sơ bộ bằng VPD-since-publish,
        xếp hạng VPH chính thức từ lần quét thứ 2. Sau ≥14 ngày, vào Cài đặt → "Căn cứ hiệu chỉnh" để chỉnh sàn T1-T4 theo phân phối thực của niche.</div>
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

const TABS = [['board', 'Board'], ['alerts', 'Alerts'], ['reports', 'Report'], ['pool', 'Data Pool'],
              ['harvest', 'Harvest'], ['settings', 'Tuning'], ['admin', 'Setting'], ['new', '+ New Niche']];
function App() {
  const h0 = readHash();
  const [me, setMe] = useState(undefined);       // undefined = đang kiểm tra, null = chưa đăng nhập
  const [wss, setWss] = useState([]);
  const [ws, setWs] = useState(h0.ws ? Number(h0.ws) : null);
  const [tab, setTab] = useState(h0.tab || 'board');
  useEffect(() => { api('GET', '/auth/me').then(setMe).catch(() => setMe(null)); }, []);
  useEffect(() => { writeHash({ tab, ws: ws ?? '' }); }, [tab, ws]);
  useEffect(() => {                              // tab trong hash không hợp lệ với vai → về board
    if (!me) return;
    const cur0 = wss.find(w => w.id === ws);
    const orgId0 = cur0 ? cur0.org_id : (me.orgs || [])[0]?.id;
    const role0 = (me.orgs || []).find(o => o.id === orgId0)?.role || 'viewer';
    const ok = ['board', 'alerts', 'reports', 'settings'].includes(tab)
      || (['pool', 'harvest', 'new'].includes(tab) && role0 !== 'viewer')   // 23/07: leader trở lên
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
  const tabs = TABS.filter(([k]) => (['new', 'pool', 'harvest'].includes(k) ? canEdit
    : k === 'admin' ? (role === 'owner' || role === 'manager') : true));
  // 23/07: Data Pool/Harvest/New Niche = leader trở lên. 04/08: manager vào tab Quản trị
  // CHỈ thấy khối xóa niche (vận hành) — key/thành viên/LLM vẫn riêng owner (server chặn thật).
  return html`
    <header class="top">
      <h1>📡 RADAR<span>Y</span></h1>
      <nav class="tabs">${tabs.map(([k, label]) => html`
        <button class=${tab === k ? 'on' : ''} onClick=${() => setTab(k)}>${label}</button>`)}</nav>
      <select class="ws" value=${ws} onChange=${e => { setWs(Number(e.target.value)); if (tab === 'new') setTab('board'); }}>
        ${wss.map(w => html`<option value=${w.id}>${w.name} (${w.videos})</option>`)}
      </select>
      ${me.sso ? '' : html`
        <span class="note" title=${me.email}>${me.email.split('@')[0]}${role !== 'owner' ? html` · <span class="rolechip ${role}">${role}</span>` : ''}</span>
        <button class="btn small ghost" onClick=${logout}>Thoát</button>`}
    </header>
    ${tab === 'admin' && (role === 'owner' || role === 'manager') ? html`
        ${role === 'owner' && html`<${OrgAdmin} orgId=${orgId} meEmail=${me.email} wss=${wss.filter(w => w.org_id === orgId)}/>`}
        <${OrgNiches} wss=${wss.filter(w => w.org_id === orgId)}
          onChanged=${async deletedId => { const l = await loadWs(true); if (ws === deletedId) setWs(l[0]?.id ?? null); }}/>
        ${role === 'owner' && html`<${OrgKeys} wss=${wss}/>`}
        ${role === 'owner' && html`<${HarvestKeys} orgId=${orgId}/>`}
        ${role === 'owner' && html`<${LlmPanel} orgId=${orgId}/>`}`
      : tab === 'new' && canEdit ? html`<${NewNiche} role=${role} onCreated=${async id => { await loadWs(true); setWs(id); setTab('board'); }}/>`
      : tab === 'harvest' ? html`<${Harvest} orgId=${orgId} canEdit=${canEdit}/>`
      : !cur ? html`<div class="panel">${canEdit ? 'Chưa có workspace nào — bấm "+ New Niche". Nhớ thêm YouTube API key trong tab Setting trước.'
                                                 : 'Org chưa có workspace nào — chờ owner/leader tạo.'}</div>`
      : tab === 'board' ? html`<${Board} ws=${ws} canEdit=${canEdit}/>`
      : tab === 'alerts' ? html`<${Alerts} ws=${ws} canEdit=${canEdit}/>`
      : tab === 'reports' ? html`<${Reports} ws=${ws} canEdit=${canEdit}/>`
      : tab === 'pool' ? html`<${Pool} ws=${ws} canEdit=${canEdit}/>`
      : html`<${Settings} ws=${ws} role=${role} orgId=${orgId}/>`}
  `;
}
render(html`<${App}/>`, document.getElementById('app'));
