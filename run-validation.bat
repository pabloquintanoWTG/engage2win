@echo off
title Engage2Win — Validation Harness
cd /d "%~dp0"

echo.
echo  Engage2Win — Phase 0 Validation
echo  =================================
echo.

pip install -q anthropic jsonschema

echo  Running harness on all maps in /samples ...
echo  (You will be asked to choose a language before processing starts.)
echo.

python validate/run.py

echo.
echo  Done. Open validate\review.html in your browser to see the results.
echo.
pause
