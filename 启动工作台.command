#!/bin/zsh
cd "$(dirname "$0")" || exit 1

# 读取目录配置在同目录的 remote_paths.json：
# waypoint_directory / map_directory：Jetson 上的目录
# 修改配置后，在页面点击“刷新文件树”即可，无需重启。

if [[ ! -x .venv/bin/python ]]; then
  echo '未找到 Python 环境，请按 README.md 的安装步骤准备。'
  read '?按回车退出'
  exit 1
fi
echo "文件夹路径配置：$(pwd)/remote_paths.json"
echo '打开浏览器访问 http://127.0.0.1:8766'
echo '修改 remote_paths.json 后，点击页面的“刷新文件树”。'
echo '关闭服务：在此窗口按 Control+C。'
exec .venv/bin/python app.py
