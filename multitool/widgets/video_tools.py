# Copyright (C) 2026  Ali Qasem
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import json
import math
import os
import subprocess
import tempfile

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..helpers import find_ff_tool, get_default_output_dir, get_subprocess_kwargs
from .common import DualHandleSlider, ProgressBarMixin

class TrimExportWidget(QWidget, ProgressBarMixin):
    def __init__(self):
        super().__init__()
        self.input_file = ""
        self.duration_ms = 0
        self.video_fps = 0.0
        self.preview_start_ms = 0
        self.preview_end_ms = 0
        self.loop_preview = False

        layout = QVBoxLayout()

        self.video_widget = QVideoWidget()
        # Adjust this value to make the trim preview player taller/shorter.
        self.video_widget.setMinimumHeight(477)
        #self.video_widget.setMinimumWidth(220)
        layout.addWidget(self.video_widget)

        self.audio_output = QAudioOutput()
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setAudioOutput(self.audio_output)

        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(120)
        self.preview_timer.timeout.connect(self._on_preview_tick)

        file_row = QHBoxLayout()
        self.select_button = QPushButton("Select File")
        self.select_button.clicked.connect(self.select_file)
        file_row.addWidget(self.select_button)
        self.selected_name = QLabel("No file selected")
        file_row.addWidget(self.selected_name)
        layout.addLayout(file_row)

        self.duration_label = QLabel("Video length: 00:00:00")
        layout.addWidget(self.duration_label)

        self.range_title = QLabel("Trim Range (Dual Handle)")
        layout.addWidget(self.range_title)

        self.range_slider = DualHandleSlider()
        self.range_slider.rangeChanged.connect(self._on_range_changed)
        self.range_slider.handleDragged.connect(self._on_slider_dragged)
        layout.addWidget(self.range_slider)

        spin_row = QHBoxLayout()
        self.start_label = QLabel("Start (hh:mm:ss.mmm):")
        spin_row.addWidget(self.start_label)
        self.start_time_input = QLineEdit("00:00:00.000")
        self.start_time_input.editingFinished.connect(self._on_time_input_changed)
        spin_row.addWidget(self.start_time_input)
        self.end_label = QLabel("End (hh:mm:ss.mmm):")
        spin_row.addWidget(self.end_label)
        self.end_time_input = QLineEdit("00:00:00.000")
        self.end_time_input.editingFinished.connect(self._on_time_input_changed)
        spin_row.addWidget(self.end_time_input)
        layout.addLayout(spin_row)

        self.seconds_only_checkbox = QCheckBox("Show seconds.milliseconds")
        self.seconds_only_checkbox.toggled.connect(self._on_time_display_mode_changed)
        layout.addWidget(self.seconds_only_checkbox)

        self.frame_step_label = QLabel("Frame step: unavailable")
        layout.addWidget(self.frame_step_label)

        frame_row = QHBoxLayout()
        self.start_prev_frame_button = QPushButton("Start -1 Frame")
        self.start_prev_frame_button.clicked.connect(lambda: self._step_handle_by_frames("start", -1))
        frame_row.addWidget(self.start_prev_frame_button)
        self.start_next_frame_button = QPushButton("Start +1 Frame")
        self.start_next_frame_button.clicked.connect(lambda: self._step_handle_by_frames("start", 1))
        frame_row.addWidget(self.start_next_frame_button)
        self.end_prev_frame_button = QPushButton("End -1 Frame")
        self.end_prev_frame_button.clicked.connect(lambda: self._step_handle_by_frames("end", -1))
        frame_row.addWidget(self.end_prev_frame_button)
        self.end_next_frame_button = QPushButton("End +1 Frame")
        self.end_next_frame_button.clicked.connect(lambda: self._step_handle_by_frames("end", 1))
        frame_row.addWidget(self.end_next_frame_button)
        layout.addLayout(frame_row)

        live_row = QHBoxLayout()
        #▶ \u25B6 \uFE0F \u27A4
        self.live_preview_button = QPushButton("▶")
        self.live_preview_button.setToolTip("Live preview (loop selected range)")
        self.live_preview_button.clicked.connect(self.live_preview)
        live_row.addWidget(self.live_preview_button)
        self.stop_preview_button = QPushButton("■")
        self.stop_preview_button.setToolTip("Stop preview")
        self.stop_preview_button.clicked.connect(self.stop_preview)
        live_row.addWidget(self.stop_preview_button)
        layout.addLayout(live_row)

        export_row = QHBoxLayout()
        self.export_mp3_button = QPushButton("Export to MP3")
        self.export_mp3_button.clicked.connect(lambda: self.export_trim("mp3"))
        export_row.addWidget(self.export_mp3_button)
        self.export_gif_button = QPushButton("Export to GIF")
        self.export_gif_button.clicked.connect(lambda: self.export_trim("gif"))
        export_row.addWidget(self.export_gif_button)
        self.export_mp4_button = QPushButton("Export to MP4")
        self.export_mp4_button.clicked.connect(lambda: self.export_trim("mp4"))
        export_row.addWidget(self.export_mp4_button)
        layout.addLayout(export_row)

        self._init_progress_bar(layout, "Ready")
        self.setLayout(layout)
        self._update_frame_step_controls()

    def _on_range_changed(self, start_value: int, end_value: int) -> None:
        self.start_time_input.blockSignals(True)
        self.end_time_input.blockSignals(True)
        self.start_time_input.setText(self._format_trim_timestamp(start_value))
        self.end_time_input.setText(self._format_trim_timestamp(end_value))
        self.start_time_input.blockSignals(False)
        self.end_time_input.blockSignals(False)

    def _on_slider_dragged(self, handle_name: str, value: int) -> None:
        del handle_name
        if not self.input_file:
            return
        self._seek_preview_to_ms(value)

    def _on_time_input_changed(self) -> None:
        start_value = self._parse_trim_timestamp(self.start_time_input.text())
        end_value = self._parse_trim_timestamp(self.end_time_input.text())
        if start_value is None or end_value is None:
            expected_format = "seconds.milliseconds" if self.seconds_only_checkbox.isChecked() else "hh:mm:ss.mmm"
            QMessageBox.warning(self, "Invalid Time", f"Please use {expected_format} format.")
            self._on_range_changed(self.range_slider.startValue(), self.range_slider.endValue())
            return

        start_value = max(0, min(start_value, self.duration_ms))
        end_value = max(0, min(end_value, self.duration_ms))
        if start_value > end_value:
            if self.sender() == self.start_time_input:
                end_value = start_value
            else:
                start_value = end_value
        self.range_slider.setValues(start_value, end_value)
        if self.sender() == self.start_time_input:
            self._seek_preview_to_ms(start_value)
        else:
            self._seek_preview_to_ms(end_value)

    def _get_trim_range(self):
        start = self.range_slider.startValue()
        end = self.range_slider.endValue()
        if end <= start:
            return None, None
        return start, end

    def _format_trim_timestamp(self, value_ms: int) -> str:
        total_ms = max(0, int(value_ms))
        if self.seconds_only_checkbox.isChecked():
            return f"{total_ms / 1000:.3f}"

        total_seconds, milliseconds = divmod(total_ms, 1000)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def _parse_trim_timestamp(self, value: str) -> int | None:
        text = value.strip()
        if not text:
            return None

        if self.seconds_only_checkbox.isChecked():
            try:
                seconds_value = float(text)
            except ValueError:
                return None
            if seconds_value < 0:
                return None
            return int(round(seconds_value * 1000))

        parts = text.split(":")
        if len(parts) != 3:
            return None

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_part = float(parts[2])
        except ValueError:
            return None

        if hours < 0 or minutes < 0 or minutes > 59 or seconds_part < 0 or seconds_part >= 60:
            return None

        total_ms = ((hours * 3600) + (minutes * 60)) * 1000
        total_ms += int(round(seconds_part * 1000))
        return total_ms

    def _format_ffmpeg_timestamp(self, value_ms: int) -> str:
        return f"{max(0, int(value_ms)) / 1000:.3f}"

    def _parse_frame_rate(self, value: str | None) -> float | None:
        if not value:
            return None

        text = value.strip()
        if not text or text == "0/0":
            return None

        try:
            if "/" in text:
                numerator_text, denominator_text = text.split("/", 1)
                numerator = float(numerator_text)
                denominator = float(denominator_text)
                if denominator == 0:
                    return None
                fps = numerator / denominator
            else:
                fps = float(text)
        except ValueError:
            return None

        if fps <= 0 or not math.isfinite(fps):
            return None
        return fps

    def _update_frame_step_controls(self) -> None:
        has_frame_step = self.video_fps > 0
        for button in (
            self.start_prev_frame_button,
            self.start_next_frame_button,
            self.end_prev_frame_button,
            self.end_next_frame_button,
        ):
            button.setEnabled(has_frame_step)

        if has_frame_step:
            frame_ms = 1000 / self.video_fps
            self.frame_step_label.setText(f"Frame step: {self.video_fps:.3f} fps ({frame_ms:.3f} ms per frame)")
        else:
            self.frame_step_label.setText("Frame step: unavailable")

    def _frame_index_for_position(self, position_ms: int) -> int:
        if self.video_fps <= 0:
            return 0
        return int(round(max(0, position_ms) * self.video_fps / 1000))

    def _frame_position_ms(self, frame_index: int) -> int:
        if self.video_fps <= 0:
            return 0
        return max(0, min(int(round(max(0, frame_index) * 1000 / self.video_fps)), self.duration_ms))

    def _step_handle_by_frames(self, handle_name: str, frame_delta: int) -> None:
        if not self.input_file or self.video_fps <= 0:
            return

        if handle_name == "start":
            current_value = self.range_slider.startValue()
            target_value = self._frame_position_ms(self._frame_index_for_position(current_value) + frame_delta)
            target_value = min(target_value, self.range_slider.endValue())
            self.range_slider.setValues(target_value, self.range_slider.endValue())
        else:
            current_value = self.range_slider.endValue()
            target_value = self._frame_position_ms(self._frame_index_for_position(current_value) + frame_delta)
            target_value = max(target_value, self.range_slider.startValue())
            self.range_slider.setValues(self.range_slider.startValue(), target_value)

        self._seek_preview_to_ms(target_value)

    def _update_duration_label(self) -> None:
        self.duration_label.setText(f"Video length: {self._format_trim_timestamp(self.duration_ms)}")

    def _on_time_display_mode_changed(self, checked: bool) -> None:
        del checked
        if self.seconds_only_checkbox.isChecked():
            self.start_label.setText("Start (seconds.milliseconds):")
            self.end_label.setText("End (seconds.milliseconds):")
        else:
            self.start_label.setText("Start (hh:mm:ss.mmm):")
            self.end_label.setText("End (hh:mm:ss.mmm):")
        self._update_duration_label()
        self._on_range_changed(self.range_slider.startValue(), self.range_slider.endValue())

    def _seek_preview_to_ms(self, position_ms: int) -> None:
        self.loop_preview = False
        self.preview_timer.stop()
        self.media_player.pause()
        self.media_player.setPosition(max(0, int(position_ms)))

    def _probe_media_timing(self, file_path: str) -> tuple[int, float | None] | None:
        ffprobe_path = find_ff_tool("ffprobe")
        if not ffprobe_path:
            QMessageBox.critical(self, "ffprobe Not Found", "Could not find ffprobe. Place ffprobe.exe in your app bin folder.")
            return None

        process = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format=duration:stream=avg_frame_rate,r_frame_rate",
                "-of",
                "json",
                file_path,
            ],
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            QMessageBox.critical(self, "ffprobe Error", process.stderr.strip() or "Unable to read video metadata.")
            return None

        try:
            probe_data = json.loads(process.stdout or "{}")
            format_data = probe_data.get("format", {})
            duration_float = float(format_data.get("duration", 0))
            streams = probe_data.get("streams", [])
            fps = None
            if streams:
                fps = self._parse_frame_rate(streams[0].get("avg_frame_rate"))
                if fps is None:
                    fps = self._parse_frame_rate(streams[0].get("r_frame_rate"))
            return max(1, int(math.ceil(duration_float * 1000))), fps
        except Exception:
            QMessageBox.critical(self, "ffprobe Error", "Could not parse video timing metadata.")
            return None

    def select_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            get_default_output_dir(),
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm)",
        )
        if not file_path:
            return

        timing_info = self._probe_media_timing(file_path)
        if timing_info is None:
            return
        duration, fps = timing_info

        self.input_file = file_path
        self.duration_ms = duration
        self.video_fps = fps or 0.0
        self.selected_name.setText(os.path.basename(file_path))
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self.media_player.pause()
        self.range_slider.setRange(0, duration)
        self.range_slider.setValues(0, duration)
        self._update_duration_label()
        self._update_frame_step_controls()
        self._on_range_changed(0, duration)
        self._seek_preview_to_ms(0)

    def live_preview(self) -> None:
        if not self.input_file:
            QMessageBox.warning(self, "No File", "Select a video file first.")
            return

        start, end = self._get_trim_range()
        if start is None:
            QMessageBox.warning(self, "Invalid Range", "Trim end must be after trim start.")
            return

        self._play_selected_range(start, end, loop=True)

    def stop_preview(self) -> None:
        self.loop_preview = False
        self.preview_timer.stop()
        self.media_player.pause()

    def _play_selected_range(self, start_ms: int, end_ms: int, loop: bool) -> None:
        self.preview_start_ms = int(start_ms)
        self.preview_end_ms = int(end_ms)
        self.loop_preview = loop
        self.media_player.setPosition(self.preview_start_ms)
        self.media_player.play()
        self.preview_timer.start()

    def _on_preview_tick(self) -> None:
        position = self.media_player.position()
        if position < self.preview_end_ms:
            return

        if self.loop_preview:
            self.media_player.setPosition(self.preview_start_ms)
            self.media_player.play()
        else:
            self.preview_timer.stop()
            self.media_player.pause()

    def export_trim(self, output_type: str) -> None:
        if not self.input_file:
            self._set_progress_idle("No file selected")
            QMessageBox.warning(self, "No File", "Select a video file first.")
            return

        start, end = self._get_trim_range()
        if start is None:
            self._set_progress_idle("Invalid range")
            QMessageBox.warning(self, "Invalid Range", "Trim end must be after trim start.")
            return

        ffmpeg_path = find_ff_tool("ffmpeg")
        if not ffmpeg_path:
            self._set_progress_idle("ffmpeg missing")
            QMessageBox.critical(self, "ffmpeg Not Found", "Could not find ffmpeg. Place ffmpeg.exe in your app bin folder.")
            return

        base_name = os.path.splitext(os.path.basename(self.input_file))[0]
        default_name = f"{base_name}_trim.{output_type}"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {output_type.upper()} File",
            os.path.join(get_default_output_dir(), default_name),
            f"{output_type.upper()} Files (*.{output_type})",
        )
        if not save_path:
            self._set_progress_idle("Ready")
            return
        if not save_path.lower().endswith(f".{output_type}"):
            save_path += f".{output_type}"

        trim_args = ["-ss", self._format_ffmpeg_timestamp(start), "-to", self._format_ffmpeg_timestamp(end), "-i", self.input_file]
        if output_type == "mp3":
            command = [ffmpeg_path, "-y", *trim_args, "-vn", "-acodec", "libmp3lame", "-q:a", "2", save_path]
        elif output_type == "gif":
            command = [ffmpeg_path, "-y", *trim_args, "-vf", "fps=10,scale=480:-1:flags=lanczos", save_path]
        else:
            command = [ffmpeg_path, "-y", *trim_args, "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", save_path]

        self._set_progress_busy(f"Exporting {output_type.upper()}...")
        QApplication.processEvents()
        process = subprocess.run(command, capture_output=True, text=True, **get_subprocess_kwargs())
        if process.returncode != 0:
            self._set_progress_idle("Export failed")
            error_text = process.stderr.strip() or "Unknown ffmpeg error"
            QMessageBox.critical(self, "Export Failed", error_text)
            return

        self._set_progress_complete("100% - done")
        QMessageBox.information(self, "Export Complete", f"Saved file:\n{save_path}")


class SingleFrameExtractWidget(TrimExportWidget):
    def __init__(self):
        super().__init__()
        self.range_title.setText("Frame Position")
        self.range_slider.hide()
        self.start_label.setText("Frame (hh:mm:ss.mmm):")
        self.end_label.hide()
        self.end_time_input.hide()
        self.start_prev_frame_button.setText("Frame -1")
        self.start_next_frame_button.setText("Frame +1")
        self.end_prev_frame_button.hide()
        self.end_next_frame_button.hide()
        self.live_preview_button.hide()
        self.stop_preview_button.hide()
        self.export_mp3_button.hide()
        self.export_gif_button.hide()
        try:
            self.export_mp4_button.clicked.disconnect()
        except TypeError:
            pass
        self.export_mp4_button.setText("Extract Frame to PNG")
        self.export_mp4_button.clicked.connect(self.extract_frame)

        self.current_frame_label = QLabel("Current frame: 0")
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setSingleStep(1)
        self.frame_slider.setPageStep(100)
        self.frame_slider.setTracking(True)
        self.frame_slider.valueChanged.connect(self._on_frame_slider_changed)

        layout = self.layout()
        layout.insertWidget(4, self.current_frame_label)
        layout.insertWidget(5, self.frame_slider)

    def _sync_frame_labels(self, value_ms: int) -> None:
        frame_index = self._frame_index_for_position(value_ms)
        self.current_frame_label.setText(f"Current frame: {frame_index}")
        formatted_time = self._format_trim_timestamp(value_ms)

        self.start_time_input.blockSignals(True)
        self.end_time_input.blockSignals(True)
        self.frame_slider.blockSignals(True)
        self.start_time_input.setText(formatted_time)
        self.end_time_input.setText(formatted_time)
        self.frame_slider.setValue(int(value_ms))
        self.start_time_input.blockSignals(False)
        self.end_time_input.blockSignals(False)
        self.frame_slider.blockSignals(False)

    def _on_frame_slider_changed(self, value: int) -> None:
        if not self.input_file:
            return
        self.range_slider.setValues(value, value)
        self._sync_frame_labels(value)
        self._seek_preview_to_ms(value)

    def _on_time_input_changed(self) -> None:
        value = self._parse_trim_timestamp(self.start_time_input.text())
        if value is None:
            expected_format = "seconds.milliseconds" if self.seconds_only_checkbox.isChecked() else "hh:mm:ss.mmm"
            QMessageBox.warning(self, "Invalid Time", f"Please use {expected_format} format.")
            self._sync_frame_labels(self.range_slider.startValue())
            return

        value = max(0, min(value, self.duration_ms))
        self.range_slider.setValues(value, value)
        self._sync_frame_labels(value)
        self._seek_preview_to_ms(value)

    def _step_handle_by_frames(self, handle_name: str, frame_delta: int) -> None:
        del handle_name
        if not self.input_file or self.video_fps <= 0:
            return

        current_value = self.range_slider.startValue()
        target_value = self._frame_position_ms(self._frame_index_for_position(current_value) + frame_delta)
        self.range_slider.setValues(target_value, target_value)
        self._sync_frame_labels(target_value)
        self._seek_preview_to_ms(target_value)

    def select_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            get_default_output_dir(),
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm)",
        )
        if not file_path:
            return

        timing_info = self._probe_media_timing(file_path)
        if timing_info is None:
            return
        duration, fps = timing_info

        self.input_file = file_path
        self.duration_ms = duration
        self.video_fps = fps or 0.0
        self.selected_name.setText(os.path.basename(file_path))
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self.media_player.pause()
        self.range_slider.setRange(0, duration)
        self.range_slider.setValues(0, 0)
        self.frame_slider.setRange(0, duration)
        self.frame_slider.setValue(0)
        self._update_duration_label()
        self._update_frame_step_controls()
        self._sync_frame_labels(0)
        self._seek_preview_to_ms(0)

    def extract_frame(self) -> None:
        if not self.input_file:
            self._set_progress_idle("No file selected")
            QMessageBox.warning(self, "No File", "Select a video file first.")
            return

        ffmpeg_path = find_ff_tool("ffmpeg")
        if not ffmpeg_path:
            self._set_progress_idle("ffmpeg missing")
            QMessageBox.critical(self, "ffmpeg Not Found", "Could not find ffmpeg. Place ffmpeg.exe in your app bin folder.")
            return

        position_ms = self.range_slider.startValue()
        frame_index = self._frame_index_for_position(position_ms)
        base_name = os.path.splitext(os.path.basename(self.input_file))[0]
        default_name = f"{base_name}_frame_{frame_index:06d}.png"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PNG Frame",
            os.path.join(get_default_output_dir(), default_name),
            "PNG Files (*.png)",
        )
        if not save_path:
            self._set_progress_idle("Ready")
            return
        if not save_path.lower().endswith(".png"):
            save_path += ".png"

        self._set_progress_busy("Extracting frame...")
        QApplication.processEvents()
        process = subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                self.input_file,
                "-ss",
                self._format_ffmpeg_timestamp(position_ms),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                save_path,
            ],
            capture_output=True,
            text=True,
            **get_subprocess_kwargs(),
        )
        if process.returncode != 0 or not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            self._set_progress_idle("Extraction failed")
            QMessageBox.critical(self, "Extraction Failed", (process.stderr or "ffmpeg could not extract the selected frame.").strip())
            return

        self._set_progress_complete("100% - done")
        QMessageBox.information(self, "Frame Saved", f"Saved PNG frame:\n{save_path}")


class ResolutionToolWidget(QWidget, ProgressBarMixin):
    def __init__(self):
        super().__init__()
        self.input_file = ""
        self.source_width = 0
        self.source_height = 0
        self.source_duration = 0.0
        self.source_bit_rate = 0
        self.source_size_bytes = 0

        layout = QVBoxLayout()
        self.info_label = QLabel("Select an MP4 file to read resolution and downscale.")
        layout.addWidget(self.info_label)

        self.select_button = QPushButton("Select MP4")
        self.select_button.clicked.connect(self.select_file)
        layout.addWidget(self.select_button)

        self.file_label = QLabel("No file selected")
        layout.addWidget(self.file_label)

        self.current_res_label = QLabel("Current resolution: -")
        layout.addWidget(self.current_res_label)

        self.target_label = QLabel("Choose lower target resolution")
        layout.addWidget(self.target_label)

        self.resolution_combo = QComboBox()
        self.resolution_combo.currentIndexChanged.connect(self.update_size_estimate)
        layout.addWidget(self.resolution_combo)

        self.estimate_label = QLabel("Estimated output size: -")
        layout.addWidget(self.estimate_label)

        self.export_button = QPushButton("Export Resized MP4")
        self.export_button.clicked.connect(self.export_resized)
        layout.addWidget(self.export_button)

        self._init_progress_bar(layout, "Ready")
        self.setLayout(layout)

    def _probe_media_info(self, file_path: str):
        ffprobe_path = find_ff_tool("ffprobe")
        if not ffprobe_path:
            QMessageBox.critical(self, "ffprobe Not Found", "Could not find ffprobe.exe in your app folder/bin.")
            return None

        process = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "stream=width,height:format=duration,bit_rate",
                "-select_streams",
                "v:0",
                "-of",
                "default=noprint_wrappers=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            **get_subprocess_kwargs(),
        )
        if process.returncode != 0:
            QMessageBox.critical(self, "ffprobe Error", process.stderr.strip() or "Could not read resolution.")
            return None

        data = {}
        for raw_line in process.stdout.splitlines():
            if "=" not in raw_line:
                continue
            key, value = raw_line.split("=", 1)
            data[key.strip()] = value.strip()

        try:
            width = int(data.get("width", "0"))
            height = int(data.get("height", "0"))
            duration = float(data.get("duration", "0") or 0)
            bit_rate = int(float(data.get("bit_rate", "0") or 0))
            return {
                "width": width,
                "height": height,
                "duration": duration,
                "bit_rate": bit_rate,
            }
        except Exception:
            QMessageBox.critical(self, "ffprobe Error", "Could not parse resolution values.")
            return None

    def _populate_presets(self) -> None:
        self.resolution_combo.clear()
        presets = [
            ("4K (3840x2160)", 2160),
            ("2K (2560x1440)", 1440),
            ("1080p (1920x1080)", 1080),
            ("720p (1280x720)", 720),
            ("480p (854x480)", 480),
        ]
        valid_presets = [preset for preset in presets if preset[1] < self.source_height]
        if not valid_presets:
            self.resolution_combo.addItem("No lower preset available", -1)
            self.estimate_label.setText("Estimated output size: -")
            return

        for label, height in valid_presets:
            self.resolution_combo.addItem(label, height)

    def update_size_estimate(self) -> None:
        target_height = int(self.resolution_combo.currentData() or -1)
        if target_height <= 0 or self.source_height <= 0:
            self.estimate_label.setText("Estimated output size: -")
            return

        scale_ratio = (target_height / self.source_height) ** 2
        if self.source_size_bytes > 0:
            estimated_bytes = int(self.source_size_bytes * scale_ratio * 0.9)
        elif self.source_bit_rate > 0 and self.source_duration > 0:
            estimated_bytes = int(self.source_bit_rate * scale_ratio * self.source_duration / 8)
        else:
            self.estimate_label.setText("Estimated output size: unavailable")
            return

        estimated_mb = estimated_bytes / (1024 * 1024)
        self.estimate_label.setText(f"Estimated output size: ~{estimated_mb:.1f} MB")

    def select_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select MP4 File", get_default_output_dir(), "MP4 Files (*.mp4)")
        if not file_path:
            return

        media_info = self._probe_media_info(file_path)
        if not media_info:
            return

        self.input_file = file_path
        self.source_width = media_info["width"]
        self.source_height = media_info["height"]
        self.source_duration = media_info["duration"]
        self.source_bit_rate = media_info["bit_rate"]
        self.source_size_bytes = os.path.getsize(file_path)

        self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
        self.current_res_label.setText(f"Current resolution: {self.source_width}x{self.source_height}")
        self._populate_presets()
        self.update_size_estimate()

    def export_resized(self) -> None:
        if not self.input_file:
            self._set_progress_idle("No file selected")
            QMessageBox.warning(self, "No File", "Select an MP4 file first.")
            return

        target_height = int(self.resolution_combo.currentData() or -1)
        if target_height <= 0:
            self._set_progress_idle("No preset selected")
            QMessageBox.warning(self, "No Preset", "No valid lower resolution preset is available.")
            return

        ffmpeg_path = find_ff_tool("ffmpeg")
        if not ffmpeg_path:
            self._set_progress_idle("ffmpeg missing")
            QMessageBox.critical(self, "ffmpeg Not Found", "Could not find ffmpeg.exe in your app folder/bin.")
            return

        base_name = os.path.splitext(os.path.basename(self.input_file))[0]
        default_name = f"{base_name}_{target_height}p.mp4"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Resized MP4",
            os.path.join(get_default_output_dir(), default_name),
            "MP4 Files (*.mp4)",
        )
        if not save_path:
            self._set_progress_idle("Ready")
            return
        if not save_path.lower().endswith(".mp4"):
            save_path += ".mp4"

        self._set_progress_busy(f"Exporting {target_height}p MP4...")
        QApplication.processEvents()
        process = subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                self.input_file,
                "-vf",
                f"scale=-2:{target_height}",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "22",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                save_path,
            ],
            capture_output=True,
            text=True,
            **get_subprocess_kwargs(),
        )

        if process.returncode != 0:
            self._set_progress_idle("Export failed")
            QMessageBox.critical(self, "Export Failed", process.stderr.strip() or "Unknown ffmpeg error")
            return

        self._set_progress_complete("100% - done")
        QMessageBox.information(self, "Export Complete", f"Saved resized file:\n{save_path}")

class VideoStitchWidget(QWidget, ProgressBarMixin):
    def __init__(self):
        super().__init__()
        self.video_paths: list[str] = []

        layout = QVBoxLayout()
        self.info_label = QLabel("Add videos, arrange order, then export as one MP4.")
        layout.addWidget(self.info_label)

        action_row = QHBoxLayout()
        self.add_button = QPushButton("Add Video(s)")
        self.add_button.clicked.connect(self.add_videos)
        action_row.addWidget(self.add_button)

        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self.remove_selected)
        action_row.addWidget(self.remove_button)

        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_videos)
        action_row.addWidget(self.clear_button)
        layout.addLayout(action_row)

        self.video_list = QListWidget()
        self.video_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.video_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        layout.addWidget(self.video_list)

        reorder_row = QHBoxLayout()
        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.clicked.connect(self.move_selected_up)
        reorder_row.addWidget(self.move_up_button)

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.clicked.connect(self.move_selected_down)
        reorder_row.addWidget(self.move_down_button)

        layout.addLayout(reorder_row)

        self.export_button = QPushButton("Export Stitched MP4")
        self.export_button.clicked.connect(self.export_stitched_mp4)
        layout.addWidget(self.export_button)

        self._init_progress_bar(layout, "Ready")
        self.setLayout(layout)

    def add_videos(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            get_default_output_dir(),
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm)",
        )
        if not file_paths:
            return

        insert_row = self.video_list.currentRow() + 1
        if insert_row <= 0:
            insert_row = self.video_list.count()

        for offset, file_path in enumerate(file_paths):
            item = QListWidgetItem(os.path.basename(file_path))
            item.setToolTip(file_path)
            item.setData(0x0100, file_path)
            self.video_list.insertItem(insert_row + offset, item)

    def remove_selected(self) -> None:
        row = self.video_list.currentRow()
        if row < 0:
            return
        self.video_list.takeItem(row)

    def clear_videos(self) -> None:
        self.video_list.clear()

    def move_selected_up(self) -> None:
        row = self.video_list.currentRow()
        if row <= 0:
            return
        item = self.video_list.takeItem(row)
        self.video_list.insertItem(row - 1, item)
        self.video_list.setCurrentRow(row - 1)

    def move_selected_down(self) -> None:
        row = self.video_list.currentRow()
        if row < 0 or row >= self.video_list.count() - 1:
            return
        item = self.video_list.takeItem(row)
        self.video_list.insertItem(row + 1, item)
        self.video_list.setCurrentRow(row + 1)

    def _get_ordered_paths(self) -> list[str]:
        ordered_paths: list[str] = []
        for index in range(self.video_list.count()):
            item = self.video_list.item(index)
            path = item.data(0x0100)
            if isinstance(path, str) and path:
                ordered_paths.append(path)
        return ordered_paths

    def _write_concat_list_file(self, paths: list[str]) -> str:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8", newline="\n")
        try:
            for path in paths:
                normalized = path.replace("\\", "/")
                escaped = normalized.replace("'", "'\\''")
                temp_file.write(f"file '{escaped}'\n")
        finally:
            temp_file.close()
        return temp_file.name

    def export_stitched_mp4(self) -> None:
        ordered_paths = self._get_ordered_paths()
        if len(ordered_paths) < 2:
            self._set_progress_idle("Need at least two videos")
            QMessageBox.warning(self, "Need More Videos", "Add at least two videos to stitch.")
            return

        ffmpeg_path = find_ff_tool("ffmpeg")
        if not ffmpeg_path:
            self._set_progress_idle("ffmpeg missing")
            QMessageBox.critical(self, "ffmpeg Not Found", "Could not find ffmpeg.exe in your app folder/bin.")
            return

        default_name = "stitched_output.mp4"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Stitched MP4",
            os.path.join(get_default_output_dir(), default_name),
            "MP4 Files (*.mp4)",
        )
        if not save_path:
            self._set_progress_idle("Ready")
            return
        if not save_path.lower().endswith(".mp4"):
            save_path += ".mp4"

        list_file_path = self._write_concat_list_file(ordered_paths)
        self._set_progress_busy("Stitching videos...")
        QApplication.processEvents()
        try:
            process = subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_file_path,
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    save_path,
                ],
                capture_output=True,
                text=True,
                **get_subprocess_kwargs(),
            )
            if process.returncode != 0:
                self._set_progress_idle("Export failed")
                QMessageBox.critical(self, "Export Failed", process.stderr.strip() or "Unknown ffmpeg error")
                return
        finally:
            try:
                os.remove(list_file_path)
            except Exception:
                pass

        self._set_progress_complete("100% - done")
        QMessageBox.information(self, "Export Complete", f"Saved stitched file:\n{save_path}")

class MkvExtractWidget(QWidget, ProgressBarMixin):
    def __init__(self):
        super().__init__()
        self.input_file = ""

        layout = QVBoxLayout()
        self.info_label = QLabel("Select an MKV file to extract video, audio, and subtitle streams.")
        layout.addWidget(self.info_label)

        self.select_button = QPushButton("Select MKV")
        self.select_button.clicked.connect(self.select_file)
        layout.addWidget(self.select_button)

        self.file_label = QLabel("No file selected")
        layout.addWidget(self.file_label)

        self.extract_button = QPushButton("Extract Streams")
        self.extract_button.clicked.connect(self.extract_streams)
        layout.addWidget(self.extract_button)

        self._init_progress_bar(layout, "Ready")
        self.setLayout(layout)

    def select_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select MKV File", get_default_output_dir(), "MKV Files (*.mkv)")
        if not file_path:
            return
        self.input_file = file_path
        self.file_label.setText(f"Selected: {os.path.basename(file_path)}")

    def _get_stream_indices(self):
        ffprobe_path = find_ff_tool("ffprobe")
        if not ffprobe_path:
            QMessageBox.critical(self, "ffprobe Not Found", "Could not find ffprobe.exe in your app folder/bin.")
            return None

        process = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "stream=index,codec_type",
                "-of",
                "csv=p=0",
                self.input_file,
            ],
            capture_output=True,
            text=True,
            **get_subprocess_kwargs(),
        )
        if process.returncode != 0:
            QMessageBox.critical(self, "ffprobe Error", process.stderr.strip() or "Could not read streams.")
            return None

        indices = {"video": [], "audio": [], "subtitle": []}
        for line in process.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != 2:
                continue
            stream_index_text, codec_type = parts
            if codec_type not in indices:
                continue
            try:
                indices[codec_type].append(int(stream_index_text))
            except Exception:
                pass
        return indices

    def extract_streams(self) -> None:
        if not self.input_file:
            self._set_progress_idle("No file selected")
            QMessageBox.warning(self, "No File", "Select an MKV file first.")
            return

        ffmpeg_path = find_ff_tool("ffmpeg")
        if not ffmpeg_path:
            self._set_progress_idle("ffmpeg missing")
            QMessageBox.critical(self, "ffmpeg Not Found", "Could not find ffmpeg.exe in your app folder/bin.")
            return

        stream_indices = self._get_stream_indices()
        if stream_indices is None:
            self._set_progress_idle("Could not read streams")
            return

        base_name = os.path.splitext(os.path.basename(self.input_file))[0]
        source_dir = os.path.dirname(self.input_file)
        output_dir = os.path.join(source_dir, base_name)
        os.makedirs(output_dir, exist_ok=True)

        total_streams = len(stream_indices["video"]) + len(stream_indices["audio"]) + len(stream_indices["subtitle"])
        if total_streams == 0:
            self._set_progress_idle("No streams found")
            QMessageBox.warning(self, "No Streams", "No extractable streams found.")
            return

        processed = 0
        self.info_label.setText("Extracting streams... video tracks will be saved as MP4.")
        self._set_progress_step(0, total_streams, f"0 / {total_streams} streams")
        QApplication.processEvents()

        for number, stream_index in enumerate(stream_indices["video"], start=1):
            output_path = os.path.join(output_dir, f"video_{number:02d}.mp4")
            process = subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-i",
                    self.input_file,
                    "-map",
                    f"0:{stream_index}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-an",
                    "-movflags",
                    "+faststart",
                    output_path,
                ],
                capture_output=True,
                text=True,
                **get_subprocess_kwargs(),
            )
            if process.returncode != 0:
                self._set_progress_idle("Video extraction failed")
                QMessageBox.critical(self, "Extraction Failed", process.stderr.strip() or "Video extraction failed.")
                return
            processed += 1
            self._set_progress_step(processed, total_streams, f"{processed} / {total_streams} streams")
            QApplication.processEvents()

        for number, stream_index in enumerate(stream_indices["audio"], start=1):
            output_path = os.path.join(output_dir, f"audio_{number:02d}.mka")
            process = subprocess.run(
                [ffmpeg_path, "-y", "-i", self.input_file, "-map", f"0:{stream_index}", "-c", "copy", output_path],
                capture_output=True,
                text=True,
                **get_subprocess_kwargs(),
            )
            if process.returncode != 0:
                self._set_progress_idle("Audio extraction failed")
                QMessageBox.critical(self, "Extraction Failed", process.stderr.strip() or "Audio extraction failed.")
                return
            processed += 1
            self._set_progress_step(processed, total_streams, f"{processed} / {total_streams} streams")
            QApplication.processEvents()

        for number, stream_index in enumerate(stream_indices["subtitle"], start=1):
            output_path = os.path.join(output_dir, f"subtitle_{number:02d}.mks")
            process = subprocess.run(
                [ffmpeg_path, "-y", "-i", self.input_file, "-map", f"0:{stream_index}", "-c", "copy", output_path],
                capture_output=True,
                text=True,
                **get_subprocess_kwargs(),
            )
            if process.returncode != 0:
                self._set_progress_idle("Subtitle extraction failed")
                QMessageBox.critical(self, "Extraction Failed", process.stderr.strip() or "Subtitle extraction failed.")
                return
            processed += 1
            self._set_progress_step(processed, total_streams, f"{processed} / {total_streams} streams")
            QApplication.processEvents()

        self._set_progress_complete(f"{processed}/{total_streams} streams done")
        self.info_label.setText("Select an MKV file to extract video, audio, and subtitle streams.")
        QMessageBox.information(self, "Done", f"Streams extracted to folder:\n{output_dir}")


class MkvCreateWidget(QWidget, ProgressBarMixin):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.info_label = QLabel("Add video, audio, and optional subtitles to create one MKV.")
        layout.addWidget(self.info_label)

        # Video tracks
        layout.addWidget(QLabel("Video Tracks"))
        video_row = QHBoxLayout()
        self.add_video_button = QPushButton("Add Video")
        self.add_video_button.clicked.connect(self.add_video_files)
        video_row.addWidget(self.add_video_button)
        self.remove_video_button = QPushButton("Remove Selected")
        self.remove_video_button.clicked.connect(lambda: self._remove_selected(self.video_list))
        video_row.addWidget(self.remove_video_button)
        self.clear_video_button = QPushButton("Clear")
        self.clear_video_button.clicked.connect(lambda: self._clear_list(self.video_list))
        video_row.addWidget(self.clear_video_button)
        self.move_video_up_button = QPushButton("Move Up")
        self.move_video_up_button.clicked.connect(lambda: self._move_selected_up(self.video_list))
        video_row.addWidget(self.move_video_up_button)
        self.move_video_down_button = QPushButton("Move Down")
        self.move_video_down_button.clicked.connect(lambda: self._move_selected_down(self.video_list))
        video_row.addWidget(self.move_video_down_button)
        layout.addLayout(video_row)

        self.video_list = QListWidget()
        self.video_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.video_list.currentRowChanged.connect(self._sync_default_combos)
        layout.addWidget(self.video_list)

        self.video_default_combo = QComboBox()
        layout.addWidget(QLabel("Default Video Track"))
        layout.addWidget(self.video_default_combo)

        # Audio tracks
        layout.addWidget(QLabel("Audio Tracks"))
        audio_row = QHBoxLayout()
        self.add_audio_button = QPushButton("Add Audio")
        self.add_audio_button.clicked.connect(self.add_audio_files)
        audio_row.addWidget(self.add_audio_button)
        self.remove_audio_button = QPushButton("Remove Selected")
        self.remove_audio_button.clicked.connect(lambda: self._remove_selected(self.audio_list))
        audio_row.addWidget(self.remove_audio_button)
        self.clear_audio_button = QPushButton("Clear")
        self.clear_audio_button.clicked.connect(lambda: self._clear_list(self.audio_list))
        audio_row.addWidget(self.clear_audio_button)
        self.move_audio_up_button = QPushButton("Move Up")
        self.move_audio_up_button.clicked.connect(lambda: self._move_selected_up(self.audio_list))
        audio_row.addWidget(self.move_audio_up_button)
        self.move_audio_down_button = QPushButton("Move Down")
        self.move_audio_down_button.clicked.connect(lambda: self._move_selected_down(self.audio_list))
        audio_row.addWidget(self.move_audio_down_button)
        layout.addLayout(audio_row)

        self.audio_list = QListWidget()
        self.audio_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.audio_list.currentRowChanged.connect(self._sync_default_combos)
        layout.addWidget(self.audio_list)

        self.audio_default_combo = QComboBox()
        layout.addWidget(QLabel("Default Audio Track"))
        layout.addWidget(self.audio_default_combo)

        # Subtitle tracks
        layout.addWidget(QLabel("Subtitle Tracks (Optional)"))
        subtitle_row = QHBoxLayout()
        self.add_subtitle_button = QPushButton("Add Subtitles")
        self.add_subtitle_button.clicked.connect(self.add_subtitle_files)
        subtitle_row.addWidget(self.add_subtitle_button)
        self.remove_subtitle_button = QPushButton("Remove Selected")
        self.remove_subtitle_button.clicked.connect(lambda: self._remove_selected(self.subtitle_list))
        subtitle_row.addWidget(self.remove_subtitle_button)
        self.clear_subtitle_button = QPushButton("Clear")
        self.clear_subtitle_button.clicked.connect(lambda: self._clear_list(self.subtitle_list))
        subtitle_row.addWidget(self.clear_subtitle_button)
        self.move_subtitle_up_button = QPushButton("Move Up")
        self.move_subtitle_up_button.clicked.connect(lambda: self._move_selected_up(self.subtitle_list))
        subtitle_row.addWidget(self.move_subtitle_up_button)
        self.move_subtitle_down_button = QPushButton("Move Down")
        self.move_subtitle_down_button.clicked.connect(lambda: self._move_selected_down(self.subtitle_list))
        subtitle_row.addWidget(self.move_subtitle_down_button)
        layout.addLayout(subtitle_row)

        self.subtitle_list = QListWidget()
        self.subtitle_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.subtitle_list.currentRowChanged.connect(self._sync_default_combos)
        layout.addWidget(self.subtitle_list)

        self.subtitle_default_combo = QComboBox()
        layout.addWidget(QLabel("Default Subtitle Track (optional)"))
        layout.addWidget(self.subtitle_default_combo)

        self.create_button = QPushButton("Create MKV")
        self.create_button.clicked.connect(self.create_mkv)
        layout.addWidget(self.create_button)

        self._init_progress_bar(layout, "Ready")
        self.setLayout(layout)
        self._sync_default_combos()

    def _add_files_to_list(self, list_widget: QListWidget, dialog_title: str, filter_text: str) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(self, dialog_title, get_default_output_dir(), filter_text)
        if not file_paths:
            return

        for file_path in file_paths:
            item = QListWidgetItem(os.path.basename(file_path))
            item.setToolTip(file_path)
            item.setData(0x0100, file_path)
            list_widget.addItem(item)
        self._sync_default_combos()

    def _remove_selected(self, list_widget: QListWidget) -> None:
        row = list_widget.currentRow()
        if row < 0:
            return
        list_widget.takeItem(row)
        self._sync_default_combos()

    def _clear_list(self, list_widget: QListWidget) -> None:
        list_widget.clear()
        self._sync_default_combos()

    def _move_selected_up(self, list_widget: QListWidget) -> None:
        row = list_widget.currentRow()
        if row <= 0:
            return
        item = list_widget.takeItem(row)
        list_widget.insertItem(row - 1, item)
        list_widget.setCurrentRow(row - 1)
        self._sync_default_combos()

    def _move_selected_down(self, list_widget: QListWidget) -> None:
        row = list_widget.currentRow()
        if row < 0 or row >= list_widget.count() - 1:
            return
        item = list_widget.takeItem(row)
        list_widget.insertItem(row + 1, item)
        list_widget.setCurrentRow(row + 1)
        self._sync_default_combos()

    def _paths_from_list(self, list_widget: QListWidget) -> list[str]:
        paths: list[str] = []
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            path = item.data(0x0100)
            if isinstance(path, str) and path:
                paths.append(path)
        return paths

    def _populate_combo(self, combo: QComboBox, paths: list[str], allow_none: bool = False) -> None:
        previous_value = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        if allow_none:
            combo.addItem("None", -1)
        for index, path in enumerate(paths):
            combo.addItem(f"{index + 1}. {os.path.basename(path)}", index)

        restored = False
        if previous_value is not None:
            for index in range(combo.count()):
                if combo.itemData(index) == previous_value:
                    combo.setCurrentIndex(index)
                    restored = True
                    break

        if not restored and combo.count() > 0:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _sync_default_combos(self) -> None:
        self._populate_combo(self.video_default_combo, self._paths_from_list(self.video_list), allow_none=False)
        self._populate_combo(self.audio_default_combo, self._paths_from_list(self.audio_list), allow_none=False)
        self._populate_combo(self.subtitle_default_combo, self._paths_from_list(self.subtitle_list), allow_none=True)

    def add_video_files(self) -> None:
        self._add_files_to_list(
            self.video_list,
            "Select Video File(s)",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.flv *.mpeg *.mpg *.m4v *.3gp *.ts *.mts)",
        )

    def add_audio_files(self) -> None:
        self._add_files_to_list(
            self.audio_list,
            "Select Audio File(s)",
            "Audio Files (*.mp3 *.aac *.m4a *.flac *.wav *.ogg *.opus *.wma *.mka)",
        )

    def add_subtitle_files(self) -> None:
        self._add_files_to_list(
            self.subtitle_list,
            "Select Subtitle File(s)",
            "Subtitle Files (*.srt *.ass *.ssa *.vtt *.sub *.sup *.mks)",
        )

    def _add_disposition_args(self, args: list[str], stream_type: str, count: int, default_index: int | None) -> None:
        for index in range(count):
            args.extend([f"-disposition:{stream_type}:{index}", "0"])
        if default_index is not None and 0 <= default_index < count:
            args.extend([f"-disposition:{stream_type}:{default_index}", "default"])

    def create_mkv(self) -> None:
        video_paths = self._paths_from_list(self.video_list)
        audio_paths = self._paths_from_list(self.audio_list)
        subtitle_paths = self._paths_from_list(self.subtitle_list)

        if not video_paths:
            self._set_progress_idle("No video added")
            QMessageBox.warning(self, "No Video", "Add at least one video file.")
            return
        if not audio_paths:
            self._set_progress_idle("No audio added")
            QMessageBox.warning(self, "No Audio", "Add at least one audio file.")
            return

        ffmpeg_path = find_ff_tool("ffmpeg")
        if not ffmpeg_path:
            self._set_progress_idle("ffmpeg missing")
            QMessageBox.critical(self, "ffmpeg Not Found", "Could not find ffmpeg.exe in your app folder/bin.")
            return

        base_name = os.path.splitext(os.path.basename(video_paths[0]))[0]
        default_name = f"{base_name}.mkv"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save MKV File",
            os.path.join(get_default_output_dir(), default_name),
            "MKV Files (*.mkv)",
        )
        if not save_path:
            self._set_progress_idle("Ready")
            return
        if not save_path.lower().endswith(".mkv"):
            save_path += ".mkv"

        command: list[str] = [ffmpeg_path, "-y"]
        all_inputs = [*video_paths, *audio_paths, *subtitle_paths]
        for file_path in all_inputs:
            command.extend(["-i", file_path])

        input_cursor = 0
        for _ in video_paths:
            command.extend(["-map", f"{input_cursor}:v:0"])
            input_cursor += 1

        for _ in audio_paths:
            command.extend(["-map", f"{input_cursor}:a:0"])
            input_cursor += 1

        for _ in subtitle_paths:
            command.extend(["-map", f"{input_cursor}:s:0"])
            input_cursor += 1

        command.extend(["-c", "copy"])

        video_default = self.video_default_combo.currentData()
        audio_default = self.audio_default_combo.currentData()
        subtitle_default = self.subtitle_default_combo.currentData()

        self._add_disposition_args(command, "v", len(video_paths), video_default if isinstance(video_default, int) else None)
        self._add_disposition_args(command, "a", len(audio_paths), audio_default if isinstance(audio_default, int) else None)
        subtitle_default_index = subtitle_default if isinstance(subtitle_default, int) and subtitle_default >= 0 else None
        self._add_disposition_args(command, "s", len(subtitle_paths), subtitle_default_index)

        command.append(save_path)

        self._set_progress_busy("Creating MKV...")
        QApplication.processEvents()
        process = subprocess.run(command, capture_output=True, text=True, **get_subprocess_kwargs())
        if process.returncode != 0:
            self._set_progress_idle("Create failed")
            QMessageBox.critical(self, "Create Failed", process.stderr.strip() or "Unknown ffmpeg error")
            return

        self._set_progress_complete("100% - done")
        QMessageBox.information(self, "Done", f"MKV created:\n{save_path}")
