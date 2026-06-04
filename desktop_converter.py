from __future__ import annotations

import os
import queue
import re
import shutil
import threading
from pathlib import Path
from typing import Optional

import ffmpeg
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


class DavConverterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DAV to MP4 Converter")
        self.root.geometry("700x320")
        self.root.minsize(640, 300)

        self.input_path: Optional[Path] = None
        self.output_path: Optional[Path] = None
        self.duration_seconds: float = 0.0
        self.busy = False

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        self.input_var = tk.StringVar(value="No file selected")
        self.output_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Pick a .dav file to begin.")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()
        self._check_prerequisites()
        self._poll_events()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(frame, text="DAV to MP4", font=("Helvetica", 18, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(
            frame,
            text="Lightweight desktop converter for macOS using ffmpeg-python.",
        )
        subtitle.pack(anchor="w", pady=(2, 14))

        pick_row = ttk.Frame(frame)
        pick_row.pack(fill="x")

        ttk.Label(pick_row, text="Input file:").pack(side="left")
        ttk.Button(pick_row, text="Choose .dav", command=self._choose_input).pack(side="right")

        ttk.Label(frame, textvariable=self.input_var, wraplength=660).pack(anchor="w", pady=(8, 8))

        ttk.Label(frame, text="Output file:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.output_var, state="readonly").pack(fill="x", pady=(4, 10))

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x")

        self.convert_btn = ttk.Button(button_row, text="Convert to MP4", command=self._start_convert)
        self.convert_btn.pack(side="left")

        self.open_btn = ttk.Button(button_row, text="Open Output Folder", command=self._open_output_folder)
        self.open_btn.pack(side="left", padx=(8, 0))

        self.reset_btn = ttk.Button(button_row, text="Reset", command=self._reset)
        self.reset_btn.pack(side="left", padx=(8, 0))

        ttk.Progressbar(
            frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
            length=640,
        ).pack(fill="x", pady=(14, 8))

        ttk.Label(frame, textvariable=self.status_var, wraplength=660).pack(anchor="w")

    def _check_prerequisites(self) -> None:
        if shutil.which("ffmpeg") is None:
            messagebox.showerror(
                "ffmpeg not found",
                "ffmpeg binary is not installed or not in PATH.\nInstall with: brew install ffmpeg",
            )
            self.convert_btn.config(state="disabled")

    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select DAV file",
            filetypes=[("DAV files", "*.dav"), ("All files", "*.*")],
        )
        if not path:
            return

        selected = Path(path)
        if selected.suffix.lower() != ".dav":
            messagebox.showwarning("Unsupported file", "Please select a .dav file.")
            return

        self.input_path = selected
        self.output_path = selected.with_name(f"{selected.stem}_converted.mp4")
        self.input_var.set(str(self.input_path))
        self.output_var.set(str(self.output_path))
        self.status_var.set("Ready to convert.")
        self.progress_var.set(0)

    def _set_busy(self, is_busy: bool) -> None:
        self.busy = is_busy
        state = "disabled" if is_busy else "normal"
        self.convert_btn.config(state=state)
        self.reset_btn.config(state=state)

    def _start_convert(self) -> None:
        if self.busy:
            return
        if self.input_path is None or self.output_path is None:
            messagebox.showinfo("No file", "Choose a .dav file first.")
            return

        if self.output_path.exists():
            if not messagebox.askyesno("Overwrite?", f"Overwrite existing file?\n{self.output_path}"):
                return

        self._set_busy(True)
        self.progress_var.set(1)
        self.status_var.set("Reading metadata...")

        worker = threading.Thread(target=self._convert_worker, daemon=True)
        worker.start()

    def _convert_worker(self) -> None:
        assert self.input_path is not None
        assert self.output_path is not None

        try:
            self.duration_seconds = self._probe_duration(self.input_path)
            success = self._run_convert(with_audio=True)
            if not success:
                self.events.put(("status", "Audio stream conversion failed. Retrying without audio..."))
                success = self._run_convert(with_audio=False)

            if success:
                self.events.put(("progress", 100.0))
                self.events.put(("done", (True, f"Done. Saved to: {self.output_path}")))
            else:
                self.events.put(("done", (False, "Conversion failed. File may be encrypted or damaged.")))
        except Exception as exc:  # noqa: BLE001
            self.events.put(("done", (False, f"Conversion failed: {exc}")))

    def _probe_duration(self, input_path: Path) -> float:
        try:
            probe = ffmpeg.probe(str(input_path))
            return float(probe.get("format", {}).get("duration", 0) or 0)
        except Exception:
            return 0.0

    def _run_convert(self, with_audio: bool) -> bool:
        assert self.input_path is not None
        assert self.output_path is not None

        in_stream = ffmpeg.input(str(self.input_path))
        output_kwargs = {
            "vcodec": "libx264",
            "preset": "veryfast",
            "crf": 23,
            "pix_fmt": "yuv420p",
            "movflags": "+faststart",
        }

        if with_audio:
            output_kwargs["acodec"] = "aac"
            output_kwargs["audio_bitrate"] = "96k"
        else:
            output_kwargs["an"] = None

        process = (
            ffmpeg.output(in_stream, str(self.output_path), **output_kwargs)
            .global_args("-y")
            .run_async(pipe_stdout=True, pipe_stderr=True)
        )

        self.events.put(("status", "Converting..."))

        while True:
            line = process.stderr.readline()
            if not line:
                break

            text = line.decode("utf-8", errors="replace")
            match = TIME_RE.search(text)
            if match and self.duration_seconds > 0:
                hours, minutes, seconds = match.groups()
                current = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                pct = min((current / self.duration_seconds) * 100, 99)
                self.events.put(("progress", pct))

        return process.wait() == 0

    def _open_output_folder(self) -> None:
        target = self.output_path or self.input_path
        if target is None:
            return
        folder = target.parent
        self.root.tk.call("tk::mac::OpenDocument", str(folder))

    def _reset(self) -> None:
        if self.busy:
            return
        self.input_path = None
        self.output_path = None
        self.duration_seconds = 0
        self.input_var.set("No file selected")
        self.output_var.set("")
        self.status_var.set("Pick a .dav file to begin.")
        self.progress_var.set(0)

    def _poll_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if event == "status":
                self.status_var.set(str(payload))
            elif event == "progress":
                self.progress_var.set(float(payload))
            elif event == "done":
                success, message = payload  # type: ignore[misc]
                self.status_var.set(str(message))
                self._set_busy(False)
                if not success:
                    messagebox.showerror("Conversion failed", str(message))

        self.root.after(100, self._poll_events)


def main() -> None:
    root = tk.Tk()
    # Use native Tk theme where available for simple, familiar controls.
    try:
        ttk.Style().theme_use("aqua")
    except tk.TclError:
        pass

    DavConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
