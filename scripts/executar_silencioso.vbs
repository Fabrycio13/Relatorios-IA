Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Obtem dinamicamente o diretorio do script (scripts/) e a raiz do projeto
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
projectDir = FSO.GetParentFolderName(scriptDir)

' Garante que o diretorio de trabalho ativo seja a raiz do projeto
WshShell.CurrentDirectory = projectDir

' Preserva o interpretador Python funcional padrao do ambiente
localAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
pythonExe = localAppData & "\Programs\Python\Python313\python.exe"

If Not FSO.FileExists(pythonExe) Then
    pythonExe = "python.exe"
End If

mainPy = projectDir & "\main.py"
cmdStr = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & mainPy & Chr(34)

' Executa com WindowStyle = 0 (invisivel) e propaga o codigo de saida do processo
exitCode = WshShell.Run(cmdStr, 0, True)
WScript.Quit exitCode
