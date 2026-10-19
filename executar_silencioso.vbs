Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c python ""D:\Projetos\Relatorios - IA\executar_fluxo.py"" >> ""D:\Projetos\Relatorios - IA\execucao.log"" 2>&1", 0, True
