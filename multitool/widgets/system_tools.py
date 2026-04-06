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

import ctypes
import os
import subprocess

from PIL import Image
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import exifread
except Exception:
    exifread = None

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

from ..helpers import get_default_output_dir, get_subprocess_kwargs

class ExifMetadataWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.image_path = ""

        layout = QVBoxLayout()
        self.info_label = QLabel("Select an image to view EXIF metadata or strip it.")
        layout.addWidget(self.info_label)

        self.select_button = QPushButton("Select Image")
        self.select_button.clicked.connect(self.select_image)
        layout.addWidget(self.select_button)

        self.file_label = QLabel("No file selected")
        layout.addWidget(self.file_label)

        button_row = QHBoxLayout()
        self.view_button = QPushButton("View EXIF Metadata")
        self.view_button.clicked.connect(self.view_exif)
        button_row.addWidget(self.view_button)

        self.strip_button = QPushButton("Strip Metadata and Save")
        self.strip_button.clicked.connect(self.strip_metadata)
        button_row.addWidget(self.strip_button)
        layout.addLayout(button_row)

        self.exif_output = QTextEdit()
        self.exif_output.setReadOnly(True)
        self.exif_output.setPlaceholderText("EXIF data will appear here.")
        layout.addWidget(self.exif_output)

        self.setLayout(layout)

    def select_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            get_default_output_dir(),
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.heic *.heif);;All Files (*)",
        )
        if not file_path:
            return

        self.image_path = file_path
        self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
        self.exif_output.clear()

    def view_exif(self) -> None:
        if not self.image_path:
            QMessageBox.warning(self, "No File", "Select an image first.")
            return

        if exifread is None:
            QMessageBox.critical(self, "Missing Dependency", "exifread is not installed. Install it with: pip install exifread")
            return

        try:
            with open(self.image_path, "rb") as file:
                tags = exifread.process_file(file, details=False)
        except Exception as exc:
            QMessageBox.critical(self, "Read Error", f"Failed to read EXIF metadata: {exc}")
            return

        if not tags:
            self.exif_output.setPlainText("No EXIF metadata found in this file.")
            return

        lines = [f"{key}: {tags[key]}" for key in sorted(tags.keys())]
        self.exif_output.setPlainText("\n".join(lines))

    def strip_metadata(self) -> None:
        if not self.image_path:
            QMessageBox.warning(self, "No File", "Select an image first.")
            return

        source_ext = os.path.splitext(self.image_path)[1].lower()
        base_name = os.path.splitext(os.path.basename(self.image_path))[0]
        extension = source_ext or ".jpg"
        suggested_name = f"{base_name}_stripped{extension}"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image Without Metadata",
            os.path.join(get_default_output_dir(), suggested_name),
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.heic *.heif);;All Files (*)",
        )
        if not save_path:
            return

        try:
            with Image.open(self.image_path) as img:
                pixel_data = list(img.getdata())
                clean_img = Image.new(img.mode, img.size)
                if img.mode == "P" and img.getpalette() is not None:
                    clean_img.putpalette(img.getpalette())
                clean_img.putdata(pixel_data)

                image_format = (img.format or "PNG").upper()
                save_kwargs = {}

                is_heif_source = source_ext in (".heic", ".heif") or image_format in ("HEIC", "HEIF")
                if is_heif_source:
                    if pillow_heif is None:
                        QMessageBox.critical(
                            self,
                            "HEIC Support Missing",
                            "HEIC/HEIF stripping requires pillow-heif.\nInstall it with: pip install pillow-heif",
                        )
                        return
                    if clean_img.mode not in ("RGB", "RGBA", "L"):
                        clean_img = clean_img.convert("RGB")
                    clean_img.save(save_path, format="HEIF", quality=95)
                    QMessageBox.information(self, "Success", f"Saved metadata-stripped image:\n{save_path}")
                    return

                if image_format in ("JPEG", "JPG"):
                    save_kwargs["quality"] = 95
                    save_kwargs["optimize"] = True
                    save_kwargs["exif"] = b""
                clean_img.save(save_path, format=image_format, **save_kwargs)

            QMessageBox.information(self, "Success", f"Saved metadata-stripped image:\n{save_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Strip Failed", f"Could not strip metadata: {exc}")

class XcopyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.source_paths: list[str] = []
        self.destination_path = ""

        layout = QVBoxLayout()
        info_label = QLabel("Add one or more files/folders, choose a destination, then run XCOPY.")
        layout.addWidget(info_label)

        source_buttons = QHBoxLayout()
        add_files_button = QPushButton("Add Files")
        add_files_button.clicked.connect(self.add_files)
        source_buttons.addWidget(add_files_button)

        add_folder_button = QPushButton("Add Folder")
        add_folder_button.clicked.connect(self.add_folder)
        source_buttons.addWidget(add_folder_button)

        clear_sources_button = QPushButton("Clear Sources")
        clear_sources_button.clicked.connect(self.clear_sources)
        source_buttons.addWidget(clear_sources_button)
        layout.addLayout(source_buttons)

        self.sources_label = QLabel("Sources: 0 selected")
        layout.addWidget(self.sources_label)

        self.sources_text = QTextEdit()
        self.sources_text.setReadOnly(True)
        self.sources_text.setPlaceholderText("Selected files/folders will appear here.")
        layout.addWidget(self.sources_text)

        destination_row = QHBoxLayout()
        self.destination_input = QLineEdit()
        destination_row.addWidget(self.destination_input)
        destination_button = QPushButton("Choose Destination")
        destination_button.clicked.connect(self.choose_destination)
        destination_row.addWidget(destination_button)
        layout.addLayout(destination_row)

        self.run_as_admin_checkbox = QCheckBox("Run with administrator privileges")
        layout.addWidget(self.run_as_admin_checkbox)

        run_button = QPushButton("Run XCOPY")
        run_button.clicked.connect(self.run_xcopy)
        layout.addWidget(run_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0 / 0")
        layout.addWidget(self.progress_bar)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("XCOPY output will appear here.")
        layout.addWidget(self.output_text)

        self.setLayout(layout)

    def add_files(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", get_default_output_dir(), "All Files (*)")
        if not file_paths:
            return
        self._add_source_paths(file_paths)

    def add_folder(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder", get_default_output_dir())
        if not folder_path:
            return
        self._add_source_paths([folder_path])

    def clear_sources(self) -> None:
        self.source_paths = []
        self._refresh_sources_display()

    def choose_destination(self) -> None:
        destination = QFileDialog.getExistingDirectory(self, "Select Destination Folder", get_default_output_dir())
        if not destination:
            return
        self.destination_path = destination
        self.destination_input.setText(destination)

    def run_xcopy(self) -> None:
        if not self.source_paths:
            QMessageBox.warning(self, "No Sources", "Add at least one source file or folder.")
            return

        destination = self.destination_input.text().strip()
        if not destination:
            QMessageBox.warning(self, "No Destination", "Select a destination folder.")
            return

        if not os.path.isdir(destination):
            QMessageBox.warning(self, "Invalid Destination", "Destination folder does not exist.")
            return

        missing_paths = [path for path in self.source_paths if not os.path.exists(path)]
        if missing_paths:
            QMessageBox.warning(self, "Missing Sources", "Some selected sources no longer exist:\n" + "\n".join(missing_paths))
            return

        self.output_text.clear()
        commands = [self._build_xcopy_command(source, destination) for source in self.source_paths]
        self._update_progress(0, len(commands))

        if self.run_as_admin_checkbox.isChecked():
            self._run_xcopy_as_admin(commands)
        else:
            self._run_xcopy_standard(commands)

    def _add_source_paths(self, new_paths: list[str]) -> None:
        existing = set(self.source_paths)
        for path in new_paths:
            if path not in existing:
                self.source_paths.append(path)
                existing.add(path)
        self._refresh_sources_display()

    def _refresh_sources_display(self) -> None:
        self.sources_label.setText(f"Sources: {len(self.source_paths)} selected")
        self.sources_text.setPlainText("\n".join(self.source_paths))

    def _build_xcopy_command(self, source_path: str, destination_root: str) -> str:
        source_path = self._to_windows_path(source_path)
        destination_root = self._to_windows_path(destination_root)
        source_is_dir = os.path.isdir(source_path)

        if source_is_dir:
            source_name = os.path.basename(os.path.normpath(source_path))
            destination_path = self._to_windows_path(os.path.join(destination_root, source_name))
            source_arg = self._to_windows_path(os.path.join(source_path, "*"))
            destination_arg = self._ensure_trailing_backslash(destination_path)
            options = ["/E", "/Y", "/I", "/H", "/R", "/C", "/K"]
        else:
            source_arg = source_path
            destination_arg = self._ensure_trailing_backslash(destination_root)
            options = ["/Y", "/H", "/R", "/C", "/K"]

        options_text = " ".join(options)
        return f"xcopy {self._quote_for_cmd(source_arg)} {self._quote_for_cmd(destination_arg)} {options_text}"

    def _run_xcopy_standard(self, commands: list[str]) -> None:
        success_count = 0
        warning_count = 0
        total_commands = len(commands)

        QApplication.processEvents()
        for index, command in enumerate(commands, start=1):
            result = subprocess.run(command, capture_output=True, text=True, shell=True, **get_subprocess_kwargs())
            output = (result.stdout or "") + (result.stderr or "")
            display_output = output.strip() if output.strip() else "(no output)"
            self.output_text.append(display_output)
            self.output_text.append("")

            if result.returncode == 1:
                success_count += 1
            elif result.returncode == 0:
                warning_count += 1
            else:
                self._update_progress(index, total_commands)
                QMessageBox.critical(self, "XCOPY Failed", f"Command failed with exit code {result.returncode}:\n{command}")
                return

            self._update_progress(index, total_commands)
            QApplication.processEvents()

        if warning_count:
            QMessageBox.information(
                self,
                "XCOPY Completed With Notes",
                f"{success_count} command(s) copied files. {warning_count} command(s) reported nothing to copy.",
            )
        else:
            QMessageBox.information(self, "XCOPY Complete", "All copy operations completed successfully.")

    def _run_xcopy_as_admin(self, commands: list[str]) -> None:
        combined_commands = " & ".join(commands)
        parameters = f"/c {combined_commands}"

        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("Running elevated XCOPY...")
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", parameters, None, 1)
        self.progress_bar.setRange(0, 1)

        if result <= 32:
            self.progress_bar.setValue(0)
            QMessageBox.warning(self, "Elevation Cancelled", "Administrator launch was cancelled or failed.")
        else:
            self.output_text.append("Started elevated XCOPY command window.")
            QMessageBox.information(self, "XCOPY Started", "XCOPY is running in an elevated command window.")

    def _update_progress(self, completed: int, total: int) -> None:
        total = max(1, int(total))
        completed = max(0, min(int(completed), total))
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(completed)
        self.progress_bar.setFormat(f"{completed} / {total}")

    def _quote_for_cmd(self, value: str) -> str:
        escaped = value.replace('"', '""')
        return f'"{escaped}"'

    def _to_windows_path(self, value: str) -> str:
        return os.path.normpath(value).replace("/", "\\")

    def _ensure_trailing_backslash(self, value: str) -> str:
        return value if value.endswith("\\") else value + "\\"
