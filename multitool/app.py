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
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .widgets.conversion import (
    AviConvertWidget,
    JpegConvertWidget,
    IcoConvertWidget,
    MovConvertWidget,
    Mp3ConvertWidget,
    Mp4ConvertWidget,
    PngConvertWidget,
    FullFrameExtractWidget,
    WebmConvertWidget,
    WebpConvertWidget,
    WmvConvertWidget,
)
from .widgets.downloads import YtDlpPlaylistWidget, YtDlpSingleWidget
from .widgets.qr import QRCodeWidget, WhatsAppQRCodeWidget, WifiQRCodeWidget
from .widgets.system_tools import ExifMetadataWidget, XcopyWidget
from .widgets.video_tools import SingleFrameExtractWidget, MkvCreateWidget, MkvExtractWidget, ResolutionToolWidget, TrimExportWidget, VideoStitchWidget

class ToolsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiTool - A collection of useful utilities")
        self.setGeometry(100, 100, 900, 620)
        self._has_centered_once = False

        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        icon_path = os.path.join(app_dir, "Assets", "icon.ico")
        self.setWindowIcon(QIcon(icon_path))

        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(8, 8, 8, 8)

        self.tab_widget = QTabWidget()

        # QR tab
        qr_page, _ = self._make_tab_page([
            (QRCodeWidget(), "URL"),
            (WhatsAppQRCodeWidget(), "Whatsapp"),
            (WifiQRCodeWidget(), "WiFi"),
        ])
        self.tab_widget.addTab(qr_page, "QR")

        # Image tab
        image_page, _ = self._make_tab_page_rows([
            [
                (IcoConvertWidget(), "ICO"),
                (PngConvertWidget(), "PNG"),
                (JpegConvertWidget(), "JPEG"),
                (WebpConvertWidget(), "WEBP"),
                (ExifMetadataWidget(), "EXIF"),
            ],
            [
                (SingleFrameExtractWidget(), "Single Frame Extraction"),
                (FullFrameExtractWidget(), "Full Frame Extraction"),
            ],
        ])
        self.tab_widget.addTab(image_page, "Image")

        # Video tab
        video_page, _ = self._make_tab_page_rows([
            [
                (Mp3ConvertWidget(), "MP3"),
                (Mp4ConvertWidget(), "MP4"),
                (AviConvertWidget(), "AVI"),
                (MovConvertWidget(), "MOV"),
                (WmvConvertWidget(), "WMV"),
                (WebmConvertWidget(), "WEBM"),
                (TrimExportWidget(), "Trim"),
                (VideoStitchWidget(), "Stitch"),
                (ResolutionToolWidget(), "Resolution"),
            ],
            [
                (MkvExtractWidget(), "MKV Extract"),
                (MkvCreateWidget(), "MKV Create"),
            ],
        ])
        self.tab_widget.addTab(video_page, "Video")

        # YouTube tab
        youtube_page, _ = self._make_tab_page([
            (YtDlpSingleWidget(), "Video Downloader"),
            (YtDlpPlaylistWidget(), "Playlist Downloader"),
        ])
        self.tab_widget.addTab(youtube_page, "Downloader")

        # System tab
        system_page, _ = self._make_tab_page([
            (XcopyWidget(), "XCOPY"),
        ])
        self.tab_widget.addTab(system_page, "System")

        self.central_layout.addWidget(self.tab_widget)
        self.setCentralWidget(self.central_widget)

    def _make_tab_page(self, tools: list[tuple[QWidget, str]]) -> tuple[QWidget, list[QPushButton]]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        stack = QStackedWidget()
        buttons: list[QPushButton] = []

        for widget, title in tools:
            index = stack.addWidget(widget)
            btn = QPushButton(title)
            btn.setCheckable(True)
            btn.clicked.connect(
                lambda _checked=False, i=index, s=stack, bl=buttons: self._set_stack_index(s, bl, i)
            )
            btn_row.addWidget(btn)
            buttons.append(btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addWidget(stack)

        if buttons:
            self._set_stack_index(stack, buttons, 0)

        return page, buttons

    def _make_tab_page_rows(self, tool_rows: list[list[tuple[QWidget, str]]]) -> tuple[QWidget, list[QPushButton]]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        stack = QStackedWidget()
        buttons: list[QPushButton] = []

        for tools in tool_rows:
            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)
            for widget, title in tools:
                index = stack.addWidget(widget)
                btn = QPushButton(title)
                btn.setCheckable(True)
                btn.clicked.connect(
                    lambda _checked=False, i=index, s=stack, bl=buttons: self._set_stack_index(s, bl, i)
                )
                btn_row.addWidget(btn)
                buttons.append(btn)
            btn_row.addStretch(1)
            layout.addLayout(btn_row)

        layout.addWidget(stack)

        if buttons:
            self._set_stack_index(stack, buttons, 0)

        return page, buttons

    def _set_stack_index(self, stack: QStackedWidget, buttons: list[QPushButton], index: int) -> None:
        stack.setCurrentIndex(index)
        for i, btn in enumerate(buttons):
            is_active = i == index
            btn.setChecked(is_active)
            btn.setStyleSheet("font-weight: 600;" if is_active else "")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_centered_once:
            self._center_on_screen()
            self._has_centered_once = True

    def _center_on_screen(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

def run_app() -> int:
    app = QApplication(sys.argv)
    window = ToolsApp()
    window.show()
    return app.exec()
