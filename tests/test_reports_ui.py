"""Headless report filter and real Qt PDF preview smoke tests."""

import os
import tempfile
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Group
from app.ui.windows import reports_workspace as module


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/arial.ttf')
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QFont(families[0], 9))
    engine = create_engine(f'sqlite:///{tmp_path / "test_reports_ui.db"}')
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Group(name='ПИ-01'))
    session.commit()
    monkeypatch.setattr(module, 'TemporaryDirectory', lambda **kwargs: tempfile.TemporaryDirectory(dir=tmp_path, **kwargs))
    widget = module.ReportsWorkspace(SimpleNamespace(repository=SimpleNamespace(session=session)))
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()
    session.close()
    engine.dispose()


def test_filters_export_and_cancel(workspace, tmp_path, monkeypatch):
    calls = []
    def build(session, path, **kwargs):
        calls.append((path, kwargs))
    monkeypatch.setattr(module, 'build_report', build)
    workspace.groups.item(0).setSelected(True)
    workspace.kind.setCurrentIndex(1)
    workspace.use_range.setChecked(True)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(tmp_path / 'export'), 'PDF'))
    workspace.export()
    assert calls[0][0].suffix == '.pdf'
    assert calls[0][1]['kind'] == 'dean' and calls[0][1]['group_ids']
    assert calls[0][1]['start_date'] is not None
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: ('', ''))
    workspace.export()
    assert len(calls) == 1


def test_preview_real_pdf_and_readonly(workspace, monkeypatch):
    from reportlab.pdfgen.canvas import Canvas
    def build(session, path, **kwargs):
        canvas = Canvas(str(path))
        canvas.drawString(20, 30, 'PDF preview')
        canvas.save()
    monkeypatch.setattr(module, 'build_report', build)
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    before = workspace.session.connection().exec_driver_sql('SELECT total_changes()').scalar()
    workspace.preview()
    assert not errors, errors
    if workspace.document:
        assert workspace.document.pageCount() == 1
    assert workspace._preview_path.read_bytes().startswith(b'%PDF-')
    assert workspace.session.connection().exec_driver_sql('SELECT total_changes()').scalar() == before


def test_errors_are_visible(workspace, monkeypatch):
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    def fail(*args, **kwargs):
        raise ValueError('Invalid range')
    monkeypatch.setattr(module, 'build_report', fail)
    workspace.preview()
    assert errors == ['Invalid range']
    assert workspace.status.text() == 'Invalid range'


def test_real_analytics_preview_and_render(workspace, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    before = list(workspace.session.connection().connection.driver_connection.iterdump())
    workspace.resize(1100, 720)
    workspace.show()
    workspace.preview()
    QApplication.processEvents()
    QTest.qWait(400)
    assert not errors, errors
    assert workspace.document.pageCount() >= 1
    assert list(workspace.session.connection().connection.driver_connection.iterdump()) == before
    screenshot = workspace.grab()
    assert not screenshot.isNull()
    assert screenshot.save(str(tmp_path / 'reports_workspace.png'))
