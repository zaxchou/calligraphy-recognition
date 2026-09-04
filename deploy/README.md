# 部署说明（SCP-only）

本目录的 Dockerfile / docker-compose.yml / nginx.conf 部署到服务器 /opt/molin-wiki/deploy/ 使用。
服务器上**没有 git 仓库**，也**禁止 git clone / git pull 部署**（国内服务器连 GitHub 不稳定）。

唯一部署入口：仓库根目录 `bash deploy.sh`（本地构建 + tar 管道 SCP，自动检测代码/数据/数据库变更）。
