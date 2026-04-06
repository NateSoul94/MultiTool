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
import platform
import shutil
import subprocess
import sys

def get_subprocess_kwargs() -> dict:
    """Return kwargs to hide subprocess console windows on Windows."""
    if platform.system() == "Windows":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}

def find_ff_tool(tool_name: str) -> str | None:
    executable_name = f"{tool_name}.exe"
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    local_candidates = [
        os.path.join(app_dir, executable_name),
        os.path.join(app_dir, "bin", executable_name),
        os.path.join(app_dir, "ffmpeg", "bin", executable_name),
    ]
    for candidate in local_candidates:
        if os.path.isfile(candidate):
            return candidate

    try:
        for item in os.listdir(app_dir):
            candidate = os.path.join(app_dir, item, "bin", executable_name)
            if os.path.isfile(candidate):
                return candidate
    except Exception:
        pass

    return shutil.which(executable_name) or shutil.which(tool_name)

def format_seconds(value: int | float) -> str:
    total_seconds = int(max(0, value))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def parse_hhmmss(value: str) -> int | None:
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
    except ValueError:
        return None
    if hours < 0 or minutes < 0 or seconds < 0 or minutes > 59 or seconds > 59:
        return None
    return hours * 3600 + minutes * 60 + seconds

def get_default_output_dir() -> str:
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    return desktop_dir if os.path.isdir(desktop_dir) else os.path.expanduser("~")

def find_idm_executable() -> str | None:
    candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Internet Download Manager", "IDMan.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Internet Download Manager", "IDMan.exe"),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "IDMan.exe"),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "bin", "IDMan.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return shutil.which("IDMan.exe")

def sanitize_file_name(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    cleaned = "".join("_" if char in invalid_chars else char for char in name).strip()
    return cleaned or "download"

def build_ytdlp_common_args() -> list[str]:
    args = ["--encoding", "utf-8", "--ignore-config", "--no-js-runtimes"]
    runtime_names = ["deno", "node", "quickjs", "bun"]

    for runtime_name in runtime_names:
        runtime_path = find_ff_tool(runtime_name)
        if runtime_path:
            args.extend(["--js-runtimes", f"{runtime_name}:{runtime_path}"])

    if not any(arg == "--js-runtimes" for arg in args):
        args.extend(["--js-runtimes", "deno"])

    return args

def build_ytdlp_error_message(stderr: str, fallback_message: str) -> str:
    details = (stderr or "").strip() or fallback_message
    lower = details.lower()
    notes: list[str] = []

    if "no supported javascript runtime could be found" in lower or "youtube extraction without a js runtime has been deprecated" in lower:
        notes.append("Install Node.js, then restart this app. yt-dlp is configured to try node, deno, and bun.")

    if "this video is not available" in lower:
        notes.append("The video may be private, removed, region-restricted, age-restricted, or blocked for your account.")

    if "challenge solving failed" in lower:
        notes.append("yt-dlp could reach YouTube, but challenge solving was incomplete. Try enabling browser cookies and loading formats again.")

    if "requested format is not available" in lower:
        notes.append("The selected format may no longer be valid for this session. Reload formats before downloading.")

    if notes:
        return details + "\n\n" + "\n".join(notes)
    return details
