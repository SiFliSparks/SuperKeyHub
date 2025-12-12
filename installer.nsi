; ============================================================================
; SuperKeyHUB NSIS Installer Script
; ============================================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ============================================================================
; Configuration
; ============================================================================
!define APP_NAME "SuperKeyHUB"
!define APP_VERSION "1.6.1"
!define APP_AUTHOR "SuperKey Team"
!define APP_DESCRIPTION "SuperKey Hardware Monitor"
!define APP_URL "https://sparks.sifli.com/projects/superkey/"
!define APP_EXE "${APP_NAME}.exe"

!define DIST_DIR "dist"
!define ASSETS_DIR "assets"

; ============================================================================
; Installer Properties
; ============================================================================
Name "${APP_NAME} ${APP_VERSION}"
OutFile "${DIST_DIR}\${APP_NAME}-${APP_VERSION}-Setup.exe"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey /LANG=2052 "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=2052 "CompanyName" "${APP_AUTHOR}"
VIAddVersionKey /LANG=2052 "FileDescription" "${APP_DESCRIPTION}"
VIAddVersionKey /LANG=2052 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=2052 "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=2052 "LegalCopyright" "Copyright (C) 2024 ${APP_AUTHOR}"

; ============================================================================
; UI Settings
; ============================================================================
!define MUI_ABORTWARNING
!define MUI_ICON "${ASSETS_DIR}\app.ico"
!define MUI_UNICON "${ASSETS_DIR}\app.ico"

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Run ${APP_NAME}"
!define MUI_FINISHPAGE_LINK "Visit Website"
!define MUI_FINISHPAGE_LINK_LOCATION "${APP_URL}"

; ============================================================================
; Install Pages
; ============================================================================
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; ============================================================================
; Uninstall Pages
; ============================================================================
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; ============================================================================
; Languages
; ============================================================================
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ============================================================================
; Install Sections
; ============================================================================
Section "Main Program (Required)" SecMain
    SectionIn RO
    
    SetOutPath "$INSTDIR"
    
    File /r "${DIST_DIR}\${APP_NAME}\*.*"
    
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    WriteRegStr HKLM "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\${APP_NAME}" "Version" "${APP_VERSION}"
    
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayIcon" "$INSTDIR\${APP_EXE}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "Publisher" "${APP_AUTHOR}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "URLInfoAbout" "${APP_URL}"
    
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "EstimatedSize" "$0"
SectionEnd

Section "Start Menu Shortcuts" SecStartMenu
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" \
        "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
SectionEnd

Section "Desktop Shortcut" SecDesktop
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

Section /o "Auto Start" SecAutoStart
    nsExec::ExecToLog 'schtasks /Create /TN "${APP_NAME}_AutoStart" /TR "\"$INSTDIR\${APP_EXE}\" --minimized" /SC ONLOGON /RL HIGHEST /DELAY 0000:5 /F'
SectionEnd

; ============================================================================
; Component Descriptions
; ============================================================================
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Install ${APP_NAME} main program files"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Create Start Menu shortcuts"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Create Desktop shortcut"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecAutoStart} "Set to auto start on login (requires admin privileges)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ============================================================================
; Uninstall Section
; ============================================================================
Section "Uninstall"
    nsExec::ExecToLog 'taskkill /F /IM "${APP_EXE}"'
    
    nsExec::ExecToLog 'schtasks /Delete /TN "${APP_NAME}_AutoStart" /F'
    
    RMDir /r "$INSTDIR"
    
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
    
    DeleteRegKey HKLM "Software\${APP_NAME}"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
SectionEnd

; ============================================================================
; Pre-Install Check
; ============================================================================
Function .onInit
    ReadRegStr $0 HKLM "Software\${APP_NAME}" "InstallDir"
    ${If} $0 != ""
        MessageBox MB_OKCANCEL|MB_ICONINFORMATION \
            "Detected existing ${APP_NAME} installation.$\n$\nClick OK to uninstall the old version first, then install the new version." \
            IDOK uninst
        Abort
    uninst:
        ExecWait '"$0\Uninstall.exe" /S'
    ${EndIf}
FunctionEnd