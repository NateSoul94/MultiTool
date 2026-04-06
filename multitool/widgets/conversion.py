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

import os
import subprocess

from PIL import Image
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..helpers import find_ff_tool, get_default_output_dir, get_subprocess_kwargs
from .common import ProgressBarMixin

class VideoConvertWidget(QWidget, ProgressBarMixin):
    def __init__(self, display_name: str, output_extension: str, ffmpeg_args: list[str], is_audio_only: bool = False):
        super().__init__()
        self.display_name = display_name
        self.output_extension = output_extension.lower().lstrip(".")
        self.ffmpeg_args = ffmpeg_args
        self.is_audio_only = is_audio_only

        layout = QVBoxLayout()
        mode_text = "audio" if self.is_audio_only else "video"
        self.idle_text = f"Convert any {mode_text} file to {self.display_name}"
        self.label = QLabel(self.idle_text)
        layout.addWidget(self.label)
        self.button = QPushButton(f"Choose File(s) and Convert to {self.display_name}")
        self.button.clicked.connect(self.convert_videos)
        layout.addWidget(self.button)

        self._init_progress_bar(layout, "Ready")
        self.setLayout(layout)

    def _find_ffmpeg(self) -> str | None:
        return find_ff_tool("ffmpeg")

    def _run_conversion(self, ffmpeg_path: str, input_path: str, output_path: str) -> tuple[bool, str]:
        process = subprocess.run(
            [ffmpeg_path, "-y", "-i", input_path, *self.ffmpeg_args, output_path],
            capture_output=True,
            text=True,
            **get_subprocess_kwargs(),
        )
        if process.returncode != 0:
            return False, (process.stderr or "Unknown ffmpeg error").strip()

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return False, "ffmpeg ran but no output file was created."
        return True, ""

    def _select_input_files(self) -> list[str]:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video File(s)",
            get_default_output_dir(),
            "Media Files (*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.flv *.mpeg *.mpg *.m4v *.3gp *.ts *.mts)",
        )
        return file_paths

    def convert_videos(self) -> None:
        file_paths = self._select_input_files()
        if not file_paths:
            self._set_progress_idle("Ready")
            return

        ffmpeg_path = self._find_ffmpeg()
        if not ffmpeg_path:
            self._set_progress_idle("ffmpeg missing")
            QMessageBox.critical(
                self,
                "ffmpeg Not Found",
                "Could not find ffmpeg.\n\nPlace ffmpeg.exe next to this app, in bin, or install ffmpeg and add it to PATH.",
            )
            return

        total_files = len(file_paths)

        if total_files == 1:
            input_path = file_paths[0]
            self.label.setText(f"Selected: {os.path.basename(input_path)}")
            default_name = f"{os.path.splitext(os.path.basename(input_path))[0]}.{self.output_extension}"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Save {self.display_name} File",
                os.path.join(get_default_output_dir(), default_name),
                f"{self.display_name} Files (*.{self.output_extension})",
            )
            if not save_path:
                self.label.setText(self.idle_text)
                self._set_progress_idle("Ready")
                return
            if not save_path.lower().endswith(f".{self.output_extension}"):
                save_path += f".{self.output_extension}"

            self.label.setText("Processing... Please wait.")
            self._set_progress_busy("Processing...")
            QApplication.processEvents()
            ok, error = self._run_conversion(ffmpeg_path, input_path, save_path)
            self.label.setText(self.idle_text)

            if not ok:
                self._set_progress_idle("Failed")
                QMessageBox.critical(self, "Conversion Failed", error)
                return

            self._set_progress_complete("100% - done")
            QMessageBox.information(self, "Success", f"{self.display_name} saved to: {save_path}")
            return

        self.label.setText(f"Selected: {total_files} files")
        output_dir = QFileDialog.getExistingDirectory(self, "Choose Output Folder", get_default_output_dir())
        if not output_dir:
            self.label.setText(self.idle_text)
            self._set_progress_idle("Ready")
            return

        self._set_progress_step(0, total_files, f"0 / {total_files} files")
        QApplication.processEvents()
        success_count = 0
        failed_files: list[str] = []
        for index, input_path in enumerate(file_paths, start=1):
            self.label.setText(f"Processing {index}/{total_files}: {os.path.basename(input_path)}")
            QApplication.processEvents()
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}.{self.output_extension}")
            ok, error = self._run_conversion(ffmpeg_path, input_path, output_path)
            if ok:
                success_count += 1
            else:
                failed_files.append(f"{os.path.basename(input_path)} ({error})")
            self._set_progress_step(index, total_files, f"{index} / {total_files} files")
            QApplication.processEvents()

        self.label.setText(self.idle_text)
        self._set_progress_complete(f"{success_count}/{total_files} completed")
        if failed_files:
            QMessageBox.warning(
                self,
                "Completed with Errors",
                f"Converted {success_count}/{total_files} files.\n\nFailed:\n" + "\n".join(failed_files),
            )
        else:
            QMessageBox.information(
                self,
                "Success",
                f"Converted {success_count} files to {self.display_name} in:\n{output_dir}",
            )


class Mp3ConvertWidget(VideoConvertWidget):
    def __init__(self):
        super().__init__(
            display_name="MP3",
            output_extension="mp3",
            ffmpeg_args=["-vn", "-acodec", "libmp3lame", "-q:a", "2"],
            is_audio_only=True,
        )


class Mp4ConvertWidget(VideoConvertWidget):
    def __init__(self):
        super().__init__(
            display_name="MP4",
            output_extension="mp4",
            ffmpeg_args=["-c:v", "libx264", "-c:a", "aac"],
        )


class AviConvertWidget(VideoConvertWidget):
    def __init__(self):
        super().__init__(
            display_name="AVI",
            output_extension="avi",
            ffmpeg_args=["-c:v", "mpeg4", "-c:a", "libmp3lame"],
        )


class MovConvertWidget(VideoConvertWidget):
    def __init__(self):
        super().__init__(
            display_name="MOV",
            output_extension="mov",
            ffmpeg_args=["-c:v", "libx264", "-c:a", "aac"],
        )


class WmvConvertWidget(VideoConvertWidget):
    def __init__(self):
        super().__init__(
            display_name="WMV",
            output_extension="wmv",
            ffmpeg_args=["-c:v", "wmv2", "-c:a", "wmav2"],
        )


class WebmConvertWidget(VideoConvertWidget):
    def __init__(self):
        super().__init__(
            display_name="WEBM",
            output_extension="webm",
            ffmpeg_args=["-c:v", "libvpx-vp9", "-c:a", "libopus"],
        )


class Mp4ToMp3Widget(Mp3ConvertWidget):
    pass


class FullFrameExtractWidget(QWidget, ProgressBarMixin):
    def __init__(self):
        super().__init__()
        self.video_path = ""
        self.idle_text = "Select a video to extract every frame as full-resolution PNG images."

        layout = QVBoxLayout()
        self.info_label = QLabel(self.idle_text)
        layout.addWidget(self.info_label)

        file_row = QHBoxLayout()
        self.select_button = QPushButton("Select Video")
        self.select_button.clicked.connect(self.select_video)
        file_row.addWidget(self.select_button)

        self.selected_name = QLabel("No video selected")
        file_row.addWidget(self.selected_name)
        layout.addLayout(file_row)

        self.extract_button = QPushButton("Extract All Frames to PNG")
        self.extract_button.clicked.connect(self.extract_frames)
        layout.addWidget(self.extract_button)

        self._init_progress_bar(layout, "Ready")
        self.setLayout(layout)

    def _find_ffmpeg(self) -> str | None:
        return find_ff_tool("ffmpeg")

    def _build_output_dir(self) -> str:
        base_name = os.path.splitext(os.path.basename(self.video_path))[0] or "video"
        parent_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose Destination Folder",
            get_default_output_dir(),
        )
        if not parent_dir:
            return ""

        preferred_dir = os.path.join(parent_dir, f"{base_name}_frames")
        output_dir = preferred_dir
        suffix = 1
        while os.path.isdir(output_dir) and os.listdir(output_dir):
            output_dir = f"{preferred_dir}_{suffix}"
            suffix += 1

        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def select_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            get_default_output_dir(),
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.flv *.mpeg *.mpg *.m4v *.3gp *.ts *.mts);;All Files (*)",
        )
        if not file_path:
            return

        self.video_path = file_path
        self.selected_name.setText(os.path.basename(file_path))
        self.info_label.setText("Ready to extract every frame as PNG at the original video resolution.")

    def extract_frames(self) -> None:
        if not self.video_path:
            self._set_progress_idle("No file selected")
            QMessageBox.warning(self, "No File", "Select a video file first.")
            return

        ffmpeg_path = self._find_ffmpeg()
        if not ffmpeg_path:
            self._set_progress_idle("ffmpeg missing")
            QMessageBox.critical(
                self,
                "ffmpeg Not Found",
                "Could not find ffmpeg.\n\nPlace ffmpeg.exe next to this app, in bin, or install ffmpeg and add it to PATH.",
            )
            return

        output_dir = self._build_output_dir()
        if not output_dir:
            self._set_progress_idle("Ready")
            return

        output_pattern = os.path.join(output_dir, "frame_%06d.png")
        self.info_label.setText("Extracting frames... Please wait.")
        self._set_progress_busy("Extracting frames...")
        QApplication.processEvents()

        process = subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                self.video_path,
                "-map",
                "0:v:0",
                "-vsync",
                "0",
                output_pattern,
            ],
            capture_output=True,
            text=True,
            **get_subprocess_kwargs(),
        )

        png_files = [name for name in os.listdir(output_dir) if name.lower().endswith(".png")]
        self.info_label.setText(self.idle_text)

        if process.returncode != 0 or not png_files:
            self._set_progress_idle("Failed")
            QMessageBox.critical(
                self,
                "Extraction Failed",
                (process.stderr or "ffmpeg could not extract frames.").strip(),
            )
            return

        self._set_progress_complete(f"{len(png_files)} frame(s) saved")
        QMessageBox.information(
            self,
            "Success",
            f"Extracted {len(png_files)} frame(s) as PNG images to:\n{output_dir}",
        )


class ImageConvertWidget(QWidget, ProgressBarMixin):
    def __init__(self, output_format: str, display_name: str, output_extension: str):
        super().__init__()
        self.output_format = output_format.upper()
        self.display_name = display_name
        self.output_extension = output_extension.lower().lstrip(".")

        layout = QVBoxLayout()
        self.label = QLabel(f"Select one or more images to convert to {self.display_name}.")
        layout.addWidget(self.label)

        self.button = QPushButton(f"Choose Image(s) and Convert to {self.display_name}")
        self.button.clicked.connect(self.convert_images)
        layout.addWidget(self.button)

        self._init_progress_bar(layout, "Ready")
        self.setLayout(layout)

    def _save_image(self, image_path: str, output_path: str) -> None:
        with Image.open(image_path) as img:
            converted = img.convert("RGBA") if self.output_format in {"ICO", "PNG", "WEBP"} else img.convert("RGB")
            converted.save(output_path, format=self.output_format)

    def convert_images(self) -> None:
        image_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Image File(s)",
            get_default_output_dir(),
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff *.heic *.heif)",
        )
        if not image_paths:
            self._set_progress_idle("Ready")
            return

        total_images = len(image_paths)

        if total_images == 1:
            image_path = image_paths[0]
            self.label.setText(f"Selected: {os.path.basename(image_path)}")
            default_name = f"{os.path.splitext(os.path.basename(image_path))[0]}.{self.output_extension}"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Save {self.display_name} File",
                os.path.join(get_default_output_dir(), default_name),
                f"{self.display_name} Files (*.{self.output_extension})",
            )
            if not save_path:
                self._set_progress_idle("Ready")
                return
            if not save_path.lower().endswith(f".{self.output_extension}"):
                save_path += f".{self.output_extension}"
            try:
                self._set_progress_busy("Processing...")
                QApplication.processEvents()
                self._save_image(image_path, save_path)
                self._set_progress_complete("100% - done")
                QMessageBox.information(self, "Success", f"{self.display_name} saved to: {save_path}")
            except Exception as exc:
                self._set_progress_idle("Failed")
                QMessageBox.critical(self, "Error", f"Failed to convert: {exc}")
            return

        self.label.setText(f"Selected: {total_images} images")
        output_dir = QFileDialog.getExistingDirectory(self, "Choose Output Folder", get_default_output_dir())
        if not output_dir:
            self._set_progress_idle("Ready")
            return

        success_count = 0
        failed_files: list[str] = []
        self._set_progress_step(0, total_images, f"0 / {total_images} files")
        for index, image_path in enumerate(image_paths, start=1):
            self.label.setText(f"Processing {index}/{total_images}: {os.path.basename(image_path)}")
            QApplication.processEvents()
            try:
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                output_path = os.path.join(output_dir, f"{base_name}.{self.output_extension}")
                self._save_image(image_path, output_path)
                success_count += 1
            except Exception as exc:
                failed_files.append(f"{os.path.basename(image_path)} ({exc})")
            self._set_progress_step(index, total_images, f"{index} / {total_images} files")
            QApplication.processEvents()

        self._set_progress_complete(f"{success_count}/{total_images} completed")
        if failed_files:
            QMessageBox.warning(
                self,
                "Completed with Errors",
                f"Converted {success_count}/{total_images} files.\n\nFailed:\n" + "\n".join(failed_files),
            )
        else:
            QMessageBox.information(
                self,
                "Success",
                f"Converted {success_count} files to {self.display_name} in:\n{output_dir}",
            )

class IcoConvertWidget(ImageConvertWidget):
    def __init__(self):
        super().__init__(output_format="ICO", display_name="ICO", output_extension="ico")

class PngConvertWidget(ImageConvertWidget):
    def __init__(self):
        super().__init__(output_format="PNG", display_name="PNG", output_extension="png")

class JpegConvertWidget(ImageConvertWidget):
    def __init__(self):
        super().__init__(output_format="JPEG", display_name="JPEG", output_extension="jpg")

class WebpConvertWidget(ImageConvertWidget):
    def __init__(self):
        super().__init__(output_format="WEBP", display_name="WEBP", output_extension="webp")
