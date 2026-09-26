#!/usr/bin/env bash
set -euo pipefail

PACKAGE="com.miguelduval.mozart.debug"
ACTIVITY="\${PACKAGE}/com.miguelduval.mozart.MainActivity"
START_TIMEOUT=90
START_WINDOW=120
LOGCAT_FILE=/tmp/mozart-logcat.txt
START_FILE=/tmp/mozart-start.txt
START_STATUS_FILE=/tmp/mozart-start-status.txt
START_HOST_PID_FILE=/tmp/mozart-start-host-pid.txt
PID_FILE=/tmp/mozart-pid.txt
PS_FILE=/tmp/mozart-ps.txt
ACTIVITY_FILE=/tmp/mozart-activity.txt
PROCESSES_FILE=/tmp/mozart-processes.txt
WINDOW_FILE=/tmp/mozart-window.txt
SCREEN_FILE=/tmp/mozart-screen.png
UI_FILE=/tmp/mozart-ui.xml
RETRY_LOGCAT_FILE=/tmp/mozart-attempt-1-logcat.txt

rm -f "$LOGCAT_FILE" "$START_FILE" "$START_STATUS_FILE" "$START_HOST_PID_FILE" "$PID_FILE" "$PS_FILE" "$ACTIVITY_FILE" "$PROCESSES_FILE" "$WINDOW_FILE" "$SCREEN_FILE" "$UI_FILE" "$RETRY_LOGCAT_FILE"

write_logcat() {
  timeout 20s adb shell logcat -d -t 2000 > "$LOGCAT_FILE" 2>/dev/null || true
}

fatal_mozart_exception() {
  grep -B3 -A12 -F "Process: $PACKAGE" "$LOGCAT_FILE" | grep -Fq "FATAL EXCEPTION"
}

system_anr_detected() {
  grep -Fq "ANR in system" "$LOGCAT_FILE"
}

start_app() {
  rm -f "$START_FILE" "$START_STATUS_FILE" "$START_HOST_PID_FILE"
  (
    set +e
    timeout "\${START_TIMEOUT}s" adb shell am start -n "$ACTIVITY" > "$START_FILE" 2>&1
    rc=$?
    printf '%s\n' "$rc" > "$START_STATUS_FILE"
  ) &
  printf '%s\n' "$!" > "$START_HOST_PID_FILE"
}

wait_for_startup() {
  for _ in $(seq 1 60); do
    write_logcat
    if fatal_mozart_exception; then
      return 2
    fi
    if grep -Fq "STARTUP: onStart complete" "$LOGCAT_FILE"; then
      return 0
    fi
    if system_anr_detected; then
      return 3
    fi
    sleep 2
  done
  return 1
}

collect_diagnostics() {
  timeout 10s adb shell pidof "$PACKAGE" > "$PID_FILE" 2>/dev/null || true
  timeout 15s adb shell ps -A > "$PS_FILE" 2>/dev/null || true
  timeout 15s adb shell dumpsys activity activities > "$ACTIVITY_FILE" 2>/dev/null || true
  timeout 15s adb shell dumpsys activity processes > "$PROCESSES_FILE" 2>/dev/null || true
  timeout 15s adb shell dumpsys window windows > "$WINDOW_FILE" 2>/dev/null || true
  write_logcat
  timeout 15s adb exec-out screencap -p > "$SCREEN_FILE" 2>/dev/null || true
  timeout 10s adb shell uiautomator dump /sdcard/mozart-ui.xml >/dev/null 2>&1 || true
  timeout 10s adb exec-out cat /sdcard/mozart-ui.xml > "$UI_FILE" 2>/dev/null || true
}

adb start-server
adb wait-for-device
timeout 30s adb shell getprop sys.boot_completed | grep -q "1"
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell am force-stop "$PACKAGE"
adb logcat -c

start_app
wait_for_startup
startup_rc=$?

if [[ "$startup_rc" -eq 2 ]]; then
  echo "Fatal Mozart Android exception detected during startup."
  collect_diagnostics
  exit 1
fi

if [[ "$startup_rc" -eq 3 ]]; then
  cp "$LOGCAT_FILE" "$RETRY_LOGCAT_FILE" 2>/dev/null || true
  echo "Android system_server ANR detected before Mozart completed startup; retrying launch once."
  timeout 20s adb shell am force-stop "$PACKAGE" >/dev/null 2>&1 || true
  adb logcat -c || true
  start_app
  wait_for_startup
  startup_rc=$?
  if [[ "$startup_rc" -eq 2 ]]; then
    echo "Fatal Mozart Android exception detected during retry."
    collect_diagnostics
    exit 1
  fi
fi

collect_diagnostics

printf '=== START STATUS ===\n'
cat "$START_STATUS_FILE" 2>/dev/null || true
printf '\n=== PID ===\n'
cat "$PID_FILE" 2>/dev/null || true
printf '\n=== START OUTPUT ===\n'
cat "$START_FILE" 2>/dev/null || true
printf '\n=== MOZART LOG MARKERS ===\n'
grep "MozartStartup" "$LOGCAT_FILE" || true
printf '\n=== MOZART PS ===\n'
grep -i "mozart" "$PS_FILE" || true

if fatal_mozart_exception; then
  echo "Fatal Mozart Android exception detected."
  exit 1
fi

if [[ "$startup_rc" -ne 0 ]]; then
  if system_anr_detected; then
    echo "Android system_server remained unhealthy after the retry; smoke test cannot establish Mozart startup."
  else
    echo "Mozart did not complete Android startup within \${START_WINDOW}s."
  fi
  exit 1
fi

if ! grep -Fq "$PACKAGE" "$PS_FILE"; then
  echo "Mozart process was not found in process list after successful startup markers."
  exit 1
fi
if ! grep -Fq "com.miguelduval.mozart.debug/com.miguelduval.mozart.MainActivity" "$ACTIVITY_FILE"; then
  echo "MainActivity was not present in activity manager state."
  exit 1
fi
if ! grep -Fq "STARTUP: nativeEngineInfo complete" "$LOGCAT_FILE"; then
  echo "MainActivity did not complete nativeEngineInfo()."
  exit 1
fi
if ! grep -Fq "STARTUP: onCreate complete" "$LOGCAT_FILE"; then
  echo "MainActivity.onCreate did not complete."
  exit 1
fi
if ! grep -Fq "STARTUP: onStart complete" "$LOGCAT_FILE"; then
  echo "MainActivity.onStart did not complete."
  exit 1
fi

echo "Mozart Android startup smoke test passed."
