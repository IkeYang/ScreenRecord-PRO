from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSystemTrayIcon,
    QMenu,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from screenrec.events import EventRecorder, MonitorGeom
from screenrec.video import ScreenCapture
from screenrec.replay import replay as replay_events


def timestamp_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Screen Recorder")

        self.settings = QSettings("ScreenRec", "Recorder")
        self.monitors = self._load_monitors()

        self.screen_combo = QComboBox()
        for i, mon in enumerate(self.monitors, start=1):
            self.screen_combo.addItem(
                f"屏幕 {i}: {mon['width']}x{mon['height']} (left={mon['left']} top={mon['top']})",
                userData=i,
            )
        if self.screen_combo.count() == 0:
            self.screen_combo.addItem("未检测到屏幕", userData=None)
            self.screen_combo.setEnabled(False)

        self.path_edit = QLineEdit()
        default_dir = self.settings.value("save_dir", str(Path.home()))
        self.path_edit.setText(str(default_dir))
        self.browse_btn = QPushButton("浏览…")
        self.browse_btn.clicked.connect(self.on_browse)

        # 录制模式
        self.mode_label = QLabel("录制模式：")
        self.rb_manual = QRadioButton("手动")
        self.rb_hotkey = QRadioButton("热键")
        self.rb_timed = QRadioButton("定时")
        self.rb_manual.setChecked(True)
        self.rb_manual.toggled.connect(self.on_mode_changed)
        self.rb_hotkey.toggled.connect(self.on_mode_changed)
        self.rb_timed.toggled.connect(self.on_mode_changed)

        self.hotkey_label = QLabel("热键：Ctrl+Shift+F10")
        self.hotkey_label.setVisible(False)
        self.duration_label = QLabel("定时时长（秒）：")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 24 * 3600)
        self.duration_spin.setValue(60)
        self.duration_label.setVisible(False)
        self.duration_spin.setVisible(False)

        # 画质 / FPS 设置
        self.fps_label = QLabel("FPS：")
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(5, 60)
        self.fps_spin.setValue(25)
        self.quality_label = QLabel("画质：")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("高（原始分辨率）", userData=1.0)
        self.quality_combo.addItem("中（0.75x）", userData=0.75)
        self.quality_combo.addItem("低（0.5x）", userData=0.5)

        self.status_label = QLabel("状态：空闲")
        self.toggle_btn = QPushButton("开始录制")
        self.toggle_btn.clicked.connect(self.on_toggle)

        # 回放脚本区域
        self.replay_path_edit = QLineEdit()
        self.replay_browse_btn = QPushButton("选择 JSON…")
        self.replay_browse_btn.clicked.connect(self.on_browse_replay)
        self.replay_delay_label = QLabel("延迟回放（秒）：")
        self.replay_delay_spin = QSpinBox()
        self.replay_delay_spin.setRange(0, 3600)
        self.replay_delay_spin.setValue(3)
        self.replay_btn = QPushButton("开始回放")
        self.replay_btn.clicked.connect(self.on_start_replay)

        form = QWidget()
        grid = QGridLayout()
        row = 0
        grid.addWidget(QLabel("屏幕选择："), row, 0)
        grid.addWidget(self.screen_combo, row, 1)
        row += 1
        grid.addWidget(QLabel("保存路径："), row, 0)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.browse_btn)
        grid.addLayout(path_row, row, 1)
        row += 1
        # 模式区域
        grid.addWidget(self.mode_label, row, 0)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.rb_manual)
        mode_row.addWidget(self.rb_hotkey)
        mode_row.addWidget(self.rb_timed)
        grid.addLayout(mode_row, row, 1)
        row += 1
        grid.addWidget(self.hotkey_label, row, 0, 1, 2)
        row += 1
        dur_row = QHBoxLayout()
        dur_row.addWidget(self.duration_label)
        dur_row.addWidget(self.duration_spin)
        grid.addLayout(dur_row, row, 0, 1, 2)
        row += 1
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.fps_label)
        quality_row.addWidget(self.fps_spin)
        quality_row.addWidget(self.quality_label)
        quality_row.addWidget(self.quality_combo)
        grid.addLayout(quality_row, row, 0, 1, 2)
        row += 1
        replay_path_row = QHBoxLayout()
        replay_path_row.addWidget(QLabel("回放脚本 JSON："))
        replay_path_row.addWidget(self.replay_path_edit)
        replay_path_row.addWidget(self.replay_browse_btn)
        grid.addLayout(replay_path_row, row, 0, 1, 2)
        row += 1
        replay_ctrl_row = QHBoxLayout()
        replay_ctrl_row.addWidget(self.replay_delay_label)
        replay_ctrl_row.addWidget(self.replay_delay_spin)
        replay_ctrl_row.addWidget(self.replay_btn)
        grid.addLayout(replay_ctrl_row, row, 0, 1, 2)
        row += 1
        grid.addWidget(self.status_label, row, 0, 1, 2)
        row += 1
        grid.addWidget(self.toggle_btn, row, 0, 1, 2)
        form.setLayout(grid)

        container = QWidget()
        v = QVBoxLayout()
        v.addWidget(form)
        container.setLayout(v)
        self.setCentralWidget(container)

        self._recording = False
        self._video: Optional[ScreenCapture] = None
        self._events: Optional[EventRecorder] = None
        self._video_path: Optional[str] = None
        self._json_path: Optional[str] = None
        self._geom: Optional[MonitorGeom] = None
        self._timer: Optional[QTimer] = None
        self._fps: int = 25

        self._replaying = False
        self._replay_thread: Optional[threading.Thread] = None

        # 托盘图标
        self._setup_tray()

        # 热键控制器（固定组合）
        self._hotkey_combo = "ctrl+shift+f10"
        self._hotkey_listener = None
        self._hotkey_supported = self._check_hotkey_available()
        if not self._hotkey_supported:
            self.rb_hotkey.setEnabled(False)
            self.hotkey_label.setText("热键：不可用（缺少 keyboard 库）")

    def _load_monitors(self) -> list[Dict[str, int]]:
        try:
            return ScreenCapture.list_monitors()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法获取屏幕信息：{e}")
            return []

    def on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录", self.path_edit.text())
        if directory:
            self.path_edit.setText(directory)
            self.settings.setValue("save_dir", directory)

    def on_browse_replay(self) -> None:
        start_dir = self.path_edit.text() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择回放脚本 JSON",
            start_dir,
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self.replay_path_edit.setText(path)

    def _selected_screen_index(self) -> int:
        data = self.screen_combo.currentData()
        if data is None:
            return -1
        return int(data)

    def _validate_dir(self, path: str) -> bool:
        if not os.path.isdir(path):
            QMessageBox.warning(self, "路径错误", "路径不存在，请先创建该文件夹。")
            return False
        if not os.access(path, os.W_OK):
            QMessageBox.warning(self, "权限错误", "路径不可写，请选择其他位置。")
            return False
        return True

    # 回放
    def on_start_replay(self) -> None:
        if self._recording:
            QMessageBox.warning(self, "无法回放", "录制进行中，无法开始回放。")
            return
        if self._replaying:
            QMessageBox.information(self, "正在回放", "当前已有回放任务在进行中。")
            return

        path = self.replay_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "无法回放", "请先选择要回放的 JSON 文件。")
            return
        if not os.path.isfile(path):
            QMessageBox.warning(self, "无法回放", "指定的 JSON 文件不存在。")
            return

        delay_secs = int(self.replay_delay_spin.value())
        self._replaying = True
        self.replay_btn.setEnabled(False)
        self.toggle_btn.setEnabled(False)
        self.status_label.setText(
            f"状态：将在 {delay_secs} 秒后开始回放（连续按两次 Esc 可中断）"
        )

        def _worker() -> None:
            try:
                replay_events(
                    path,
                    speed=1.0,
                    dry_run=False,
                    start_delay=float(delay_secs),
                    allow_esc_stop=True,
                )
            except SystemExit:
                # 依赖缺失等情况会通过 SystemExit 抛出，统一视为回放结束
                pass
            finally:
                QTimer.singleShot(0, self._on_replay_finished)

        self._replay_thread = threading.Thread(target=_worker, name="ReplayThread", daemon=True)
        self._replay_thread.start()

    def _on_replay_finished(self) -> None:
        self._replaying = False
        self._replay_thread = None
        self.replay_btn.setEnabled(True)
        self.toggle_btn.setEnabled(True)
        if not self._recording:
            self.status_label.setText("状态：空闲")

    def on_toggle(self) -> None:
        if self._replaying:
            QMessageBox.warning(self, "无法录制", "回放进行中，暂时无法开始录制。")
            return
        if not self._recording:
            self.start_recording()
        else:
            self.stop_recording()

    # 模式切换
    def _current_mode(self) -> str:
        if self.rb_timed.isChecked():
            return "timed"
        if self.rb_hotkey.isChecked():
            return "hotkey"
        return "manual"

    def on_mode_changed(self) -> None:
        mode = self._current_mode()
        self.hotkey_label.setVisible(mode == "hotkey")
        self.duration_label.setVisible(mode == "timed")
        self.duration_spin.setVisible(mode == "timed")
        # 启停热键监听
        if mode == "hotkey":
            self._enable_hotkey(True)
        else:
            self._enable_hotkey(False)

    def start_recording(self) -> None:
        if self.screen_combo.count() == 0 or not self.screen_combo.isEnabled():
            QMessageBox.warning(self, "无法录制", "未检测到可用屏幕。")
            return
        idx = self._selected_screen_index()
        if idx < 1 or idx > len(self.monitors):
            QMessageBox.warning(self, "无法录制", "屏幕索引无效。")
            return

        outdir = self.path_edit.text().strip()
        if not self._validate_dir(outdir):
            return

        mon = self.monitors[idx - 1]
        geom = MonitorGeom(
            left=int(mon["left"]),
            top=int(mon["top"]),
            width=int(mon["width"]),
            height=int(mon["height"]),
        )
        base = timestamp_name()
        video_path = os.path.join(outdir, f"{base}.avi")
        json_path = os.path.join(outdir, f"{base}.json")

        fps = int(self.fps_spin.value())
        quality_scale = float(self.quality_combo.currentData() or 1.0)
        self._fps = fps

        try:
            video = ScreenCapture(mon, video_path, fps=fps, scale=quality_scale)
            events = EventRecorder(geom)
            video.start()
            events.start()
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"无法开始录制：{e}")
            return

        self._recording = True
        self._video = video
        self._events = events
        self._video_path = video_path
        self._json_path = json_path
        self._geom = geom

        self.toggle_btn.setText("停止录制")
        self.screen_combo.setEnabled(False)
        self.path_edit.setEnabled(False)
        self.browse_btn.setEnabled(False)
        if self._current_mode() == "timed":
            secs = int(self.duration_spin.value())
            self._start_timer(secs)
            self.status_label.setText(f"状态：录制中…（将于 {secs} 秒后自动停止）")
        else:
            self.status_label.setText("状态：录制中…")

        self._update_tray_recording(True)

    def stop_recording(self) -> None:
        if not self._recording:
            return
        assert self._video is not None
        assert self._events is not None
        assert self._json_path is not None
        assert self._geom is not None

        # 停止定时器
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

        try:
            self._video.stop()
            self._events.stop()
        finally:
            data = {
                "meta": {
                    "screen": asdict(self._geom),
                    "fps": int(self._fps or 25),
                    "started_at": os.path.basename(self._video_path)[:-4] if self._video_path else "",
                },
                "events": self._events.snapshot(),
            }
            try:
                with open(self._json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"事件文件保存失败：{e}")

        self._recording = False
        self._video = None
        self._events = None
        saved_video = self._video_path or ""
        saved_json = self._json_path or ""
        self._video_path = None
        self._json_path = None
        self._geom = None

        self.toggle_btn.setText("开始录制")
        self.screen_combo.setEnabled(True)
        self.path_edit.setEnabled(True)
        self.browse_btn.setEnabled(True)
        if saved_video:
            self.status_label.setText(f"状态：已保存至 {saved_video}")
        else:
            self.status_label.setText("状态：空闲")
        self._update_tray_recording(False)

    # 定时器
    def _start_timer(self, secs: int) -> None:
        if self._timer is not None:
            self._timer.stop()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(1, secs) * 1000)
        self._timer.timeout.connect(self.stop_recording)
        self._timer.start()

    # 托盘图标
    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("Screen Recorder")
        menu = QMenu()
        self.action_show = QAction("显示窗口", self)
        self.action_toggle = QAction("开始录制", self)
        self.action_quit = QAction("退出", self)
        self.action_show.triggered.connect(self._tray_show)
        self.action_toggle.triggered.connect(self.on_toggle)
        self.action_quit.triggered.connect(self._tray_quit)
        menu.addAction(self.action_show)
        menu.addAction(self.action_toggle)
        menu.addSeparator()
        menu.addAction(self.action_quit)
        self.tray.setContextMenu(menu)
        self._update_tray_recording(False)
        self.tray.show()

    def _update_tray_recording(self, is_rec: bool) -> None:
        # Use SP_MediaStop while recording (toggle action is stop), SP_MediaPlay when idle
        icon = self.style().standardIcon(QStyle.SP_MediaStop if is_rec else QStyle.SP_MediaPlay)
        self.tray.setIcon(icon)
        self.tray.setToolTip("录制中" if is_rec else "空闲")
        self.action_toggle.setText("停止录制" if is_rec else "开始录制")
        if is_rec:
            try:
                self.tray.showMessage("屏幕录制", "正在录制…", QSystemTrayIcon.Information, 1500)
            except Exception:
                pass

    def _tray_show(self) -> None:
        self.showNormal()
        self.activateWindow()

    def _tray_quit(self) -> None:
        if self._recording:
            self.stop_recording()
        QApplication.instance().quit()

    # 热键
    def _check_hotkey_available(self) -> bool:
        try:
            import keyboard  # type: ignore[import]
            _ = keyboard.add_hotkey  # type: ignore[attr-defined]
            return True
        except Exception:
            return False

    def _enable_hotkey(self, enable: bool) -> None:
        # Start/stop global hotkey listener for toggle using `keyboard` library
        if not self._hotkey_supported:
            return
        try:
            import keyboard  # type: ignore[import]
        except Exception:
            return
        if enable and self._hotkey_listener is None:

            def _cb() -> None:
                # 由非 GUI 线程触发，使用 singleShot 切回主线程
                QTimer.singleShot(0, self._on_hotkey_triggered)

            handle = keyboard.add_hotkey(self._hotkey_combo, _cb)
            self._hotkey_listener = handle
        elif not enable and self._hotkey_listener is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_listener)
            except Exception:
                pass
            self._hotkey_listener = None

    def _on_hotkey_triggered(self) -> None:
        if self._current_mode() != "hotkey":
            return
        self.on_toggle()

    # 清理
    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self._enable_hotkey(False)
        except Exception:
            pass
        if self._recording:
            self.stop_recording()
        if self._replaying:
            # 回放线程为 daemon，直接退出应用即可
            self._replaying = False
        super().closeEvent(event)


def run() -> int:
    # Ensure Qt uses PySide6's own plugin directory to avoid interference
    try:
        from PySide6.QtCore import QLibraryInfo, QCoreApplication
        QCoreApplication.setLibraryPaths(
            [QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)]
        )
    except Exception:
        pass

    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.resize(700, 200)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
