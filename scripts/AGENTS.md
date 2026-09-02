# Script instructions

This directory contains equivalent Docker Compose start and stop entry points for macOS, Linux, and Windows PowerShell.

- Shell scripts must use POSIX `sh`, stop on errors, and resolve the repository root relative to the script location.
- PowerShell scripts must stop on errors and resolve the repository root from `$PSScriptRoot`.
- Start scripts build and start the Compose service in detached mode.
- Stop scripts use `docker compose down` without `--volumes` so application data persists.