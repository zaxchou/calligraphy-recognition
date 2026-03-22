@echo off
echo y | ssh-keygen -t ed25519 -C "trae@local" -f "%USERPROFILE%\.ssh\id_ed25519_new" -N ""
