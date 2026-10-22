@echo off
rem ============================================================
rem  podcast_video.bat  -  audio -> podcast video (local, offline)
rem
rem  Just double-click me:
rem    first run with an empty input\  -> prints how to start
rem    once input\ has stuff            -> makes output\podcast.mp4
rem
rem  Folder layout (everything you put in goes to input\):
rem    input\ref\          3~10s reference clips (A = you, B = someone else)
rem    input\script.txt    the dialogue: blocks of "A:" / "B:" + lines
rem    input\script.json   voices/config; copy input\script.example.json
rem    input\broll\        optional background videos (dashcam / scenery ...)
rem    input\lines\        optional ready-made per-sentence wavs
rem    input\lines.txt     one sentence per line, matches input\lines\
rem    input\cover.png     optional cover image (jpg / jpeg / webp ok)
rem    input\bg.png        optional background for the auto cover (circle + title on top)
rem    input\circle.png    optional picture inside the circle (auto-cropped round)
rem    output\             everything produced lands here
rem
rem  Look & feel (title size, subtitle size, font, bg, circle ...) can be set
rem  in input\script.json under the "video" block, so double-click still works.
rem
rem  Drag & drop: drop a script.txt / script.json / timeline.json onto this file.
rem  Manual:
rem    podcast_video.bat                       (auto: look at input\)
rem    podcast_video.bat demo                  (preview the layout, fake audio)
rem    podcast_video.bat from-lines --dir input\lines --text-file input\lines.txt
rem    podcast_video.bat render --timeline output\timeline.json
rem    podcast_video.bat transcribe              (input\ref wav -> ref_text, offline)
rem    podcast_video.bat sample -e google -v zh-CN   (audition a free online voice)
rem    podcast_video.bat sample -e baidu  -v 0
rem    podcast_video.bat auto --ai-engine google     (B speaks with an online voice)
rem
rem  This file is deliberately ASCII-only to avoid codepage issues.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title podcast video

set "HERE=%~dp0"
set "PY="
set "BUNDLE=%HERE%..\tools_aigc_GPT-SoVITS\GPT-SoVITS-v2pro-20250604\runtime\python.exe"
if exist "%BUNDLE%" set "PY=%BUNDLE%"
if not defined PY for %%P in (python.exe) do if not defined PY set "PY=%%~$PATH:P"
if not defined PY goto nopy
if not exist "%HERE%podcast.py" goto noscript

rem --- no argument: do the automatic thing (look at input\) ---
if "%~1"=="" (
  "%PY%" "%HERE%podcast.py" auto
  goto done
)

rem --- a dropped .txt: it is the dialogue script (A: / B: blocks) ---
if /i "%~x1"==".txt" (
  "%PY%" "%HERE%podcast.py" build --text "%~1" %2 %3 %4 %5 %6 %7 %8
  goto done
)

rem --- a dropped .json: has "duration" -> timeline, otherwise -> voices/config ---
if /i "%~x1"==".json" (
  findstr /i /c:duration "%~1" >nul
  if not errorlevel 1 (
    "%PY%" "%HERE%podcast.py" render --timeline "%~1" %2 %3 %4 %5 %6 %7 %8
    goto done
  )
  "%PY%" "%HERE%podcast.py" build --script "%~1" %2 %3 %4 %5 %6 %7 %8
  goto done
)

"%PY%" "%HERE%podcast.py" %*
goto done

:nopy
echo [x] python not found. Install one, or keep the GPT-SoVITS bundle at ..\tools_aigc_GPT-SoVITS\
goto done

:noscript
echo [x] podcast.py not found. Put this .bat next to it.

:done
echo.
echo ---- finished ----
pause
