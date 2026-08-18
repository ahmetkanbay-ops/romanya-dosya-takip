' Backend'i konsol penceresi GOSTERMEDEN (arka planda, gizli) baslatir.
' Windows Gorev Zamanlayicisi'ndaki "RomanyaDosyaTakipBackend" gorevi
' oturum acilisinda bu dosyayi calistirir -- kullanici hicbir siyah
' pencere gormez, backend sessizce arka planda ayaga kalkar.
Set WshShell = CreateObject("WScript.Shell")
gorevKlasoru = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
WshShell.Run """" & gorevKlasoru & "start_backend.bat""", 0, False
