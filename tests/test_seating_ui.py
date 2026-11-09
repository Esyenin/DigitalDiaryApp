"""Headless scene geometry and side-effect-free rendering."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from app.ui.windows.seating_workspace import SeatItem, SeatingWorkspace
from tests.test_journal_activity import activity


def test_draft_geometry_and_read(activity):
    app = QApplication.instance() or QApplication([])
    service, lesson = activity
    widget = SeatingWorkspace(SimpleNamespace(repository=SimpleNamespace(session=service.session)), lesson_id=lesson)
    assert len([i for i in widget.scene.items() if isinstance(i, SeatItem)]) == 2
    assert not service.session.new and not service.session.dirty
    widget.new_draft()
    seat = SeatItem(widget, dict(label='A', x=20, y=30), draft=True)
    widget.scene.addItem(seat)
    seat.setPos(250, 150)
    assert seat.sceneBoundingRect().width() >= 140
    assert seat.pos().x() == 250
    widget.resize(640, 480)
    widget.show()
    app.processEvents()
    assert widget.view.viewport().width() > 200
    widget.close()
