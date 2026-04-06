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
import os
import re
import shutil
import subprocess
from urllib.parse import quote

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..helpers import (
    build_ytdlp_common_args,
    build_ytdlp_error_message,
    find_ff_tool,
    find_idm_executable,
    get_default_output_dir,
    get_subprocess_kwargs,
    sanitize_file_name,
)

class YtDlpSingleWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.video_title = "video"
        self.video_url = ""

        layout = QVBoxLayout()
        self.info_label = QLabel("Paste a video link, load formats, then choose what to download.")
        layout.addWidget(self.info_label)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        url_row.addWidget(self.url_input)
        self.load_formats_button = QPushButton("Load Formats")
        self.load_formats_button.clicked.connect(self.load_formats)
        url_row.addWidget(self.load_formats_button)
        layout.addLayout(url_row)

        self.formats_list = QListWidget()
        self.formats_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.formats_list)

        output_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(get_default_output_dir())
        output_row.addWidget(self.output_dir_input)
        self.choose_output_button = QPushButton("Choose Folder")
        self.choose_output_button.clicked.connect(self.choose_output_folder)
        output_row.addWidget(self.choose_output_button)
        layout.addLayout(output_row)

        self.use_idm_checkbox = QCheckBox("Prefer IDM for MP4 when possible")
        self.use_idm_checkbox.setChecked(True)
        layout.addWidget(self.use_idm_checkbox)

        cookies_row = QHBoxLayout()
        self.use_browser_cookies_checkbox = QCheckBox("Use browser cookies")
        cookies_row.addWidget(self.use_browser_cookies_checkbox)
        self.browser_combo = QComboBox()
        self.browser_combo.addItem("Edge", "edge")
        self.browser_combo.addItem("Chrome", "chrome")
        self.browser_combo.addItem("Firefox", "firefox")
        self.browser_combo.addItem("Brave", "brave")
        cookies_row.addWidget(self.browser_combo)
        layout.addLayout(cookies_row)

        self.download_button = QPushButton("Download Selected")
        self.download_button.clicked.connect(self.download_selected)
        layout.addWidget(self.download_button)

        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setFormat("0%")
        layout.addWidget(self.download_progress)

        self.setLayout(layout)

    def _find_ytdlp(self) -> str | None:
        return find_ff_tool("yt-dlp")

    def _ytdlp_common_args(self) -> list[str]:
        return build_ytdlp_common_args()

    def _friendly_ytdlp_error(self, stderr: str, fallback_message: str) -> str:
        return build_ytdlp_error_message(stderr, fallback_message)

    def _browser_cookie_args(self) -> list[str]:
        if not self.use_browser_cookies_checkbox.isChecked():
            return []
        browser_name = str(self.browser_combo.currentData() or "edge")
        return ["--cookies-from-browser", browser_name]

    def _extract_download_percent(self, line: str) -> int | None:
        match = re.search(r"(\d{1,3}(?:\.\d+)?)%", line)
        if not match:
            return None
        try:
            value = int(float(match.group(1)))
        except ValueError:
            return None
        return max(0, min(value, 100))

    def _run_yt_dlp_download_with_progress(self, command: list[str], progress_label: str) -> tuple[int, str]:
        command_with_progress = [*command, "--newline"]
        output_lines: list[str] = []

        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setFormat("0%")

        process = subprocess.Popen(
            command_with_progress,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                output_lines.append(line)

                percent = self._extract_download_percent(line)
                if percent is not None:
                    self.download_progress.setRange(0, 100)
                    self.download_progress.setValue(percent)
                    self.download_progress.setFormat(f"{percent}%")
                    self.info_label.setText(f"{progress_label}... {percent}%")
                elif "[download]" in line and "Destination:" in line:
                    self.info_label.setText(line.replace("[download]", "").strip())
                elif "[Merger]" in line or "[ExtractAudio]" in line:
                    self.download_progress.setRange(0, 0)
                    self.info_label.setText(f"{progress_label}... finalizing")

                QApplication.processEvents()

        return_code = process.wait()
        if return_code == 0:
            self.download_progress.setRange(0, 100)
            self.download_progress.setValue(100)
            self.download_progress.setFormat("100%")
        elif self.download_progress.maximum() == 0:
            self.download_progress.setRange(0, 100)
            self.download_progress.setValue(0)
            self.download_progress.setFormat("0%")

        return return_code, "\n".join(output_lines)

    def _build_single_format_item(self, fmt: dict) -> QListWidgetItem | None:
        format_id = str(fmt.get("format_id", "")).strip()
        acodec = str(fmt.get("acodec", "none")).lower()
        vcodec = str(fmt.get("vcodec", "none")).lower()
        ext = str(fmt.get("ext", "")).lower()
        height = int(fmt.get("height") or 0)
        fps = int(fmt.get("fps") or 0)
        tbr = float(fmt.get("tbr") or 0)
        abr = float(fmt.get("abr") or fmt.get("tbr") or 0)
        size_bytes = int(fmt.get("filesize") or fmt.get("filesize_approx") or 0)
        size_text = f"{size_bytes / (1024 * 1024):.1f} MB" if size_bytes > 0 else "size unknown"

        if not format_id:
            return None

        if vcodec == "none" and acodec != "none":
            abr_text = f"{abr:.0f}k" if abr > 0 else "bitrate?"
            label = f"MP3 from {ext or 'audio'} | {abr_text} | {acodec or 'codec?'} | {size_text} | id={format_id}"
            item = QListWidgetItem(label)
            item.setData(0x0100, {"kind": "mp3", "format_id": format_id})
            return item

        if vcodec != "none" and acodec != "none":
            res_text = f"{height}p" if height > 0 else "unknown"
            fps_text = f"{fps}fps" if fps > 0 else "fps?"
            bitrate_text = f"{tbr:.0f}k" if tbr > 0 else "bitrate?"
            label = f"MP4 {res_text} | {fps_text} | {bitrate_text} | {ext or 'mp4'} | {size_text} | id={format_id}"
            item = QListWidgetItem(label)
            item.setData(0x0100, {"kind": "mp4_progressive", "format_id": format_id, "selector": format_id})
            return item

        if vcodec != "none" and acodec == "none":
            res_text = f"{height}p" if height > 0 else "unknown"
            fps_text = f"{fps}fps" if fps > 0 else "fps?"
            bitrate_text = f"{tbr:.0f}k" if tbr > 0 else "bitrate?"
            selector = f"{format_id}+bestaudio/best"
            label = f"MP4 {res_text} | {fps_text} | {bitrate_text} | video-only {ext or 'stream'} + best audio | id={format_id}"
            item = QListWidgetItem(label)
            item.setData(0x0100, {"kind": "mp4_adaptive", "format_id": format_id, "selector": selector})
            return item

        return None

    def _populate_format_list(self, data: dict) -> None:
        formats = data.get("formats", [])
        seen_labels: set[str] = set()

        self.formats_list.clear()
        mp3_item = QListWidgetItem("MP3 (best audio)")
        mp3_item.setData(0x0100, {"kind": "mp3_best"})
        self.formats_list.addItem(mp3_item)

        format_items: list[QListWidgetItem] = []
        for fmt in formats:
            item = self._build_single_format_item(fmt)
            if item is None:
                continue
            label = item.text()
            if label in seen_labels:
                continue
            seen_labels.add(label)
            format_items.append(item)

        if not format_items:
            for requested in data.get("requested_downloads", []):
                requested_formats = requested.get("requested_formats") or []
                if not requested_formats:
                    continue

                video_format = None
                audio_format = None
                for requested_format in requested_formats:
                    if str(requested_format.get("vcodec", "none")).lower() != "none":
                        video_format = requested_format
                    if str(requested_format.get("acodec", "none")).lower() != "none":
                        audio_format = requested_format

                requested_selector = str(requested.get("format_id", "")).strip()
                if video_format is not None and audio_format is not None and requested_selector:
                    height = int(video_format.get("height") or 0)
                    fps = int(video_format.get("fps") or 0)
                    ext = str(video_format.get("ext", "mp4")).lower()
                    tbr = float(requested.get("tbr") or video_format.get("tbr") or 0)
                    size_bytes = int(requested.get("filesize") or requested.get("filesize_approx") or 0)
                    size_text = f"{size_bytes / (1024 * 1024):.1f} MB" if size_bytes > 0 else "size unknown"
                    res_text = f"{height}p" if height > 0 else "unknown"
                    fps_text = f"{fps}fps" if fps > 0 else "fps?"
                    bitrate_text = f"{tbr:.0f}k" if tbr > 0 else "bitrate?"
                    label = f"MP4 {res_text} | {fps_text} | {bitrate_text} | merged selection | {size_text} | id={requested_selector}"
                    if label not in seen_labels:
                        item = QListWidgetItem(label)
                        item.setData(0x0100, {"kind": "mp4_adaptive", "format_id": requested_selector, "selector": requested_selector})
                        format_items.append(item)
                        seen_labels.add(label)

                if audio_format is not None:
                    item = self._build_single_format_item(audio_format)
                    if item is not None and item.text() not in seen_labels:
                        format_items.append(item)
                        seen_labels.add(item.text())

        format_items.sort(key=lambda item: item.text())
        for item in format_items:
            self.formats_list.addItem(item)

    def choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Download Folder", self.output_dir_input.text().strip() or get_default_output_dir())
        if folder:
            self.output_dir_input.setText(folder)

    def load_formats(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing Link", "Paste a video link first.")
            return

        yt_dlp_path = self._find_ytdlp()
        if not yt_dlp_path:
            QMessageBox.critical(self, "yt-dlp Not Found", "Could not find yt-dlp.exe in your app folder/bin.")
            return

        self.info_label.setText("Loading formats...")
        QApplication.processEvents()
        common_args = self._ytdlp_common_args()
        attempts = [
            [
                yt_dlp_path,
                *common_args,
                *self._browser_cookie_args(),
                "--no-playlist",
                "--extractor-args",
                "youtube:player_client=default;formats=duplicate",
                "-J",
                url,
            ],
            [
                yt_dlp_path,
                *common_args,
                *self._browser_cookie_args(),
                "--no-playlist",
                "--extractor-args",
                "youtube:player_client=default,-ios;formats=duplicate",
                "-J",
                url,
            ],
            [yt_dlp_path, *common_args, *self._browser_cookie_args(), "--no-playlist", "-J", url],
        ]

        process = None
        for command in attempts:
            process = subprocess.run(command, capture_output=True, text=True, **get_subprocess_kwargs())
            if process.returncode == 0:
                break

        if process is None or process.returncode != 0:
            self.info_label.setText("Paste a YouTube link, load formats, then choose what to download.")
            stderr_text = process.stderr if process is not None else ""
            QMessageBox.critical(self, "yt-dlp Error", self._friendly_ytdlp_error(stderr_text, "Could not load video formats."))
            return

        try:
            data = json.loads(process.stdout)
        except Exception:
            self.info_label.setText("Paste a YouTube link, load formats, then choose what to download.")
            QMessageBox.critical(self, "Parse Error", "Could not parse yt-dlp format response.")
            return

        self.video_url = url
        self.video_title = data.get("title", "video")
        self._populate_format_list(data)

        self.info_label.setText(f"Loaded formats for: {self.video_title}")
        if self.formats_list.count() == 1:
            QMessageBox.information(self, "Formats Loaded", "Only MP3 option is available for this link.")

    def _download_with_idm(self, direct_url: str, output_dir: str, file_name: str) -> bool:
        idm_path = find_idm_executable()
        if not idm_path:
            return False

        process = subprocess.run(
            [
                idm_path,
                "/d",
                direct_url,
                "/p",
                output_dir,
                "/f",
                file_name,
                "/n",
            ],
            capture_output=True,
            text=True,
        )
        return process.returncode == 0

    def _resolve_direct_format_url(self, yt_dlp_path: str, url: str, format_id: str) -> str | None:
        process = subprocess.run(
            [yt_dlp_path, *self._ytdlp_common_args(), *self._browser_cookie_args(), "--no-playlist", "-f", format_id, "-g", url],
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            return None
        for line in process.stdout.splitlines():
            candidate = line.strip()
            if candidate:
                return candidate
        return None

    def download_selected(self) -> None:
        selected_item = self.formats_list.currentItem()
        if selected_item is None:
            QMessageBox.warning(self, "No Selection", "Select an item to download.")
            return

        if not self.video_url:
            QMessageBox.warning(self, "No Video Loaded", "Load formats for a video first.")
            return

        output_dir = self.output_dir_input.text().strip() or get_default_output_dir()
        if not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Invalid Folder", "Choose a valid output folder.")
            return

        yt_dlp_path = self._find_ytdlp()
        if not yt_dlp_path:
            QMessageBox.critical(self, "yt-dlp Not Found", "Could not find yt-dlp.exe in your app folder/bin.")
            return

        selected_data = selected_item.data(0x0100)
        if not isinstance(selected_data, dict):
            QMessageBox.warning(self, "Invalid Selection", "Could not read selected format info.")
            return

        kind = str(selected_data.get("kind", "")).lower()
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

        self.info_label.setText("Downloading...")
        QApplication.processEvents()

        if kind in ("mp3_best", "mp3"):
            command = [
                yt_dlp_path,
                *self._ytdlp_common_args(),
                *self._browser_cookie_args(),
                "--no-playlist",
            ]
            if kind == "mp3":
                source_audio_id = str(selected_data.get("format_id", "")).strip()
                if source_audio_id:
                    command.extend(["-f", source_audio_id])
            command.extend(
                [
                    "-x",
                    "--audio-format",
                    "mp3",
                    "--audio-quality",
                    "0",
                    "-o",
                    output_template,
                    self.video_url,
                ]
            )

            return_code, command_output = self._run_yt_dlp_download_with_progress(command, "Downloading")
            self.info_label.setText("Paste a YouTube link, load formats, then choose what to download.")
            if return_code != 0:
                error_msg = self._friendly_ytdlp_error(command_output, "yt-dlp failed to download MP3.")
                if "decrypt" in command_output.lower() and self._browser_cookie_args():
                    error_msg = "Decrypt error detected. Try disabling browser cookies or retrying.\n\nDetails: " + error_msg
                QMessageBox.critical(self, "Download Failed", error_msg)
                return
            QMessageBox.information(self, "Download Complete", "MP3 download finished.")
            return

        if kind not in ("mp4_progressive", "mp4_adaptive"):
            self.info_label.setText("Paste a YouTube link, load formats, then choose what to download.")
            QMessageBox.warning(self, "Invalid Selection", "Unknown format kind.")
            return

        format_selector = str(selected_data.get("selector", "")).strip()
        if not format_selector:
            format_selector = str(selected_data.get("format_id", "")).strip()
        if not format_selector:
            self.info_label.setText("Paste a YouTube link, load formats, then choose what to download.")
            QMessageBox.warning(self, "Invalid Selection", "Missing format id.")
            return

        if self.use_idm_checkbox.isChecked() and kind == "mp4_progressive":
            progressive_id = str(selected_data.get("format_id", "")).strip()
            direct_url = self._resolve_direct_format_url(yt_dlp_path, self.video_url, progressive_id)
            if direct_url:
                safe_title = sanitize_file_name(self.video_title)
                idm_file_name = f"{safe_title}_{progressive_id}.mp4"
                if self._download_with_idm(direct_url, output_dir, idm_file_name):
                    self.info_label.setText("Paste a YouTube link, load formats, then choose what to download.")
                    QMessageBox.information(
                        self,
                        "Sent To IDM",
                        "Download was sent to IDM. If IDM queue mode is enabled, start it from IDM.",
                    )
                    return

        command = [
            yt_dlp_path,
            *self._ytdlp_common_args(),
            *self._browser_cookie_args(),
            "--no-playlist",
            "-f",
            format_selector,
            "--merge-output-format",
            "mp4",
            "-o",
            output_template,
            self.video_url,
        ]
        return_code, command_output = self._run_yt_dlp_download_with_progress(command, "Downloading")
        self.info_label.setText("Paste a YouTube link, load formats, then choose what to download.")
        if return_code != 0:
            error_msg = self._friendly_ytdlp_error(command_output, "yt-dlp failed to download MP4.")
            if "decrypt" in command_output.lower() and self._browser_cookie_args():
                error_msg = "Decrypt error detected. Try disabling browser cookies or retrying.\n\nDetails: " + error_msg
            QMessageBox.critical(self, "Download Failed", error_msg)
            return

        QMessageBox.information(self, "Download Complete", "MP4 download finished.")

class YtDlpPlaylistWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.info_label = QLabel("Paste a playlist link to download all videos with yt-dlp.")
        layout.addWidget(self.info_label)

        self.playlist_url_input = QLineEdit()
        self.playlist_url_input.setPlaceholderText("https://www.youtube.com/playlist?list=...")
        layout.addWidget(self.playlist_url_input)

        download_type_row = QHBoxLayout()
        self.download_type_combo = QComboBox()
        self.download_type_combo.addItem("Video", "video")
        self.download_type_combo.addItem("Audio (MP3)", "mp3")
        self.download_type_combo.currentIndexChanged.connect(self._on_download_type_changed)
        download_type_row.addWidget(QLabel("Download Type:"))
        download_type_row.addWidget(self.download_type_combo)
        layout.addLayout(download_type_row)

        self.format_combo = QComboBox()
        self.format_combo.addItem("Best available", "bestvideo*+bestaudio/best")
        self.format_combo.addItem("1080p + best audio", "bestvideo[height<=1080]+bestaudio/best")
        self.format_combo.addItem("720p + best audio", "bestvideo[height<=720]+bestaudio/best")
        self.format_combo.addItem("480p + best audio", "bestvideo[height<=480]+bestaudio/best")
        self.format_combo.addItem("360p + best audio", "bestvideo[height<=360]+bestaudio/best")
        layout.addWidget(self.format_combo)

        output_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(get_default_output_dir())
        output_row.addWidget(self.output_dir_input)
        self.choose_output_button = QPushButton("Choose Folder")
        self.choose_output_button.clicked.connect(self.choose_output_folder)
        output_row.addWidget(self.choose_output_button)
        layout.addLayout(output_row)

        cookies_row = QHBoxLayout()
        self.use_browser_cookies_checkbox = QCheckBox("Use browser cookies")
        cookies_row.addWidget(self.use_browser_cookies_checkbox)
        self.browser_combo = QComboBox()
        self.browser_combo.addItem("Edge", "edge")
        self.browser_combo.addItem("Chrome", "chrome")
        self.browser_combo.addItem("Firefox", "firefox")
        self.browser_combo.addItem("Brave", "brave")
        cookies_row.addWidget(self.browser_combo)
        layout.addLayout(cookies_row)

        self.download_button = QPushButton("Download Playlist")
        self.download_button.clicked.connect(self.download_playlist)
        layout.addWidget(self.download_button)

        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setFormat("0%")
        layout.addWidget(self.download_progress)

        self.setLayout(layout)

    def _find_ytdlp(self) -> str | None:
        return find_ff_tool("yt-dlp")

    def _ytdlp_common_args(self) -> list[str]:
        return build_ytdlp_common_args()

    def _friendly_ytdlp_error(self, stderr: str, fallback_message: str) -> str:
        return build_ytdlp_error_message(stderr, fallback_message)

    def _browser_cookie_args(self) -> list[str]:
        if not self.use_browser_cookies_checkbox.isChecked():
            return []
        browser_name = str(self.browser_combo.currentData() or "edge")
        return ["--cookies-from-browser", browser_name]

    def _extract_download_percent(self, line: str) -> int | None:
        match = re.search(r"(\d{1,3}(?:\.\d+)?)%", line)
        if not match:
            return None
        try:
            value = int(float(match.group(1)))
        except ValueError:
            return None
        return max(0, min(value, 100))

    def _run_yt_dlp_download_with_progress(self, command: list[str], progress_label: str) -> tuple[int, str]:
        command_with_progress = [*command, "--newline"]
        output_lines: list[str] = []

        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setFormat("0%")

        process = subprocess.Popen(
            command_with_progress,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                output_lines.append(line)

                percent = self._extract_download_percent(line)
                if percent is not None:
                    self.download_progress.setRange(0, 100)
                    self.download_progress.setValue(percent)
                    self.download_progress.setFormat(f"{percent}%")
                    self.info_label.setText(f"{progress_label}... {percent}%")
                elif "[download]" in line and "Destination:" in line:
                    self.info_label.setText(line.replace("[download]", "").strip())
                elif "[Merger]" in line or "[ExtractAudio]" in line:
                    self.download_progress.setRange(0, 0)
                    self.info_label.setText(f"{progress_label}... finalizing")

                QApplication.processEvents()

        return_code = process.wait()
        if return_code == 0:
            self.download_progress.setRange(0, 100)
            self.download_progress.setValue(100)
            self.download_progress.setFormat("100%")
        elif self.download_progress.maximum() == 0:
            self.download_progress.setRange(0, 100)
            self.download_progress.setValue(0)
            self.download_progress.setFormat("0%")

        return return_code, "\n".join(output_lines)

    def _on_download_type_changed(self) -> None:
        """Hide format combo when audio is selected since MP3 quality is always best."""
        download_type = str(self.download_type_combo.currentData() or "video")
        self.format_combo.setEnabled(download_type == "video")

    def choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Download Folder", self.output_dir_input.text().strip() or get_default_output_dir())
        if folder:
            self.output_dir_input.setText(folder)

    def download_playlist(self) -> None:
        url = self.playlist_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing Link", "Paste a playlist link first.")
            return

        output_dir = self.output_dir_input.text().strip() or get_default_output_dir()
        if not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Invalid Folder", "Choose a valid output folder.")
            return

        yt_dlp_path = self._find_ytdlp()
        if not yt_dlp_path:
            QMessageBox.critical(self, "yt-dlp Not Found", "Could not find yt-dlp.exe in your app folder/bin.")
            return

        download_type = str(self.download_type_combo.currentData() or "video")
        output_template = os.path.join(output_dir, "%(playlist_title)s", "%(playlist_index)03d - %(title)s.%(ext)s")

        self.info_label.setText("Downloading playlist... this may take a while.")
        QApplication.processEvents()

        if download_type == "mp3":
            command = [
                yt_dlp_path,
                *self._ytdlp_common_args(),
                *self._browser_cookie_args(),
                "--yes-playlist",
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",
                "-o",
                output_template,
                url,
            ]
        else:
            format_selector = str(self.format_combo.currentData() or "bestvideo*+bestaudio/best")
            command = [
                yt_dlp_path,
                *self._ytdlp_common_args(),
                *self._browser_cookie_args(),
                "--yes-playlist",
                "-f",
                format_selector,
                "--merge-output-format",
                "mp4",
                "-o",
                output_template,
                url,
            ]

        return_code, command_output = self._run_yt_dlp_download_with_progress(command, "Downloading playlist")
        self.info_label.setText("Paste a playlist link to download all videos with yt-dlp.")
        if return_code != 0:
            error_msg = self._friendly_ytdlp_error(command_output, "yt-dlp failed to download playlist.")
            if "decrypt" in command_output.lower() and self.use_browser_cookies_checkbox.isChecked():
                error_msg = "Decrypt error detected. Try disabling browser cookies or retrying without them.\n\nDetails: " + error_msg
            QMessageBox.critical(
                self,
                "Playlist Download Failed",
                error_msg,
            )
            return

        QMessageBox.information(self, "Playlist Complete", "Playlist download finished.")
