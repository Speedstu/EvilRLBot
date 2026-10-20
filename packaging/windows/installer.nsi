Unicode True
!include "MUI2.nsh"
!define PRODUCT "Evil RLBot"
!define VERSION "2026.10.20.4"
!define PUBLISHER "Evil RLBot Community"
!ifndef ROOT
!define ROOT "${__FILEDIR__}\..\.."
!endif
Name "${PRODUCT}"
OutFile "${ROOT}\dist\EvilRLBot-Windows-x64-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\EvilRLBot"
RequestExecutionLevel user
ShowInstDetails show
ShowUninstDetails show
SetCompressor /SOLID lzma
BrandingText "Evil RLBot - Native V4/V5 Windows Engine"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Evil RLBot" SEC_MAIN
  ; Only replace app-owned interpreters to prevent mixing old/new pip internals.
  ; User bots and PyTorch live separately under LOCALAPPDATA\EvilRLBot.
  RMDir /r "$INSTDIR\runtime\v4"
  RMDir /r "$INSTDIR\runtime\v5"
  SetOutPath "$INSTDIR"
  File /r "${ROOT}\release\EvilRLBot\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Evil RLBot"
  CreateShortCut "$SMPROGRAMS\Evil RLBot\Evil RLBot.lnk" "$INSTDIR\EvilRLBot.exe"
  CreateShortCut "$SMPROGRAMS\Evil RLBot\Diagnostics.lnk" "$INSTDIR\EvilRLBot-Debug.cmd"
  CreateShortCut "$DESKTOP\Evil RLBot.lnk" "$INSTDIR\EvilRLBot.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EvilRLBot" "DisplayName" "${PRODUCT}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EvilRLBot" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EvilRLBot" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EvilRLBot" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EvilRLBot" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\Evil RLBot.lnk"
  Delete "$SMPROGRAMS\Evil RLBot\Evil RLBot.lnk"
  Delete "$SMPROGRAMS\Evil RLBot\Diagnostics.lnk"
  RMDir "$SMPROGRAMS\Evil RLBot"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\EvilRLBot"
  RMDir /r "$INSTDIR"
  ; Preserve user bots and Python dependencies on upgrades/uninstall.
SectionEnd
