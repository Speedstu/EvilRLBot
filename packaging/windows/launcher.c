#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
#include <stdio.h>

int WINAPI wWinMain(HINSTANCE inst,HINSTANCE previous,PWSTR command,int show) {
    WCHAR location[32768], python[32768], script[32768], cmd[32768];
    DWORD got=GetModuleFileNameW(NULL,location,32767);
    if (!got || got >= 32767) {
        MessageBoxW(NULL,L"Cannot find Evil RLBot installation directory.",L"Evil RLBot",MB_OK|MB_ICONERROR);
        return 1;
    }
    WCHAR *slash=wcsrchr(location,L'\\');
    if (!slash) return 2;
    *slash=L'\0';
    if (swprintf(python,32768,L"%ls\\runtime\\v5\\pythonw.exe",location) < 0 ||
        swprintf(script,32768,L"%ls\\ui\\classic.py",location) < 0) return 3;
    if(GetFileAttributesW(python)==INVALID_FILE_ATTRIBUTES ||
       GetFileAttributesW(script)==INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL,L"Runtime files are missing.\n\nExtract the WHOLE EvilRLBot-Windows ZIP before running EvilRLBot.exe.",L"Evil RLBot",MB_OK|MB_ICONERROR);
        return 4;
    }
    if(swprintf(cmd,32768,L"\"%ls\" \"%ls\"",python,script)<0) return 5;
    STARTUPINFOW startup={0};
    PROCESS_INFORMATION process={0};
    startup.cb=sizeof(startup);
    if (!CreateProcessW(python,cmd,NULL,NULL,FALSE,0,NULL,location,&startup,&process)) {
        WCHAR msg[250];
        swprintf(msg,250,L"Unable to start Evil RLBot.\nWindows error: %lu\nRun EvilRLBot-Debug.cmd for details.",GetLastError());
        MessageBoxW(NULL,msg,L"Evil RLBot",MB_OK|MB_ICONERROR);
        return 6;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
