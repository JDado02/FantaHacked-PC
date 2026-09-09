' Avvia FantaHacked senza mostrare la finestra nera del prompt.
' Per chiudere il programma si usa il pulsante "Chiudi" dentro l'applicazione.
' Se qualcosa non va, prova ad avviare "Avvia FantaHacked.bat": mostra gli errori.
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
cartella = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = cartella
sh.Run """" & cartella & "\Avvia FantaHacked.bat""", 0, False
