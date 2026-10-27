@echo off
set PYTHON=C:\Users\migue\.cline\data\workspaces\chat\Mozart\.venv-aura\Scripts\python.exe
set SCRIPT=C:\Users\migue\.cline\data\workspaces\chat\Mozart\pilot_train.py
set RUN_DIR=C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\runs\pilot-20261027_145544
"%PYTHON%" "%SCRIPT%" > "%RUN_DIR%\stdout.log" 2> "%RUN_DIR%\stderr.log"