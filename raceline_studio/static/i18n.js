/* One interface, two languages. Keys are the original Chinese UI copy. */
(() => {
  const rows = `手动调速点保持不变，仅调整两端邻点。已有路线可选中要保留的速度段后平滑；可撤销。 | Keep manually edited speeds fixed; adjust only neighboring transitions. For an existing route, select the segment to preserve first. Undo is available.
已保留固定段速度，仅平滑两端衔接。可用“撤销调速”恢复。 | Pinned speeds preserved; only neighboring transitions smoothed. Use Undo speed edit to restore.
请先调整一段速度，或选中需要保持速度不变的点，再平滑衔接。 | Adjust a speed segment, or select the points whose speeds must stay fixed, before smoothing.
固定速度点索引无效。 | Invalid pinned speed indices.
衔接空间不足或固定段内部仍有突变；已保留固定点速度，仅调整可用邻点。 | Transition space is insufficient or a pinned segment still contains a jump. Pinned speeds were preserved; only available neighbors were adjusted.
仅平滑速度变化过陡处及前后邻点，可升速或降速；远处速度不变，可撤销。 | Smooth only steep transitions and nearby points, allowing increases or decreases. Distant speeds stay unchanged; undo is available.
已局部平滑速度过渡，远处速度未改变。可用“撤销调速”恢复。 | Local speed transitions smoothed; distant speeds unchanged. Use Undo speed edit to restore.
未发现过陡的速度变化，速度保持不变。 | No steep speed transitions found; speeds unchanged.
已局部平滑，但仍有过陡速度段；为保留远处速度，未扩大到整圈。 | Local smoothing completed, but some steep segments remain. Distant speeds were preserved instead of changing the whole loop.
选中点实际速度倍率 | Selected-point speed multiplier (m/s)
已完成平滑，但最低速度仍高于部分弯道限速；请降低最低速度。平滑不代表抓地校验通过。 | Smoothing completed, but minimum speed still exceeds some corner limits. Lower minimum speed; smoothing does not certify grip.
平滑已完成，速度曲线已更新。可用“撤销调速”恢复。 | Smoothing completed and the speed curve updated. Use Undo speed edit to restore.
当前速度没有需要降低的突变，未修改速度。 | No speed spikes needed reducing; speeds are unchanged.
一键平滑速度 | Smooth speed
只降低突变速度，让慢点前后平缓衔接；按保守的加减速与弯道限速处理，可撤销。不能保证实车不打滑。 | Reduce speed spikes and ease transitions around slow points, using conservative acceleration, braking and corner limits. Undo is available. This cannot guarantee tire grip.
正在平滑速度… | Smoothing speed…
速度已平滑：保留慢点、降低突变，并施加保守的加减速与弯道限速。可用“撤销调速”恢复。 | Speed smoothed: slow points retained, spikes reduced, conservative acceleration, braking and corner limits applied. Use Undo speed edits to restore.
请先生成速度，再平滑当前速度。 | Generate a speed profile before smoothing it.
当前最小速度高于部分弯道的保守限速，请降低最小速度后重试。 | Minimum speed exceeds the conservative corner limit. Lower minimum speed and try again.
远程赛道工作台 | Remote track workspace
载入示例赛道 | Load sample track
文件 | Files
未连接 · 设置 SSH | Disconnected · Configure SSH
主机 IP / 名称 | Host IP / name
用户名 | Username
端口 | Port
密码 | Password
首次填写，之后自动登录 | Enter once for automatic login
下次自动连接 | Connect automatically next time
连接 | Connect
断开 | Disconnect
忘记 | Forget
读取位置 | Browse location
Jetson 读取文件夹路径 | Jetson folder path
输入Jetson 读取文件夹路径 | Enter a Jetson folder path
打开目录 | Open folder
打开 | Open
↻ 刷新文件树 | ↻ Refresh file tree
文件树 | File tree
连接后自动显示小车上的文件树。 | The Jetson file tree appears after connecting.
等待连接 Jetson。 | Waiting for Jetson connection.
规划与导入 | Planning & import
导入赛道 | Import track
导入方式 | Import method
已有 CSV | Existing CSV
SLAM 地图 | SLAM map
中心线 CSV 可单独使用，也可附 PNG。附 YAML 后可按米制坐标叠加并检查墙壁。 | Use a centerline CSV alone or with a PNG. Add YAML to align the map in meters and check walls.
选择路线 CSV | Select route CSV
尚未选择 | Not selected
地图 PNG / PGM | Map PNG / PGM
可选 | Optional
地图 YAML | Map YAML
CSV 模式可选；地图模式必需 | Optional for CSV; required for map mode
CSV 默认按表头识别；不明确时再选择列排列。 | CSV columns are detected from headers. Choose a layout only if detection is unclear.
高级导入设置 | Advanced import settings
本机导入 · CSV 列排列 | Local import · CSV columns
自动识别（推荐） | Auto-detect (recommended)
中心线：x,y,右宽,左宽（4 列） | Centerline: x,y,right width,left width (4 columns)
Pure Pursuit：x,y,yaw,speed（4/5 列） | Pure Pursuit: x,y,yaw,speed (4/5 columns)
Levine MPPI：s,x,y,…（9/10 列） | Levine MPPI: s,x,y,… (9/10 columns)
Pure Pursuit / MPPI 模式先导入坐标，速度需重新生成；无地图时请填写单侧宽度。 | Pure Pursuit / MPPI import coordinates only; regenerate speed. Without a map, enter half-width.
Jetson 预览 · CSV 列排列 | Jetson preview · CSV columns
Pure Pursuit（4/5 列） | Pure Pursuit (4/5 columns)
MPPI（9/10 列） | MPPI (9/10 columns)
缺少宽度或 YAML？ | Missing width or YAML?
CSV 缺宽度时：单侧宽度 / m | CSV without width: half-width / m
留空则由地图计算 | Leave blank to calculate from map
CSV＋PNG 无 YAML 可以导入，PNG 会单独预览。它不会参与边界检查；提供 YAML 后才能对齐地图。 | A CSV and PNG can be imported without YAML. The PNG is previewed separately and cannot be used for boundary checks until YAML aligns it.
地图边界与清理 | Map boundaries & cleanup
CSV 边界来源 | CSV boundary source
有地图时以原始地图为准（推荐） | Use original map when available (recommended)
保留 CSV 宽度，同时检查地图 | Keep CSV widths and also check the map
已有 CSV 保留路线形状，仅按弧长重采样。地图模式不把宽度射线端点连接成墙壁；优化分为可行性修复和路线优化。 | An existing CSV retains its route shape and is resampled by arc length. Map mode does not connect width-ray endpoints as walls; optimization repairs feasibility before optimizing the route.
清理地图提取副本（仅自动提取参考线时） | Clean map extraction copy (only for automatic reference-line extraction)
填补小孔最大面积 / m² | Maximum small-hole area / m²
补缝半径 / m | Gap-closing radius / m
清理仅用于稳定参考线提取，原始地图始终参与净空检查。填 0 可关闭对应处理；复杂岔路仍建议提供参考 CSV。 | Cleanup stabilizes reference-line extraction; clearance checks still use the original map. Set 0 to disable a step. For complex junctions, provide a reference CSV.
反转行驶方向 | Reverse driving direction
Jetson 读取目录可在 remote_paths.json 修改。导入规划只读取路线几何，速度重新计算。 | Jetson browse folders can be changed in remote_paths.json. Planning imports geometry and recalculates speed.
导入并生成中心线 | Import and generate centerline
车辆参数与约束 | Vehicle parameters & constraints
车辆与约束 | Vehicle & constraints
转弯限制方式 | Turning-limit method
最大前轮转角＋轴距 | Maximum front-wheel angle + wheelbase
直接输入最小转弯半径 | Enter minimum turning radius
转角定义 | Steering-angle definition
Ackermann 等效前轮转角 | Equivalent Ackermann front-wheel angle
实测内侧前轮转角 | Measured inner front-wheel angle
最大前轮转角 / ° | Maximum front-wheel angle / °
请输入你的车辆参数 | Enter your vehicle parameters
前轮轮距 / m | Front track width / m
左右前轮中心间距 | Distance between front wheel centers
后轴中心最小转弯半径 / m | Minimum rear-axle turning radius / m
请输入最小半径 | Enter minimum radius
轴距 / m | Wheelbase / m
前后轴中心间距 | Distance between front and rear axle centers
最小半径 | Minimum radius
待填写 | Enter value
曲率上限 | Curvature limit
路径跟踪点 | Route tracking point
后轴中心（当前 Ackermann 模型） | Rear axle center (current Ackermann model)
尚不确定，先核对车辆坐标 | Unsure — check vehicle coordinates first
车身总宽 / m | Overall vehicle width / m
含轮胎 | Including tires
车身总长 / m | Overall vehicle length / m
整车外廓 | Full vehicle envelope
后轴至车尾 / m | Rear axle to vehicle tail / m
后悬长度 | Rear overhang
额外边界余量 / m | Extra boundary margin / m
前轮转角、轴距、车宽、车长已按你提供的仿真车辆数据预填，仍可修改。后轴至车尾距离尚未确认。边界检查采用覆盖整车的保守包络圆。 | Steering angle, wheelbase, width and length are prefilled from your simulation data and remain editable. Rear overhang is unconfirmed. Boundary checks use a conservative circle enclosing the vehicle.
高级计算设置 | Advanced calculation settings
计算精度 | Calculation precision
优化控制点 | Optimization control points
80 · 快速 | 80 · Fast
140 · 标准 | 140 · Standard
220 · 精细 | 220 · Fine
导出间距 / m | Export spacing / m
运行截止条件 | Stopping conditions
最大求解时间 / 秒 | Maximum solve time / s
停滞检查窗口 / 次 | Plateau check window / iterations
窗口内最小改善 / % | Minimum window improvement / %
同一精度阶段内，连续可行迭代的最佳目标值改善不足阈值时尝试结束；0% 可关闭停滞停止。时限包括粗网格初始化，在下一次求解检查时停止，最终验证及保存可能额外用时。仅导出通过加密约束检查的路线。 | Stops when the best objective improves less than the threshold over consecutive feasible iterations at one precision level; 0% disables plateau stopping. The time limit includes coarse initialization. Final validation and saving may take extra time. Only routes passing dense constraint checks are exported.
路线算法 | Route algorithm
最短行车线 | Shortest path
最小曲率行车线（整体平顺） | Minimum-curvature path (smoother overall)
最小化整圈路程，满足车辆曲率与边界约束。 | Minimize lap distance subject to vehicle curvature and boundary constraints.
计算最短行车线 | Calculate shortest path
两种算法均为局部数值优化；最小曲率不等于最短圈时。 | Both algorithms are local numerical optimizers; minimum curvature does not imply minimum lap time.
计算结果与导出 | Results & export
计算结果 | Results
等待计算 | Waiting for calculation
优化路线长度 | Optimized route length
查看详细计算指标 | View detailed metrics
中心线长度 | Centerline length
相比中心线缩短（负值为增加） | Shorter than centerline (negative means longer)
曲率平方积分 ∮κ² ds | Integrated squared curvature ∮κ² ds
最大绝对曲率 | Maximum absolute curvature
最小边界距离 | Minimum boundary clearance
规划速度范围 | Planned speed range
计算后检查曲率、边界与闭合连续性。 | Curvature, boundaries and loop continuity are checked after calculation.
导出文件 | Export files
结果自动保存到本地输出目录，也可逐个下载。 | Results are saved locally and can also be downloaded individually.
中心线 CSV | Centerline CSV
x, y, 右宽, 左宽 | x, y, right width, left width
最短路线 CSV | Shortest-path CSV
x, y, 弧长, 曲率, 前轮转角 | x, y, arc length, curvature, front-wheel angle
带速度的 waypoint CSV | Waypoint CSV with speed
x, y, vx_mps, 弧长, 曲率… | x, y, vx_mps, arc length, curvature…
更多导出 · 图片与打包 | More exports · images & archive
路线对比 PNG | Route comparison PNG
地图＋中心线＋优化路线 | Map + centerline + optimized route
速度曲线 PNG | Speed curve PNG
每个位置的目标速度和曲率 | Target speed and curvature at each position
下载全部结果 | Download all results
CSV、PNG 和计算报告 | CSV, PNG and calculation report
本机保存位置 | Local save location
导入或计算后显示 | Shown after import or calculation
复制保存路径 | Copy save path
速度是基于所填动力学上限的规划值，仍需用实际车辆验证。 | Planned speeds use the entered dynamics limits; validate them on the actual vehicle.
保存到 Jetson | Save to Jetson
尚未选择保存对象 | No save source selected
写入内容 | Content to write
速度 waypoint（m/s） | Speed waypoints (m/s)
Pure Pursuit（0–1 比例） | Pure Pursuit (0–1 ratio)
优化路线 CSV | Optimized route CSV
编辑后的 waypoint CSV | Edited waypoint CSV
Jetson 目标文件 | Jetson destination file
核对上方保存对象及目标路径后保存，覆盖前自动备份。 | Check the source and destination path. An existing file is backed up before overwrite.
打开地图或路线 | Open a map or route
等待打开 | Waiting to open
打开文件 → 选择路线 → 编辑点位 → 设置速度 → 检查与保存 | Open file → Choose route → Edit waypoints → Set speed → Check & save
从左栏连接 Jetson 并打开地图或 CSV，也可载入示例。 | Connect to Jetson and open a map or CSV from the left, or load the sample.
背景图 | Background
当前地图（坐标叠加） | Current map (coordinate overlay)
原始图片（单独预览） | Original image (separate preview)
无背景图 | No background
中心线 | Centerline
路线 | Route
速度（红慢青快） | Speed (red slow, cyan fast)
地图 | Map
放大 | Zoom in
缩小 | Zoom out
适应画布 | Fit to canvas
赛道中心线和优化路线，可拖动平移、滚轮缩放 | Track centerline and optimized route; drag to pan, scroll to zoom
从左侧打开文件 | Open a file from the left
展开左侧文件树，单击地图、YAML 或 CSV 直接预览。 | Expand the file tree and click a map, YAML or CSV to preview it.
体验示例赛道 | Try sample track
地图坐标 · 单位：米 | Map coordinates · meters
拖动平移 / 滚轮缩放 | Drag to pan / scroll to zoom
曲率检查 | Curvature check
计算完成后显示沿路径的曲率 | Route curvature appears after calculation
沿路径的曲率与允许上限 | Route curvature and allowed limit
速度曲线 | Speed curve
生成后显示直道与弯道目标速度 | Target speeds for straights and turns appear after generation
沿路径的目标速度 | Target speed along route
连接 Jetson，从左侧文件树打开地图或 CSV。 | Connect to Jetson, then open a map or CSV from the file tree.
编辑栏目 | Edit panel
1. 点 | 1. Waypoints
2. 速度 | 2. Speed
① Waypoint 编辑 | ① Waypoint editing
编辑来源 | Edit source
生成的优化轨迹 | Generated optimized route
生成的中心线 | Generated centerline
当前预览的 CSV | Current CSV preview
编辑这条路线 | Edit this route
继续上次编辑 | Resume previous edit
Waypoint 总点数 | Total waypoints
弯道加密 | Turn density
0% · 等距 | 0% · Even spacing
等距分布 | Even spacing
弯道更密 | Denser in turns
总点数不变；向右让直道更疏、弯道更密。点击下方按钮应用，保留起点，可撤销。 | Keep the same total count; move right for fewer points on straights and more in turns. Apply below; the start point is preserved and changes can be undone.
按点数与分布重新生成 | Regenerate with count & distribution
减少点数会改变局部形状。 | Reducing point count can change local shape.
显示原赛道边界 | Show original track boundaries
框选多个点 | Box-select points
全选 | Select all
清除 | Clear
Ctrl 点击增减选点；Ctrl 拖动空白处框选。松开 Ctrl 后拖动选中点，整组一起移动。 | Ctrl-click to toggle points; Ctrl-drag blank canvas to box-select. Release Ctrl, then drag a selected point to move the group.
允许拖动已选 waypoint | Allow dragging selected waypoints
Ctrl 点击节点选中；普通拖动空白处平移。 | Ctrl-click to select a point; drag blank canvas to pan.
应用点坐标 | Apply point coordinates
撤销 | Undo
重做 | Redo
平滑强度 | Smoothing strength
轻微 | Light
标准 | Standard
较强 | Strong
平滑选中段 | Smooth selection
一键平滑整圈 | Smooth entire loop
保留点数，局部平滑不移动未选点。可撤销。 | Keep the point count; local smoothing leaves unselected points in place. Undo is available.
导出编辑后的 CSV | Export edited CSV
返回原路线 | Return to original route
修改只作用于编辑副本。编辑后需重新检查曲率和边界；导出不包含旧速度。 | Changes affect only the edit copy. Recheck curvature and boundaries afterward; exported CSV excludes old speeds.
下一步：设置速度 → | Next: Set speed →
② 速度编辑 | ② Speed editing
已选 0 点 | 0 points selected
Ctrl 点击赛道或曲线选点；Ctrl 拖动赛道空白处框选。速度选点独立保存。 | Ctrl-click the track or curve to select points; Ctrl-drag blank track space to box-select. Speed selection is saved separately.
最低速度 / m/s | Minimum speed / m/s
最高速度 / m/s | Maximum speed / m/s
加速度 / m/s² | Acceleration / m/s²
制动 / m/s² | Braking / m/s²
低摩擦系数 μ | Low friction coefficient μ
高摩擦系数 μ | High friction coefficient μ
重新计算整圈速度 | Recalculate loop speed
曲率限速 → 闭环加速 / 制动。修改路径后自动重算速度。 | Curvature speed limit → closed-loop acceleration / braking. Speed is recalculated when the route changes.
选中点 −5% | Selected points −5%
选中点 +5% | Selected points +5%
选中点速度比例倍率 | Selected-point speed ratio multiplier
应用倍率 ×1.00 | Apply multiplier ×1.00
设为低摩擦 | Set low friction
设为高摩擦 | Set high friction
撤销调速 | Undo speed edit
在速度栏目中选中节点，可批量调速或设置摩擦系数。手动调速不会重新施加动力学限制。 | Select points in the Speed tab to batch-edit speed or friction. Manual speed edits do not reapply dynamics limits.
MPPI 单侧宽度 / m（导出常量） | MPPI half-width / m (export constant)
Pure Pursuit：0–1 比例＋μ；MPPI：m/s＋μ。默认参数沿用案例，请按车辆设置。 | Pure Pursuit: 0–1 ratio + μ; MPPI: m/s + μ. Default parameters follow the example; adjust for your vehicle.
下一步：检查与保存 → | Next: Check & save →
文件信息 | File information
从左侧打开地图或路线。 | Open a map or route from the left.
移除叠加地图 | Remove map overlay
返回规划结果 | Return to planning result
正在连接 Jetson… | Connecting to Jetson…
已取消连接。 | Connection cancelled.
请等待当前计算完成。 | Wait for the current calculation.
没有地图或路线文件 | No map or route files
连接 Jetson 后显示文件树。 | Connect to Jetson to see the file tree.
展开文件夹 · 单击预览 | Expand folders · click to preview
单击文件预览；展开文件夹浏览下一级。 | Click a file to preview; expand folders to browse deeper.
已断开。当前预览保留在本机。 | Disconnected. The current preview remains local.
已忘记当前登录信息。 | Saved login details removed.
请先连接 Jetson。 | Connect to Jetson first.
请等待计算完成。 | Wait for the calculation to finish.
尚无所选规划结果。文件预览不会生成新的 CSV。 | No selected planning result. Previewing a file does not generate a new CSV.
请填写目标文件路径。 | Enter a destination file path.
请等待当前计算或保存完成。 | Wait for the current calculation or save.
请先生成所选路线，或打开至少 12 个点的 CSV。 | Generate the selected route or open a CSV with at least 12 points.
当前路线超过 5000 点，请先减小输入文件或调整生成间距。 | This route exceeds 5,000 points. Reduce the input or adjust generation spacing.
重新从所选原路线开始？当前未导出的编辑副本会被替换。 | Restart from the selected original route? The unexported edit copy will be replaced.
地图尚未加载成功，请稍后再进入编辑。 | The map has not loaded yet. Try editing again shortly.
按住 Ctrl 点击选点或取消；Ctrl 拖动空白处框选。 | Hold Ctrl and click to select or deselect points; Ctrl-drag blank canvas to box-select.
已打开编辑副本。Ctrl 点击选点，松开 Ctrl 后拖动选中点。 | Edit copy opened. Ctrl-click to select, then release Ctrl and drag a selected point.
已恢复空白处拖动平移。 | Blank-canvas dragging now pans again.
已恢复上次编辑副本。 | Previous edit copy restored.
请输入有效的 X/Y 坐标。 | Enter valid X/Y coordinates.
已按当前节点坐标移动所选节点。 | Selected points moved using the current point coordinates.
已撤销。 | Undone.
已重做。 | Redone.
0% · 等距（待应用） | 0% · Even spacing (pending)
请输入 12–5000 的整数点数。 | Enter an integer point count from 12 to 5,000.
请至少选中三个节点，或使用“平滑整圈”。 | Select at least three points or smooth the entire loop.
整圈已平滑，点数不变，可撤销。 | Entire loop smoothed; point count unchanged. Undo is available.
所选节点已平滑，未选节点保持不变，可撤销。 | Selected points smoothed; unselected points unchanged. Undo is available.
地图图片无法显示。 | Map image could not be displayed.
路线坐标 / 米 | Route coordinates / m
地图坐标 / 米 | Map coordinates / m
图片 / 像素 | Image / pixels
图像大小 | Image size
分辨率 | Resolution
地图原点 | Map origin
地图缺少 YAML，当前仅显示米制路线。打开对应 YAML 后可叠加。 | Map YAML is missing. Only the route in meters is shown. Open matching YAML to overlay the map.
图片预览 · 像素坐标 | Image preview · pixel coordinates
原图预览 · 像素坐标 | Original image preview · pixel coordinates
仅显示路线与边界 | Show route and boundaries only
按地图坐标叠加 | Overlay using map coordinates
未载入带坐标的背景图 | No georeferenced background loaded
原始图片预览 · 切回“当前地图”继续编辑路线 | Original image preview · switch to Current map to resume route editing
CSV 没有数据。 | CSV contains no data.
CSV 没有坐标行。 | CSV contains no coordinate rows.
两列坐标 | Two coordinate columns
按表头 · 实际速度 m/s | Header-based · actual speed m/s
中心线与宽度 | Centerline and widths
按坐标表头 | Coordinate headers
Pure Pursuit · 速度比例 | Pure Pursuit · speed ratio
CSV 列含义不明确，请选择列排列后再导入。 | CSV columns are ambiguous. Choose a column layout before importing.
坐标不是有效数字，请检查列排列。 | Coordinates are not valid numbers. Check the column layout.
保存本组设置 | Save these settings
已恢复本机保存的设置。 | Locally saved settings restored.
本组设置已保存到当前浏览器。 | These settings were saved in this browser.
浏览器不允许保存；本次设置仍然有效。 | Browser storage is unavailable; current settings remain active.
编辑副本 | Edit copy
预览 CSV | CSV preview
优化轨迹 | Optimized route
速度参数或路径无效，请修改后重算 | Invalid speed parameters or route; edit and recalculate
正在计算当前路径速度… | Calculating speed for the current route…
打开路线后显示速度曲线 | Open a route to see its speed curve
速度 / m/s | Speed / m/s
请先在速度栏目中 Ctrl 选中节点。 | Ctrl-select points in the Speed tab first.
请等待当前路径的速度计算完成。 | Wait for the current route speed calculation.
路径或速度已改变，请重新导出。 | Route or speed changed; export again.
未打开路线 | No route open
打开文件 | Open file
选择路线 | Choose route
检查与保存 | Check & save
设置速度 | Set speed
编辑点位 | Edit waypoints
速度已更新 · 手动调整 | Speed updated · manually edited
速度已更新 | Speed updated
速度重算中 | Recalculating speed
速度未就绪 | Speed not ready
无路线 | No route
通用 CSV · m/s | General CSV · m/s
Pure Pursuit · 0–1 比例＋μ | Pure Pursuit · 0–1 ratio + μ
尚无编辑副本 | No edit copy
几何 CSV · 不含速度 | Geometry CSV · no speed
文件已生成 | File generated
请先生成 / 导出对应文件 | Generate / export the corresponding file first
请求失败 | Request failed
正在计算… | Calculating…
计算 | Calculate\u0020
载入示例… | Loading sample…
已载入内置合成赛道。可调整车辆参数，选择算法后计算路线。 | Sample track loaded. Adjust vehicle parameters, choose an algorithm, then calculate a route.
中心线已就绪 | Centerline ready
中心线 PNG | Centerline PNG
可开始优化 | Ready to optimize
原始地图约束 | Original map constraints
CSV 走廊约束 | CSV corridor constraints
保存路径已复制。 | Save path copied.
请按 ⌘C / Ctrl+C 复制选中的路径。 | Press ⌘C / Ctrl+C to copy the selected path.
请完整填写有效的车辆参数与运行截止条件，再开始计算。 | Enter valid vehicle parameters and stopping conditions before calculating.
当前模型需要后轴中心坐标。请先确认车辆跟踪点。 | The current model requires rear-axle-center coordinates. Confirm the vehicle tracking point.
正在导入… | Importing…
正在读取地图并生成中心线… | Reading map and generating centerline…
中心线已生成并保存。下一步：填写车辆参数，再计算路线。 | Centerline generated and saved. Next, enter vehicle parameters and calculate a route.
路线已就绪，可生成速度表 | Route ready; generate a speed table
提前停止 · 加密检查通过 | Stopped early · dense checks passed
已收敛 · 加密检查通过 | Converged · dense checks passed
曲率不超过填写的转向上限 | Curvature within the entered steering limit
整车包络＋余量检查通过 | Vehicle envelope and margin checks passed
闭环连续，无自交 | Closed loop is continuous, with no self-intersection
求解器正常收敛 | Solver converged normally
路线计算完成。可在右栏调整速度，并在左栏导出或保存到 Jetson。 | Route calculated. Adjust speed on the right; export or save to Jetson on the left.
优化中 | Optimizing
计算中… | Calculating…
正在根据车辆转向能力、尺寸与赛道边界求解… | Solving with vehicle steering, dimensions and track boundaries…
本次计算未通过 | Calculation did not pass
保留上次通过的结果 | Keeping last valid result
未生成可行路线 | No feasible route generated
参数已改变 | Parameters changed
参数已改变。画布和导出按钮仍对应上次成功结果，请重新计算以应用新参数。 | Parameters changed. The canvas and export buttons still show the last valid result; recalculate to apply the new values.
最小曲率行车线 | Minimum-curvature path
最小化整圈 ∮κ² ds，以实际弧长加权；允许路线变长，不保证最大曲率或圈时最小。 | Minimize ∮κ² ds over the loop, weighted by arc length. The route may grow longer; this does not guarantee minimum peak curvature or lap time.
已选择 | Selected\u0020
。请计算新路线；之前保存的文件仍在原输出目录。 | . Calculate a new route; previously saved files remain in the original output folder.
Ctrl 点击增减选点；Ctrl 拖动空白处框选。松开 Ctrl 后双击画布空白处，或按 Esc，清除当前选择。 | Ctrl-click to toggle points; Ctrl-drag blank canvas to box-select. Release Ctrl and double-click blank canvas, or press Esc, to clear selection.
取消选择：松开 Ctrl，双击画布空白处 / Esc | Clear selection: release Ctrl and double-click blank canvas / Esc
首次连接 | First connection to
，请核对主机指纹： | . Check the host fingerprint:
信任此主机？ | Trust this host?
用已生成的规划结果覆盖文件？ | Overwrite this file with the generated planning result?
将先自动备份旧文件。 | The old file will be backed up first.
上限 | Limit
比例 | Ratio
示例 · Harbor Loop | Sample · Harbor Loop
内置合成赛道，不代表真实车辆能力。 | Built-in synthetic track; it does not represent the real vehicle's capabilities.
已按 YAML 分辨率及原点加载地图。 | Map loaded using YAML resolution and origin.
图片预览（像素坐标）。同名 YAML 可提供米制坐标。 | Image preview in pixels. Matching YAML can provide meter coordinates.
已自动匹配同名 YAML，按米制坐标显示。 | Matching YAML found; displayed in meter coordinates.
同名 YAML 指向另一张图片，保持像素预览。 | Matching YAML points to a different image; keeping pixel preview.
同名 YAML 无法加载，保持像素预览。 | Matching YAML could not be loaded; keeping pixel preview.
请选择 CSV/TXT、地图图片或地图 YAML。 | Choose a CSV/TXT file, map image or map YAML.
路线预览；未进行闭环、宽度或可行性检查。 | Route preview; loop, width and feasibility have not been checked.
无法预览路线。请检查 CSV 列格式及有效的 x/y 坐标（2–100000 点）。 | Cannot preview route. Check CSV columns and valid x/y coordinates (2–100,000 points).
Waypoint 坐标必须是有效数字。 | Waypoint coordinates must be valid numbers.
需要 12–5000 个有限的 x/y 坐标。 | Provide 12–5,000 finite x/y coordinates.
相邻点不能重合；闭环无需重复首点。 | Adjacent points cannot overlap; do not repeat the first point to close the loop.
Waypoint 个数必须是 12–5000 的整数。 | Waypoint count must be an integer from 12 to 5,000.
弯道加密强度必须在 0–1 之间。 | Turn-density strength must be between 0 and 1.
局部平滑需要至少选中三个有效节点。 | Local smoothing requires at least three valid selected points.
速度参数必须为有效数字。 | Speed parameters must be valid numbers.
速度、加减速及摩擦系数必须为正数，最小值不能大于最大值。 | Speed, acceleration, braking and friction must be positive; minimum cannot exceed maximum.
仅允许本机访问。 | Local access only.
请通过本地网页操作。 | Use the local web page.
不允许跨站请求。 | Cross-site requests are not allowed.
处理失败，请检查输入文件。详细信息见运行终端。 | Processing failed. Check the input file; details are in the terminal.
CSV 文件为空。 | CSV file is empty.
CSV 没有数值数据。 | CSV contains no numeric data.
CSV 至少需要两列有限数值。 | CSV needs at least two columns of finite numbers.
地图太大，请先缩小至 6000 像素以内并更新分辨率。 | Map is too large. Reduce it below 6,000 pixels and update the resolution.
没有找到封闭的环形赛道。请检查墙壁缺口、未知区域；也可改用有序 CSV 指定路线。 | No closed loop track found. Check wall gaps and unknown areas, or provide an ordered route CSV.
未知路线算法。 | Unknown route algorithm.
正在打开 | Opening
已保存： | Saved:\u0020
备份： | Backup:\u0020
已选中 | Selected
当前文件 | Current file
显示方式 | Display mode
提示 | Note
CSV 格式 | CSV format
已打开编辑副本 | Edit copy opened
编辑副本 · 未重新验证 | Edit copy · not revalidated
Waypoint 编辑 · 待验证 | Waypoint edit · validation pending
闭环编辑副本 · 未重新验证 | Closed-loop edit copy · not revalidated
文件预览 | File preview
原规划路线 | Original planned route
已移动 | Moved
个节点，可撤销。 | nodes; undo is available.
个点。拖动其中一个点可整体移动。 | points. Drag one to move the whole group.
在空白处拖出矩形框选节点；拖动选中点可整体移动。 | Drag a rectangle on blank canvas to select points; drag a selected point to move the group.
已生成 | Generated
个 waypoint | waypoints
，保留起点，可撤销。 | ; start point preserved. Undo is available.
已导出 | Exported
个点。 | points.\u0020
注意：路径存在自交。 | Warning: route self-intersects.\u0020
可在“保存到 Jetson”选择编辑后的 CSV。 | Select the edited CSV under Save to Jetson.
所选节点 | Selected points
正在计算当前路径速度… | Calculating speed for the current route…
手动调速 | Manual speed edit
估算 | Estimated
已调整 | Adjusted
点的速度比例。手动调整可能超出加速、制动或抓地限制；重算整圈会覆盖手动比例。 | points' speed ratios. Manual edits may exceed acceleration, braking or grip limits; full recalculation overwrites them.
已设置 | Set
点的摩擦系数，并重新计算整圈速度。 | points' friction coefficients and recalculated full-loop speed.
应用倍率 × | Apply multiplier ×
保存对象： | Save source:\u0020
点数： | Points:\u0020
格式： | Format:\u0020
几何编辑尚未重新验证边界与曲率。 | Geometry edits have not been revalidated for boundaries or curvature.
原中心线 | Original centerline
原优化结果 | Original optimized result
曲率上限 | Curvature limit
路径 | Route
加密检查点 | dense check points
提前停止 | Stopped early
计算完成 | Calculation complete
已收敛 | Converged
选中 | Selected
个参考点 | reference points
已识别： | Detected:\u0020
行 | rows
坐标预览： | Coordinate preview:\u0020
导入规划后重新计算速度。 | Speed is recalculated after importing for planning.
此 CSV 有 | This CSV has
列且缺少明确坐标表头，请在高级导入设置中选择列排列。 | columns without clear coordinate headers. Choose a column layout in Advanced import settings.
速度规划需要至少三个有效的路线点及曲率。 | Speed planning needs at least three valid route points and curvature values.
闭环速度约束未收敛，请检查路线与参数。 | Closed-loop speed constraints did not converge. Check the route and parameters.
达到最大求解时间 | Maximum solve time reached:
第 | Round
次迭代 | iterations
已用 | elapsed
秒 | s
正在生成粗网格初值（计入求解时限） | Generating coarse-grid seed (included in solve time)
优化中 | Optimizing
阶段一：修复可行性 | Stage 1: Repair feasibility
加密约束检查 | dense constraint check
本轮求解结束 | This solve round ended
正在进行加密约束检查… | Running dense constraint checks…
求解器未确认收敛，不代表最优解。 | Solver convergence is unconfirmed; this does not imply an optimal solution.
已保存通过约束检查的可行路线 | Saved a feasible route that passed constraint checks
路线 / CSV | Routes / CSV
地图 / MAPS | Maps / MAPS
路径配置必须是 JSON 对象。 | Path configuration must be a JSON object.
请填写有效的 Jetson 目录。 | Enter a valid Jetson directory.
SSH 端口无效。 | Invalid SSH port.
请填写主机地址、用户名及有效端口。 | Enter a host address, username and valid port.
首次连接请填写密码。 | Enter a password for the first connection.
首次连接：请核对并信任主机指纹。 | First connection: verify and trust the host fingerprint.
SSH 未连接，请先连接 Jetson。 | SSH is disconnected. Connect to Jetson first.
远程路径无效。 | Invalid remote path.
请选择不超过 40 MB 的普通文件。 | Select a regular file no larger than 40 MB.
文件超过 40 MB。 | File exceeds 40 MB.
文件为空或超过 40 MB。 | File is empty or exceeds 40 MB.
只能覆盖普通文件，不能覆盖目录或符号链接。 | Only regular files can be overwritten, not folders or symbolic links.
目标文件已存在或发生变化，请确认覆盖。 | Destination exists or has changed. Confirm overwrite.
原文件已被删除，请刷新后另存。 | Original file was deleted. Refresh and save elsewhere.
写入期间文件发生变化，已取消覆盖。 | File changed during writing; overwrite cancelled.
请检查 remote_paths.json 的格式和读取路径。 | Check the format and browse paths in remote_paths.json.
主机指纹已改变，请核实 Jetson 身份后再连接。 | Host fingerprint changed. Verify the Jetson identity before reconnecting.
SSH 登录失败，请检查用户名和密码。 | SSH login failed. Check username and password.
SSH/SFTP 操作失败：请检查网络、远程路径、权限及 SFTP 服务。 | SSH/SFTP failed. Check network, remote path, permissions and SFTP service.
连接设置失败，请检查 macOS 钥匙串是否允许此 Python 程序访问。 | Connection setup failed. Check whether macOS Keychain allows this Python process access.
目录超过 2000 项，请输入更具体的目录。 | Folder has over 2,000 items. Enter a more specific path.
请选择 CSV/TXT waypoint 或地图图片/YAML。 | Choose CSV/TXT waypoints or a map image/YAML.
本阶段仅写入 CSV/TXT waypoint。 | Only CSV/TXT waypoints can be written here.
请先选择已生成的 CSV 结果。 | Select a generated CSV result first.
本地结果不存在或过大。 | Local result is missing or too large.
参考路径自交。请提供一条按顺序排列、不自交的闭合赛道。 | Reference route self-intersects. Provide an ordered closed track without crossings.
已选择 YAML，还需要选择它对应的地图图片。 | You selected YAML; also choose its matching map image.
未知的 CSV 边界来源。 | Unknown CSV boundary source.
地图图片太大，请缩小至 6000 像素以内。 | Map image is too large. Reduce it below 6,000 pixels.
无法读取地图图片。 | Cannot read map image.
未提供 YAML：PNG 仅作原图参考，不参与地图边界校验或米制坐标叠加。 | No YAML was provided. The PNG is only a visual reference and cannot be used for boundary checks or meter-coordinate overlays.
仅从 SLAM 地图提取中心线需要地图图片和 YAML，以确定米制比例与原点。 | Extracting a centerline from a SLAM map requires a map image and YAML for scale and origin.
默认逆时针；宽度射线仅限制搜索范围，不连接成虚构墙壁。仅支持单一封闭赛道。 | Default direction is counterclockwise. Width rays limit search only and are not joined into artificial walls. Only one closed track is supported.
请选择中心线 CSV 文件。 | Choose a centerline CSV file.
CSV 参考线与原始地图不对齐或净空不足，请检查 resolution、origin 和 CSV 坐标；不会自动平移路线。 | CSV reference route is misaligned with the map or lacks clearance. Check resolution, origin and CSV coordinates; the route is not shifted automatically.
保留 CSV 路线形状，仅按弧长重采样；边界以原始地图为准，CSV 自带宽度不作为障碍边界。 | CSV route shape is preserved and resampled by arc length. The original map defines boundaries; CSV widths are not treated as walls.
使用手动填写的统一宽度。结果只针对该假定走廊，未检查真实墙壁。 | Using manually entered uniform width. Results apply to that assumed corridor; real walls have not been checked.
仅检查 CSV 给出的赛道宽度；没有使用图片像素验证墙壁。 | Only CSV track widths were checked; image pixels were not used to validate walls.
保留 CSV 路线形状；同时检查所选 CSV 宽度约束与原始地图净空。 | CSV route shape is preserved. Both selected CSV width constraints and original-map clearance are checked.
未知导入方式。 | Unknown import method.
请重新导入地图，原会话可能已过期。 | Reimport the map; the previous session may have expired.
已有一项计算正在运行，请等待它完成。 | A calculation is already running. Wait for it to finish.
正在准备约束… | Preparing constraints…
计算失败，详细信息见终端。中心线仍可导出。 | Calculation failed; see terminal for details. The centerline can still be exported.
请先导入地图或计算路线。 | Import a map or calculate a route first.
计算任务不存在，请重新导入。 | Calculation job is missing. Reimport the track.
无效结果目录。 | Invalid result folder.
文件不存在。 | File does not exist.`;
  const entries = rows.split('\n').map(line => {
    const at = line.indexOf(' | ');
    return [line.slice(0, at), line.slice(at + 3)];
  });
  const exact = new Map(entries);
  const fragments = [...entries].filter(([key]) => key.length > 1 && !/^\d/.test(key)).sort((a, b) => b[0].length - a[0].length);
  const textState = new WeakMap();
  const attributeState = new WeakMap();
  let current = localStorage.getItem('raceline-language') === 'en' ? 'en' : 'zh';
  let scheduled = false;

  function translate(source) {
    if (current === 'zh' || !/[\u3400-\u9fff]/.test(source)) return source;
    if (exact.has(source)) return exact.get(source);
    // Dynamic captions and messages retain numbers, file names and paths.
    const dynamic = [
      [/^已按实际速度调整 (\d+) 个选中点，并限制在最低与最高速度之间。连续点击会累乘；未选点不变。$/, m => `Scaled the actual speeds of ${m[1]} selected points, clamped to minimum and maximum speed. Repeated clicks compound; unselected points are unchanged.`],
      [/^已调整 (\d+) 点的速度比例。手动调整可能超出加速、制动或抓地限制；重算整圈会覆盖手动比例。$/, m => `Adjusted speed ratios for ${m[1]} points. Manual changes may exceed acceleration, braking or grip limits; recalculating the loop overwrites manual ratios.`],
      [/^已设置 (\d+) 点的摩擦系数，并重新计算整圈速度。$/, m => `Set friction for ${m[1]} points and recalculated full-loop speed.`],
      [/^已选中 (\d+) 个点。拖动其中一个点可整体移动。$/, m => `${m[1]} points selected. Drag one to move the whole group.`],
      [/^已移动 (\d+) 个节点，可撤销。$/, m => `Moved ${m[1]} points. Undo is available.`],
      [/^已选 (\d+) 点 · 当前 (\d+) \/ (\d+)$/, m => `${m[1]} points selected · current ${m[2]} / ${m[3]}`],
      [/^已生成 (\d+) 个 waypoint · 弯道加密 (\d+)%[，]?保留起点，可撤销。$/, m => `Generated ${m[1]} waypoints · denser turns ${m[2]}%. Start point preserved; undo is available.`],
      [/^已生成 (\d+) 个 waypoint · 等距分布，保留起点，可撤销。$/, m => `Generated ${m[1]} waypoints with even spacing. Start point preserved; undo is available.`],
      [/^已导出 (\d+) 个点。(注意：路径存在自交。)?可在“保存到 Jetson”选择编辑后的 CSV。$/, m => `Exported ${m[1]} points. ${m[2] ? 'Warning: route self-intersects. ' : ''}Select the edited CSV under Save to Jetson.`],
      [/^此 CSV 有 (\d+) 列且缺少明确坐标表头，请在高级导入设置中选择列排列。$/, m => `This CSV has ${m[1]} columns without clear coordinate headers. Choose a column layout in Advanced import settings.`]
    ];
    for (const [pattern, render] of dynamic) {
      const match = source.match(pattern);
      if (match) return render(match);
    }
    let result = source
      .replace(/已选 (\d+) 点/g, '$1 points selected')
      .replace(/(\d+) 个 (waypoints?|参考点|节点|点)/g, (_, n, noun) => `${n} ${noun === '参考点' ? 'reference points' : noun === '节点' ? 'nodes' : 'points'}`)
      .replace(/(\d+) 点/g, '$1 points')
      .replace(/(\d+)% · 待应用/g, '$1% · Pending')
      .replace(/(\d+)% · 已应用/g, '$1% · Applied')
      .replace(/(\d+)% · 等距/g, '$1% · Even spacing')
      .replace(/(\d+) 行/g, '$1 rows');
    for (const [key, value] of fragments) result = result.split(key).join(value);
    return result;
  }
  function syncText(node) {
    const before = node.nodeValue;
    if (!before.trim()) return;
    let state = textState.get(node);
    if (!state || state.display !== before) state = { source: before, display: before };
    const next = translate(state.source);
    textState.set(node, { source: state.source, display: next });
    if (before !== next) node.nodeValue = next;
  }
  function syncAttributes(element) {
    let states = attributeState.get(element);
    if (!states) { states = new Map(); attributeState.set(element, states); }
    for (const name of ['placeholder', 'title', 'aria-label']) {
      if (!element.hasAttribute(name)) continue;
      const before = element.getAttribute(name);
      let state = states.get(name);
      if (!state || state.display !== before) state = { source: before, display: before };
      const next = translate(state.source);
      states.set(name, { source: state.source, display: next });
      if (before !== next) element.setAttribute(name, next);
    }
  }
  function sync(root = document.body) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) { syncText(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    syncAttributes(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      if (walker.currentNode.nodeType === Node.TEXT_NODE) {
        if (!walker.currentNode.parentElement?.closest('.file-name, [data-no-translate]')) syncText(walker.currentNode);
      }
      else syncAttributes(walker.currentNode);
    }
    document.documentElement.lang = current === 'en' ? 'en' : 'zh-CN';
    document.title = current === 'en' ? 'Raceline Studio · Remote Track Workspace' : 'Raceline Studio · 远程赛道工作台';
    const button = document.getElementById('languageToggle');
    if (button) {
      const label = current === 'en' ? '中文' : 'English';
      const description = current === 'en' ? 'Switch to Chinese' : 'Switch to English';
      if (button.textContent !== label) button.textContent = label;
      if (button.title !== description) button.title = description;
      if (button.getAttribute('aria-label') !== description) button.setAttribute('aria-label', description);
    }
  }
  function setLanguage(language) {
    current = language === 'en' ? 'en' : 'zh';
    localStorage.setItem('raceline-language', current);
    sync();
    if (typeof window.draw === 'function') window.draw();
    if (typeof window.drawCurve === 'function') window.drawCurve();
    if (typeof window.drawSpeed === 'function') window.drawSpeed();
    window.dispatchEvent(new CustomEvent('raceline-language-change', { detail: { language: current } }));
  }
  window.i18n = { t: translate, language: () => current, setLanguage, confirm: message => window.confirm(translate(message)) };
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('languageToggle').onclick = () => setLanguage(current === 'en' ? 'zh' : 'en');
    sync();
    new MutationObserver(() => {
      if (scheduled) return;
      scheduled = true;
      queueMicrotask(() => { scheduled = false; sync(); });
    }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['placeholder', 'title', 'aria-label'] });
  });
})();
