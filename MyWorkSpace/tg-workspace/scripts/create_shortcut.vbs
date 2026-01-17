Set WshShell = CreateObject("WScript.Shell")
Set Shortcut = WshShell.CreateShortcut(WshShell.SpecialFolders("Desktop") & "\TG Workspace.lnk")
Shortcut.TargetPath = "D:\VsCode\MyWorkSpace\tg-workspace\TG Workspace.bat"
Shortcut.WorkingDirectory = "D:\VsCode\MyWorkSpace\tg-workspace"
Shortcut.Description = "TG Workspace - Lead Management"
Shortcut.IconLocation = "D:\VsCode\MyWorkSpace\tg-workspace\apps\desktop\public\icon.svg"
Shortcut.Save
WScript.Echo "Shortcut created on Desktop!"
