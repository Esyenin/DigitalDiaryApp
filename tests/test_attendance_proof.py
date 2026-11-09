"""Managed documents use isolated databases, never the configured app database."""
import base64
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import Base, AttendanceRevision
from app.models.attendance_proof import ProofDocument, ProofChunk
from app.services.attendance_proof import ProofService, MAX_SIZE, validate_content
from app.ui.data.proof_migration import ensure_proof_schema, install_proof_guards


PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')


@pytest.fixture
def session(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'test_proof.db'))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        install_proof_guards(conn)
    with Session(engine) as session:
        # No global application fixtures or destructive setup. This isolated
        # schema deliberately has no enrollment guards; the revision is the boundary.
        session.add(AttendanceRevision(id=1, attendance_id=1, status='excused',
            reason='medical', source='test', occurred_at=datetime.now(timezone.utc),
            operation_key=uuid4().hex))
        session.commit()
        yield session
    engine.dispose()


def test_attach_read_idempotent_and_listing(session):
    service = ProofService(session)
    doc = service.attach(1, r'C:\private\certificate.PNG', PNG)
    session.commit()
    assert doc.filename == 'certificate.PNG'
    assert doc.approved_at.tzinfo is not None
    assert service.attach(1, 'other.png', PNG).id == doc.id
    assert service.read(doc.id) == ('certificate.PNG', 'image/png', PNG)
    assert [x.id for x in service.list_for_attendance(1)] == [doc.id]
    assert session.scalar(select(ProofChunk)).data_text == base64.b64encode(PNG).decode()


@pytest.mark.parametrize('filename', ['CON.png', 'evil:abc.png', 'evil\x00.png', 'x.png.', 'x?.png'])
def test_hostile_names(filename):
    with pytest.raises(ValueError):
        validate_content(filename, PNG)


@pytest.mark.parametrize('filename,content', [('x.jpg', PNG), ('x.png', b'bad'),
    ('x.pdf', b'%PDF-1.4\n%%EOF'), ('x.png', b'x' * (MAX_SIZE + 1))],
    ids=['extension', 'signature', 'broken-pdf', 'oversized'])
def test_invalid_content(filename, content):
    with pytest.raises(ValueError):
        validate_content(filename, content)


def test_excused_only(session):
    session.get(AttendanceRevision, 1).status = 'present'
    session.flush()
    with pytest.raises(ValueError):
        ProofService(session).attach(1, 'x.png', PNG)
    assert not list(session.scalars(select(ProofDocument)))


@pytest.mark.parametrize('sql', [
    "UPDATE proof_documents SET filename='changed.png' WHERE id=1",
    'DELETE FROM proof_documents WHERE id=1',
    "UPDATE proof_chunks SET data_text='AAAA' WHERE document_id=1",
    'DELETE FROM proof_chunks WHERE document_id=1',
    "INSERT INTO proof_chunks(document_id,position,data_text) VALUES(1,1,'AAAA')",
    'UPDATE proof_documents SET sealed=0 WHERE id=1',
])
def test_direct_mutations_rejected(session, sql):
    ProofService(session).attach(1, 'x.png', PNG)
    session.commit()
    with pytest.raises(DBAPIError):
        session.execute(text(sql))
    session.rollback()
    assert ProofService(session).read(1)[2] == PNG


def test_read_detects_tampering_even_without_guards(session):
    service = ProofService(session)
    doc = service.attach(1, 'x.png', PNG)
    session.commit()
    session.execute(text('DROP TRIGGER proof_proof_chunks_update'))
    session.execute(text("UPDATE proof_chunks SET data_text='AAAA'"))
    session.commit()
    session.expire_all()
    with pytest.raises(ValueError, match='integrity'):
        service.read(doc.id)


def test_migration_repeat_and_backup(tmp_path):
    path = tmp_path / 'test_migrate.db'
    engine = create_engine('sqlite:///' + str(path))
    # Existing database; only the additive proof tables are created.
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE sentinel (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('INSERT INTO sentinel VALUES(37)')
    ensure_proof_schema(engine)
    ensure_proof_schema(engine)
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT id FROM sentinel').scalar() == 37
    assert len(list(tmp_path.glob('*.pre-proof-*.bak'))) == 1
    engine.dispose()


def test_postgresql_backup_requires_no_external_binary_or_files(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.ui.data.proof_migration import _backup
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('PATH', '')
    _backup(SimpleNamespace(dialect=SimpleNamespace(name='postgresql')))
    assert list(tmp_path.iterdir()) == []


def test_archive_column_types_and_content(session):
    from sqlalchemy import String
    service = ProofService(session)
    doc = service.attach(1, 'x.png', PNG)
    session.commit()
    assert isinstance(ProofChunk.__table__.c.data_text.type, String)
    assert ProofChunk.__table__.c.data_text.type.length == 12000
    # Reconstruct using only the string values an XLSX archive carries.
    encoded = ''.join(session.scalars(select(ProofChunk.data_text).order_by(ProofChunk.position)))
    restored = base64.b64decode(encoded, validate=True)
    assert hashlib.sha256(restored).hexdigest() == doc.sha256
    assert len(restored) == doc.size


def test_transaction_rollback(session):
    ProofService(session).attach(1, 'x.png', PNG)
    session.rollback()
    assert not list(session.scalars(select(ProofDocument)))
    assert not list(session.scalars(select(ProofChunk)))


def pdf_bytes(catalog_extra=b'', action=None):
    content = b'%PDF-1.4\n'
    objects = [b'<< /Type /Catalog /Pages 2 0 R ' + catalog_extra + b' >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>']
    if action is not None:
        objects.append(action)
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content += str(index).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    xref = len(content)
    content += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    content += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    content += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n'.encode() + str(xref).encode() + b'\n%%EOF\n'
    return content


@pytest.mark.parametrize('indirect', [False, True])
def test_encoded_active_pdf_names_rejected(indirect):
    action = b'<< /S /Java#53cript /J#53 (app.alert\(1\)) >>'
    content = pdf_bytes(b'/Open#41ction ' + (b'4 0 R' if indirect else action),
                        action if indirect else None)
    with pytest.raises(ValueError, match='active PDF'):
        validate_content('active.pdf', content)


def test_pdf_parser_and_signature(session):
    content = pdf_bytes()
    service = ProofService(session)
    doc = service.attach(1, 'evidence.pdf', content)
    assert service.read(doc.id) == ('evidence.pdf', 'application/pdf', content)
    with pytest.raises(ValueError):
        service.attach(1, 'evidence.png', content)
    with pytest.raises(ValueError):
        service.attach(1, 'bad.pdf', content.replace(b'/Type /Page', b'/Type /XXXX'))


def test_jpeg_structure():
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage
    image = QImage(2, 2, QImage.Format_RGB32)
    image.fill(0xffffff)
    stream = QBuffer()
    stream.open(QIODevice.WriteOnly)
    assert image.save(stream, 'JPEG')
    assert validate_content('evidence.jpeg', bytes(stream.data()))[1] == 'image/jpeg'
    with pytest.raises(ValueError):
        validate_content('broken.jpg', b'\xff\xd8\xffbroken')


def test_raw_sealed_insert_rejected(session):
    with pytest.raises(DBAPIError):
        session.execute(text("""INSERT INTO proof_documents
            (revision_id,filename,mime,size,sha256,sealed,approved_at)
            VALUES(1,'x.png','image/png',68,:digest,1,CURRENT_TIMESTAMP)"""),
            {'digest': hashlib.sha256(PNG).hexdigest()})
    session.rollback()


def test_dialog_read_only(session, monkeypatch):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from types import SimpleNamespace
    from PySide6.QtWidgets import QApplication, QWidget
    from app.models import Attendance
    from app.ui.windows.proof_dialog import ProofDialog
    application = QApplication.instance() or QApplication([])
    session.add(Attendance(id=1, student_id=1, lesson_id=1, is_visited=False))
    session.commit()
    ProofService(session).attach(1, 'x.png', PNG)
    session.commit()
    window = QWidget()
    window.repository = SimpleNamespace(session=session)
    before = session.connection().connection.driver_connection.total_changes
    dialog = ProofDialog(window, 1, 1)
    assert dialog.revisions.count() == 1
    assert dialog.documents.count() == 1
    assert dialog.attach_button.isEnabled()
    assert session.connection().connection.driver_connection.total_changes == before
    dialog.close()
    window.close()
