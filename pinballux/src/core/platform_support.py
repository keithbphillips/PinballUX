"""
Platform detection and Raspberry Pi specific behaviour.

PinballUX runs unchanged on desktop Linux. On a Raspberry Pi (Raspberry Pi OS with the
labwc Wayland desktop) a few things have to be done differently; they are all switched
on from here so the rest of the code just asks "should I?":

* Qt runs under XWayland (QT_QPA_PLATFORM=xcb). labwc does not let a native Wayland
  client choose its output, so the backglass/DMD windows could not be placed on the
  right monitor. XWayland presents all monitors as one X screen, where absolute window
  positions work.
* Video is decoded in software (QT_FFMPEG_DECODING_HW_DEVICE_TYPES=""). The Pi 5 has
  no H.264 hardware decoder; Qt's FFmpeg backend otherwise tries h264_v4l2m2m, fails
  and stalls the wheel on preview videos.
* Sound effects are played with an external ffplay process instead of QMediaPlayer.
  Qt Multimedia blocks the GUI thread on the Pi when audio sources change quickly
  (moving the wheel), which freezes navigation.
* Preview videos play silently and every frontend audio stream is released while a
  table runs, and the frontend is suspended (SIGSTOP) for the duration of play, so
  VPinball has the CPU, GPU and sound device to itself (otherwise its audio pops).

Every switch can be forced either way with an environment variable:

    PINBALLUX_RASPBERRY_PI=1|0        treat this machine as a Pi (or not)
    PINBALLUX_FFPLAY_AUDIO=1|0        sound effects via ffplay
    PINBALLUX_VIDEO_AUDIO=1|0         preview videos / background music with sound
    PINBALLUX_SUSPEND_FRONTEND=1|0    suspend the frontend while a table is played
"""

import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Optional

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_flag(name: str) -> Optional[bool]:
    """Return True/False if the variable is set to a recognised value, else None."""
    value = os.environ.get(name, "").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    return None


@lru_cache(maxsize=1)
def raspberry_pi_model() -> Optional[str]:
    """The board model string (e.g. 'Raspberry Pi 5 Model B Rev 1.0'), or None."""
    for path in ("/proc/device-tree/model", "/sys/firmware/devicetree/base/model"):
        try:
            model = Path(path).read_bytes().rstrip(b"\x00").decode(errors="replace").strip()
        except OSError:
            continue
        if "Raspberry Pi" in model:
            return model
    return None


def is_raspberry_pi() -> bool:
    forced = _env_flag("PINBALLUX_RASPBERRY_PI")
    if forced is not None:
        return forced
    return raspberry_pi_model() is not None


def use_ffplay_audio() -> bool:
    """Play sound effects with ffplay (only if ffplay is actually installed)."""
    forced = _env_flag("PINBALLUX_FFPLAY_AUDIO")
    wanted = forced if forced is not None else is_raspberry_pi()
    return wanted and shutil.which("ffplay") is not None


def video_audio_enabled() -> bool:
    """Whether preview videos and the wheel background music open an audio output."""
    forced = _env_flag("PINBALLUX_VIDEO_AUDIO")
    if forced is not None:
        return forced
    return not is_raspberry_pi()


def release_audio_during_play() -> bool:
    """Stop and release every frontend audio stream while a table is running."""
    return is_raspberry_pi()


def suspend_frontend_during_play() -> bool:
    forced = _env_flag("PINBALLUX_SUSPEND_FRONTEND")
    if forced is not None:
        return forced
    return is_raspberry_pi()


def vpx_pi_wrapper() -> Path:
    """Script that runs VPinball and suspends the frontend while the table is played."""
    return Path(__file__).resolve().parent / "vpx_pi_wrapper.sh"


def apply_qt_environment() -> None:
    """Set the Pi's Qt environment. Must run before the QApplication is created.

    Uses setdefault, so anything the user exported explicitly wins.
    """
    if not is_raspberry_pi():
        return
    # Only switch to XWayland when an X display is available (labwc starts XWayland).
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("DISPLAY", ":0")
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "")
