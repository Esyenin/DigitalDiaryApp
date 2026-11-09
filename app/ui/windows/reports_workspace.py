"""Read-only report filters, embedded PDF preview, and explicit export."""

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QBuffer, QIODevice, QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QComboBox, QDateEdit, QCheckBox, QListWidget, QListWidgetItem, QPushButton,
    QFileDialog, QMessageBox, QLabel, QAbstractItemView, QSplitter)
from sqlalchemy import select

from app.models import AcademicTerm, CourseOffering, Group
from app.services.journal_reports import build_report

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
except ImportError:
    QPdfDocument = QPdfView = None


class ReportsWorkspace(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.session = window.repository.session
        self._temporary = TemporaryDirectory(prefix='diary_reports_')
        self._preview_path = Path(self._temporary.name) / 'preview.pdf'
        root = QVBoxLayout(self)
        splitter = QSplitter()
        root.addWidget(splitter)
        filters = QWidget()
        form = QFormLayout(filters)
        self.kind = QComboBox()
        self.kind.addItem('Куратор', 'curator')
        self.kind.addItem('Деканат', 'dean')
        self.as_of = QDateEdit(QDate.currentDate())
        self.as_of.setCalendarPopup(True)
        self.term = QComboBox()
        self.term.addItem('Все семестры', None)
        self.groups = QListWidget()
        self.courses = QListWidget()
        for field in (self.groups, self.courses):
            field.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            field.setMaximumHeight(130)
        with self.session.no_autoflush:
            for row in self.session.scalars(select(AcademicTerm).order_by(AcademicTerm.name)):
                self.term.addItem(f'{row.name} (#{row.id})', row.id)
            for model, field in ((Group, self.groups), (CourseOffering, self.courses)):
                for row in self.session.scalars(select(model).order_by(model.name)):
                    item = QListWidgetItem(f'{row.name} (#{row.id})')
                    item.setData(Qt.ItemDataRole.UserRole, row.id)
                    field.addItem(item)
        self.use_range = QCheckBox('Ограничить период')
        self.start = QDateEdit(QDate.currentDate().addMonths(-6))
        self.end = QDateEdit(QDate.currentDate())
        for field in (self.start, self.end):
            field.setCalendarPopup(True)
            field.setEnabled(False)
            self.use_range.toggled.connect(field.setEnabled)
        for title, field in [('Отчёт', self.kind), ('На дату', self.as_of), ('Семестр', self.term),
                             ('Группы', self.groups), ('Курсы', self.courses),
                             ('', self.use_range), ('С', self.start), ('По', self.end)]:
            form.addRow(title, field)
        actions = QHBoxLayout()
        self.preview_button = QPushButton('Предпросмотр')
        self.export_button = QPushButton('Сохранить PDF')
        actions.addWidget(self.preview_button)
        actions.addWidget(self.export_button)
        form.addRow(actions)
        splitter.addWidget(filters)
        if QPdfView is not None:
            self.document = QPdfDocument(self)
            self._buffer = QBuffer(self)
            self.viewer = QPdfView(self)
            self.viewer.setDocument(self.document)
            self.viewer.setPageMode(QPdfView.PageMode.MultiPage)
            self.viewer.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            splitter.addWidget(self.viewer)
        else:
            self.document = None
            self.viewer = QPushButton('Открыть предпросмотр PDF')
            self.viewer.setEnabled(False)
            self.viewer.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._preview_path))))
            splitter.addWidget(self.viewer)
        splitter.setStretchFactor(1, 1)
        self.preview_button.clicked.connect(self.preview)
        self.export_button.clicked.connect(self.export)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.destroyed.connect(self._temporary.cleanup)

    def closeEvent(self, event):
        if self.document:
            self.document.close()
            self._buffer.close()
        super().closeEvent(event)

    def filters(self):
        def ids(widget):
            return [item.data(Qt.ItemDataRole.UserRole) for item in widget.selectedItems()] or None
        return dict(kind=self.kind.currentData(), as_of=self.as_of.date().toPython(),
                    term_id=self.term.currentData(), group_ids=ids(self.groups), offering_ids=ids(self.courses),
                    start_date=self.start.date().toPython() if self.use_range.isChecked() else None,
                    end_date=self.end.date().toPython() if self.use_range.isChecked() else None)

    def _build(self, path):
        try:
            build_report(self.session, path, **self.filters())
            self.status.setText('PDF сформирован')
            return True
        except Exception as exc:
            self.status.setText(str(exc))
            QMessageBox.warning(self, 'Отчёт', str(exc))
            return False

    def preview(self):
        if self.document:
            self.document.close()
            self._buffer.close()
        if not self._build(self._preview_path):
            return
        if self.document:
            self._buffer.setData(self._preview_path.read_bytes())
            self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.document.load(self._buffer)
            if self.document.error() != QPdfDocument.Error.None_:
                self.status.setText(f'Ошибка предпросмотра: {self.document.error()}')
        else:
            self.viewer.setEnabled(True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._preview_path)))

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Сохранить отчёт', 'journal_report.pdf', 'PDF (*.pdf)')
        if path:
            if not path.lower().endswith('.pdf'):
                path += '.pdf'
            self._build(Path(path))
