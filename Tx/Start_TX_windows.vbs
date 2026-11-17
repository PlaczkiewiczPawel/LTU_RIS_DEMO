Option Explicit

Dim files, shell, repository, bootstrap
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
repository = files.GetParentFolderName(files.GetParentFolderName(WScript.ScriptFullName))
bootstrap = files.BuildPath(repository, "start_windows.vbs")
shell.Run Chr(34) & WScript.FullName & Chr(34) & " " & _
    Chr(34) & bootstrap & Chr(34) & " tx", 0, False
