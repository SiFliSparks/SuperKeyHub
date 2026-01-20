; ============================================================================
; SuperKeyHUB NSIS Installer Script
; ============================================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ============================================================================
; Configuration
; ============================================================================
!define APP_NAME "SuperKeyHUB"
!define APP_VERSION "1.7.5"
!define APP_AUTHOR "SuperKey Team"
!define APP_DESCRIPTION "SuperKey Hardware Monitor"
!define APP_URL "https://sparks.sifli.com/projects/superkey/"
!define APP_EXE "${APP_NAME}.exe"

!define DIST_DIR "dist"
!define ASSETS_DIR "assets"

; Auto-start registry path
!define AUTOSTART_REG_KEY "Software\Microsoft\Windows\CurrentVersion\Run"
; Legacy task scheduler task name (for cleanup)
!define LEGACY_TASK_NAME "${APP_NAME}_AutoStart"

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
    ; Use registry for auto-start (HKCU, no admin required)
    WriteRegStr HKCU "${AUTOSTART_REG_KEY}" "${APP_NAME}" '"$INSTDIR\${APP_EXE}" --minimized'
SectionEnd

; ============================================================================
; Component Descriptions
; ============================================================================
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Install ${APP_NAME} main program files"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Create Start Menu shortcuts"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Create Desktop shortcut"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecAutoStart} "Set to auto start on login"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ============================================================================
; Uninstall Section
; ============================================================================
Section "Uninstall"
    ; Kill running process
    nsExec::ExecToLog 'taskkill /F /IM "${APP_EXE}"'
    
    ; Clean auto-start - registry method (current)
    DeleteRegValue HKCU "${AUTOSTART_REG_KEY}" "${APP_NAME}"
    
    ; Clean legacy auto-start - task scheduler method (for old versions)
    nsExec::ExecToLog 'schtasks /Delete /TN "${LEGACY_TASK_NAME}" /F'
    
    ; Delete program files
    RMDir /r "$INSTDIR"
    
    ; Delete shortcuts
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
    
    ; Delete registry keys
    DeleteRegKey HKLM "Software\${APP_NAME}"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    
    ; Delete user config directory (optional, comment out to keep user config)
    RMDir /r "$APPDATA\SuperKey"
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
