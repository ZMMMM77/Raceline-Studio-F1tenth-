# Jetson 远程文件树与画布预览

## 修改读取目录

编辑同目录 `remote_paths.json`。这里的路径全部位于 SSH 连接的小车（Jetson）上，不是 Mac 文件夹：

```json
{
  "waypoint_directory": "/home/jetson/ros2_ws/src/pure_pursuit/waypoints",
  "map_directory": "/home/jetson/ros2_ws/src/maps"
}
```

上面只是路径示例，请换成实际位置。默认值 `~` 表示当前 SSH 用户的家目录。
保存后点击左侧「刷新文件树」，不需要重启。启动文件 `start.command` 也注明了配置文件位置。

## 操作

1. 启动工作台，在左侧 SSH 设置中连接小车；已保存密码时可自动连接。
2. 连接后自动展开两个配置目录。单击文件夹展开/收起，子目录按需读取。
3. 单击 CSV/TXT 直接显示路线，不弹出 Mac 文件选择窗口，也不要求先运行优化。
4. 单击 YAML 自动读取它的 `image` 文件，并应用 `resolution`、`origin`。
5. 单击 PNG/PGM/JPG 尝试匹配同名 YAML；无有效 YAML 仍可显示原图。
6. 先打开有 YAML 坐标的地图，再点击 CSV，路线会叠加显示。滚轮缩放、拖动画布、适应画布均可用。
7. 右侧显示所选文件路径、waypoint 数量、地图尺寸与坐标信息。原有规划、结果、保存功能折叠放在右侧。
8. 左侧路径框可以临时打开其他 Jetson 目录；「刷新文件树」返回后台配置的两个根目录。

这是只读预览，不修改远程文件，不自动重采样或优化路线；原有规划结果和文件预览互相独立。CSV 自动识别常见表头、x/y 首两列和 s/x/y 格式；有歧义时用「CSV 预览格式」选择 Pure Pursuit / MPPI。

SSH 密码仍保存在 macOS 钥匙串，配置 JSON 不包含密码。首次连接确认主机指纹。保存到 Jetson 仍写入原有规划结果并在覆盖前备份，预览本身不生成 CSV。

## 验证

39 项自动测试通过，包括地图/YAML 匹配、PGM 转 PNG、CSV 预览、路径配置即时更新及原有规划/SSH 回归测试。浏览器使用模拟 Jetson 文件验证文件树展开和地图路线叠加；本次未连接真实小车。


## SSH CSV planning

Open a CSV from the SSH file tree, then expand Planning & import and click Import current remote CSV for planning. The current remote map and YAML are included when available. Without a map, use CSV widths or enter half-width in Advanced import settings. Set the vehicle constraints, select minimum curvature or shortest path, and calculate. Export the generated CSV from Results & export.

This uses the same closed-loop validation, resampling, constraints and optimizer as local import. Speed is regenerated. Source files remain unchanged until Save to Jetson is explicitly used. Reopening another preview requires importing that file before optimizing it.

The remote import regression tests cover local/remote equivalence, missing widths, relative YAML image paths, changed SSH identity, invalid loops, and optimization followed by CSV download. The browser workflow was also verified using the current remote Levine CSV and map.
## Connection recovery

The page checks the SFTP channel every 15 seconds while visible and checks again when you return to the page. With automatic login enabled, a broken connection is reopened using the saved host, port and username. Temporary failures use a retry delay of up to 60 seconds; Refresh checks immediately. Manually disconnecting or forgetting a login suspends background recovery until you connect again or reopen the page. Authentication failures and host-key changes require user action.

Passwords stay in macOS Keychain. A successfully authenticated password is also retained in memory for that Studio process so an idle disconnect does not require another Keychain access. Existing saved passwords are not rewritten on every reconnect. If saving a newly entered password fails, the live SSH session remains usable and the page shows a warning. No password is written to project files or diagnostic logs. File overwrite operations are never automatically retried.
