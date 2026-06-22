#!/usr/bin/env python3
"""Serve local debug endpoints for Mac camera preview and capture.

The iOS Simulator does not provide the same hardware camera path as a physical
iPhone. This bridge gives the Flutter debug build a localhost-only way to show
live host Mac camera frames and take a JPEG with AVFoundation through ffmpeg.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import tempfile
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Sequence
from urllib.parse import parse_qs, urlparse


LOGGER = logging.getLogger("dev_mac_camera_bridge")
JPEG_START = b"\xff\xd8"
JPEG_END = b"\xff\xd9"


class CaptureError(RuntimeError):
    """Raised when ffmpeg cannot return a usable camera image."""


class LiveFrameBuffer:
    """Keeps a live ffmpeg camera stream and exposes the latest JPEG frame."""

    def __init__(
        self,
        *,
        ffmpeg_bin: str,
        device: str,
        fps: int,
        width: int,
    ) -> None:
        """Create the live frame buffer.

        Args:
            ffmpeg_bin: Path or command name for ffmpeg.
            device: ffmpeg AVFoundation video device index or name.
            fps: Target preview frames per second.
            width: Preview JPEG width. Height is derived by ffmpeg.
        """

        self._ffmpeg_bin = ffmpeg_bin
        self._device = device
        self._fps = fps
        self._width = width
        self._condition = threading.Condition()
        self._latest_frame: bytes | None = None
        self._latest_frame_at = 0.0
        self._frame_id = 0
        self._process: subprocess.Popen[bytes] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._closed = False

    def start(self) -> None:
        """Start ffmpeg if it is not already streaming."""

        with self._condition:
            if self._closed:
                raise CaptureError("camera preview is closed")
            if self._process is not None and self._process.poll() is None:
                return
            self._latest_frame = None
            self._latest_frame_at = 0.0
            command = [
                self._ffmpeg_bin,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "avfoundation",
                "-framerate",
                str(self._fps),
                "-pixel_format",
                "nv12",
                "-i",
                _avfoundation_input(self._device),
                "-an",
                "-vf",
                f"scale={self._width}:-2",
                "-q:v",
                "5",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "-",
            ]
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._reader_thread = threading.Thread(
                target=self._read_stdout,
                name="lemon-mac-camera-preview-reader",
                daemon=True,
            )
            self._stderr_thread = threading.Thread(
                target=self._drain_stderr,
                name="lemon-mac-camera-preview-stderr",
                daemon=True,
            )
            self._reader_thread.start()
            self._stderr_thread.start()

    def wait_for_frame(
        self,
        timeout_seconds: float,
        *,
        after_frame_id: int | None = None,
    ) -> tuple[int, bytes]:
        """Return a frame, optionally waiting for one newer than `after_frame_id`.

        Args:
            timeout_seconds: Maximum time to wait for a usable frame.
            after_frame_id: Optional last frame id seen by the client. When
                provided, this method waits until a newer frame is available.

        Returns:
            A tuple of the monotonically increasing frame id and JPEG bytes.

        Raises:
            CaptureError: If no matching frame is available before timeout.
        """

        attempted_restart = False
        while True:
            self.start()
            deadline = time.monotonic() + timeout_seconds
            process_to_restart: subprocess.Popen[bytes] | None = None
            with self._condition:
                while self._latest_frame is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        if attempted_restart:
                            raise CaptureError("camera preview frame timed out")
                        process_to_restart = self._process
                        self._process = None
                        self._condition.notify_all()
                        attempted_restart = True
                        break
                    self._condition.wait(timeout=remaining)
                if process_to_restart is None and self._latest_frame is not None:
                    if after_frame_id is not None and self._frame_id > after_frame_id:
                        return self._frame_id, self._latest_frame
                    while after_frame_id is not None and self._frame_id <= after_frame_id:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            if attempted_restart:
                                return self._frame_id, self._latest_frame
                            process_to_restart = self._process
                            self._process = None
                            self._condition.notify_all()
                            attempted_restart = True
                            break
                        self._condition.wait(timeout=remaining)
                    if process_to_restart is None:
                        return self._frame_id, self._latest_frame
            self._terminate_process(process_to_restart)

    def latest_frame_is_fresh(self, max_age_seconds: float) -> bool:
        """Return whether the current frame is new enough for capture."""

        with self._condition:
            return (
                self._latest_frame is not None
                and time.monotonic() - self._latest_frame_at <= max_age_seconds
            )

    def stop(self) -> None:
        """Stop the live ffmpeg process."""

        with self._condition:
            self._closed = True
            process = self._process
            self._process = None
            self._condition.notify_all()
        self._terminate_process(process)

    def _terminate_process(self, process: subprocess.Popen[bytes] | None) -> None:
        """Terminate a stale ffmpeg process without touching current state."""

        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    def _read_stdout(self) -> None:
        process = self._process
        stdout = process.stdout if process is not None else None
        if stdout is None:
            return
        buffer = bytearray()
        should_restart = False
        try:
            while True:
                chunk = stdout.read(8192)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    start = buffer.find(JPEG_START)
                    if start < 0:
                        buffer.clear()
                        break
                    end = buffer.find(JPEG_END, start + len(JPEG_START))
                    if end < 0:
                        if start > 0:
                            del buffer[:start]
                        break
                    frame_end = end + len(JPEG_END)
                    frame = bytes(buffer[start:frame_end])
                    del buffer[:frame_end]
                    with self._condition:
                        self._frame_id += 1
                        self._latest_frame = frame
                        self._latest_frame_at = time.monotonic()
                        self._condition.notify_all()
        finally:
            with self._condition:
                if self._process is process:
                    self._process = None
                    should_restart = not self._closed
                self._condition.notify_all()
            if should_restart:
                time.sleep(0.1)
                try:
                    self.start()
                except CaptureError:
                    LOGGER.debug("ffmpeg preview restart failed", exc_info=True)

    def _drain_stderr(self) -> None:
        process = self._process
        stderr = process.stderr if process is not None else None
        if stderr is None:
            return
        for line in iter(stderr.readline, b""):
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                LOGGER.debug("ffmpeg preview: %s", text)


def _avfoundation_input(device: str) -> str:
    """Build the AVFoundation input selector.

    Args:
        device: ffmpeg AVFoundation video device index or name.

    Returns:
        A selector that disables audio capture to avoid microphone permission
        prompts and keep this bridge image-only.
    """

    stripped = device.strip()
    if ":" in stripped:
        return stripped
    return f"{stripped}:none"


def list_devices(ffmpeg_bin: str) -> int:
    """Print the local AVFoundation camera list from ffmpeg.

    Args:
        ffmpeg_bin: Path or command name for ffmpeg.

    Returns:
        The ffmpeg exit code. ffmpeg commonly exits non-zero after listing
        devices because no real input is opened.
    """

    completed = subprocess.run(
        [
            ffmpeg_bin,
            "-hide_banner",
            "-f",
            "avfoundation",
            "-list_devices",
            "true",
            "-i",
            "",
        ],
        check=False,
    )
    return completed.returncode


def capture_jpeg(
    *,
    ffmpeg_bin: str,
    device: str,
    timeout_seconds: float,
) -> bytes:
    """Capture one JPEG frame from the selected Mac camera.

    Args:
        ffmpeg_bin: Path or command name for ffmpeg.
        device: ffmpeg AVFoundation video device index or name.
        timeout_seconds: Maximum time to wait for camera startup and capture.

    Returns:
        JPEG bytes suitable for the mobile OCR upload flow.

    Raises:
        CaptureError: If ffmpeg fails, times out, or writes an empty file.
    """

    with tempfile.TemporaryDirectory(prefix="lemon-mac-camera-") as tmp_dir:
        output_path = Path(tmp_dir) / "capture.jpg"
        command = [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "avfoundation",
            "-framerate",
            "30",
            "-pixel_format",
            "nv12",
            "-i",
            _avfoundation_input(device),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-y",
            str(output_path),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise CaptureError("camera capture timed out") from exc
        except subprocess.CalledProcessError as exc:
            LOGGER.debug("ffmpeg capture failed: %s", exc.stderr.strip())
            raise CaptureError("camera capture failed") from exc

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise CaptureError("camera capture was empty")
        return output_path.read_bytes()


def _json_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, body: dict) -> None:
    """Write a small JSON response without exposing local file paths."""

    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(status.value)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _parse_after_frame_id(query: str) -> int | None:
    """Parse the optional frame cursor from a preview request query string."""

    raw_values = parse_qs(query).get("after")
    if not raw_values:
        return None
    try:
        return int(raw_values[0])
    except (TypeError, ValueError):
        return None


class CameraBridgeHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks, live frames, and camera captures."""

    server: "CameraBridgeServer"

    def do_GET(self) -> None:
        """Handle `/health`, `/frame.jpg`, and `/capture` requests."""

        parsed = urlparse(self.path)
        if parsed.path == "/health":
            stats = self.server.snapshot_stats()
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "lemon-aid-dev-mac-camera-bridge",
                    "image": "jpeg",
                    "preview": "frame.jpg",
                    **stats,
                },
            )
            return
        if parsed.path == "/frame.jpg":
            frame_id: int | None
            try:
                frame_id, image = self.server.live_frames.wait_for_frame(
                    self.server.preview_timeout_seconds,
                    after_frame_id=_parse_after_frame_id(parsed.query),
                )
            except CaptureError:
                try:
                    frame_id = None
                    image = capture_jpeg(
                        ffmpeg_bin=self.server.ffmpeg_bin,
                        device=self.server.device,
                        timeout_seconds=self.server.preview_timeout_seconds,
                    )
                except CaptureError:
                    _json_response(
                        self,
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {
                            "status": "error",
                            "code": "camera_preview_unavailable",
                        },
                    )
                    self.server.record_preview_result(ok=False)
                    return
            self.server.record_preview_result(ok=True, frame_id=frame_id)
            self._write_jpeg(image, frame_id=frame_id)
            return
        if parsed.path == "/capture":
            try:
                if self.server.live_frames.latest_frame_is_fresh(
                    max_age_seconds=2.0,
                ):
                    frame_id, image = self.server.live_frames.wait_for_frame(
                        timeout_seconds=1.0,
                    )
                else:
                    frame_id = None
                    image = capture_jpeg(
                        ffmpeg_bin=self.server.ffmpeg_bin,
                        device=self.server.device,
                        timeout_seconds=self.server.timeout_seconds,
                    )
            except CaptureError:
                _json_response(
                    self,
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "status": "error",
                        "code": "camera_capture_failed",
                    },
                )
                return
            self._write_jpeg(image, frame_id=frame_id)
            return
        _json_response(
            self,
            HTTPStatus.NOT_FOUND,
            {"status": "error", "code": "not_found"},
        )

    def log_message(self, fmt: str, *args: object) -> None:
        """Route access logs through the module logger."""

        message = fmt % args
        if 'GET /frame.jpg' in message and ' 200 ' in message:
            LOGGER.debug("%s - %s", self.address_string(), message)
            return
        LOGGER.info("%s - %s", self.address_string(), message)

    def _write_jpeg(self, image: bytes, *, frame_id: int | None) -> None:
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        if frame_id is not None:
            self.send_header("X-Lemon-Frame-Id", str(frame_id))
        self.send_header("Content-Length", str(len(image)))
        self.end_headers()
        try:
            self.wfile.write(image)
        except BrokenPipeError:
            LOGGER.debug("client disconnected before JPEG write completed")


class CameraBridgeServer(ThreadingHTTPServer):
    """Threaded localhost HTTP server carrying capture configuration."""

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        ffmpeg_bin: str,
        device: str,
        timeout_seconds: float,
        preview_timeout_seconds: float,
        preview_fps: int,
        preview_width: int,
    ) -> None:
        """Create the configured bridge server.

        Args:
            server_address: Host and port to bind.
            handler_class: HTTP request handler class.
            ffmpeg_bin: Path or command name for ffmpeg.
            device: ffmpeg AVFoundation video device index or name.
            timeout_seconds: Maximum time for each capture request.
            preview_timeout_seconds: Maximum time for each live preview frame
                request before the mobile UI should retry.
            preview_fps: Target live preview frames per second.
            preview_width: Preview JPEG width.
        """

        self.live_frames: LiveFrameBuffer | None = None
        super().__init__(server_address, handler_class)
        self.ffmpeg_bin = ffmpeg_bin
        self.device = device
        self.timeout_seconds = timeout_seconds
        self.preview_timeout_seconds = preview_timeout_seconds
        self._stats_lock = threading.Lock()
        self._preview_ok_count = 0
        self._preview_error_count = 0
        self._last_frame_id: int | None = None
        self.live_frames = LiveFrameBuffer(
            ffmpeg_bin=ffmpeg_bin,
            device=device,
            fps=preview_fps,
            width=preview_width,
        )

    def record_preview_result(self, *, ok: bool, frame_id: int | None = None) -> None:
        """Record preview request health without storing image bytes."""

        with self._stats_lock:
            if ok:
                self._preview_ok_count += 1
                self._last_frame_id = frame_id
            else:
                self._preview_error_count += 1

    def snapshot_stats(self) -> dict[str, int | None]:
        """Return safe preview counters for smoke verification."""

        with self._stats_lock:
            return {
                "preview_ok_count": self._preview_ok_count,
                "preview_error_count": self._preview_error_count,
                "last_frame_id": self._last_frame_id,
            }

    def server_close(self) -> None:
        """Stop camera streaming when the HTTP server closes."""

        if self.live_frames is not None:
            self.live_frames.stop()
        super().server_close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run the Lemon-Aid debug Mac camera bridge.",
    )
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8755)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument(
        "--device",
        default="0",
        help="AVFoundation video device index or name. Use --list-devices first.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    parser.add_argument(
        "--preview-timeout-seconds",
        type=float,
        default=2.0,
        help="Maximum wait for each live preview frame request.",
    )
    parser.add_argument(
        "--preview-fps",
        type=int,
        default=30,
        help="Preview stream frame rate. MacBook cameras usually support 30.",
    )
    parser.add_argument("--preview-width", type=int, default=720)
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List AVFoundation devices and exit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bridge until interrupted."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = parse_args(argv)
    if args.list_devices:
        return list_devices(args.ffmpeg_bin)

    server = CameraBridgeServer(
        (args.listen_host, args.listen_port),
        CameraBridgeHandler,
        ffmpeg_bin=args.ffmpeg_bin,
        device=args.device,
        timeout_seconds=args.timeout_seconds,
        preview_timeout_seconds=args.preview_timeout_seconds,
        preview_fps=args.preview_fps,
        preview_width=args.preview_width,
    )
    LOGGER.info(
        "mac_camera_bridge_listening listen=%s:%s device=%s",
        args.listen_host,
        args.listen_port,
        args.device,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("mac_camera_bridge_stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
