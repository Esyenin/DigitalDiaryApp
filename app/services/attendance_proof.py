"""Proof storage. Transactions belong to the caller; no client paths are stored."""
import base64
import hashlib
import re
from io import BytesIO
from pathlib import PureWindowsPath

from sqlalchemy import select

from app.models.education import AttendanceRevision
from app.models.attendance_proof import ProofChunk, ProofDocument

MAX_SIZE = 5 * 1024 * 1024
CHUNK_SIZE = 12000


def _validate_pdf_objects(content):
    """Inspect decoded names/references, not just their encoded byte spelling."""
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject
    forbidden = {'/JavaScript', '/JS', '/Launch', '/EmbeddedFile', '/EmbeddedFiles',
                 '/OpenAction', '/AA', '/RichMedia', '/XFA', '/SubmitForm',
                 '/ImportData', '/GoToR', '/GoToE', '/URI'}
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted or not 0 < len(reader.pages) <= 1000:
            raise ValueError('Encrypted or excessive PDF structure.')
        pending = [(reader.trailer, 0)]
        visited, count = set(), 0
        while pending:
            obj, depth = pending.pop()
            count += 1
            if count > 50000 or depth > 64:
                raise ValueError('Excessive PDF object graph.')
            if isinstance(obj, IndirectObject):
                key = (obj.idnum, obj.generation)
                if key in visited:
                    continue
                visited.add(key)
                obj = obj.get_object()
            if isinstance(obj, DictionaryObject):
                if any(str(key) in forbidden or str(value) in forbidden for key, value in obj.items()):
                    raise ValueError('Active PDF content is forbidden.')
                pending.extend((value, depth + 1) for value in obj.values())
            elif isinstance(obj, ArrayObject):
                pending.extend((value, depth + 1) for value in obj)
    except Exception as exc:
        raise ValueError('Invalid or active PDF document.') from exc


def validate_content(filename, content):
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_SIZE:
        raise ValueError('Proof must contain between 1 byte and 5 MiB.')
    name = PureWindowsPath(str(filename)).name
    if (not name or len(name) > 255 or name in {'.', '..'}
            or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name)
            or name.endswith((' ', '.'))
            or name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM%d' % n for n in range(10)), *('LPT%d' % n for n in range(10))}):
        raise ValueError('Unsafe proof filename.')
    suffix = PureWindowsPath(name).suffix.lower()
    if content.startswith(b'%PDF-'):
        if (suffix != '.pdf' or not re.match(rb'%PDF-[12]\.\d', content)
                or not content.rstrip().endswith(b'%%EOF')
                or not re.search(rb'\bstartxref\s+\d+', content)
                or b'/Type /Catalog' not in content or b'/Type /Page' not in content
                or re.search(rb'/(JavaScript|JS|Launch|EmbeddedFile|OpenAction|AA)\b', content)):
            raise ValueError('Invalid or active PDF document.')
        offset = int(re.findall(rb'\bstartxref\s+(\d+)', content)[-1])
        if (offset >= len(content) or not (content[offset:].startswith(b'xref')
                or re.match(rb'\d+\s+\d+\s+obj', content[offset:]))
                or not re.search(rb'\d+\s+\d+\s+obj\b', content)
                or b'endobj' not in content):
            raise ValueError('Invalid PDF cross-reference structure.')
        _validate_pdf_objects(content)
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice
        from PySide6.QtPdf import QPdfDocument
        buffer = QBuffer()
        buffer.setData(QByteArray(content))
        buffer.open(QIODevice.ReadOnly)
        document = QPdfDocument()
        document.load(buffer)
        if document.status() != QPdfDocument.Status.Ready or not 0 < document.pageCount() <= 1000:
            raise ValueError('Invalid, encrypted or excessive PDF structure.')
        document.close()
        mime = 'application/pdf'
    else:
        png = content.startswith(b'\x89PNG\r\n\x1a\n')
        jpeg = content.startswith(b'\xff\xd8\xff')
        if not ((png and suffix == '.png') or (jpeg and suffix in {'.jpg', '.jpeg'})):
            raise ValueError('Filename and PDF/PNG/JPEG signature must match.')
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice
        from PySide6.QtGui import QImageReader
        buffer = QBuffer()
        buffer.setData(QByteArray(content))
        buffer.open(QIODevice.ReadOnly)
        reader = QImageReader(buffer)
        size = reader.size()
        if size.width() <= 0 or size.height() <= 0 or size.width() * size.height() > 25000000:
            raise ValueError('Invalid or excessive image dimensions.')
        if reader.read().isNull():
            raise ValueError('Invalid image structure.')
        mime = 'image/png' if png else 'image/jpeg'
    return name, mime


class ProofService:
    def __init__(self, session):
        self.session = session

    def attach(self, revision_id, filename, content: bytes):
        name, mime = validate_content(filename, content)
        revision = self.session.get(AttendanceRevision, revision_id)
        if revision is None or revision.status != 'excused':
            raise ValueError('Proof requires an excused attendance revision.')
        digest = hashlib.sha256(content).hexdigest()
        existing = self.session.scalar(select(ProofDocument).where(
            ProofDocument.revision_id == revision_id, ProofDocument.sha256 == digest))
        if existing:
            self.read(existing.id)
            return existing
        connection = self.session.connection()
        # sqlite3 legacy mode does not BEGIN for SELECT; a first SAVEPOINT
        # would otherwise become a committed outer transaction on RELEASE.
        if connection.dialect.name == 'sqlite' and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql('BEGIN')
        with self.session.begin_nested():
            doc = ProofDocument(revision_id=revision_id, filename=name, mime=mime,
                                size=len(content), sha256=digest, sealed=False)
            self.session.add(doc)
            self.session.flush()
            encoded = base64.b64encode(content).decode('ascii')
            self.session.add_all(ProofChunk(document_id=doc.id, position=i // CHUNK_SIZE,
                data_text=encoded[i:i + CHUNK_SIZE]) for i in range(0, len(encoded), CHUNK_SIZE))
            self.session.flush()
            doc.sealed = True
            self.session.flush()
            self.read(doc.id)
        return doc

    def read(self, document_id):
        doc = self.session.get(ProofDocument, document_id)
        if doc is None or not doc.sealed:
            raise ValueError('Proof document is missing or unfinished.')
        chunks = list(self.session.scalars(select(ProofChunk).where(
            ProofChunk.document_id == doc.id).order_by(ProofChunk.position)))
        if (not chunks or [c.position for c in chunks] != list(range(len(chunks)))
                or any(not 0 < len(c.data_text) <= CHUNK_SIZE for c in chunks)
                or sum(len(c.data_text) for c in chunks) > ((MAX_SIZE + 2) // 3) * 4):
            raise ValueError('Invalid proof chunks.')
        try:
            encoded = ''.join(c.data_text for c in chunks)
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('Invalid proof encoding.') from exc
        if (base64.b64encode(content).decode('ascii') != encoded or len(content) != doc.size
                or hashlib.sha256(content).hexdigest() != doc.sha256):
            raise ValueError('Proof integrity check failed.')
        name, mime = validate_content(doc.filename, content)
        if name != doc.filename or mime != doc.mime:
            raise ValueError('Invalid proof metadata.')
        return name, mime, content

    def list_for_attendance(self, attendance_id):
        return list(self.session.scalars(select(ProofDocument).join(AttendanceRevision,
            AttendanceRevision.id == ProofDocument.revision_id).where(
            AttendanceRevision.attendance_id == attendance_id, ProofDocument.sealed.is_(True))
            .order_by(ProofDocument.id)))
