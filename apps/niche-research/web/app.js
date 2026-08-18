import { h, render } from 'preact'
import { useState, useEffect, useRef, useCallback } from 'preact/hooks'
import htm from 'htm'
const html = htm.bind(h)

// ── Stage config ──────────────────────────────────────────────────────────────
const STAGES = [
  ['S1','Scan'],['S3','Keywords'],['S4','Comments'],
  ['S5','Crack'],['S6','Monetize'],['S7','Demand'],
  ['S8','Go/No-Go'],['S9','Sub-niche'],['S10','Beachhead'],
  ['S11','Bets'],['S12','Auditor'],['S13','Plan'],
  ['S19','Summary'],['S18','Report'],
]
const STAGE_IDS = STAGES.map(([id]) => id)

const LLM_AGENTS = [
  {key:'namer',  label:'S9b  Đặt tên cụm'},
  {key:'auditor',label:'S12  Auditor'},
  {key:'plan',   label:'S13  Execution Plan'},
  {key:'summary',label:'S19  Summary'},
  {key:'dna',    label:'S16/17  DNA'},
]

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmt_date = ts => {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleDateString('vi-VN',{day:'2-digit',month:'2-digit',year:'2-digit'}) +
    ' ' + d.toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit'})
}

const fmt_size = b => {
  if (b == null) return ''
  if (b < 1024) return b + ' B'
  if (b < 1024*1024) return (b/1024).toFixed(0) + ' KB'
  return (b/1024/1024).toFixed(1) + ' MB'
}

const fmt_num = v => {
  if (v == null) return '—'
  if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(1).replace(/\.0$/,'') + 'M'
  if (Math.abs(v) >= 1e3) return (v/1e3).toFixed(1).replace(/\.0$/,'') + 'k'
  return String(Math.round(v))
}

const parse_stage = line => {
  const m = line.match(/>>>\s*\[(\d+)\/(\d+)\]\s+(S[\w/]+)/)
  if (!m) return null
  const raw = m[3]
  return STAGE_IDS.find(id => raw === id || raw.startsWith(id+'/') || raw === id+'b')
    || raw.replace(/b$/,'').split('/')[0]
}

const init_stages = () => Object.fromEntries(STAGES.map(([id]) => [id,'idle']))

const canRun = role => role === 'leader' || role === 'manager' || role === 'admin'

// ── Status chip & dot ─────────────────────────────────────────────────────────
const STATUS_LABELS = {done:'Có báo cáo', running:'Đang chạy', paused:'Dở dang', new:'Trống'}

function StatusChip({status}) {
  return html`<span class=${`chip ${status}`}>
    <span class="dot"></span>${STATUS_LABELS[status]||status}
  </span>`
}
function StatusDot({status}) {
  return html`<span class=${`status-dot ${status}`}></span>`
}

// ── Stage Pills ───────────────────────────────────────────────────────────────
function StagePills({stages}) {
  return html`<div class="pills">
    ${STAGES.map(([id,label]) => html`
      <span key=${id} class=${`pill ${stages[id]||'idle'}`}>${id} ${label}</span>`)}
  </div>`
}

// ── Upload Zone ───────────────────────────────────────────────────────────────
function UploadZone({file, onFile, accept='.txt',
                     label='Chọn hoặc kéo thả competitors.txt',
                     hint='File text chứa API key YouTube + danh sách kênh',
                     icon='📄'}) {
  const [drag, setDrag] = useState(false)
  const inp = useRef(null)
  const onDrop = e => { e.preventDefault(); setDrag(false); const f=e.dataTransfer?.files?.[0]; if(f) onFile(f) }
  return html`<div class=${`upload-zone ${drag?'drag':''}`}
    onClick=${()=>inp.current?.click()}
    onDragOver=${e=>{e.preventDefault();setDrag(true)}}
    onDragLeave=${()=>setDrag(false)}
    onDrop=${onDrop}>
    <input ref=${inp} type="file" accept=${accept} onChange=${e=>onFile(e.target.files[0])} />
    <div class="uz-icon">${icon}</div>
    ${file
      ? html`<div class="uz-name">${file.name}</div><div class="uz-hint">Bấm để đổi file</div>`
      : html`<div class="uz-name">${label}</div>
             <div class="uz-hint">${hint}</div>`}
  </div>`
}

// ── Markdown renderer (SUMMARY.md) ────────────────────────────────────────────
function mdRender(md) {
  const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
  const inline = s => esc(s)
    .replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>')
    .replace(/\*([^*]+)\*/g,'<i>$1</i>')
    .replace(/`([^`]+)`/g,'<code>$1</code>')
  const lines = md.split('\n')
  const out = []
  let i = 0, inUl = false, inOl = false, inCode = false, codeBuf = []
  const closeLists = () => {
    if (inUl) { out.push('</ul>'); inUl = false }
    if (inOl) { out.push('</ol>'); inOl = false }
  }
  while (i < lines.length) {
    const line = lines[i]
    if (line.trim().startsWith('```')) {
      if (!inCode) { inCode = true; codeBuf = [] }
      else { out.push('<pre class="md-code">'+esc(codeBuf.join('\n'))+'</pre>'); inCode = false }
      i++; continue
    }
    if (inCode) { codeBuf.push(line); i++; continue }
    if (/^\s*\|/.test(line)) {
      closeLists()
      const tbl = []
      while (i < lines.length && /^\s*\|/.test(lines[i])) { tbl.push(lines[i]); i++ }
      const rows = tbl.filter(l => !/^\s*\|[\s\-:|]+\|?\s*$/.test(l))
        .map(l => l.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(c => inline(c.trim())))
      out.push('<div class="md-table-wrap"><table class="md-table">' + rows.map((r, ri) =>
        '<tr>' + r.map(c => ri===0 ? `<th>${c}</th>` : `<td>${c}</td>`).join('') + '</tr>'
      ).join('') + '</table></div>')
      continue
    }
    const hm = line.match(/^(#{1,4})\s+(.*)/)
    if (hm) { closeLists(); const lv = hm[1].length + 1; out.push(`<h${lv}>${inline(hm[2])}</h${lv}>`); i++; continue }
    if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) { closeLists(); out.push('<hr>'); i++; continue }
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inUl) { closeLists(); out.push('<ul>'); inUl = true }
      out.push('<li>'+inline(line.replace(/^\s*[-*]\s+/,''))+'</li>'); i++; continue
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      if (!inOl) { closeLists(); out.push('<ol>'); inOl = true }
      out.push('<li>'+inline(line.replace(/^\s*\d+[.)]\s+/,''))+'</li>'); i++; continue
    }
    if (/^\s*>\s?/.test(line)) { closeLists(); out.push('<blockquote>'+inline(line.replace(/^\s*>\s?/,''))+'</blockquote>'); i++; continue }
    if (line.trim() === '') { closeLists(); i++; continue }
    closeLists(); out.push('<p>'+inline(line)+'</p>'); i++
  }
  closeLists()
  return out.join('\n')
}

function MarkdownViewer({project, filename, onBack}) {
  const [content, setContent] = useState(null)
  const [error,   setError]   = useState('')

  useEffect(() => {
    setContent(null); setError('')
    fetch(`/api/mdtext/${project.name}/${encodeURIComponent(filename)}`)
      .then(r => { if(!r.ok) throw new Error('Không tải được tài liệu'); return r.json() })
      .then(d => setContent(d.content))
      .catch(e => setError(e.message))
  }, [project.name, filename])

  return html`<div class="report-viewer">
    <div class="rv-header">
      <button class="btn sm" onClick=${onBack}>← Quay lại</button>
      <h3>📝 ${filename}</h3>
    </div>
    ${error && html`<div style="padding:24px 20px;color:var(--danger)">${error}</div>`}
    ${content == null && !error && html`<div style="padding:24px 20px;color:var(--muted)">Đang tải…</div>`}
    ${content != null && html`<div class="md-outer">
      <div class="md-body" dangerouslySetInnerHTML=${{__html: mdRender(content)}}></div>
    </div>`}
  </div>`
}

// ── Report Viewer (Excel) ─────────────────────────────────────────────────────
function ReportViewer({project, filename, onBack}) {
  const [data,    setData]    = useState(null)
  const [tab,     setTab]     = useState(0)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  useEffect(() => {
    setLoading(true); setError(''); setTab(0)
    fetch(`/api/report/${project.name}/${encodeURIComponent(filename)}`)
      .then(r => { if(!r.ok) throw new Error('Không tải được báo cáo'); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [project.name, filename])

  const sheet = data?.sheets?.[tab]

  return html`<div class="report-viewer">
    <div class="rv-header">
      <button class="btn sm" onClick=${onBack}>← Quay lại</button>
      <h3>📊 ${filename}</h3>
    </div>

    ${loading && html`<div style="padding:24px 20px;color:var(--muted)">Đang đọc file…</div>`}
    ${error   && html`<div style="padding:24px 20px;color:var(--danger)">${error}</div>`}

    ${data && html`<div class="rv-tabs">
      ${data.sheets.map((s,i) => html`
        <button key=${i} class=${'rv-tab'+(tab===i?' active':'')} onClick=${()=>setTab(i)}>
          ${s.name}
        </button>`)}
    </div>`}

    ${sheet && html`<div class="rv-table-wrap">
      ${sheet.total_rows > 300 && html`
        <div class="rv-cap-note">⚠ Hiển thị 300/${sheet.total_rows} dòng đầu tiên — tải file về để xem đầy đủ</div>`}
      ${sheet.rows.length === 0
        ? html`<div style="color:var(--muted);padding:20px 0;font-size:13px">Sheet trống</div>`
        : html`<table class="rv-table">
            <tbody>
              ${sheet.rows.map((row, ri) => html`
                <tr key=${ri}>
                  ${row.map((cell, ci) => html`
                    <td key=${ci} title=${cell}>${cell}</td>`)}
                </tr>`)}
            </tbody>
          </table>`}
    </div>`}
  </div>`
}

// ── LLM Dropdown ──────────────────────────────────────────────────────────────
function LLMDropdown({projectName, onDone}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState('')

  const run = async agent => {
    setOpen(false); setBusy(agent)
    try { await fetch(`/api/llm/${projectName}/${agent}`,{method:'POST'}); onDone&&onDone(agent) }
    finally { setBusy('') }
  }

  return html`<div class="dropdown">
    <button class="btn sm ghost" onClick=${()=>setOpen(o=>!o)}>
      ${busy ? html`<span class="spin"></span>` : ''} 🤖 LLM ▾
    </button>
    ${open && html`<div class="dropdown-menu">
      ${LLM_AGENTS.map(a => html`<button key=${a.key} onClick=${()=>run(a.key)}>${a.label}</button>`)}
    </div>`}
  </div>`
}

// ── Library Tab (Thư viện tài liệu) ──────────────────────────────────────────
function LibraryTab({project, role, docs, onReload, onRead}) {
  const [drag,      setDrag]      = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error,     setError]     = useState('')
  const inp = useRef(null)

  const upload = async f => {
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.xlsx')) { setError('Chỉ chấp nhận file .xlsx'); return }
    setUploading(true); setError('')
    const fd = new FormData(); fd.append('file', f)
    try {
      const r = await fetch(`/api/upload/${project.name}`,{method:'POST',body:fd})
      if(!r.ok){ const d=await r.json(); throw new Error(d.detail||'Lỗi upload') }
      onReload()
    } catch(e){ setError(e.message) } finally { setUploading(false) }
  }

  const del = async doc => {
    if(!confirm(`Xóa "${doc.filename}" khỏi dự án?`)) return
    const r = await fetch(`/api/doc/${project.name}/${encodeURIComponent(doc.filename)}`,{method:'DELETE'})
    if(!r.ok){ const d=await r.json(); setError(d.detail||'Lỗi xóa'); return }
    onReload()
  }

  const dl = f => window.open(`/api/download/${project.name}/${encodeURIComponent(f)}`,'_blank')

  const ICON  = {xlsx:'📊', md:'📝'}
  const ORIGIN= {pipeline:'từ phân tích', upload:'upload'}

  return html`<div class="lib-wrap">
    <div class=${`lib-upload ${drag?'drag':''}`}
      onClick=${()=>inp.current?.click()}
      onDragOver=${e=>{e.preventDefault();setDrag(true)}}
      onDragLeave=${()=>setDrag(false)}
      onDrop=${e=>{e.preventDefault();setDrag(false);upload(e.dataTransfer?.files?.[0])}}>
      <input ref=${inp} type="file" accept=".xlsx" style="display:none"
        onChange=${e=>{upload(e.target.files[0]); e.target.value=''}} />
      ${uploading
        ? html`<span class="spin"></span> Đang upload…`
        : '⬆ Kéo thả file .xlsx vào đây — hoặc bấm để chọn — để thêm báo cáo vào dự án'}
    </div>
    ${error && html`<p style="color:var(--danger);font-size:13px;margin-bottom:10px">⚠ ${error}</p>`}

    ${docs === null && html`<div style="color:var(--muted);padding:16px 0">Đang tải…</div>`}

    ${docs && docs.length === 0 && html`
      <div class="lib-empty">
        <div style="font-size:34px;margin-bottom:10px">🗂</div>
        <div style="font-weight:600;margin-bottom:6px">Dự án chưa có tài liệu nào</div>
        <div style="font-size:13px;color:var(--muted)">
          Upload báo cáo .xlsx ở khung trên${canRun(role) ? ', hoặc sang tab 🔬 Phân tích để tạo báo cáo từ danh sách đối thủ' : ''}.
        </div>
      </div>`}

    ${docs && docs.map(doc => html`
      <div key=${doc.filename} class="doc-row">
        <div class="doc-ico">${ICON[doc.type]||'📄'}</div>
        <div class="doc-info">
          <div class="doc-name" title=${doc.filename}>${doc.filename}</div>
          <div class="doc-meta">
            <span class=${`badge ${doc.origin}`}>${ORIGIN[doc.origin]||doc.origin}</span>
            <span>${fmt_size(doc.size)}</span>
            <span>${fmt_date(doc.mtime)}</span>
          </div>
        </div>
        <button class="btn sm primary" onClick=${()=>onRead(doc)}>📖 Đọc</button>
        <button class="btn sm" onClick=${()=>dl(doc.filename)}>⬇</button>
        ${(role==='admin'||role==='manager') && html`
          <button class="btn sm danger" onClick=${()=>del(doc)}>Xóa</button>`}
      </div>`)}
  </div>`
}

// ── Analysis Tab (pipeline) ───────────────────────────────────────────────────
function AnalysisTab({project, onRefresh}) {
  const hasRun = project.has_run || project.status === 'running'

  // start-form state (dự án chưa từng chạy)
  const [file,  setFile]  = useState(null)
  const [opts,  setOpts]  = useState({skip_comments:false,force:false,deepdive:false,llm:false})
  const [error, setError] = useState('')
  const [busy,  setBusy]  = useState(false)

  // pipeline state
  const [started, setStarted] = useState(hasRun)
  const [stages,  setStages]  = useState(init_stages)
  const [lines,   setLines]   = useState([])
  const [running, setRunning] = useState(project.status==='running')
  const logRef    = useRef(null)
  const esRef     = useRef(null)
  const activeRef = useRef(null)

  const advance = useCallback(sid => {
    setStages(s => {
      const n={...s}
      if(activeRef.current) n[activeRef.current]='done'
      if(sid in n) n[sid]='now'
      activeRef.current=sid
      return n
    })
  },[])

  const finish = useCallback(() => {
    setStages(s=>{ const n={...s}; if(activeRef.current) n[activeRef.current]='done'; return n })
    setRunning(false); onRefresh()
  },[onRefresh])

  const openSSE = useCallback(() => {
    esRef.current?.close()
    const es = new EventSource(`/api/log/${project.name}`)
    esRef.current = es
    es.onmessage = e => {
      const line = JSON.parse(e.data)
      setLines(l=>[...l,line])
      const sid = parse_stage(line)
      if(sid) advance(sid)
      requestAnimationFrame(()=>{ if(logRef.current) logRef.current.scrollTop=logRef.current.scrollHeight })
    }
    es.addEventListener('done', () => { es.close(); finish() })
    es.onerror = () => { es.close(); setRunning(false) }
  },[project.name, advance, finish])

  useEffect(()=>{
    if(started) openSSE()
    return ()=>esRef.current?.close()
  },[project.name, started])

  const start = async () => {
    if(!file){ setError('Chưa chọn file competitors.txt'); return }
    setBusy(true); setError('')
    const fd = new FormData()
    fd.append('name', project.name); fd.append('competitors', file)
    Object.entries(opts).forEach(([k,v]) => fd.append(k, v))
    try {
      const r = await fetch('/api/run',{method:'POST',body:fd})
      if(!r.ok){ setError(await r.text()); setBusy(false); return }
      setLines([]); setStages(init_stages()); setRunning(true); setStarted(true); setBusy(false)
      onRefresh()
    } catch(e){ setError(e.message); setBusy(false) }
  }

  const resume = async () => {
    setLines([]); setStages(init_stages()); setRunning(true)
    await fetch(`/api/resume/${project.name}`,{method:'POST'}); openSSE()
  }
  const stop = async () => {
    await fetch(`/api/stop/${project.name}`,{method:'POST'}); setRunning(false)
  }
  const toggle = k => setOpts(o=>({...o,[k]:!o[k]}))

  if (!started) {
    return html`<div class="lib-wrap">
      <div class="panel" style="max-width:640px">
        <div class="panel-title">🔬 Tạo báo cáo từ danh sách đối thủ</div>
        <div class="formrow">
          <label>File competitors</label>
          <${UploadZone} file=${file} onFile=${setFile} />
        </div>
        <div class="formrow">
          <label>Tùy chọn</label>
          <div class="checks">
            <label><input type="checkbox" checked=${opts.skip_comments} onChange=${()=>toggle('skip_comments')} />Bỏ comment</label>
            <label><input type="checkbox" checked=${opts.force}         onChange=${()=>toggle('force')} />Force rebuild</label>
            <label><input type="checkbox" checked=${opts.deepdive}      onChange=${()=>toggle('deepdive')} />Deep-dive transcript</label>
            <label><input type="checkbox" checked=${opts.llm}           onChange=${()=>toggle('llm')} />🤖 LLM</label>
          </div>
        </div>
        ${error && html`<p style="color:var(--danger);margin-bottom:10px;font-size:13px">⚠ ${error}</p>`}
        <button class="btn primary" disabled=${busy} onClick=${start}>
          ${busy ? html`<span class="spin"></span> Đang khởi chạy…` : '▶  START'}
        </button>
        <p class="note" style="margin-top:10px">Kết quả (Excel + SUMMARY) tự xuất hiện trong tab 📚 Thư viện khi xong.</p>
      </div>
    </div>`
  }

  return html`<div class="detail-wrap">
    <${StagePills} stages=${stages} />
    <div class="detail-actions">
      ${running
        ? html`<button class="btn sm danger" onClick=${stop}>■ Dừng</button>`
        : html`<button class="btn sm ghost"  onClick=${resume}>🔄 Resume</button>`}
      <${LLMDropdown} projectName=${project.name} onDone=${()=>{openSSE();onRefresh()}} />
      <span style="font-size:12px;color:var(--muted);margin-left:auto">
        ${running ? 'Pipeline đang chạy — theo dõi log bên dưới' : 'Bấm Resume để chạy tiếp phần thiếu'}
      </span>
    </div>
    <div class="log-outer">
      <div class="log-wrap" ref=${logRef}>
        <pre>${lines.length ? lines.join('\n') : '(Chưa có log)'}</pre>
      </div>
    </div>
  </div>`
}

// ── Watch Tab (Tầng 2/3 — theo dõi + đồ thị + tín hiệu) ──────────────────────
function WatchTab({project, role}) {
  const [cfg,    setCfg]    = useState(null)
  const [series, setSeries] = useState(null)
  const [sigs,   setSigs]   = useState([])
  const [busy,   setBusy]   = useState(false)
  const [note,   setNote]   = useState('')

  const load = useCallback(() => {
    fetch(`/api/watch/${project.name}`).then(r=>r.json()).then(setCfg).catch(()=>{})
    fetch(`/api/timeseries/${project.name}`).then(r=>r.json()).then(d=>setSeries(d.series)).catch(()=>setSeries([]))
    fetch('/api/signals').then(r=>r.json())
      .then(d=>setSigs((d.signals||[]).filter(s=>s.project===project.name)))
      .catch(()=>{})
  },[project.name])
  useEffect(()=>{ load() },[load])

  const save = async (patch) => {
    setBusy(true); setNote('')
    try {
      const body = {enabled: cfg.enabled, interval_days: cfg.interval_days, ...patch}
      const r = await fetch(`/api/watch/${project.name}`,{method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})
      const d = await r.json()
      if(!r.ok) throw new Error(d.detail||'Lỗi')
      setCfg(c=>({...c, ...body}))
    } catch(e){ setNote('⚠ '+e.message) } finally { setBusy(false) }
  }

  const runNow = async () => {
    setBusy(true); setNote('')
    try {
      const r = await fetch(`/api/watch/${project.name}/run`,{method:'POST'})
      if(!r.ok){ const d=await r.json(); throw new Error(d.detail||'Lỗi') }
      setNote('⏳ Đang quét — theo dõi log ở tab 🔬 Phân tích; đồ thị tự cập nhật khi xong.')
    } catch(e){ setNote('⚠ '+e.message) } finally { setBusy(false) }
  }

  if (!cfg) return html`<div class="lib-wrap" style="color:var(--muted)">Đang tải…</div>`

  const last = series && series.length ? series[series.length-1] : null
  const trM  = last && TREND_META[last.trend]

  return html`<div class="lib-wrap">

    ${canRun(role) && html`<div class="watch-card">
      <button class=${'btn sm '+(cfg.enabled?'primary':'')} disabled=${busy}
        onClick=${()=>save({enabled: !cfg.enabled})}>
        ${cfg.enabled ? '🔔 Đang theo dõi' : '🔕 Bật theo dõi'}
      </button>
      ${cfg.enabled && html`<label class="watch-int">Chu kỳ:
        <select value=${String(cfg.interval_days)} disabled=${busy}
          onChange=${e=>save({interval_days: Number(e.target.value)})}>
          <option value="3">3 ngày</option>
          <option value="7">7 ngày</option>
          <option value="14">14 ngày</option>
        </select>
      </label>`}
      <button class="btn sm ghost" disabled=${busy} onClick=${runNow}>⚡ Quét ngay</button>
      <span class="dt-dim" style="font-size:12px">
        ${cfg.last_run ? `Quét gần nhất: ${fmt_date(cfg.last_run)}` : 'Chưa quét lần nào'}
      </span>
      ${note && html`<span style="font-size:12px;color:var(--warn)">${note}</span>`}
    </div>`}

    ${last && html`<div class="watch-stats">
      <div class="wstat"><div class="wv">${last.n_videos}</div><div class="wl">video valid</div></div>
      <div class="wstat"><div class="wv">${last.n_outliers}</div><div class="wl">outlier OX≥3</div></div>
      <div class="wstat"><div class="wv">${fmt_num(last.views)}</div><div class="wl">tổng views</div></div>
      <div class="wstat"><div class="wv">${fmt_num(last.excess)}</div><div class="wl">Σ excess</div></div>
      <div class="wstat"><div class=${'wv '+(trM?trM.cls:'')}>${trM ? trM.icon+' '+trM.label : '—'}</div><div class="wl">trend</div></div>
    </div>`}

    ${series === null
      ? html`<div style="color:var(--muted)">Đang tải đồ thị…</div>`
      : series.length === 0
        ? html`<div class="lib-empty">
            <div style="font-size:34px;margin-bottom:10px">📈</div>
            <div style="font-weight:600;margin-bottom:6px">Chưa có snapshot nào</div>
            <div style="font-size:13px;color:var(--muted)">
              ${cfg.watchable
                ? 'Bật theo dõi hoặc bấm ⚡ Quét ngay — mỗi lần quét chụp 1 snapshot làm điểm dữ liệu cho đồ thị.'
                : 'Dự án chỉ chứa báo cáo upload (không có competitors.txt) — không có nguồn để quét.'}
            </div>
          </div>`
        : html`<div>
            <${LineChart} series=${series} yKey="excess"
              label="Σ excess của outliers — sức bật của niche (reach vượt kỳ vọng)" color="var(--accent)" />
            <${LineChart} series=${series} yKey="views"
              label="Tổng views các video theo dõi" color="var(--link)" />
            <${LineChart} series=${series} yKey="n_outliers"
              label="Số video outlier (OX ≥ 3)" color="var(--ok)" />
          </div>`}

    ${sigs.length > 0 && html`<div class="signals-box" style="margin-top:16px">
      <div class="signals-title">🔔 Tín hiệu của dự án này</div>
      <div class="signals-scroll">
        ${sigs.slice(0,20).map((s,i)=>html`<${SignalRow} key=${i} s=${s} showProject=${false} />`)}
      </div>
    </div>`}
  </div>`
}

// ── Project View (3 tab: Thư viện / Phân tích / Theo dõi) ────────────────────
function ProjectView({project, role, onRefresh, onDeleted}) {
  const [tab,     setTab]     = useState('lib')   // 'lib' | 'run'
  const [docs,    setDocs]    = useState(null)
  const [reading, setReading] = useState(null)    // doc | null

  const loadDocs = useCallback(() => {
    fetch(`/api/docs/${project.name}`)
      .then(r=>r.json()).then(d=>setDocs(d.docs))
      .catch(()=>setDocs([]))
  },[project.name])

  useEffect(()=>{ setDocs(null); setReading(null); setTab('lib'); loadDocs() },[project.name])
  // Khi pipeline xong (doc_count đổi) → refresh thư viện
  useEffect(()=>{ loadDocs() },[project.doc_count, project.status])

  const delProject = async () => {
    if(!confirm(`Xóa dự án "${project.name}" cùng TOÀN BỘ tài liệu?`)) return
    const typed = prompt(`Gõ lại tên dự án để xác nhận xóa:`)
    if(typed !== project.name){ alert('Tên không khớp — hủy xóa.'); return }
    const r = await fetch(`/api/projects/${project.name}`,{method:'DELETE'})
    if(!r.ok){ const d=await r.json(); alert(d.detail||'Lỗi xóa'); return }
    onDeleted()
  }

  if (reading) {
    const V = reading.type === 'md' ? MarkdownViewer : ReportViewer
    return html`<${V} project=${project} filename=${reading.filename}
      onBack=${()=>setReading(null)} />`
  }

  return html`<div class="pv-wrap">
    <div class="pv-head">
      <h2>${project.name}</h2>
      <${StatusChip} status=${project.status} />
      <span class="pv-meta">${docs ? docs.length : project.doc_count || 0} tài liệu · ${fmt_date(project.mtime)}</span>
      <div class="spacer"></div>
      ${(role==='admin'||role==='manager') && html`
        <button class="btn sm danger" title="Xóa dự án" onClick=${delProject}>🗑</button>`}
    </div>

    <div class="tabbar">
      <button class=${'tab'+(tab==='lib'?' active':'')} onClick=${()=>setTab('lib')}>
        📚 Thư viện
      </button>
      ${canRun(role) && html`
        <button class=${'tab'+(tab==='run'?' active':'')} onClick=${()=>setTab('run')}>
          🔬 Phân tích
        </button>`}
      ${project.watchable && html`
        <button class=${'tab'+(tab==='watch'?' active':'')} onClick=${()=>setTab('watch')}>
          📈 Theo dõi${project.watch ? ' 🔔' : ''}
        </button>`}
    </div>

    ${tab==='lib' && html`
      <${LibraryTab} project=${project} role=${role} docs=${docs}
        onReload=${()=>{loadDocs();onRefresh()}}
        onRead=${doc=>setReading(doc)} />`}

    ${tab==='run' && canRun(role) && html`
      <${AnalysisTab} project=${project} onRefresh=${()=>{loadDocs();onRefresh()}} />`}

    ${tab==='watch' && project.watchable && html`
      <${WatchTab} project=${project} role=${role} />`}
  </div>`
}

// ── New Project Panel ─────────────────────────────────────────────────────────
function NewProjectPanel({onClose, onCreated}) {
  const [name,  setName]  = useState('')
  const [busy,  setBusy]  = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if(!name.trim()){ setError('Chưa đặt tên dự án'); return }
    setBusy(true); setError('')
    try {
      const r = await fetch('/api/projects',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name.trim()})})
      const d = await r.json()
      if(!r.ok) throw new Error(d.detail||'Lỗi tạo dự án')
      onCreated(d.name)
    } catch(e){ setError(e.message); setBusy(false) }
  }

  return html`<div class="panel" style="max-width:560px">
    <div class="panel-title">＋ Tạo dự án mới
      ${onClose && html`<button class="btn sm" style="margin-left:auto" onClick=${onClose}>✕</button>`}
    </div>
    <div class="formrow">
      <label>Tên dự án</label>
      <input type="text" placeholder="vd: life-in-vietnam" autofocus
             value=${name} onInput=${e=>setName(e.target.value)}
             onKeyDown=${e=>{ if(e.key==='Enter') submit() }} />
    </div>
    ${error && html`<p style="color:var(--danger);margin-bottom:10px;font-size:13px">⚠ ${error}</p>`}
    <div style="display:flex;gap:10px">
      <button class="btn primary" disabled=${busy} onClick=${submit}>
        ${busy ? html`<span class="spin"></span> Đang tạo…` : '＋ Tạo dự án'}
      </button>
      ${onClose && html`<button class="btn" onClick=${onClose} disabled=${busy}>Hủy</button>`}
    </div>
    <p class="note" style="margin-top:10px">
      Dự án là <b>hồ sơ niche</b>: sau khi tạo, bạn có thể upload các báo cáo liên quan
      vào 📚 Thư viện và/hoặc chạy 🔬 Phân tích đối thủ để tạo báo cáo mới.
    </p>
  </div>`
}

// ── Members Panel ─────────────────────────────────────────────────────────────
function MembersPanel({myUsername}) {
  const [data,    setData]    = useState(null)
  const [invRole, setInvRole] = useState('seo')
  const [newInv,  setNewInv]  = useState(null)
  const [busy,    setBusy]    = useState(false)
  const [msg,     setMsg]     = useState(null)
  const [pwUser,  setPwUser]  = useState(null)   // username đang đổi mật khẩu
  const [pwVal,   setPwVal]   = useState('')
  const [pwBusy,  setPwBusy]  = useState(false)
  const origin = typeof window !== 'undefined' ? window.location.origin : ''

  const load = () => fetch('/api/users').then(r=>r.json()).then(setData).catch(e=>setMsg({text:e.message,ok:false}))
  useEffect(()=>{ load() },[])

  const createInvite = async () => {
    setBusy(true); setMsg(null); setNewInv(null)
    try {
      const r = await fetch('/api/invite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:invRole})})
      const d = await r.json()
      if(!r.ok) throw new Error(d.detail||'Lỗi')
      setNewInv(d); load()
    } catch(e){ setMsg({text:e.message,ok:false}) } finally { setBusy(false) }
  }

  const revokeInvite = async code => {
    await fetch(`/api/invite/${code}`,{method:'DELETE'}); load()
  }

  const removeUser = async username => {
    if(!confirm(`Xóa tài khoản ${username}?`)) return
    const r = await fetch(`/api/users/${username}`,{method:'DELETE'})
    if(!r.ok){ const d=await r.json(); setMsg({text:d.detail,ok:false}); return }
    load()
  }

  const setRole = async (username, role) => {
    await fetch(`/api/users/${username}/role`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role})}); load()
  }

  const startPw = uname => { setPwUser(uname); setPwVal(''); setMsg(null) }

  const savePw = async () => {
    if(pwVal.length < 6){ setMsg({text:'Mật khẩu tối thiểu 6 ký tự',ok:false}); return }
    setPwBusy(true); setMsg(null)
    try {
      const r = await fetch(`/api/users/${pwUser}/password`,{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pwVal})})
      if(!r.ok){ const d=await r.json(); throw new Error(d.detail||'Lỗi') }
      setMsg({text:`✓ Đã đổi mật khẩu cho ${pwUser}`,ok:true})
      setPwUser(null); setPwVal('')
    } catch(e){ setMsg({text:e.message,ok:false}) } finally { setPwBusy(false) }
  }

  if(!data) return html`<div style="color:var(--muted);padding:20px">Đang tải…</div>`

  const users   = Object.entries(data.users||{})
  const invites = Object.entries(data.invites||{})

  const thStyle = {textAlign:'left',padding:'6px 8px',color:'var(--muted)',fontWeight:600,borderBottom:'1px solid var(--border)'}
  const tdStyle = {padding:'7px 8px',borderBottom:'1px solid var(--border-soft)',verticalAlign:'middle'}

  const pwEditor = uname => html`<span style="display:inline-flex;gap:6px;align-items:center">
    <input type="password" placeholder="Mật khẩu mới (≥6)" value=${pwVal}
      style="background:var(--raised);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:5px 9px;font:inherit;width:170px"
      onInput=${e=>setPwVal(e.target.value)} />
    <button class="btn sm primary" disabled=${pwBusy} onClick=${savePw}>Lưu</button>
    <button class="btn sm" onClick=${()=>setPwUser(null)}>✕</button>
  </span>`

  return html`<div>

    <div class="settings-section">
      <div class="settings-heading">Tài khoản Quản trị</div>
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <tbody><tr>
          <td style=${tdStyle}><b>${myUsername||'admin'}</b></td>
          <td style=${tdStyle}><span class="chip done" style="font-size:11px;padding:2px 8px">Quản trị</span></td>
          <td style=${{...tdStyle,textAlign:'right'}}>
            ${pwUser===myUsername
              ? pwEditor(myUsername)
              : html`<button class="btn sm ghost" onClick=${()=>startPw(myUsername)}>🔑 Đổi mật khẩu</button>`}
          </td>
        </tr></tbody>
      </table>
    </div>

    <div class="settings-section">
      <div class="settings-heading">Thành viên (${users.length})</div>
      ${users.length===0 && html`<p style="color:var(--muted);font-size:13px">Chưa có thành viên nào. Tạo mã mời để thêm.</p>`}
      ${users.length>0 && html`<table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr>
          <th style=${thStyle}>Username</th>
          <th style=${thStyle}>Role</th>
          <th style=${{...thStyle,textAlign:'right'}}>Thao tác</th>
        </tr></thead>
        <tbody>
          ${users.map(([uname, info]) => html`
            <tr key=${uname}>
              <td style=${tdStyle}>${uname}</td>
              <td style=${tdStyle}>
                <select style="background:var(--raised);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:4px 8px;font:inherit;cursor:pointer"
                        onChange=${e=>setRole(uname,e.target.value)}>
                  <option value="leader" selected=${info.role==='leader'}>Leader</option>
                  <option value="seo"    selected=${info.role==='seo'}>SEO</option>
                </select>
              </td>
              <td style=${{...tdStyle,textAlign:'right'}}>
                ${pwUser===uname
                  ? pwEditor(uname)
                  : html`<span style="display:inline-flex;gap:6px">
                      <button class="btn sm ghost" onClick=${()=>startPw(uname)}>🔑</button>
                      <button class="btn sm danger" onClick=${()=>removeUser(uname)}>Xóa</button>
                    </span>`}
              </td>
            </tr>`)}
        </tbody>
      </table>`}
    </div>

    <div class="settings-section">
      <div class="settings-heading">Tạo mã mời</div>
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:12px">
        <select style="background:var(--raised);border:1px solid var(--border);border-radius:7px;color:var(--text);padding:7px 11px;font:inherit"
                value=${invRole} onChange=${e=>setInvRole(e.target.value)}>
          <option value="leader">Leader — tạo báo cáo</option>
          <option value="seo">SEO — xem, download, upload</option>
        </select>
        <button class="btn primary" disabled=${busy} onClick=${createInvite}>
          ${busy?html`<span class="spin"></span>`:'+ Tạo mã mời'}
        </button>
      </div>
      ${newInv && html`<div style="background:var(--accent-soft);border:1px solid var(--accent);border-radius:8px;padding:12px 14px;margin-bottom:12px">
        <div style="font-size:12px;color:var(--muted);margin-bottom:6px">Link mời (hết hạn sau 7 ngày):</div>
        <code style="font-size:13px;word-break:break-all;color:var(--accent)">${origin}/api/register?code=${newInv.code}</code>
        <div style="margin-top:8px;display:flex;gap:8px">
          <button class="btn sm primary" onClick=${()=>navigator.clipboard?.writeText(`${origin}/api/register?code=${newInv.code}`)}>📋 Copy link</button>
          <span style="font-size:12px;color:var(--muted);align-self:center">Role: ${newInv.role}</span>
        </div>
      </div>`}

      ${invites.length>0 && html`<div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:6px">Mã mời đang hoạt động:</div>
        ${invites.map(([code,inv]) => html`<div key=${code} style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--border-soft)">
          <code style="font-size:12.5px;color:var(--accent)">${code}</code>
          <span style="font-size:12px;color:var(--muted)">${inv.role}</span>
          <span style="font-size:11px;color:var(--faint);flex:1">hết hạn ${inv.expires?.slice(0,10)}</span>
          <button class="btn sm danger" onClick=${()=>revokeInvite(code)}>Hủy</button>
        </div>`)}
      </div>`}
    </div>

    ${msg && html`<p style=${{color:msg.ok?'var(--ok)':'var(--danger)',fontSize:'13px'}}>${msg.text}</p>`}
  </div>`
}

// ── Settings Panel ────────────────────────────────────────────────────────────
function SettingsPanel({onClose, role, username, sso}) {
  const [tab,    setTab]    = useState('keys')  // 'keys' | 'members'
  const [fields, setFields] = useState([])
  const [vals,   setVals]   = useState({})
  const [busy,   setBusy]   = useState(false)
  const [msg,    setMsg]    = useState(null)

  useEffect(()=>{
    fetch('/api/settings').then(r=>r.json()).then(d=>{
      setFields(d.settings)
      const init={}; d.settings.forEach(f=>{ if(!f.secret) init[f.key]=f.value }); setVals(init)
    }).catch(e=>setMsg({text:e.message,ok:false}))
  },[])

  const save = async () => {
    setBusy(true); setMsg(null)
    const updates={}; Object.entries(vals).forEach(([k,v])=>{ if(v!=null) updates[k]=v })
    try {
      const r = await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({updates})})
      const d = await r.json()
      if(!r.ok) throw new Error(d.detail||'Lỗi lưu')
      setFields(d.settings)
      setVals(v=>{ const n={...v}; d.settings.forEach(f=>{ if(!f.secret) n[f.key]=f.value; else delete n[f.key] }); return n })
      setMsg({text:'✓ Đã lưu thành công',ok:true})
    } catch(e){ setMsg({text:e.message,ok:false}) } finally { setBusy(false) }
  }

  const keyFields = fields.filter(f=>['LLM_PROVIDER','ANTHROPIC_API_KEY','GLM_API_KEY','OPENAI_API_KEY','GROK_API_KEY','TRANSCRIPT_API_KEY'].includes(f.key))
  const advFields = fields.filter(f=>['GLM_THINKING','SHORTS_GATE','MAX_COMMENTS'].includes(f.key))

  const Field = ({f}) => html`<div class="formrow" key=${f.key}>
    <label>
      ${f.label}
      ${f.secret && (f.set
        ? html`<span class="key-tag set">✓ đã có</span>`
        : html`<span class="key-tag missing">chưa có</span>`)}
    </label>
    <input type=${f.secret?'password':'text'}
      placeholder=${f.secret?(f.set?`••••${f.tail}  ← để trống là giữ nguyên`:'Chưa cấu hình'):(f.hint||'')}
      value=${vals[f.key]||''}
      onInput=${e=>setVals(v=>({...v,[f.key]:e.target.value}))}
      autocomplete="off" />
  </div>`

  const tabStyle = active => ({
    padding:'7px 16px', fontWeight:600, fontSize:'13px', cursor:'pointer',
    color: active ? 'var(--accent)' : 'var(--muted)',
    background:'none', border:'none',
    borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
  })

  return html`<div class="panel">
    <div class="panel-title">⚙ Cài đặt
      ${onClose && html`<button class="btn sm" style="margin-left:auto" onClick=${onClose}>✕</button>`}
    </div>
    <div style="display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:18px">
      <button style=${tabStyle(tab==='keys')}    onClick=${()=>setTab('keys')}>🔑 API Keys</button>
      ${role==='admin' && !sso && html`<button style=${tabStyle(tab==='members')} onClick=${()=>setTab('members')}>👥 Thành viên</button>`}
    </div>

    ${tab==='keys' && html`<div>
      ${fields.length===0 && html`<div style="color:var(--muted)">Đang tải…</div>`}
      ${fields.length>0 && html`
        <div class="settings-section">
          <div class="settings-heading">LLM Provider & Keys</div>
          ${keyFields.map(f=>html`<${Field} f=${f} />`)}
        </div>
        <div class="settings-section">
          <div class="settings-heading">Tùy chọn nâng cao</div>
          ${advFields.map(f=>html`<${Field} f=${f} />`)}
        </div>
        ${msg && html`<p style=${{color:msg.ok?'var(--ok)':'var(--danger)',marginBottom:'10px',fontSize:'13px'}}>${msg.text}</p>`}
        <div style="display:flex;gap:10px;margin-top:6px">
          <button class="btn primary" disabled=${busy} onClick=${save}>
            ${busy?html`<span class="spin"></span> Đang lưu…`:'💾  Lưu cài đặt'}
          </button>
          ${onClose && html`<button class="btn" onClick=${onClose}>Hủy</button>`}
        </div>
        <p class="note" style="margin-top:10px">Key lưu vào <code>.env</code> trên server. Để trống = giữ nguyên.</p>
      `}
    </div>`}

    ${tab==='members' && role==='admin' && !sso && html`<${MembersPanel} myUsername=${username} />`}
  </div>`
}

// ── Sidebar project list ──────────────────────────────────────────────────────
function Sidebar({projects, selected, onSelect, onNew, loading, role}) {
  return html`<aside class="sidebar">
    <div class="sidebar-head">
      <span class="sidebar-title">Dự án ${loading ? html`<span class="spin" style="margin-left:4px"></span>` : `(${projects.length})`}</span>
      ${canRun(role) && html`<button class="btn sm primary" onClick=${onNew}>＋ Tạo</button>`}
    </div>
    <div class="proj-list">
      ${projects.length===0 && !loading && html`
        <div style="padding:20px 14px;color:var(--muted);font-size:13px;text-align:center">
          Chưa có dự án nào
        </div>`}
      ${projects.map(p => html`
        <div key=${p.name}
             class=${`proj-row ${selected===p.name?'selected':''}`}
             onClick=${()=>onSelect(p)}>
          <div class="pname">${p.name}</div>
          <div class="pmeta">
            <${StatusDot} status=${p.status} />
            <span>${fmt_date(p.mtime)}</span>
            ${p.doc_count>0 && html`<span style="color:var(--accent);font-size:10.5px">${p.doc_count} 📄</span>`}
            ${p.watch && html`<span title="Đang theo dõi" style="font-size:10px">🔔</span>`}
          </div>
        </div>`)}
    </div>
  </aside>`
}

// ── SVG charts (tự vẽ — không thư viện ngoài) ────────────────────────────────
function Sparkline({points, w=110, h=30}) {
  if (!points || points.length < 2) return html`<span class="dt-dim">—</span>`
  const min = Math.min(...points), max = Math.max(...points)
  const ny = v => max === min ? h/2 : (h-4) - ((v-min)/(max-min)) * (h-8) + 2
  const step = (w-6) / (points.length-1)
  const xy = points.map((v,i) => [3+i*step, ny(v)])
  const d  = xy.map(([x,y],i) => `${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = d + ` L${xy[xy.length-1][0].toFixed(1)},${h-1} L3,${h-1} Z`
  const up = points[points.length-1] >= points[0]
  const col = up ? 'var(--ok)' : 'var(--danger)'
  return html`<svg width=${w} height=${h} viewBox=${`0 0 ${w} ${h}`} style="display:block">
    <path d=${area} fill=${col} opacity="0.12"/>
    <path d=${d} fill="none" stroke=${col} stroke-width="1.6" stroke-linejoin="round"/>
    <circle cx=${xy[xy.length-1][0]} cy=${xy[xy.length-1][1]} r="2.4" fill=${col}/>
  </svg>`
}

function LineChart({series, yKey, label, color='var(--accent)', fmt=fmt_num}) {
  const W=620, H=200, PL=52, PR=14, PT=16, PB=30
  if (!series || series.length < 2) {
    return html`<div class="chart-card">
      <div class="chart-title">${label}</div>
      <div class="chart-empty">Cần ≥ 2 snapshot để vẽ đồ thị — mỗi lần quét tạo 1 điểm dữ liệu.</div>
    </div>`
  }
  const pts  = series.map(s => s[yKey] ?? 0)
  let ymin = Math.min(...pts), ymax = Math.max(...pts)
  if (ymin === ymax) { ymin -= 1; ymax += 1 }
  const X = i => PL + (i/(pts.length-1)) * (W-PL-PR)
  const Y = v => PT + (1 - (v-ymin)/(ymax-ymin)) * (H-PT-PB)
  const xy = pts.map((v,i) => [X(i), Y(v)])
  const d  = xy.map(([x,y],i) => `${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = d + ` L${xy[xy.length-1][0].toFixed(1)},${H-PB} L${PL},${H-PB} Z`
  const ymid = (ymin+ymax)/2
  // Nhãn trục X: đầu · giữa · cuối (đủ định vị, không rối)
  const xticks = [0, Math.floor((pts.length-1)/2), pts.length-1]
    .filter((v,i,a) => a.indexOf(v) === i)
  return html`<div class="chart-card">
    <div class="chart-title">${label}
      <span class="chart-last">${fmt(pts[pts.length-1])}</span>
    </div>
    <svg width="100%" viewBox=${`0 0 ${W} ${H}`} style="display:block">
      ${[ymin, ymid, ymax].map(v => html`
        <g key=${v}>
          <line x1=${PL} y1=${Y(v)} x2=${W-PR} y2=${Y(v)} stroke="var(--border-soft)" stroke-width="1"/>
          <text x=${PL-7} y=${Y(v)+3.5} text-anchor="end" font-size="10" fill="var(--faint)">${fmt(v)}</text>
        </g>`)}
      <path d=${area} fill=${color} opacity="0.10"/>
      <path d=${d} fill="none" stroke=${color} stroke-width="2" stroke-linejoin="round"/>
      ${xy.map(([x,y],i) => html`
        <circle key=${i} cx=${x} cy=${y} r="3" fill=${color}>
          <title>${series[i].date}: ${fmt(pts[i])}</title>
        </circle>`)}
      ${xticks.map(i => html`
        <text key=${'x'+i} x=${X(i)} y=${H-8} text-anchor="middle" font-size="10" fill="var(--faint)">
          ${series[i].date?.slice(5)}
        </text>`)}
    </svg>
  </div>`
}

// ── Signals (Tầng 3) ──────────────────────────────────────────────────────────
const SIG_RENDER = {
  NEW_OUTLIER: s => html`<span class="sig-ico">📈</span>
    <span class="sig-text"><b>«${s.title}»</b> đạt OX ${s.ox} · ${fmt_num(s.views)} views
      <span class="dt-dim">(${s.channel}${s.prev_ox != null ? ` · trước: OX ${s.prev_ox}` : ' · video mới'})</span>
      ${s.sub === 'early_confirmed' && html`<span class="sig-tag">✓ early-confirmed</span>`}
    </span>`,
  TREND_FLIP: s => html`<span class="sig-ico">${s.to === 'DECLINING' ? '📉' : '📈'}</span>
    <span class="sig-text">Trend đổi chiều: <b>${s.from} → ${s.to}</b>
      ${s.to === 'DECLINING' && html`<span class="sig-tag danger">tín hiệu thoát</span>`}
      ${s.to === 'RISING' && html`<span class="sig-tag ok">cửa đang mở</span>`}
    </span>`,
  NEW_CHALLENGER: s => html`<span class="sig-ico">🌱</span>
    <span class="sig-text">Kênh trẻ có outlier đầu tiên: <b>${s.channel}</b>
      <span class="dt-dim">(${s.n_outliers} outlier — người mới đang thắng được ở niche này)</span>
    </span>`,
}

function SignalRow({s, showProject}) {
  const render = SIG_RENDER[s.type]
  return html`<div class="sig-row">
    ${render ? render(s) : html`<span class="sig-text">${s.type}</span>`}
    <span class="sig-meta">
      ${showProject && s.project && html`<span class="sig-proj">${s.project}</span>`}
      <span class="dt-dim">${s.date}</span>
    </span>
  </div>`
}

// ── Dashboard (Tầng 1 monitoring — bản đồ portfolio) ─────────────────────────
const FRESH_DAYS = 14, AGING_DAYS = 42

const freshness = ts => {
  if (!ts) return null
  const days = (Date.now()/1000 - ts) / 86400
  return days < FRESH_DAYS ? 'fresh' : days < AGING_DAYS ? 'aging' : 'stale'
}
const FRESH_META = {
  fresh: {dot:'🟢', label:'mới'},
  aging: {dot:'🟡', label:'sắp cũ'},
  stale: {dot:'🔴', label:'cũ — nên Refresh'},
}
const VERDICT_CLS = {'GO':'ok', 'CONDITIONAL':'warn', 'NO-GO':'danger'}
const TREND_META  = {
  RISING:    {icon:'↗', cls:'ok',     label:'RISING'},
  FLAT:      {icon:'→', cls:'muted',  label:'FLAT'},
  DECLINING: {icon:'↘', cls:'danger', label:'DECLINING'},
}

function Dashboard({onOpen, role, onNew, reloadKey}) {
  const [rows, setRows] = useState(null)
  const [sigs, setSigs] = useState([])
  const [seenTs] = useState(() => Number(localStorage.getItem('nr_sig_seen') || 0))

  useEffect(() => {
    let alive = true
    fetch('/api/dashboard').then(r=>r.json())
      .then(d => { if(alive) setRows(d.projects) })
      .catch(()=>{ if(alive) setRows([]) })
    fetch('/api/signals').then(r=>r.json())
      .then(d => {
        if(!alive) return
        setSigs(d.signals || [])
        if (d.signals?.length) localStorage.setItem('nr_sig_seen', String(d.signals[0].ts || 0))
      })
      .catch(()=>{})
    return () => { alive = false }
  }, [reloadKey])

  if (rows === null) return html`<div class="lib-wrap" style="color:var(--muted)">Đang tải tổng quan…</div>`

  const nGo    = rows.filter(r=>r.verdict==='GO').length
  const nCond  = rows.filter(r=>r.verdict==='CONDITIONAL').length
  const nStale = rows.filter(r=>freshness(r.scanned_at)==='stale').length
  const nNew   = sigs.filter(s=>(s.ts||0) > seenTs).length

  return html`<div class="dash-wrap">
    <div class="dash-head">
      <h2>🗂 Tổng quan portfolio</h2>
      <div class="dash-stats">
        <span class="dash-stat">${rows.length} dự án</span>
        ${nGo>0   && html`<span class="dash-stat ok">${nGo} GO</span>`}
        ${nCond>0 && html`<span class="dash-stat warn">${nCond} CONDITIONAL</span>`}
        ${nStale>0&& html`<span class="dash-stat danger">${nStale} data cũ</span>`}
        ${nNew>0  && html`<span class="dash-stat danger">🔔 ${nNew} tín hiệu mới</span>`}
      </div>
      <div class="spacer"></div>
      ${canRun(role) && html`<button class="btn sm primary" onClick=${onNew}>＋ Tạo dự án</button>`}
    </div>

    ${sigs.length > 0 && html`<div class="signals-box">
      <div class="signals-title">🔔 Tín hiệu gần đây</div>
      <div class="signals-scroll">
        ${sigs.slice(0, 12).map((s,i) => html`
          <div key=${i} class=${(s.ts||0) > seenTs ? 'sig-fresh' : ''}>
            <${SignalRow} s=${s} showProject=${true} />
          </div>`)}
      </div>
    </div>`}

    <div class="dash-table-wrap">
      <table class="dash-table">
        <thead><tr>
          <th>Dự án</th><th>Verdict</th><th>Điểm</th><th>Beachhead</th>
          <th>Bets</th><th>Trend</th><th>Diễn biến</th><th>Dữ liệu</th><th>📄</th>
        </tr></thead>
        <tbody>
          ${rows.map(r => {
            const fr = freshness(r.scanned_at)
            const tr = TREND_META[r.trend]
            return html`<tr key=${r.name} onClick=${()=>onOpen({name:r.name})}>
              <td class="dt-name">
                ${r.running && html`<span class="spin" style="margin-right:6px"></span>`}${r.name}
                ${r.watch && html`<span title="Đang theo dõi" style="margin-left:5px">🔔</span>`}
              </td>
              <td>${r.verdict
                ? html`<span class=${'verdict-badge '+(VERDICT_CLS[r.verdict]||'')}>${r.verdict}</span>`
                : html`<span class="dt-dim">—</span>`}</td>
              <td>${r.attractiveness != null
                ? html`<b>${Math.round(r.attractiveness)}</b><span class="dt-dim">/100</span>`
                : html`<span class="dt-dim">—</span>`}</td>
              <td class="dt-beach" title=${r.beachhead||''}>${r.beachhead || html`<span class="dt-dim">—</span>`}</td>
              <td>${r.bets
                ? html`<span class="bets-cell">
                    ${r.bets.clone_now>0 && html`<span class="bet ok" title="CLONE NOW">🟢${r.bets.clone_now}</span>`}
                    ${r.bets.clone>0     && html`<span class="bet ok2" title="CLONE">🔵${r.bets.clone}</span>`}
                    ${r.bets.test>0      && html`<span class="bet warn" title="TEST">🟡${r.bets.test}</span>`}
                    ${(r.bets.clone_now+r.bets.clone+r.bets.test)===0 && html`<span class="dt-dim">0</span>`}
                  </span>`
                : html`<span class="dt-dim">—</span>`}</td>
              <td>${tr
                ? html`<span class=${'trend-cell '+tr.cls}>${tr.icon} ${tr.label}</span>`
                : html`<span class="dt-dim">—</span>`}</td>
              <td title="Σ excess của outliers qua các lần quét">
                <${Sparkline} points=${r.spark} /></td>
              <td>${fr
                ? html`<span title=${FRESH_META[fr].label}>${FRESH_META[fr].dot} ${fmt_date(r.scanned_at).split(' ')[0]}</span>`
                : r.source==='xlsx'
                  ? html`<span class="dt-dim" title="Báo cáo tĩnh (upload) — không có dữ liệu scan để theo dõi">tĩnh</span>`
                  : html`<span class="dt-dim">chưa scan</span>`}</td>
              <td>${r.doc_count>0 ? r.doc_count : html`<span class="dt-dim">0</span>`}</td>
            </tr>`
          })}
        </tbody>
      </table>
    </div>

    <p class="note" style="padding:10px 18px">
      Dữ liệu: 🟢 dưới ${FRESH_DAYS} ngày · 🟡 dưới ${AGING_DAYS} ngày · 🔴 cũ hơn — kết luận niche có hạn
      sử dụng, vào dự án bấm Resume/Refresh để quét lại. Hàng "tĩnh" = báo cáo upload, chỉ đọc — muốn
      theo dõi niche đó, tạo dự án với competitors.txt riêng.
    </p>
  </div>`
}

// ── App Root ──────────────────────────────────────────────────────────────────
function App() {
  const [projects, setProjects] = useState([])
  const [view,     setView]     = useState('welcome')  // 'welcome'|'newproj'|'project'|'settings'
  const [current,  setCurrent]  = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [me,       setMe]       = useState({username:'', role:'seo'})

  useEffect(()=>{
    fetch('/api/me').then(r=>r.json()).then(setMe).catch(()=>{})
  },[])

  const load = useCallback(async () => {
    try {
      const r  = await fetch('/api/projects')
      const ps = await r.json()
      setProjects(ps)
      setCurrent(cur => cur ? (ps.find(x => x.name === cur.name) || cur) : null)
    } catch(e){ console.error(e) } finally { setLoading(false) }
  },[])

  useEffect(()=>{ load(); const t=setInterval(load,8000); return ()=>clearInterval(t) },[load])

  const selectProject = p => {
    const fresh = projects.find(x=>x.name===p.name)||p
    setCurrent(fresh); setView('project')
  }
  const onCreated = name => {
    setCurrent({name, status:'new', mtime:Date.now()/1000, has_run:false, doc_count:0})
    setView('project'); load()
  }
  const onDeleted = () => { setCurrent(null); setView('welcome'); load() }

  return html`<div id="app-shell">
    <header class="top-header">
      <h1 style="cursor:pointer" title="Về tổng quan" onClick=${()=>{setCurrent(null);setView('welcome')}}>Niche <span>Research</span></h1>
      <span class="sub" style="margin-left:4px">/ trung tâm dữ liệu niche</span>
      <div class="spacer"></div>
      ${me.username && !me.sso && html`
        <div class="user-badge">
          <div class="avatar">${me.username[0].toUpperCase()}</div>
          <span>${me.username}</span>
          <span class=${'chip '+(me.role==='admin'?'done':me.role==='manager'?'done':me.role==='leader'?'running':'new')} style="font-size:10.5px;padding:2px 7px">
            ${me.role==='admin'?'Quản trị':me.role==='manager'?'Manager':me.role==='leader'?'Leader':'SEO'}
          </span>
        </div>`}
      ${me.role==='admin' && !me.sso && html`<button class="btn sm icon" title="Cài đặt" onClick=${()=>setView(v=>v==='settings'?'welcome':'settings')}>⚙</button>`}
    </header>

    <div class="body-wrap">
      <${Sidebar}
        projects=${projects}
        selected=${view==='project' ? current?.name : null}
        loading=${loading}
        onSelect=${selectProject}
        onNew=${()=>setView('newproj')}
        role=${me.role} />

      <div class="main-area detail-mode">
        ${view==='welcome' && (projects.length > 0
          ? html`<${Dashboard}
              role=${me.role}
              onOpen=${selectProject}
              onNew=${()=>setView('newproj')}
              reloadKey=${projects.map(p=>`${p.name}:${p.status}:${p.doc_count}`).join('|')} />`
          : html`<div class="welcome">
              <div class="icon">🗂</div>
              <h2>Trung tâm dữ liệu niche</h2>
              <p>Mỗi dự án là một <b>hồ sơ niche</b> — gom báo cáo phân tích đối thủ và các báo cáo
              liên quan về một chỗ để đọc, hiểu và triển khai.<br/>
              ${canRun(me.role) ? html`Bấm <b>＋ Tạo</b> để bắt đầu.` : 'Chờ Leader tạo dự án đầu tiên.'}</p>
            </div>`)}

        ${view==='newproj' && html`
          <div class="lib-wrap">
            <${NewProjectPanel}
              onClose=${()=>setView('welcome')}
              onCreated=${onCreated} />
          </div>`}

        ${view==='project' && current && html`
          <${ProjectView}
            project=${current}
            role=${me.role}
            onRefresh=${load}
            onDeleted=${onDeleted} />`}

        ${view==='settings' && html`
          <div class="lib-wrap">
            <${SettingsPanel} onClose=${()=>setView('welcome')} role=${me.role} username=${me.username} sso=${me.sso} />
          </div>`}
      </div>
    </div>
  </div>`
}

render(html`<${App} />`, document.getElementById('app'))
