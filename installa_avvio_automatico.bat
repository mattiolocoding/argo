@echo off
REM Mette Argo nella cartella "Esecuzione automatica" di Windows.
REM Dopo aver lanciato questo file UNA VOLTA, Argo partira' da solo
REM ogni volta che accendi il PC. Per annullare: vedi disinstalla sotto.

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$lnk = $ws.CreateShortcut('%STARTUP%\Argo.lnk');" ^
  "$lnk.TargetPath = '%~dp0avvia_argo.bat';" ^
  "$lnk.WorkingDirectory = '%~dp0';" ^
  "$lnk.WindowStyle = 7;" ^
  "$lnk.Description = 'Avvia Argo all accensione';" ^
  "$lnk.Save()"

echo.
echo ============================================
echo  Fatto. Argo partira' da solo a ogni avvio.
echo ============================================
echo.
echo  Per DISATTIVARLO in futuro: premi Win+R, scrivi  shell:startup
echo  e cancella il collegamento "Argo".
echo.
pause
