#!/bin/bash
# Recover a wedged user@1000.service (cgroup v2 "Failed to spawn executor: Device or resource busy").
#
# Cause: leftover processes in the user@1000 cgroup tree that survive SIGKILL (foreign PID
# namespace - they read as PID `0` in cgroup.procs). systemd then can't CLONE_INTO_CGROUP.
#
# Deliberately does NOT use `loginctl terminate-user` or a blind `rmdir` sweep of the slice:
# terminate-user completes asynchronously and tears down the session we just restarted (~25-60s
# later), which is what made this look like it "re-wedged on its own". cgroup.kill is enough.
exec >>/home/adamsl/fix-user-session.log 2>&1
echo "=== start $(date) ==="
loginctl enable-linger adamsl 2>/dev/null

for attempt in 1 2 3; do
  # deepest-first, so children are emptied before parents
  find /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service -name cgroup.kill -printf '%d %p\n' 2>/dev/null \
    | sort -rn | awk '{print $2}' | while read -r k; do echo 1 > "$k" 2>/dev/null; done
  sleep 4
  left=$(find /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service -name cgroup.procs 2>/dev/null \
    | while read -r f; do cat "$f" 2>/dev/null; done | grep -c .)
  echo "attempt $attempt: $left procs left in user@1000 tree"
  [ "$left" = "0" ] && break
done

# only now remove the emptied directories (racing rmdir against cgroup.kill silently fails)
find /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service -depth -type d 2>/dev/null \
  | while read -r d; do rmdir "$d" 2>/dev/null; done

systemctl reset-failed user@1000.service user-1000.slice 2>/dev/null
systemctl start user@1000.service
sleep 5
echo "user@1000: $(systemctl is-active user@1000.service)"
echo "=== done $(date) ==="
