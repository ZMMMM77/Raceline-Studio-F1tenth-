# 速度系统

算法对照 https://github.com/cedrichld/raceline_UI_f1tenth 中的 profile_velocity：
Menger 曲率绝对值、长度 max(3,N//10) 的周期均值滤波、sqrt(μ*9.81/κ) 限速、两圈前向加速和两圈后向制动；比例 r=(v-v_min)/(v_max-v_min)。保持现有路线生成算法。

右侧参数默认采用案例 UI：v_min=1.5、v_max=7.6、a_max=6、a_brake=8、低 μ=0.41、高 μ=0.70。用户应按车设置。选中点 ±5% 或倍率调整的是 r，随后 v=v_min+r*(v_max-v_min)，手动比例不自动施加动力学限制。修改坐标/点数/速度参数会重算并覆盖手动速度。局部摩擦设置后重算整圈。重采样按节点相对顺序迁移摩擦分布。撤销调速独立于坐标撤销。

曲线和赛道按固定 0–1 速度比例使用案例配色：红→黄→绿→青绿，不按当前路线极值重新拉伸，鼠标悬停曲线显示点序号、m/s、比例和 μ。原赛道边界独立保留。

左栏：规划与导入、计算结果与导出、保存到 Jetson。
- Pure Pursuit CSV：x,y,yaw,speed_ratio,friction（逗号，比例0–1）。
- MPPI CSV：s_m;x_m;y_m;psi_rad;kappa_radpm;vx_mps;ax_mps2;w_tr_right_m;w_tr_left_m;friction（分号，真实m/s）。宽度使用右栏显式填写的单侧常量。
- 通用速度 CSV：x_m,y_m,vx_mps,s_m,psi_rad,kappa_radpm,ax_mps2。
- CSV metadata 保存速度参数；从 Jetson 打开带表头的上述格式会恢复速度/摩擦。无表头请选择明确的 Pure Pursuit / MPPI 预览格式。导入规划仍按原逻辑重新采样、重新规划速度。
- 编辑后的几何 CSV 仍可单独导出，不含速度。

导出和 Jetson 保存始终针对当前显示的路线（编辑副本 / CSV 预览 / 优化轨迹 / 中心线）。路径或速度变化会作废缓存，待当前速度计算完成后再导出。速度导出保存为独立结果目录，不更改已有几何结果；源程序仍在原安装目录更新。

新 API /api/velocity/profile 和 /api/velocity/export 使用相同核心。旧 /api/speed-profile 保留请求格式兼容层，计算已切换至新核心。当前速度模型不做赛道可行性验证，几何编辑后的原边界检查状态仍为待验证。

界面采用三栏工作流 A：右栏先 Waypoint 再速度，顶部标记当前阶段及路线；左栏三个操作组统一样式，Jetson 保存区列出真实来源、点数、格式及速度状态。速度绘图区高度缩小20%，主赛道画布尺寸保持不变。
