#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Downloader GUI in the same style as the provided PDF editor:
- ttkbootstrap (theme: flatly)
- Paste a YouTube URL
- Choose output format: mp3, wav, or mp4
- Pick a destination folder
- Download with progress + log

Requirements (install with pip):
    pip install yt-dlp ttkbootstrap pillow imageio-ffmpeg

This script will auto-detect FFmpeg:
- First tries system PATH
- If not found, tries bundled binary from imageio-ffmpeg

Tested with Python 3.10+.
"""

import os
import sys
import shutil
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from datetime import datetime

import ttkbootstrap as tb
from ttkbootstrap.constants import *

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Try to detect FFmpeg automatically
_FFMPEG_PATH = shutil.which("ffmpeg")
if _FFMPEG_PATH is None:
    try:
        import imageio_ffmpeg
        _FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        _FFMPEG_PATH = None


class YouTubeDownloaderApp:
    def __init__(self):
        self.root = tb.Window(
            title="📥 YouTube Downloader",
            themename="flatly",
            size=(900, 600)
        )

        # State
        self.downloading = False
        self.stop_flag = False
        self.current_total_bytes = None

        self._build_ui()
        self._check_dependencies()
        self.root.mainloop()

    # ---------------------- UI ---------------------- #
    def _build_ui(self):
        # Top controls
        top = tb.Frame(self.root, padding=10)
        top.pack(fill=X)

        # URL input
        url_lbl = tb.Label(top, text="YouTube Link:")
        url_lbl.pack(side=LEFT)
        self.url_var = tk.StringVar()
        self.url_entry = tb.Entry(top, textvariable=self.url_var, width=60)
        self.url_entry.pack(side=LEFT, padx=8)

        # Format chooser
        fmt_lbl = tb.Label(top, text="Format:")
        fmt_lbl.pack(side=LEFT, padx=(8, 2))
        self.format_var = tk.StringVar(value="mp3")
        self.format_combo = tb.Combobox(top, values=["mp3", "wav", "mp4"], textvariable=self.format_var, state="readonly", width=6)
        self.format_combo.pack(side=LEFT)

        # Destination chooser
        dest_btn = tb.Button(top, text="Choose Folder", bootstyle="secondary", command=self._choose_folder)
        dest_btn.pack(side=LEFT, padx=8)
        self.dest_var = tk.StringVar(value=os.path.expanduser("~"))
        self.dest_label = tb.Label(top, textvariable=self.dest_var, bootstyle="secondary")
        self.dest_label.pack(side=LEFT, padx=(0, 8))

        # Download button
        self.dl_btn = tb.Button(top, text="Download", bootstyle="success", command=self._start_download, width=12)
        self.dl_btn.pack(side=LEFT, padx=4)

        # Clear log button
        tb.Button(top, text="Clear Log", bootstyle="warning", command=self._clear_log, width=10).pack(side=LEFT, padx=4)

        # Middle section: progress + log
        mid = tb.Frame(self.root, padding=(10, 0, 10, 10))
        mid.pack(fill=BOTH, expand=True)

        # Progress group
        prog_group = tb.LabelFrame(mid, text="Progress", padding=10)
        prog_group.pack(fill=X)

        self.progress = tb.Progressbar(prog_group, orient=HORIZONTAL, mode="determinate")
        self.progress.pack(fill=X)

        self.status_var = tk.StringVar(value="Idle")
        self.status_lbl = tb.Label(prog_group, textvariable=self.status_var)
        self.status_lbl.pack(anchor=W, pady=(6, 0))

        # Log group
        log_group = tb.LabelFrame(mid, text="Log", padding=10)
        log_group.pack(fill=BOTH, expand=True, pady=(10, 0))

        self.log_text = tk.Text(log_group, height=18, wrap="word", borderwidth=0)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)

        log_scroll = tb.Scrollbar(log_group, command=self.log_text.yview)
        log_scroll.pack(side=RIGHT, fill=Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        # Bottom: small tips
        bottom = tb.Frame(self.root, padding=10)
        bottom.pack(fill=X)
        tb.Label(bottom, text="Tip: Audio formats (mp3/wav) require FFmpeg. If system FFmpeg not found, bundled imageio-ffmpeg will be used.", bootstyle=INFO).pack(side=LEFT)

    def _choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_var.set(path)

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def _append_log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)

    # ---------------- Dependencies ------------------ #
    def _check_dependencies(self):
        if yt_dlp is None:
            messagebox.showerror(
                "Missing Dependency",
                "The 'yt-dlp' package is not installed.\n\nInstall with:\n    pip install yt-dlp"
            )
        if _FFMPEG_PATH is None:
            self._append_log("Warning: FFmpeg not found. MP3/WAV extraction will fail until FFmpeg is installed (system or imageio-ffmpeg).")
        else:
            self._append_log(f"FFmpeg detected: {_FFMPEG_PATH}")

    # ---------------- Download Logic ---------------- #
    def _start_download(self):
        if self.downloading:
            return

        url = self.url_var.get().strip()
        out_dir = self.dest_var.get().strip()
        fmt = self.format_var.get().strip().lower()

        if not url:
            messagebox.showerror("No URL", "Please paste a YouTube link.")
            return
        if not os.path.isdir(out_dir):
            messagebox.showerror("Invalid Folder", "Please choose a valid destination folder.")
            return
        if fmt in ("mp3", "wav") and _FFMPEG_PATH is None:
            messagebox.showerror("FFmpeg required", "FFmpeg is required for audio extraction (mp3/wav). Please install FFmpeg or pip install imageio-ffmpeg.")
            return
        if yt_dlp is None:
            messagebox.showerror("yt-dlp not installed", "Install yt-dlp first: pip install yt-dlp")
            return

        # Disable UI while running
        self.downloading = True
        self.stop_flag = False
        self.dl_btn.config(state=DISABLED)
        self.progress.configure(value=0, maximum=100)
        self.status_var.set("Starting…")
        self._append_log(f"Queued download: {url} → {fmt.upper()} in {out_dir}")

        t = threading.Thread(target=self._download_worker, args=(url, out_dir, fmt), daemon=True)
        t.start()

    def _download_worker(self, url: str, out_dir: str, fmt: str):
        def progress_hook(d):
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes')
                percent = 0
                if total and downloaded:
                    try:
                        percent = int(downloaded / total * 100)
                    except Exception:
                        percent = 0
                self.root.after(0, self._update_progress, percent, d)
            elif d.get('status') == 'finished':
                self.root.after(0, self._on_download_finished, d)

        outtmpl = os.path.join(out_dir, '%(title)s.%(ext)s')
        ydl_opts = {
            'outtmpl': outtmpl,
            'progress_hooks': [progress_hook],
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': _FFMPEG_PATH or None,
        }

        if fmt == 'mp4':
            ydl_opts.update({
                'format': 'bv*+ba/b',
                'merge_output_format': 'mp4',
                'postprocessors': [
                    {
                        'key': 'FFmpegVideoRemuxer',
                        'preferedformat': 'mp4',
                    }
                ]
            })
        else:
            codec = 'mp3' if fmt == 'mp3' else 'wav'
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': codec,
                        'preferredquality': '0',
                    }
                ]
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title') or 'video'
                self.root.after(0, self._append_log, f"Completed: {title}")
        except Exception as e:
            self.root.after(0, self._on_download_error, str(e))
        finally:
            self.root.after(0, self._reset_ui)

    # --------------- UI Update Callbacks --------------- #
    def _update_progress(self, percent: int, d: dict):
        self.progress.configure(value=max(0, min(100, percent)))
        spd = d.get('speed')
        eta = d.get('eta')
        rate = f" @ {self._human_readable_rate(spd)}" if spd else ""
        eta_txt = f" – ETA {eta}s" if eta else ""
        self.status_var.set(f"Downloading… {percent}%{rate}{eta_txt}")

        if percent % 5 == 0:
            self._append_log(self.status_var.get())

    def _on_download_finished(self, d: dict):
        filename = d.get('filename') or 'output'
        self.status_var.set("Post-processing…")
        self._append_log(f"Downloaded to: {filename}")

    def _on_download_error(self, err: str):
        self.status_var.set("Error")
        self._append_log(f"ERROR: {err}")
        messagebox.showerror("Download Error", err)

    def _reset_ui(self):
        self.downloading = False
        self.dl_btn.config(state=NORMAL)
        if not self.status_var.get().startswith("Error"):
            self.status_var.set("Done")

    # ----------------- Helpers ----------------- #
    @staticmethod
    def _human_readable_rate(bps):
        if not bps:
            return ""
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        i = 0
        rate = float(bps)
        while rate >= 1024 and i < len(units) - 1:
            rate /= 1024.0
            i += 1
        return f"{rate:.1f} {units[i]}"


if __name__ == '__main__':
    YouTubeDownloaderApp()
