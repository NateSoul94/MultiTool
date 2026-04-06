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
import re
import subprocess
from urllib.parse import quote

import qrcode
from qrcode.image.svg import SvgImage
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..helpers import get_default_output_dir, get_subprocess_kwargs

class QRCodeWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("Enter or paste the URL here")
        layout.addWidget(self.url_input)

        self.paste_button = QPushButton("Paste", self)
        self.paste_button.clicked.connect(self.paste_url)
        layout.addWidget(self.paste_button)

        self.circle_checkbox = QCheckBox("Circles instead of squares", self)
        layout.addWidget(self.circle_checkbox)

        self.generate_button = QPushButton("Generate and Save QR Code", self)
        self.generate_button.clicked.connect(self.generate_and_save_qr_code)
        layout.addWidget(self.generate_button)

        self.setLayout(layout)

    def paste_url(self) -> None:
        clipboard = QApplication.clipboard()
        self.url_input.setText(clipboard.text())

    def _is_in_finder_area(self, row: int, col: int, border: int, matrix_size: int) -> bool:
        finder_size = 7
        finder_origins = [
            (border, border),
            (matrix_size - border - finder_size, border),
            (border, matrix_size - border - finder_size),
        ]
        for origin_col, origin_row in finder_origins:
            if origin_row <= row < origin_row + finder_size and origin_col <= col < origin_col + finder_size:
                return True
        return False

    def _build_circle_style_svg(self, qr, module_size: int = 10) -> str:
        matrix = qr.get_matrix()
        matrix_size = len(matrix)
        total_size = matrix_size * module_size
        border = qr.border

        circles: list[str] = []
        module_radius = module_size * 0.42
        for row in range(matrix_size):
            for col in range(matrix_size):
                if matrix[row][col] and not self._is_in_finder_area(row, col, border, matrix_size):
                    center_x = (col + 0.5) * module_size
                    center_y = (row + 0.5) * module_size
                    circles.append(
                        f'<circle cx="{center_x:.3f}" cy="{center_y:.3f}" r="{module_radius:.3f}" fill="#000000" />'
                    )

        finder_size = 7
        finder_origins = [
            (border, border),
            (matrix_size - border - finder_size, border),
            (border, matrix_size - border - finder_size),
        ]
        finders: list[str] = []
        for origin_col, origin_row in finder_origins:
            center_x = (origin_col + 3.5) * module_size
            center_y = (origin_row + 3.5) * module_size
            outer_radius = 3.5 * module_size
            middle_radius = 2.5 * module_size
            inner_radius = 1.5 * module_size
            finders.append(f'<circle cx="{center_x:.3f}" cy="{center_y:.3f}" r="{outer_radius:.3f}" fill="#000000" />')
            finders.append(f'<circle cx="{center_x:.3f}" cy="{center_y:.3f}" r="{middle_radius:.3f}" fill="#FFFFFF" />')
            finders.append(f'<circle cx="{center_x:.3f}" cy="{center_y:.3f}" r="{inner_radius:.3f}" fill="#000000" />')

        svg_content = [
            f'<svg width="{total_size}" height="{total_size}" viewBox="0 0 {total_size} {total_size}" xmlns="http://www.w3.org/2000/svg">',
            #f'<rect width="{total_size}" height="{total_size}" fill="#FFFFFF" />',
            *circles,
            *finders,
            "</svg>",
        ]
        return "\n".join(svg_content)

    def generate_and_save_qr_code(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a URL.")
            return

        use_styled_qr = self.circle_checkbox.isChecked()
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save QR Code",
            os.path.join(get_default_output_dir(), "qrcode.svg"),
            "SVG Files (*.svg)",
        )
        if not save_path:
            return
        if not save_path.lower().endswith(".svg"):
            save_path += ".svg"

        try:
            if use_styled_qr:
                qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
                qr.add_data(url)
                qr.make(fit=True)
                svg_text = self._build_circle_style_svg(qr)
                with open(save_path, "w", encoding="utf-8") as file:
                    file.write(svg_text)
            else:
                img = qrcode.make(url, image_factory=SvgImage)
                with open(save_path, "wb") as file:
                    img.save(file)

            QMessageBox.information(self, "Success", f"QR code saved to: {save_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to generate QR code: {exc}")

class WhatsAppQRCodeWidget(QRCodeWidget):
    def __init__(self):
        QWidget.__init__(self)
        layout = QVBoxLayout()

        self.phone_input = QLineEdit(self)
        self.phone_input.setPlaceholderText("Phone number with country code (e.g. 96512345678)")
        self.phone_input.textChanged.connect(self._refresh_url_preview)
        layout.addWidget(self.phone_input)

        self.message_input = QLineEdit(self)
        self.message_input.setPlaceholderText("Optional message text")
        self.message_input.textChanged.connect(self._refresh_url_preview)
        layout.addWidget(self.message_input)

        self.url_preview = QLineEdit(self)
        self.url_preview.setReadOnly(True)
        self.url_preview.setPlaceholderText("WhatsApp URL preview will appear here")
        layout.addWidget(self.url_preview)

        self.circle_checkbox = QCheckBox("Circles instead of squares", self)
        layout.addWidget(self.circle_checkbox)

        self.generate_button = QPushButton("Generate and Save WhatsApp QR Code", self)
        self.generate_button.clicked.connect(self.generate_and_save_whatsapp_qr_code)
        layout.addWidget(self.generate_button)

        self.setLayout(layout)
        self._refresh_url_preview()

    def _build_whatsapp_url(self):
        phone_raw = self.phone_input.text().strip()
        message_raw = self.message_input.text().strip()
        phone_digits = "".join(character for character in phone_raw if character.isdigit())
        if not phone_digits:
            return None, "Please enter a valid phone number with country code."

        url = f"https://wa.me/{phone_digits}"
        if message_raw:
            encoded_message = quote(message_raw, safe="")
            url += f"?text={encoded_message}"
        return url, None

    def _refresh_url_preview(self) -> None:
        url, error_message = self._build_whatsapp_url()
        if error_message:
            self.url_preview.clear()
        else:
            self.url_preview.setText(url)

    def generate_and_save_whatsapp_qr_code(self) -> None:
        url, error_message = self._build_whatsapp_url()
        if error_message:
            QMessageBox.warning(self, "Input Error", error_message)
            return

        use_styled_qr = self.circle_checkbox.isChecked()
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save WhatsApp QR Code",
            os.path.join(get_default_output_dir(), "whatsapp_qrcode.svg"),
            "SVG Files (*.svg)",
        )
        if not save_path:
            return
        if not save_path.lower().endswith(".svg"):
            save_path += ".svg"

        try:
            if use_styled_qr:
                qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
                qr.add_data(url)
                qr.make(fit=True)
                svg_text = self._build_circle_style_svg(qr)
                with open(save_path, "w", encoding="utf-8") as file:
                    file.write(svg_text)
            else:
                img = qrcode.make(url, image_factory=SvgImage)
                with open(save_path, "wb") as file:
                    img.save(file)

            QMessageBox.information(self, "Success", f"WhatsApp URL:\n{url}\n\nQR code saved to:\n{save_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to generate QR code: {exc}")

class WifiQRCodeWidget(QRCodeWidget):
    def __init__(self):
        QWidget.__init__(self)
        layout = QVBoxLayout()

        self.available_networks_combo = QComboBox(self)
        self.available_networks_combo.setPlaceholderText("Select detected WiFi network")
        self.available_networks_combo.currentIndexChanged.connect(self._on_network_selected)

        scan_row = QHBoxLayout()
        scan_row.addWidget(self.available_networks_combo)
        self.scan_networks_button = QPushButton("Scan Networks", self)
        self.scan_networks_button.clicked.connect(self.scan_available_networks)
        scan_row.addWidget(self.scan_networks_button)
        layout.addLayout(scan_row)

        self.ssid_input = QLineEdit(self)
        self.ssid_input.setPlaceholderText("WiFi network name (SSID)")
        self.ssid_input.textChanged.connect(self._refresh_wifi_preview)
        layout.addWidget(self.ssid_input)

        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("WiFi password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.textChanged.connect(self._refresh_wifi_preview)
        layout.addWidget(self.password_input)

        self.security_combo = QComboBox(self)
        self.security_combo.addItem("WPA/WPA2", "WPA")
        self.security_combo.addItem("WEP", "WEP")
        self.security_combo.addItem("Open (No Password)", "nopass")
        self.security_combo.currentIndexChanged.connect(self._refresh_wifi_preview)
        layout.addWidget(self.security_combo)

        self.hidden_checkbox = QCheckBox("Hidden network", self)
        self.hidden_checkbox.stateChanged.connect(self._refresh_wifi_preview)
        layout.addWidget(self.hidden_checkbox)

        self.payload_preview = QLineEdit(self)
        self.payload_preview.setReadOnly(True)
        self.payload_preview.setPlaceholderText("WiFi QR payload preview will appear here")
        layout.addWidget(self.payload_preview)

        self.circle_checkbox = QCheckBox("Circles instead of squares", self)
        layout.addWidget(self.circle_checkbox)

        self.generate_button = QPushButton("Generate and Save WiFi QR Code", self)
        self.generate_button.clicked.connect(self.generate_and_save_wifi_qr_code)
        layout.addWidget(self.generate_button)

        self.setLayout(layout)
        self.scan_available_networks()
        self._refresh_wifi_preview()

    def _on_network_selected(self) -> None:
        selected_ssid = self.available_networks_combo.currentData()
        if selected_ssid is None:
            return
        ssid_value = str(selected_ssid).strip()
        if not ssid_value:
            return
        self.ssid_input.setText(ssid_value)

    def _parse_ssids_from_netsh(self, output_text: str) -> list[str]:
        found_ssids: list[str] = []
        seen_ssids: set[str] = set()
        for line in output_text.splitlines():
            stripped = line.strip()
            match = re.match(r"SSID\s+\d+\s*:\s*(.*)", stripped)
            if not match:
                continue
            ssid = match.group(1).strip()
            if not ssid or ssid in seen_ssids:
                continue
            seen_ssids.add(ssid)
            found_ssids.append(ssid)
        return found_ssids

    def scan_available_networks(self) -> None:
        command = ["netsh", "wlan", "show", "networks", "mode=bssid"]
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", **get_subprocess_kwargs())
        if process.returncode != 0:
            QMessageBox.warning(self, "Scan Failed", "Could not read available WiFi networks on this device.")
            return

        ssids = self._parse_ssids_from_netsh(process.stdout)
        self.available_networks_combo.blockSignals(True)
        self.available_networks_combo.clear()
        self.available_networks_combo.addItem("Choose detected network...", "")
        for ssid in ssids:
            self.available_networks_combo.addItem(ssid, ssid)
        self.available_networks_combo.blockSignals(False)

        if not ssids:
            QMessageBox.information(self, "No Networks Found", "No visible WiFi networks were found. You can still type SSID manually.")

    def _escape_wifi_value(self, value: str) -> str:
        escaped = value.replace("\\", "\\\\")
        escaped = escaped.replace(";", "\\;")
        escaped = escaped.replace(",", "\\,")
        escaped = escaped.replace(":", "\\:")
        return escaped

    def _build_wifi_payload(self) -> tuple[str | None, str | None]:
        ssid = self.ssid_input.text().strip()
        password = self.password_input.text()
        security = str(self.security_combo.currentData() or "WPA")
        hidden = self.hidden_checkbox.isChecked()

        if not ssid:
            return None, "Please enter the WiFi network name (SSID)."

        if security != "nopass" and not password:
            return None, "Please enter the WiFi password, or choose Open (No Password)."

        ssid_value = self._escape_wifi_value(ssid)
        password_value = self._escape_wifi_value(password)
        hidden_value = "true" if hidden else "false"

        if security == "nopass":
            payload = f"WIFI:T:nopass;S:{ssid_value};H:{hidden_value};;"
        else:
            payload = f"WIFI:T:{security};S:{ssid_value};P:{password_value};H:{hidden_value};;"
        return payload, None

    def _refresh_wifi_preview(self) -> None:
        payload, error_message = self._build_wifi_payload()
        if error_message:
            self.payload_preview.clear()
        else:
            self.payload_preview.setText(payload)

    def generate_and_save_wifi_qr_code(self) -> None:
        payload, error_message = self._build_wifi_payload()
        if error_message:
            QMessageBox.warning(self, "Input Error", error_message)
            return

        use_styled_qr = self.circle_checkbox.isChecked()
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save WiFi QR Code",
            os.path.join(get_default_output_dir(), "wifi_qrcode.svg"),
            "SVG Files (*.svg)",
        )
        if not save_path:
            return
        if not save_path.lower().endswith(".svg"):
            save_path += ".svg"

        try:
            if use_styled_qr:
                qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
                qr.add_data(payload)
                qr.make(fit=True)
                svg_text = self._build_circle_style_svg(qr)
                with open(save_path, "w", encoding="utf-8") as file:
                    file.write(svg_text)
            else:
                img = qrcode.make(payload, image_factory=SvgImage)
                with open(save_path, "wb") as file:
                    img.save(file)

            QMessageBox.information(self, "Success", f"WiFi QR code saved to:\n{save_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to generate WiFi QR code: {exc}")
