<#
====================================================================
 ARGO - produzione/build/firma.ps1
 Firma di code-signing SELF-SIGNED per l'eseguibile ARGO su Windows.
====================================================================

 AVVISO ONESTO (LEGGERE PRIMA DI USARE):

   Una firma SELF-SIGNED *non* e' emessa da una Certificate Authority
   riconosciuta da Windows.  Di conseguenza:

     - Windows SmartScreen mostrera' comunque "Editore sconosciuto"
       (Unknown publisher) all'avvio dell'eseguibile.
     - Il "Reputation check" di SmartScreen NON viene superato: gli
       utenti vedranno l'avviso blu "Windows ha protetto il PC".
     - La firma serve solo a garantire integrita' (il file non e'
       stato manomesso) e a chi importa MANUALMENTE il certificato
       tra quelli fidati (es. la tua stessa macchina, una flotta
       aziendale gestita via GPO).

   Per la VERA fiducia (nessun avviso SmartScreen, nome editore
   verificato) serve un certificato di code-signing a pagamento:

     - OV (Organization Validation): ~100-300 euro/anno, costruisce
       reputazione nel tempo.
     - EV (Extended Validation): piu' caro, su token hardware,
       reputazione SmartScreen immediata.

   Emittenti tipici: DigiCert, Sectigo, GlobalSign, SSL.com.

 In breve: questo script e' utile per test interni e distribuzione
 controllata, NON sostituisce un certificato CA per il pubblico.

--------------------------------------------------------------------

 UTILIZZO (dopo aver costruito l'exe con PyInstaller):

   # firma l'eseguibile principale prodotto da PyInstaller
   powershell -ExecutionPolicy Bypass -File produzione\build\firma.ps1 `
       -EseguibileDaFirmare "produzione\build\dist\ARGO\ARGO.exe"

   # opzionale: nome del certificato e server di timestamp personalizzati
   powershell -ExecutionPolicy Bypass -File produzione\build\firma.ps1 `
       -EseguibileDaFirmare ".\dist\ARGO\ARGO.exe" `
       -NomeCertificato "ARGO Self-Signed" `
       -ServerTimestamp "http://timestamp.digicert.com"

 Lo script:
   1) crea un certificato di code-signing self-signed in
      Cert:\CurrentUser\My (solo se non ne esiste gia' uno con lo
      stesso nome);
   2) firma l'eseguibile con Set-AuthenticodeSignature, includendo un
      timestamp (cosi' la firma resta valida anche dopo la scadenza
      del certificato).

 Non richiede privilegi di amministratore: opera nel cert store
 dell'utente corrente.
#>

[CmdletBinding()]
param(
    # Percorso dell'eseguibile (o DLL/script) da firmare. Obbligatorio.
    [Parameter(Mandatory = $true)]
    [string]$EseguibileDaFirmare,

    # Nome leggibile del certificato self-signed (Subject CN).
    [string]$NomeCertificato = "ARGO Self-Signed",

    # Server di timestamp RFC 3161. Garantisce che la firma resti
    # valida anche dopo la scadenza del certificato.
    [string]$ServerTimestamp = "http://timestamp.digicert.com",

    # Anni di validita' del certificato appena creato.
    [int]$AnniValidita = 3
)

# Interrompi al primo errore: meglio fallire chiaramente che firmare
# in modo ambiguo.
$ErrorActionPreference = "Stop"

# Avviso a video, cosi' chi lancia lo script non si sorprende davanti
# all'avviso SmartScreen.
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Yellow
Write-Host " ATTENZIONE: firma SELF-SIGNED (non CA-trusted)." -ForegroundColor Yellow
Write-Host " Windows SmartScreen mostrera' comunque 'Editore sconosciuto'." -ForegroundColor Yellow
Write-Host " Per la fiducia pubblica serve un certificato OV/EV a pagamento." -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Yellow
Write-Host ""

# --- 1) Verifica che il file da firmare esista ----------------------
if (-not (Test-Path -LiteralPath $EseguibileDaFirmare)) {
    Write-Error "File da firmare non trovato: $EseguibileDaFirmare"
    exit 1
}
# Normalizza a percorso assoluto per evitare ambiguita'.
$EseguibileDaFirmare = (Resolve-Path -LiteralPath $EseguibileDaFirmare).Path
Write-Host "File da firmare : $EseguibileDaFirmare"
Write-Host "Certificato     : $NomeCertificato"
Write-Host "Timestamp       : $ServerTimestamp"
Write-Host ""

# --- 2) Cerca o crea il certificato di code-signing -----------------
# Cerchiamo nel personal store dell'utente un certificato di code
# signing con il Subject corrispondente. La condizione sull'EKU
# (Enhanced Key Usage 1.3.6.1.5.5.7.3.3 = Code Signing) evita di
# riusare per errore un certificato non adatto.
$soggetto = "CN=$NomeCertificato"
$cert = Get-ChildItem -Path Cert:\CurrentUser\My |
        Where-Object {
            $_.Subject -eq $soggetto -and
            $_.EnhancedKeyUsageList.ObjectId -contains "1.3.6.1.5.5.7.3.3"
        } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1

if ($null -ne $cert) {
    Write-Host "Certificato gia' presente (thumbprint $($cert.Thumbprint)), lo riuso." -ForegroundColor Green
}
else {
    Write-Host "Nessun certificato trovato: ne creo uno nuovo self-signed..." -ForegroundColor Cyan
    # New-SelfSignedCertificate con tipo CodeSigningCert genera una
    # coppia di chiavi adatta alla firma del codice. Resta solo
    # nell'utente corrente: niente privilegi admin necessari.
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $soggetto `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyUsage DigitalSignature `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -HashAlgorithm SHA256 `
        -NotAfter (Get-Date).AddYears($AnniValidita)

    Write-Host "Creato certificato (thumbprint $($cert.Thumbprint))." -ForegroundColor Green
    Write-Host ""
    Write-Host "Suggerimento: per evitare l'avviso di certificato non fidato" -ForegroundColor DarkGray
    Write-Host "SU QUESTA MACCHINA puoi importarlo tra le 'Trusted Root" -ForegroundColor DarkGray
    Write-Host "Certification Authorities' (richiede admin). Sulle macchine" -ForegroundColor DarkGray
    Write-Host "altrui questo non e' possibile/consigliabile: serve una CA vera." -ForegroundColor DarkGray
}

Write-Host ""

# --- 3) Firma l'eseguibile ------------------------------------------
# Includiamo sempre il timestamp: senza, alla scadenza del certificato
# la firma diventerebbe invalida. Con il timestamp resta valida perche'
# attesta che la firma e' avvenuta mentre il certificato era valido.
Write-Host "Firma in corso..." -ForegroundColor Cyan
$risultato = Set-AuthenticodeSignature `
    -FilePath $EseguibileDaFirmare `
    -Certificate $cert `
    -HashAlgorithm SHA256 `
    -TimestampServer $ServerTimestamp

# --- 4) Riporta l'esito (degrada con grazia) ------------------------
Write-Host ""
switch ($risultato.Status) {
    "Valid" {
        Write-Host "OK - file firmato con successo (firma 'Valid')." -ForegroundColor Green
        Write-Host "Ricorda: e' self-signed, SmartScreen avvisera' comunque." -ForegroundColor Yellow
        exit 0
    }
    "UnknownError" {
        # Tipico quando il certificato non e' nella Trusted Root: la
        # firma c'e' ma la catena non e' fidata. Non e' un errore di
        # firma vero e proprio per il caso self-signed.
        Write-Host "Firma applicata, ma la catena non e' fidata (self-signed)." -ForegroundColor Yellow
        Write-Host "Stato riportato: $($risultato.Status) - atteso per un cert self-signed." -ForegroundColor Yellow
        Write-Host "Messaggio: $($risultato.StatusMessage)" -ForegroundColor DarkGray
        exit 0
    }
    default {
        Write-Host "Firma NON riuscita. Stato: $($risultato.Status)" -ForegroundColor Red
        Write-Host "Messaggio: $($risultato.StatusMessage)" -ForegroundColor Red
        exit 1
    }
}
