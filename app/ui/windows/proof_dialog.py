"""Attendance proof viewer. Preview bytes in Qt, never execute external files."""
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QMessageBox, QFileDialog, QLabel, QScrollArea)
from sqlalchemy import select

from app.models import Attendance, AttendanceRevision
from app.models.attendance_proof import ProofDocument
from app.services.attendance_proof import ProofService, MAX_SIZE


class ProofDialog(QDialog):
    def __init__(self, window, lesson_id, student_id):
        super().__init__(window)
        self.repo = window.repository
        self.setWindowTitle('Attendance documents')
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        self.revisions = QComboBox()
        attendance = self.repo.session.scalar(select(Attendance).where(
            Attendance.lesson_id == lesson_id, Attendance.student_id == student_id))
        if attendance:
            for revision in self.repo.session.scalars(select(AttendanceRevision).where(
                    AttendanceRevision.attendance_id == attendance.id).order_by(AttendanceRevision.id.desc())):
                previous = revision.previous_status or 'unknown'
                self.revisions.addItem(f'{revision.id}: {previous} -> {revision.status} - {revision.reason}', revision.id)
        layout.addWidget(self.revisions)
        self.documents = QListWidget()
        layout.addWidget(self.documents)
        buttons = QHBoxLayout()
        self.attach_button = QPushButton('Attach document')
        self.attach_button.clicked.connect(self.attach)
        buttons.addWidget(self.attach_button)
        preview = QPushButton('Preview')
        preview.clicked.connect(self.preview)
        buttons.addWidget(preview)
        layout.addLayout(buttons)
        self.revisions.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.documents.clear()
        key = self.revisions.currentData()
        revision = self.repo.session.get(AttendanceRevision, key) if key else None
        self.attach_button.setEnabled(bool(revision and revision.status == 'excused'))
        if key:
            for doc in self.repo.session.scalars(select(ProofDocument).where(
                    ProofDocument.revision_id == key, ProofDocument.sealed.is_(True))):
                item = QListWidgetItem(f'{doc.filename} ({doc.size} bytes)')
                item.setData(256, doc.id)
                self.documents.addItem(item)

    def attach(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Attendance proof', '',
                                                 'Documents (*.pdf *.png *.jpg *.jpeg)')
        if not filename:
            return
        try:
            with open(filename, 'rb') as stream:
                content = stream.read(MAX_SIZE + 1)
            self.repo.proof_action('attach', revision_id=self.revisions.currentData(),
                                   filename=filename, content=content)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, 'Document rejected', str(exc))

    def preview(self):
        item = self.documents.currentItem()
        if item is None:
            return
        try:
            name, mime, content = ProofService(self.repo.session).read(item.data(256))
            dialog = QDialog(self)
            dialog.setWindowTitle(name)
            dialog.resize(800, 650)
            layout = QVBoxLayout(dialog)
            if mime == 'application/pdf':
                from PySide6.QtPdf import QPdfDocument
                from PySide6.QtPdfWidgets import QPdfView
                buffer = QBuffer(dialog)
                buffer.setData(QByteArray(content))
                buffer.open(QIODevice.ReadOnly)
                document = QPdfDocument(dialog)
                document.load(buffer)
                if document.status() != QPdfDocument.Status.Ready:
                    raise ValueError('PDF cannot be rendered.')
                view = QPdfView(dialog)
                view.setDocument(document)
            else:
                view = QScrollArea(dialog)
                label = QLabel()
                pixmap = QPixmap()
                pixmap.loadFromData(content)
                label.setPixmap(pixmap)
                view.setWidget(label)
            layout.addWidget(view)
            dialog.exec()
        except Exception as exc:
            QMessageBox.warning(self, 'Preview failed', str(exc))
