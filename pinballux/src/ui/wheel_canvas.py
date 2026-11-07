"""
WheelCanvas - a custom-painted, continuously animated table wheel.

Everything (stage, spotlight, logos) is drawn in one paintEvent from a single
floating-point wheel position, so motion is sub-pixel smooth and new input
re-targets the running animation instead of restarting it. Logos are scaled
once into cached pixmaps (plus a soft drop shadow), never per frame.
"""

import math
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, QVariantAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import (QPainter, QPixmap, QImage, QColor, QFont, QPen, QBrush, QPainterPath,
                         QLinearGradient, QRadialGradient)
from PyQt6.QtWidgets import QWidget

from ..core.logger import get_logger

logger = get_logger(__name__)

ACCENT = QColor(110, 185, 255)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Hermite smoothstep; works for edge0 > edge1 too (falling ramp)."""
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


class _WheelLogo:
    """Cached artwork for one table: full-size and small logo plus matching shadows."""

    BOX_W = 1.30  # logo box, relative to the base size
    BOX_H = 0.90

    def __init__(self, table: dict, box: int):
        self.table = table
        self.box = box
        source = self._load_source(table)
        self.full = self._fit(source, box * self.BOX_W, box * self.BOX_H)
        self.small = self._fit(source, box * self.BOX_W * 0.6, box * self.BOX_H * 0.6)
        self.full_shadow = self._shadow(self.full)
        self.small_shadow = self._shadow(self.small)

    @staticmethod
    def _load_source(table: dict) -> QPixmap:
        path = table.get('wheel_image', '') or ''
        if path and Path(path).exists():
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return pixmap
            logger.warning(f"Failed to load wheel image {path}")
        return _WheelLogo._placeholder(table)

    @staticmethod
    def _placeholder(table: dict) -> QPixmap:
        """Clean name plate for tables without wheel art."""
        w, h = 640, 360
        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        plate = QRectF(8, 40, w - 16, h - 80)
        grad = QLinearGradient(0, plate.top(), 0, plate.bottom())
        grad.setColorAt(0, QColor(42, 48, 64))
        grad.setColorAt(1, QColor(20, 23, 32))
        p.setBrush(grad)
        p.setPen(QPen(QColor(255, 255, 255, 40), 3))
        p.drawRoundedRect(plate, 36, 36)
        p.setPen(QColor(235, 240, 250))
        font = QFont("Ubuntu Sans", 44, QFont.Weight.DemiBold)
        p.setFont(font)
        name = table.get('name', 'Unknown Table')
        p.drawText(plate.adjusted(28, 10, -28, -60), int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), name)
        sub = " · ".join(str(x) for x in (table.get('manufacturer'), table.get('year')) if x)
        if sub:
            p.setFont(QFont("Ubuntu Sans", 26))
            p.setPen(QColor(160, 175, 200))
            p.drawText(plate.adjusted(28, 0, -28, -24), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom), sub)
        p.end()
        return QPixmap.fromImage(image)

    @staticmethod
    def _fit(source: QPixmap, box_w: float, box_h: float) -> QPixmap:
        return source.scaled(max(1, int(box_w)), max(1, int(box_h)), Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)

    @staticmethod
    def _shadow(pixmap: QPixmap) -> QPixmap:
        """Soft drop shadow from the logo's alpha: tint black, then blur by down/up-scaling."""
        w, h = pixmap.width(), pixmap.height()
        if w < 2 or h < 2:
            return pixmap
        pad = max(4, int(min(w, h) * 0.12))
        canvas = QImage(w + 2 * pad, h + 2 * pad, QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.drawPixmap(pad, pad, pixmap)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(canvas.rect(), QColor(0, 0, 0, 255))
        p.end()
        small = canvas.scaled(max(1, canvas.width() // 10), max(1, canvas.height() // 10),
                              Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        blurred = small.scaled(canvas.width(), canvas.height(),
                               Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return QPixmap.fromImage(blurred)

    def pick(self, scale: float):
        """Best cached logo/shadow for a draw scale (1.0 = full size)."""
        if scale <= 0.66:
            return self.small, self.small_shadow, scale / 0.6
        return self.full, self.full_shadow, scale


class WheelCanvas(QWidget):
    """Painted wheel of table logos laid out on an arc."""

    settled = pyqtSignal(int)  # emitted with the table index when motion stops

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._logos: List[_WheelLogo] = []
        self._tables: List[dict] = []
        self._position = 0.0     # continuous wheel position, in table units (unbounded)
        self._target = 0         # integer target position (unbounded; wrapped on lookup)
        self._visible_width = 0  # logical width actually visible (differs from width() when rotated)
        self._bottom_reserve = 160  # space kept clear under the logos for the info panel
        self._logo_box = 0

        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_anim_value)
        self._anim.finished.connect(self._on_anim_finished)
        self.step_duration = 320       # ms for a single step from rest
        self.chained_duration = 200    # ms when re-targeting mid-motion (held flipper)

    # ----- data -------------------------------------------------------------------------

    def set_tables(self, tables: List[dict]):
        self._tables = list(tables)
        self._anim.stop()
        self._position = 0.0
        self._target = 0
        self._rebuild_logos()
        self.update()

    def set_layout_metrics(self, visible_width: int, bottom_reserve: int):
        """visible_width: logical width that is on screen (the widget may be wider when rotated)."""
        changed = (visible_width != self._visible_width) or (bottom_reserve != self._bottom_reserve)
        self._visible_width = visible_width
        self._bottom_reserve = bottom_reserve
        if changed:
            self._rebuild_logos()
            self.update()

    def _base_size(self) -> int:
        vw = self._visible_width or self.width() or 1920
        return int(max(170, min(340, vw * 0.135)))

    def _rebuild_logos(self):
        box = self._base_size()
        if box == self._logo_box and len(self._logos) == len(self._tables) and \
                all(l.table is t for l, t in zip(self._logos, self._tables)):
            return
        self._logo_box = box
        self._logos = [_WheelLogo(t, box) for t in self._tables]

    # ----- navigation -------------------------------------------------------------------

    @property
    def current_index(self) -> int:
        n = len(self._tables)
        return self._target % n if n else 0

    @property
    def is_moving(self) -> bool:
        return self._anim.state() == QVariantAnimation.State.Running

    def step(self, delta: int):
        """Move the selection by delta tables, animating from wherever the wheel is now."""
        if not self._tables:
            return
        moving = self.is_moving
        self._target += delta
        self._anim.stop()
        self._anim.setStartValue(float(self._position))
        self._anim.setEndValue(float(self._target))
        self._anim.setDuration(self.chained_duration if moving else self.step_duration)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def jump_to(self, index: int):
        """Show index immediately (no animation)."""
        self._anim.stop()
        n = len(self._tables)
        self._target = index % n if n else 0
        self._position = float(self._target)
        self.update()

    def _on_anim_value(self, value):
        self._position = float(value)
        self.update()

    def _on_anim_finished(self):
        self._position = float(self._target)
        self.update()
        self.settled.emit(self.current_index)

    # ----- painting ---------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_logos()

    def _geometry(self):
        """Arc geometry in widget coordinates."""
        w, h = self.width(), self.height()
        vw = self._visible_width or w
        size = self._base_size()
        cx = w / 2.0
        cy = h - self._bottom_reserve - size * _WheelLogo.BOX_H * 0.5 - 28  # centre of the selected logo
        radius = vw * 1.6
        step_angle = (size * 1.08) / radius                   # spacing along the arc
        return cx, cy, size, radius, step_angle, vw

    def paintEvent(self, event):
        if self.width() <= 0 or self.height() <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx, cy, size, radius, step_angle, vw = self._geometry()
        self._paint_stage(p, cx, cy, size, radius, vw)

        n = len(self._logos)
        if n == 0:
            p.end()
            return

        # Which wheel slots to draw: enough to cover the visible width, never the same table twice
        reach = 6
        half = n / 2.0
        base = math.floor(self._position)
        slots = []
        for k in range(base - reach, base + reach + 2):
            d = k - self._position
            if abs(d) > reach or (n < 2 * reach + 1 and not (-half < d <= half)):
                continue
            slots.append((d, k % n))

        # Spotlight behind the selected logo (fades while it moves away)
        nearest = min((abs(d) for d, _ in slots), default=1.0)
        self._paint_spotlight(p, cx, cy, size, 1.0 - min(1.0, nearest * 1.6))

        # Far logos first so the selected one is drawn on top
        for d, idx in sorted(slots, key=lambda s: -abs(s[0])):
            self._paint_logo(p, self._logos[idx], d, cx, cy, size, radius, step_angle, vw)
        p.end()

    def _paint_stage(self, p: QPainter, cx, cy, size, radius, vw):
        """Dark glass band following the arc, with a fine highlight along its edge."""
        h = self.height()
        rim = radius + size * 0.72
        top_y = cy - size * 0.72
        circle_c = QPointF(cx, top_y + rim)

        band = QPainterPath()
        band.addEllipse(circle_c, rim, rim)
        clip = QPainterPath()
        clip.addRect(QRectF(cx - vw, top_y - 4, 2 * vw, h - top_y + 8))
        band = band.intersected(clip)

        g = QLinearGradient(0, top_y, 0, h)
        g.setColorAt(0.0, QColor(12, 15, 26, 175))
        g.setColorAt(min(0.99, (size * 0.45) / max(1.0, h - top_y)), QColor(8, 10, 18, 238))
        g.setColorAt(1.0, QColor(4, 5, 9, 250))
        p.fillPath(band, QBrush(g))

        # Highlight along the top of the arc, brightest in the middle, fading to the sides
        edge = QPainterPath()
        span = math.asin(min(1.0, (vw * 0.5) / rim))
        start_deg = 90 + math.degrees(span)
        edge.arcMoveTo(QRectF(circle_c.x() - rim, circle_c.y() - rim, 2 * rim, 2 * rim), start_deg)
        edge.arcTo(QRectF(circle_c.x() - rim, circle_c.y() - rim, 2 * rim, 2 * rim), start_deg, -2 * math.degrees(span))
        lg = QLinearGradient(cx - vw * 0.5, 0, cx + vw * 0.5, 0)
        for stop, alpha in ((0.0, 0), (0.25, 70), (0.5, 170), (0.75, 70), (1.0, 0)):
            c = QColor(ACCENT)
            c.setAlpha(alpha)
            lg.setColorAt(stop, c)
        glow = QColor(ACCENT)
        glow.setAlpha(28)
        p.setPen(QPen(QBrush(lg), 2.0))
        p.drawPath(edge)
        glow_grad = QLinearGradient(lg)
        for stop, alpha in ((0.0, 0), (0.5, 40), (1.0, 0)):
            c = QColor(ACCENT)
            c.setAlpha(alpha)
            glow_grad.setColorAt(stop, c)
        p.setPen(QPen(QBrush(glow_grad), 10.0))
        p.drawPath(edge)

    def _paint_spotlight(self, p: QPainter, cx, cy, size, strength: float):
        if strength <= 0.01:
            return
        r = size * 0.95
        rg = QRadialGradient(QPointF(cx, cy + size * 0.05), r)
        c0 = QColor(ACCENT)
        c0.setAlpha(int(80 * strength))
        c1 = QColor(ACCENT)
        c1.setAlpha(int(22 * strength))
        rg.setColorAt(0.0, c0)
        rg.setColorAt(0.55, c1)
        rg.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(rg))
        p.drawEllipse(QPointF(cx, cy + size * 0.05), r * 1.25, r)

    @staticmethod
    def _scale_at(ad: float) -> float:
        return 0.48 + 0.52 * math.exp(-0.9 * ad)

    @staticmethod
    def _arc_offset(d: float, size: float) -> float:
        """Distance along the arc from the centre for slot offset d. Integrates a spacing that
        shrinks with the logos, so gaps look even instead of growing towards the ends."""
        ad = abs(d)
        u = size * (0.74 * ad + (0.72 / 0.9) * (1.0 - math.exp(-0.9 * ad)))
        return u if d >= 0 else -u

    def _paint_logo(self, p: QPainter, logo: _WheelLogo, d: float, cx, cy, size, radius, step_angle, vw):
        ad = abs(d)
        theta = self._arc_offset(d, size) / radius
        x = cx + radius * math.sin(theta)
        y = cy + radius * (1.0 - math.cos(theta))
        if abs(x - cx) > vw * 0.5 + size:
            return

        scale = self._scale_at(ad)
        edge = abs(radius * math.sin(theta)) / (vw * 0.5)     # 0 centre .. 1 screen edge
        opacity = _smoothstep(1.02, 0.80, edge) * (0.72 + 0.28 * math.exp(-4.0 * d * d))
        if opacity <= 0.01:
            return

        pixmap, shadow, k = logo.pick(scale)
        pw, ph = pixmap.width() * k, pixmap.height() * k

        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(theta) * 0.8)
        p.setOpacity(opacity)

        # Soft drop shadow, slightly below the logo
        sw, sh = shadow.width() * k, shadow.height() * k
        p.setOpacity(opacity * 0.55)
        p.drawPixmap(QRectF(-sw / 2, -sh / 2 + size * 0.035, sw, sh), shadow, QRectF(shadow.rect()))
        p.setOpacity(opacity)

        p.drawPixmap(QRectF(-pw / 2, -ph / 2, pw, ph), pixmap, QRectF(pixmap.rect()))
        p.restore()
