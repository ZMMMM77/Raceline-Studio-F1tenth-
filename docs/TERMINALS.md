# Jetson node terminals

The bottom panel switches between **Speed curve** and **Node terminals** without changing the map size. The expand button opens a temporary larger terminal view; Escape restores it.

1. Connect to Jetson using the existing SSH settings.
2. Open **Node terminals → Settings**. Add a terminal for each command group.
3. Enter its name, Jetson working directory, environment setup (`source` commands), and launch command. Save settings.
4. Use **Start** for one terminal, or check **Include in Start all** for each terminal that belongs in the saved startup group.
5. Use **Stop** to send Ctrl+C. Once the process exits, **Start** can launch it again.

Jetson needs `python3`, `bash`, and `tmux` (on Ubuntu: `sudo apt install tmux`). Commands run as the existing SSH user. Studio does not install packages automatically or launch anything on page load.

**Start all** issues commands in list order; it does not wait for ROS readiness. Already running sessions are skipped. A failed environment setup or working-directory change prevents that terminal's launch command from running.

Output refreshes every two seconds while the terminal panel is visible. The viewer keeps the latest 300 history lines plus the current screen, up to 100 KB. It supports line input and Ctrl+C, not a full VT emulator or fullscreen programs such as vim. Warning/error lines are highlighted. The optional readiness keyword matches recent output only; it is not a ROS topic-health check. Exit status is shown when a process finishes.

Switching tabs, closing the page, or disconnecting SSH does not stop the tmux sessions. Reconnect to the same Jetson with the same local settings to recover them. A Jetson reboot ends the sessions. Stop live sessions before removing their settings; removing a saved terminal requires a connection to verify it is stopped.

Settings are stored locally in `.remote/terminals.json`, which is excluded from Git. Do not place passwords in launch commands. The dedicated tmux server uses `-L raceline-studio` and its own session names; existing user terminals are not stopped. It starts without the user's tmux configuration so custom window numbering does not affect targeting.

Session persistence and respawning use the documented [tmux session and pane commands](https://man.openbsd.org/tmux).
