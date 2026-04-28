@echo off
REM stop.bat -- kill all AXIOM-Body child processes spawned by start.py.
REM
REM start.py binds children to a Windows job-object so closing the parent
REM kills the children. But if start.py was killed without a chance to
REM clean up (Ctrl-Break, Task Manager kill, blue screen), the children
REM can persist. This script finds and terminates them by name.

setlocal

echo [stop] AXIOM-Body shutdown
echo [stop] terminating any python.exe started under this repo

REM Use wmic to scope kills to python.exe whose CommandLine contains the
REM repo's project name. This avoids killing unrelated python processes.
for /f "tokens=*" %%P in ('wmic process where "name='python.exe' and CommandLine like '%%AXIOM-Body%%'" get ProcessId /value ^| find "ProcessId"') do (
    for /f "tokens=2 delims==" %%I in ("%%P") do (
        echo [stop] killing PID %%I
        taskkill /F /PID %%I >nul 2>&1
    )
)

REM Belt-and-suspenders: kill the inline http.server too if it's still bound.
for /f "tokens=*" %%P in ('wmic process where "name='python.exe' and CommandLine like '%%http.server%%7897%%'" get ProcessId /value ^| find "ProcessId"') do (
    for /f "tokens=2 delims==" %%I in ("%%P") do (
        echo [stop] killing http.server PID %%I
        taskkill /F /PID %%I >nul 2>&1
    )
)

echo [stop] done.
endlocal
