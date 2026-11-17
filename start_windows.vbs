Option Explicit

Dim files, shell, repository, bootstrap, component, pathEntry, searchDirectory, version
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
repository = files.GetParentFolderName(WScript.ScriptFullName)
bootstrap = files.BuildPath(repository, "launch_app.py")

If WScript.Arguments.Count <> 1 Then WScript.Quit 1
component = LCase(WScript.Arguments(0))
If component <> "ris" And component <> "rx" And component <> "tx" Then WScript.Quit 1
shell.CurrentDirectory = repository

TryStart files.BuildPath(repository, ".venv\Scripts\python.exe"), _
    files.BuildPath(repository, ".venv\Scripts\pythonw.exe"), ""

' Explicit versions also work when another virtual environment is active.
For Each pathEntry In Split(shell.Environment("PROCESS")("PATH"), ";")
    searchDirectory = shell.ExpandEnvironmentStrings(Replace(Trim(pathEntry), Chr(34), ""))
    If Len(searchDirectory) > 0 Then
        For Each version In Array("-3.13", "-3.12", "-3.11", "-3.10")
            TryStart files.BuildPath(searchDirectory, "py.exe"), _
                files.BuildPath(searchDirectory, "pyw.exe"), " " & version
        Next
    End If
Next

For Each pathEntry In Split(shell.Environment("PROCESS")("PATH"), ";")
    searchDirectory = shell.ExpandEnvironmentStrings(Replace(Trim(pathEntry), Chr(34), ""))
    If Len(searchDirectory) > 0 Then
        TryStart files.BuildPath(searchDirectory, "python.exe"), _
            files.BuildPath(searchDirectory, "pythonw.exe"), ""
    End If
Next

MsgBox "Python 3.10-3.13 was not found." & vbCrLf & vbCrLf & _
    "Install Python with the Python launcher or add Python to PATH." & vbCrLf & _
    "Then run this launcher again to prepare .venv automatically.", _
    vbCritical, "Demo startup error"
WScript.Quit 1

Sub TryStart(consolePython, windowPython, selector)
    Dim status
    If Not files.FileExists(consolePython) Or Not files.FileExists(windowPython) Then Exit Sub
    On Error Resume Next
    status = shell.Run(Chr(34) & consolePython & Chr(34) & selector & _
        " -c " & Chr(34) & "import sys; sys.exit(not ((3, 10) <= " & _
        "sys.version_info[:2] < (3, 14)))" & Chr(34), 0, True)
    If Err.Number <> 0 Then
        Err.Clear
        Exit Sub
    End If
    If status <> 0 Then Exit Sub
    shell.Run Chr(34) & windowPython & Chr(34) & selector & " " & _
        Chr(34) & bootstrap & Chr(34) & " " & component, 0, False
    If Err.Number = 0 Then WScript.Quit 0
    Err.Clear
End Sub
