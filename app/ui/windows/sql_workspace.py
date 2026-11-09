"""Embedded, bounded read-only SQL inspection workspace."""

from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget)
from PySide6.QtCore import Qt

from app.services.sql_viewer import SQLReadOnlyViewer


class SQLWorkspace(QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName('DetailPage')
        self.window = window
        self.viewer = SQLReadOnlyViewer(window.repository.engine.url,
            getattr(window, 'postgres_readonly_url', None))
        self.result = None
        layout = QVBoxLayout(self)
        title = QLabel('SQL viewer')
        title.setObjectName('DetailTitle')
        layout.addWidget(title)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Table / column'])
        self.editor = QPlainTextEdit()
        self.editor.setObjectName('sqlQuery')
        self.editor.setMinimumHeight(80)
        self.rows_limit = QSpinBox()
        self.rows_limit.setRange(1, 10000)
        self.rows_limit.setValue(500)
        self.timeout = QSpinBox()
        self.timeout.setRange(1, 10000)
        self.timeout.setValue(2000)
        form = QFormLayout()
        if self.viewer.url.get_backend_name() == 'postgresql':
            self.readonly_url = QLineEdit(getattr(window, 'postgres_readonly_url', '') or '')
            self.readonly_url.setEchoMode(QLineEdit.EchoMode.Password)
            self.readonly_url.setObjectName('postgresReadonlyUrl')
            form.addRow('Read-only connection URL', self.readonly_url)
            self.readonly_url.editingFinished.connect(self.configure_postgres)
        form.addRow('Maximum rows', self.rows_limit)
        form.addRow('Timeout (ms)', self.timeout)
        self.run_button = QPushButton('Run query')
        self.save_button = QPushButton('Save TXT')
        self.save_button.setEnabled(False)
        refresh = QPushButton('Refresh schema')
        actions = QHBoxLayout()
        for button in (self.run_button, self.save_button, refresh):
            actions.addWidget(button)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        panel = QWidget()
        right = QVBoxLayout(panel)
        right.addWidget(self.editor)
        right.addLayout(form)
        right.addLayout(actions)
        right.addWidget(self.status)
        right.addWidget(self.table, 1)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(panel)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        self.run_button.clicked.connect(self.run_query)
        self.save_button.clicked.connect(self.save_result)
        refresh.clicked.connect(self.refresh_schema)
        self.refresh_schema()

    def configure_postgres(self):
        self.viewer.postgres_url = self.readonly_url.text().strip() or None
        self.window.postgres_readonly_url = self.viewer.postgres_url
        self.result = None
        self.save_button.setEnabled(False)
        self.table.setRowCount(0)
        self.refresh_schema()

    def refresh_schema(self):
        self.tree.clear()
        try:
            for table, columns in self.viewer.schema().items():
                item = QTreeWidgetItem(self.tree, [table])
                for column in columns:
                    QTreeWidgetItem(item, [column])
            self.status.clear()
        except Exception as exc:
            self.status.setText(str(exc))

    def run_query(self):
        self.result = None
        self.save_button.setEnabled(False)
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.run_button.setEnabled(False)
        try:
            result = self.viewer.execute(self.editor.toPlainText(),
                max_rows=self.rows_limit.value(), timeout_ms=self.timeout.value())
            self.table.setColumnCount(len(result['columns']))
            self.table.setHorizontalHeaderLabels(result['columns'])
            self.table.setRowCount(len(result['rows']))
            for row, values in enumerate(result['rows']):
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem('NULL' if value is None else str(value)))
            self.result = result
            self.save_button.setEnabled(True)
            self.status.setText(f"{len(result['rows'])} rows" + (' (truncated)' if result['truncated'] else ''))
        except Exception as exc:
            self.status.setText(str(exc))
        finally:
            self.run_button.setEnabled(True)

    def save_result(self):
        if self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Save SQL result', '', 'Text files (*.txt)')
        if path:
            try:
                self.viewer.save_txt(self.result, path)
            except Exception as exc:
                self.status.setText(str(exc))
