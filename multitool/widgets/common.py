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

from PyQt6.QtCore import QRect, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QProgressBar, QWidget


class ProgressBarMixin:
    def _init_progress_bar(self, layout, idle_text: str = "Ready") -> None:
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(idle_text)
        layout.addWidget(self.progress_bar)

    def _set_progress_idle(self, text: str = "Ready") -> None:
        if not hasattr(self, "progress_bar"):
            return
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(text)

    def _set_progress_busy(self, text: str = "Working...") -> None:
        if not hasattr(self, "progress_bar"):
            return
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat(text)

    def _set_progress_complete(self, text: str = "Done") -> None:
        if not hasattr(self, "progress_bar"):
            return
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(text)

    def _set_progress_step(self, completed: int, total: int, text: str | None = None) -> None:
        if not hasattr(self, "progress_bar"):
            return
        total = max(1, int(total))
        completed = max(0, min(int(completed), total))
        percent = int(round((completed / total) * 100))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(text or f"{percent}%")


class DualHandleSlider(QWidget):
    rangeChanged = pyqtSignal(int, int)
    handleDragged = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 0
        self._start = 0
        self._end = 0
        self._active_handle = None
        self.setMinimumHeight(36)

    def setRange(self, minimum_value: int, maximum_value: int) -> None:
        self._minimum = int(minimum_value)
        self._maximum = int(maximum_value)
        self._start = max(self._minimum, min(self._start, self._maximum))
        self._end = max(self._start, min(self._end, self._maximum))
        self.update()
        self.rangeChanged.emit(self._start, self._end)

    def setValues(self, start_value: int, end_value: int) -> None:
        start_value = max(self._minimum, min(int(start_value), self._maximum))
        end_value = max(start_value, min(int(end_value), self._maximum))
        changed = (start_value != self._start) or (end_value != self._end)
        self._start = start_value
        self._end = end_value
        self.update()
        if changed:
            self.rangeChanged.emit(self._start, self._end)

    def startValue(self) -> int:
        return self._start

    def endValue(self) -> int:
        return self._end

    def _value_to_pos(self, value: int) -> int:
        left = 12
        right = max(left + 1, self.width() - 12)
        if self._maximum <= self._minimum:
            return left
        ratio = (value - self._minimum) / (self._maximum - self._minimum)
        return int(left + ratio * (right - left))

    def _pos_to_value(self, position: int) -> int:
        left = 12
        right = max(left + 1, self.width() - 12)
        position = max(left, min(position, right))
        if right == left or self._maximum <= self._minimum:
            return self._minimum
        ratio = (position - left) / (right - left)
        return int(round(self._minimum + ratio * (self._maximum - self._minimum)))

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        center_y = self.height() // 2
        left = 12
        right = max(left + 1, self.width() - 12)
        base_rect = QRect(left, center_y - 3, right - left, 6)
        painter.setPen(QPen(QColor(140, 140, 140), 1))
        painter.setBrush(QBrush(QColor(160, 160, 160)))
        painter.drawRoundedRect(base_rect, 3, 3)

        start_pos = self._value_to_pos(self._start)
        end_pos = self._value_to_pos(self._end)
        selected_rect = QRect(start_pos, center_y - 4, max(2, end_pos - start_pos), 8)
        painter.setPen(QPen(QColor(64, 132, 255), 1))
        painter.setBrush(QBrush(QColor(64, 132, 255)))
        painter.drawRoundedRect(selected_rect, 4, 4)

        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.setBrush(QBrush(QColor(245, 245, 245)))
        painter.drawEllipse(start_pos - 7, center_y - 7, 14, 14)
        painter.drawEllipse(end_pos - 7, center_y - 7, 14, 14)
        painter.end()

    def mousePressEvent(self, event) -> None:
        click_x = int(event.position().x())
        start_pos = self._value_to_pos(self._start)
        end_pos = self._value_to_pos(self._end)
        self._active_handle = "start" if abs(click_x - start_pos) <= abs(click_x - end_pos) else "end"
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self._active_handle:
            return
        value = self._pos_to_value(int(event.position().x()))
        if self._active_handle == "start":
            self.setValues(min(value, self._end), self._end)
            self.handleDragged.emit("start", self._start)
        else:
            self.setValues(self._start, max(value, self._start))
            self.handleDragged.emit("end", self._end)

    def mouseReleaseEvent(self, event) -> None:
        del event
        self._active_handle = None
    