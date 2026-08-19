# ============================================================================
# Romanya Dosya Takip -- Render'dan haftalık yerel yedek alma (2026-08-19)
#
# Windows Task Scheduler tarafından haftada bir tetiklenir. Bilgisayar o an
# kapalıysa, Task Scheduler "en kısa sürede telafi et" ayarı sayesinde bir
# sonraki açılışta/oturum açılışında otomatik çalışır.
#
# 2026-08-20 DÜZELTMESİ: İlk sürümde bildirim (Windows Forms NotifyIcon) kodu
# ASIL yedekleme işinden ÖNCE çalışıyordu -- Task Scheduler'ın arka plan
# oturumunda (masaüstü etkileşimi olmadan) bu GUI çağrısı sessizce
# başarısız olup script'i daha yedekleme hiç başlamadan durdurdu (Task
# Scheduler yine de "başarılı" (exit 0) gösterdi, ama hiçbir log satırı
# oluşmadı -- kanıt buydu). Artık ASIL İŞ (python script'i) ÖNCE çalışıyor,
# bildirimler try/catch içinde İKİNCİL/best-effort -- bildirim başarısız
# olsa bile yedekleme ASLA etkilenmez.
# ============================================================================

$backendDizin = "C:\Users\ahmet\romanya-dosya-takip - güncel\backend"
$yedekKlasor = Join-Path $backendDizin "render_yedekleri"
$gorevLogu = Join-Path $yedekKlasor "gorev_calisma_log.txt"
New-Item -ItemType Directory -Force -Path $yedekKlasor | Out-Null
Add-Content -Path $gorevLogu -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Gorev tetiklendi (Task Scheduler)."

function Bildir($baslik, $mesaj) {
    # Bildirim best-effort -- Task Scheduler'ın bazı oturumlarında (masaustu
    # etkilesimi kisitliysa) GUI cagrisi basarisiz olabilir, bu ASLA asil
    # yedekleme islemini durdurmamali.
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        Add-Type -AssemblyName System.Drawing -ErrorAction Stop
        $balon = New-Object System.Windows.Forms.NotifyIcon
        $balon.Icon = [System.Drawing.SystemIcons]::Information
        $balon.Visible = $true
        $balon.BalloonTipTitle = $baslik
        $balon.BalloonTipText = $mesaj
        $balon.ShowBalloonTip(15000)
        Start-Sleep -Seconds 6
        $balon.Dispose()
    } catch {
        Add-Content -Path $gorevLogu -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] (bildirim gosterilemedi, onemli degil: $($_.Exception.Message))"
    }
}

Bildir "Romanya Dosya Takip" "Render'dan haftalik yedek aliniyor, bitince haber verecegim..."

# TAM yol kullanılıyor -- Windows'un "WindowsApps\python.exe" takma adı
# (App Execution Alias) Task Scheduler'ın kısıtlı ortamında güvenilir
# çalışmıyor (2026-08-19: ilk otomatik test bu yüzden hiçbir şey yapmadı).
$pythonYolu = "C:\Users\ahmet\AppData\Local\Python\pythoncore-3.14-64\python.exe"

if (-not (Test-Path $pythonYolu)) {
    Add-Content -Path $gorevLogu -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] HATA: python.exe bulunamadi -- $pythonYolu"
    Bildir "Romanya Dosya Takip - Yedek HATASI" "python.exe bulunamadi, yedek alinamadi. gorev_calisma_log.txt'e bak."
    exit 1
}

Set-Location $backendDizin
$baslangic = Get-Date
$cikti = & $pythonYolu render_yedek_al.py 2>&1 | Out-String
$sure = (Get-Date) - $baslangic
$basariliMi = $LASTEXITCODE -eq 0

Add-Content -Path $gorevLogu -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Bitti. ExitCode=$LASTEXITCODE Sure=$([int]$sure.TotalSeconds)sn"
if (-not $basariliMi) {
    Add-Content -Path $gorevLogu -Value $cikti
}

if ($basariliMi) {
    Bildir "Romanya Dosya Takip - Yedek Tamamlandi" "Render yedegi basariyla alindi ($([int]$sure.TotalMinutes) dk surdu). Detay: backend\render_yedekleri\yedek_gecmisi.log"
} else {
    Bildir "Romanya Dosya Takip - Yedek HATASI" "Yedek alma sirasinda bir sorun oldu, log dosyasini kontrol et: backend\render_yedekleri\yedek_gecmisi.log"
}
