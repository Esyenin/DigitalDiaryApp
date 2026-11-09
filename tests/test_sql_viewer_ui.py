import os
import sqlite3
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QFileDialog
from sqlalchemy.engine import make_url

from app.ui.windows.sql_workspace import SQLWorkspace


def test_workspace_read_errors_and_export(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / 'test_sql_ui.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE demo(value TEXT)')
        connection.execute("INSERT INTO demo VALUES ('sample')")
    before = path.read_bytes()
    window = SimpleNamespace(repository=SimpleNamespace(engine=SimpleNamespace(url=make_url(f'sqlite:///{path}'))))
    widget = SQLWorkspace(window)
    assert widget.tree.topLevelItem(0).text(0) == 'demo'
    widget.editor.setPlainText('SELECT * FROM demo')
    widget.run_button.click()
    assert widget.table.item(0, 0).text() == 'sample'
    output = tmp_path / 'output.txt'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(output), ''))
    widget.save_button.click()
    assert 'sample' in output.read_text(encoding='utf-8')
    widget.editor.setPlainText('DELETE FROM demo')
    widget.run_button.click()
    assert 'rejected' in widget.status.text()
    assert not widget.save_button.isEnabled()
    assert widget.table.rowCount() == 0
    assert path.read_bytes() == before
    widget.close()
    app.processEvents()


def test_postgres_readonly_connection_is_configurable_without_python(monkeypatch):
    from PySide6.QtWidgets import QLineEdit
    from app.services.sql_viewer import SQLReadOnlyViewer
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(SQLReadOnlyViewer, 'schema', lambda self: {})
    window = SimpleNamespace(repository=SimpleNamespace(engine=SimpleNamespace(
        url=make_url('postgresql+psycopg2://application@localhost/diary'))))
    widget = SQLWorkspace(window)
    assert widget.readonly_url.echoMode() == QLineEdit.EchoMode.Password
    url = 'postgresql://reader@localhost/reporting'
    widget.readonly_url.setText(url)
    widget.readonly_url.editingFinished.emit()
    assert widget.viewer.postgres_url == window.postgres_readonly_url == url
    assert not widget.save_button.isEnabled()
    widget.close()
    app.processEvents()
