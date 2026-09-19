#!/bin/sh
# FUT Asistanı sunucusunu (yeniden) başlatır ve tarayıcıda açar.
cd "$(dirname "$0")"
PID=$(ss -ltnp 2>/dev/null | grep ':8765 ' | grep -o 'pid=[0-9]*' | cut -d= -f2)
[ -n "$PID" ] && kill $PID && sleep 1
setsid nohup .venv/bin/python ui.py >/dev/null 2>&1 &
