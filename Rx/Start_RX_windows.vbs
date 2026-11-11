Option Explicit

Dim files, shell, directory, repository, python, launcher
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
directory = files.GetParentFolderName(WScript.ScriptFullName)
repository = files.GetParentFolderName(directory)
python = files.BuildPath(repository, ".venv\Scripts\pythonw.exe")
launcher = files.BuildPath(directory, "launch_rx.py")

If Not files.FileExists(python) Then
    MsgBox "Python environment not found:" & vbCrLf & python & vbCrLf & vbCrLf & _
        "Prepare the repository .venv with NumPy, Matplotlib and UHD first.", _
        vbCritical, "RX startup error"
    WScript.Quit 1
End If

shell.CurrentDirectory = directory
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & launcher & Chr(34), 0, False
