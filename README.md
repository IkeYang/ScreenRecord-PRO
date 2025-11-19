# 开源免费的屏幕录制专家 🎥🖱️⌨️

一款轻量、易用、跨屏幕的屏幕与键鼠同步录制工具。支持将屏幕录制为 AVI 视频，并以 JSON 结构化保存键盘/鼠标事件（含归一化坐标和时间戳）。既有简洁 GUI，也有强大 CLI，适合测试复现、教学演示、UX 分析与自动化数据采集等场景。

<p align="center">
  <b>免费开源 · 多屏支持 · 低门槛 · 录制与回放键鼠脚本</b>
  <br/>
  <sub>Built with PySide6 · MSS · OpenCV · keyboard/mouse</sub>
  <br/>
</p>

---

## ✨ 功能亮点
- 🖥️ 多屏检测与选择：列出所有显示器，按需选择录制目标
- 🎬 屏幕录制到 AVI：默认 XVID 编码（失败自动回退 MJPG），25 FPS 流畅输出
- 🖱️ 键鼠事件采集：移动/点击/滚轮与键盘按下/抬起，全量记录
- 📐 坐标归一化：事件坐标相对当前屏幕宽高转为 [0,1] 范围，便于回放/脚本生成
- ⌨️ 模式丰富：手动控制、全局热键（Ctrl+Shift+F10）、定时自动停止
- 🧭 托盘状态与快捷菜单：录制指示、快速开始/停止、显示窗口、退出
- 🗂️ 时间戳命名与路径记忆：按 `YYYY-MM-DD_HH-MM-SS` 自动命名，记住上次保存目录
- 🧰 双形态使用：图形界面（PySide6）与命令行（argparse）随心选
- 🔁 键鼠脚本回放：基于 JSON 自动回放操作，支持设置延迟、倍速和双 Esc 中断

---

## 🚀 快速开始

### 1) 安装依赖（推荐虚拟环境/conda 环境）
```
pip install -r requirements.txt
```

### 2) 启动 GUI
```
python run_gui.py
```
- 选择屏幕与保存目录（需已存在且可写）
- 选择模式：手动 / 热键（Ctrl+Shift+F10） / 定时（秒）
- 点击“开始录制 / 停止录制”，或在热键模式下直接使用热键

### 3) 使用 CLI
- 列出屏幕：
```
python main.py --list
```
- 录制屏幕 1，保存到 output 目录并录制 60s（可选设置画质与 FPS）：
```
python main.py --screen 1 --outdir ./output --duration 60 --fps 25 --quality high
```
- 输出文件：`YYYY-MM-DD_HH-MM-SS.avi` 和同名 `JSON` 事件文件

### 4) 回放已录制的键鼠脚本
- GUI 回放：在主界面中选择“回放脚本 JSON”、设置“延迟回放（秒）”，点击“开始回放”，可在几秒后自动回放录制时的键鼠操作；连续按下两次 Esc 可中断回放。
- CLI 回放（可选）：
```
python replay.py ./output/2023-10-27_15-30-00.json --speed 1.0 --delay 3 --esc-stop
```
- 支持 `--speed` 控制播放速度，`--delay` 设置开始前延迟秒数，`--dry-run` 仅打印事件而不真正发送键鼠输入。

---

## 🧱 平台与依赖
- Python 3.12（其他版本可能兼容，未系统测试）
- GUI：PySide6（Qt）
- 屏幕采集：mss + OpenCV（写入 AVI）
- 键盘监听：keyboard · 鼠标监听：mouse

### Linux 额外依赖（Qt xcb）
若运行 GUI 提示 “Qt 平台插件 xcb 无法加载”，请安装以下系统包（Ubuntu/Debian）：
```
sudo apt-get update
sudo apt-get install -y \
  libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-keysyms1 \
  libxcb-image0 libxcb-render-util0 libxkbcommon-x11-0
```
若报错引用了 `cv2` 的 Qt 插件路径，可尝试：
- 卸载 GUI 版 OpenCV，改用无 GUI 的版本（避免 Qt 插件冲突）：
  ```
  pip uninstall -y opencv-python && pip install opencv-python-headless
  ```
- 直接运行 `python run_gui.py`（项目已清理冲突的 Qt 插件环境变量并固定 PySide6 插件路径）

---

## 🗃️ 事件数据格式（JSON）
- 文件结构：
```json
{
  "meta": {
    "screen": {"left": 0, "top": 0, "width": 1920, "height": 1080},
    "fps": 25,
    "started_at": "2023-10-27_15-30-00"
  },
  "events": [
    {
      "timestamp": 1666888888.12345,
      "t_rel": 0.532,
      "type": "mouse_click",
      "event": "press",
      "pos_x_norm": 0.525,
      "pos_y_norm": 0.813,
      "button": "Button.left"
    }
  ]
}
```
- 事件类型：`mouse_move` / `mouse_click` / `mouse_scroll` / `key_press` / `key_release`
- 鼠标事件包含 `pos_x_norm`、`pos_y_norm`；滚轮包含 `scroll_dx`、`scroll_dy`
- `timestamp` 为 Unix 时间戳；`t_rel` 为相对录制起点秒数

---

## 🧭 路线图
- [x] M1：CLI 原型（屏幕录制、键鼠记录、归一化、落盘）
- [x] M2：GUI（屏幕/路径选择、开始/停止、状态）
- [x] M3：热键模式、定时模式、托盘指示
- [ ] 更多编码器与参数可选（如自定义 fourcc/fps）
- [ ] 自定义热键、快捷键冲突检测
- [ ] 录制区域裁剪、捕获光标样式、点击高亮
- [ ] 一键导出 Demo/回放脚本

---

## 🤝 参与贡献
- 欢迎提交 Issue/PR，一起完善功能与体验！
- 建议：基于 feature 分支提交，遵循清晰的提交说明；附带复现步骤或截图更佳。

---

## 🙏 致谢
- [mss](https://github.com/BoboTiG/python-mss) · 高性能多平台屏幕抓取
- [OpenCV](https://opencv.org/) · 视频编码写入
- [keyboard](https://github.com/boppreh/keyboard) · 键盘全局监听
- [mouse](https://github.com/boppreh/mouse) · 鼠标全局监听
- [PySide6](https://wiki.qt.io/Qt_for_Python) · 现代化跨平台 GUI

如果这个项目对你有帮助，欢迎 Star 支持！⭐
