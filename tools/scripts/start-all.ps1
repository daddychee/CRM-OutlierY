# start-all.ps1 — bat cac dich vu nen cua platform v2 (giai doan dev, chay tay).
# Them dich vu moi: them 1 muc vao $dichVu (PHAI ghi cong vao docs\PORTS.md truoc).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pidDir = Join-Path $root 'logs\pids'
New-Item -ItemType Directory -Force -Path $pidDir | Out-Null

function Test-Cong($port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $port); $c.Close(); return $true
    } catch { return $false }
}

$py = Join-Path $root '.venv\Scripts\python.exe'

# 19/08: PYTHONUTF8=1 cho MOI dich vu — open() khong khai encoding tren Windows
# mac dinh cp1252, ghi tieng Viet la chet (dinh that: radary render_board 500
# khi Quet ngay; V2 chay VPS Linux nen chua tung lo). Code da va encoding='utf-8'
# nhung day la luoi do cho code vendored/port sau nay.
$env:PYTHONUTF8 = '1'

# RadarY (APPS.md app 1/6): du lieu tro data/radary (RADARY_DATA_DIR).
# 19/08 USER CHOT: BAT SCHEDULER V3 chay SONG SONG V2 (user da can quota —
# 'API hoan toan du'; pool da chia thi truong, so lieu da dong bo tu V2).
# ntfy pool goc 1+2 da TAT tren V3 (ke thua V2 bat) — khong push trung topic;
# pool thi truong moi mac dinh tat, Owner bat sau khi subscribe topic moi.
$env:RADARY_DATA_DIR = (Join-Path $root 'data/radary')
$env:RADARY_SCHEDULER = '1'
$env:RADARY_TRUST_PROXY = '1'

# Content Ultimate (APPS.md app 2/6): du lieu tro data/content-ultimate; SSO bat.
# App KHONG co scheduler nen (pipeline chi chay khi user bam) - khac RadarY.
$env:CU_DATA_DIR = (Join-Path $root 'data/content-ultimate')
$env:CU_TRUST_PROXY = '1'

# Niche Research (APPS.md app 3 - Owner chen len 18/08): du lieu tro
# data/niche-research; SSO bat; WATCH SCHEDULER TAT o V3 (he that C:\ van tu
# watch theo lich tren CUNG du an - V3 chay song song la dot doi quota YouTube;
# nghiem thu watch bang POST /api/watch/{name}/run tay).
$env:NICHE_DATA_DIR = (Join-Path $root 'data/niche-research')
$env:NICHE_TRUST_PROXY = '1'
$env:NICHE_SCHEDULER = '0'

# SEO Optimize (APPS.md app 4/6, dua vao 19/08): du lieu tro data/seo-optimize;
# SSO bat (khoa tu KET qua GATEWAY_URL, khong doc .env/api.txt). App KHONG co
# scheduler nen — sinh metadata/extract chi chay khi user bam.
$env:SEO_DATA_DIR = (Join-Path $root 'data/seo-optimize')
$env:SEO_TRUST_PROXY = '1'

# PlannerY (APPS.md app 5/6, dua vao 19/08): du lieu tro data/plannery (BAN SAO
# plan.json he that 19/08 - V2 cong 8123 van la nguon that toi cutover). SSO bat:
# vai 100% theo header gateway (X-Remote-Actions truoc, X-Remote-Role fallback),
# users.json noi bo KHONG con thang header (va bay DE.md:462); tu dong hoa goi
# loopback phai gui X-Remote-Role: admin (nhanh ADMIN_USERS tat khi SSO).
$env:PLANNER_DATA_DIR = (Join-Path $root 'data/plannery')
$env:PLANNER_HOST = '127.0.0.1'
$env:PLANNER_PORT = '9116'
$env:PLANNER_TRUST_PROXY = '1'
# Bay UTF-8 may Windows nay: app in tieng Viet ra stdout -> cp1252 chet luc khoi dong.
$env:PYTHONIOENCODING = 'utf-8'

# AI Agent (31/08 — tab giam sat B3 bat duoc): app tung chay MOCK lang le tren he
# that vi start-all khong dat MOCK_MODE; default CODE da doi sang chay that + kho
# :6343 (vector_client.py). Model embedding cache o data\fastembed_cache — task
# SYSTEM co Temp rieng (C:\Windows\Temp) KHONG co model, thieu env nay la tai lai
# ~2GB moi lan (cung ho bay HF_HOME cua SpeakY 31/07).
$env:FASTEMBED_CACHE_PATH = (Join-Path $root 'data\fastembed_cache')

# Canh bao day B5 (31/08): vong giam sat nen cua gateway phat ntfy khi app chet/
# module loi/viec nen tre nhip. Owner: bo comment dong duoi + thay topic KHO DOAN
# (ntfy.sh cong khai theo topic!) roi subscribe topic do tren app ntfy dien thoai.
# Chua dat topic → canh bao chi nam o so su co (data/logs/giam-sat) + tab Applications.
# $env:GIAM_SAT_NTFY_TOPIC = 'outliery-doi-chuoi-nay-kho-doan'

# NAS (to-chuc doc nen/common/nas_sync.py; gateway goi dong_bo_nen luc dang nhap/
# doi mat khau): app con KHONG tu goi load_dotenv() - chi nen/gateway/main.py doc
# thang .env goc, moi app khac phai duoc bom bien qua day (cung khuon
# RADARY_DATA_DIR/CU_DATA_DIR o tren). NAS_DONG_BO=true (18/08 - Owner xac nhan
# muon kiem chung that): se TAO/DONG BO TAI KHOAN WINDOWS THAT tren may nay khi
# dang nhap/doi mat khau qua gateway - dung dung TEN + MAT KHAU OUTLIERY.
$env:NAS_DUONG_DAN = '\\192.168.1.250\NAS1;\\192.168.1.250\Video'
$env:NAS_RIENG_MANAGER = 'NAS1'
$env:NAS_DONG_BO = 'true'
# Video Review: video KHONG nam trong app - app lien ket thang toi file goc tren NAS
# (user chot 20/08). Share 'Video' cua server nam ngay tren may nay (o F:) nen doc
# thang o dia, KHONG di duong UNC (tac vu SYSTEM khong co credential mang).
$env:VR_NAS_DIR = 'F:\OutlierY Nas 2'

# ffprobe cho video-review: do codec luc them video. File H.265 phat ra TIENG ma
# hinh den va KHONG bao loi gi (su co 20/08) -> app phai tu biet ma canh bao.
# Dung ban ffmpeg 8.1.2 da cai san cho SpeakY (he V2, cung may). Thieu ffprobe thi
# app CHI bo qua buoc do - khong bao bua, va luoi chot ben trinh duyet van chay.
$env:VR_FFPROBE = 'C:\OutlierY\tools\ffmpeg\bin\ffprobe.exe'

# Tasky (31/08 - Owner chot "nguoi dung tai len app, tai lieu gom het vao 1 folder
# tren NAS"): file dinh kem chep vao day roi luu DUONG DAN nhu moi tai lieu khac -
# app KHONG giu ban thu hai. Share 'NAS1' nam ngay tren may nay (o G:) nen doc
# thang o dia, KHONG di duong UNC (cung bay VR_NAS_DIR o tren).
$env:NAS_TASKY_GOC = 'G:\OutlierY Nas 1\Tasky'


# Duong UNC cua goc NAS: trang xem dua duong nay de nguoi dung dan vao Explorer
# (trinh duyet khong mo duoc file:// tu trang http). Share 'Video' = F:\OutlierY Nas 2.
$env:VR_NAS_UNC = '\\192.168.1.250\Video'

# ffmpeg (canh ffprobe) de QUET THU file tren NAS co dut/hong khong — file chep
# do van du dung luong va doc duoc header nen chi giai ma moi lo (su co LI088.2).
$env:VR_FFMPEG = 'C:\OutlierY\tools\ffmpeg\bin\ffmpeg.exe'

# RenderY (30/08): tool dung video, ma nam NGOAI repo (F:\RenderY) vi la tool co san
# duoc nhung vao, khong di tru. Cung khuon bien nhu VR_*: app con KHONG doc .env.
#   TRUST_PROXY=1 -> tin header X-Remote-* (an toan vi app bind 127.0.0.1).
#   NAS: share 'Video' nam ngay tren may nay o F: -> doc thang o dia, KHONG di UNC
#   (tac vu SYSTEM khong co credential mang — cung bay VR_NAS_DIR o tren).
$env:RENDERY_TRUST_PROXY = '1'
# GOC NAS, khong phai mot thu muc co dinh: moi tap co ma rieng (LI001, SH042, IN002...)
# va nam rai theo series. Nhan su DAN duong dan thu muc tap; rao duy nhat la phai
# nam trong goc nay. Trong thu muc tap co thu muc con 'RenderY' chua cac chuong
# H (hook) / C1..Cn (chapter) / E (end).
$env:RENDERY_NAS = 'F:\OutlierY Nas 2'
# Envato/Vecteezy KHONG co API key — dang nhap bang TRINH DUYET, phien luu o
# F:\RenderY\autoedit\.browser_profiles\. Chi can EMAIL de BAT nguon; het phien
# thi chay `rendery.bat sub-status` roi dang nhap lai bang Chrome tren may chu.
# Vi khong phai khoa API nen KHONG dat trong ket (General > API Keys) — ket chi
# giu bi mat dang khoa; day la thong tin tai khoan + phien trinh duyet.
$env:ENVATO_EMAIL = 'taikhoan.sequoia@gmail.com'
$env:VECTEEZY_EMAIL = 'taikhoan.sequoia@gmail.com'
# Whisper (chuong THIEU .srt thi nhan dang de lay timestamp): model 'small' ~464MB
# tai ve HF cache. Tac vu SYSTEM co %USERPROFILE% KHAC nen khong tro tuong minh
# thi no tai lai lan nua vao cho khac — cung bay da ghi cho SpeakY (he cu).
$env:HF_HOME = 'C:\Users\Administrator\.cache\huggingface'
$renderyPy = 'F:\RenderY\autoedit\.venv\Scripts\python.exe'

$dichVu = @(
    @{ Ten = 'qdrant-test'; Cong = 6343
       Exe = (Join-Path $root 'tools\qdrant\qdrant.exe')
       Args = '--config-path "' + (Join-Path $root 'tools\qdrant\config.yaml') + '"'
       Wd = (Join-Path $root 'tools\qdrant') }
    @{ Ten = 'app-mau'; Cong = 9190; Exe = $py
       Args = '-m uvicorn main:app --app-dir "apps/app-mau/src" --host 127.0.0.1 --port 9190'
       Wd = $root }
    @{ Ten = 'gateway'; Cong = 9000; Exe = $py
       # 19/08 Owner mo LAN cho team: gateway bind 0.0.0.0 (link http://192.168.1.250:9000)
       # — app phu van loopback, proxy cat het x-remote-* tu ngoai, firewall chi mo 9000.
       Args = '-m uvicorn nen.gateway.main:app --host 0.0.0.0 --port 9000'
       Wd = $root }
    @{ Ten = 'ai-agent'; Cong = 9101; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/ai-agent" --host 127.0.0.1 --port 9101'
       Wd = $root }
    @{ Ten = 'data-analytics'; Cong = 9102; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/data-analytics" --host 127.0.0.1 --port 9102'
       Wd = $root }
    @{ Ten = 'to-chuc'; Cong = 9103; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/to-chuc" --host 127.0.0.1 --port 9103'
       Wd = $root }
    @{ Ten = 'video-review'; Cong = 9114; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/video-review" --host 127.0.0.1 --port 9114'
       Wd = $root }
    @{ Ten = 'radary'; Cong = 9111; Exe = $py
       Args = '-m uvicorn radary.api:app --app-dir "apps/radary" --host 127.0.0.1 --port 9111'
       Wd = $root }
    @{ Ten = 'content-ultimate'; Cong = 9112; Exe = $py
       Args = '-m contentultimate.server --port 9112 --no-browser'
       Wd = $root }
    @{ Ten = 'niche-research'; Cong = 9113; Exe = $py
       Args = '-m uvicorn server:app --app-dir "apps/niche-research" --host 127.0.0.1 --port 9113'
       Wd = $root }
    @{ Ten = 'seo-optimize'; Cong = 9115; Exe = $py
       Args = '-m seo.server --host 127.0.0.1 --port 9115'
       Wd = (Join-Path $root 'apps/seo-optimize') }
    @{ Ten = 'plannery'; Cong = 9116; Exe = $py
       Args = 'server.py --no-browser'
       Wd = (Join-Path $root 'apps/plannery') }
    @{ Ten = 'tasky'; Cong = 9117; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/tasky" --host 127.0.0.1 --port 9117'
       Wd = $root }
    @{ Ten = 'thumby'; Cong = 9119; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/thumby" --host 127.0.0.1 --port 9119'
       Wd = $root }
    # RenderY: venv RIENG (F:\RenderY\autoedit\.venv) vi ma nam ngoai repo — dung
    # $renderyPy chu khong phai $py cua nen.
    @{ Ten = 'rendery'; Cong = 9118; Exe = $renderyPy
       Args = '-m uvicorn autoedit.web.server:app --host 127.0.0.1 --port 9118'
       Wd = 'F:\RenderY\autoedit' }
    @{ Ten = 'caddy-tls'; Cong = 9443
       Exe = (Join-Path $root 'tools\caddy\caddy.exe')
       Args = 'run --config "' + (Join-Path $root 'tools\caddy\Caddyfile') + '"'
       Wd = (Join-Path $root 'tools\caddy') }
)

foreach ($dv in $dichVu) {
    if (Test-Cong $dv.Cong) {
        Write-Host ("[=] {0} da chay san (cong {1})" -f $dv.Ten, $dv.Cong)
        continue
    }
    if (-not (Test-Path $dv.Exe)) {
        Write-Host ("[!] {0}: thieu {1} - bo qua" -f $dv.Ten, $dv.Exe); continue
    }
    $p = Start-Process -FilePath $dv.Exe -ArgumentList $dv.Args `
        -WorkingDirectory $dv.Wd -WindowStyle Hidden -PassThru
    $p.Id | Out-File -FilePath (Join-Path $pidDir ($dv.Ten + '.pid')) -Encoding ascii
    Write-Host ("[+] {0} da bat (PID {1}, cong {2})" -f $dv.Ten, $p.Id, $dv.Cong)
}

# Heartbeat B4 giam sat (31/08): bao 'toi vua chay xong' cho gateway —
# gateway chet thi khong duoc lam hong job (try/catch nuot loi).
try { Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:9000/api/nhip-viec/start-all' -TimeoutSec 5 | Out-Null } catch {}
