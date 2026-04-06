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

from .common import DualHandleSlider
from .conversion import (
    JpegConvertWidget, IcoConvertWidget, PngConvertWidget, WebpConvertWidget,
    AviConvertWidget, MovConvertWidget, Mp3ConvertWidget, Mp4ConvertWidget, WebmConvertWidget, WmvConvertWidget
)
from .downloads import YtDlpPlaylistWidget, YtDlpSingleWidget
from .qr import QRCodeWidget, WhatsAppQRCodeWidget, WifiQRCodeWidget
from .system_tools import ExifMetadataWidget, XcopyWidget
from .video_tools import MkvExtractWidget, MkvCreateWidget, ResolutionToolWidget, TrimExportWidget, VideoStitchWidget
