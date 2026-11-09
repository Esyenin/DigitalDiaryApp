"""Real Cyrillic PDF output from canonical DTOs, without database writes."""

import sys
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Group
from app.services.journal_reports import build_report


@pytest.fixture
def report_data(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "test_reports.db"}')
    Base.metadata.create_all(engine)
    session = Session(engine)
    group = Group(name='ИВТ-01')
    session.add(group)
    session.commit()
    course = dict(id=1, name='Высшая математика', earned=Decimal('85.25'), maximum=Decimal('100'),
                  remaining=Decimal('14.75'), debts=[], pending=[], scale100=True, excellent=True, history_complete=True)
    attendance = dict(present=2, late=1, excused=0, absent=1, unknown=1, total=5, percentage=None, complete=False)
    student = dict(id=1, name='Иванов Александр', courses=[course], attendance=attendance,
                   behavior=[dict(polarity='positive'), dict(polarity='negative'), dict(polarity='negative')], warnings=[])
    data = dict(id=group.id, name=group.name, students=[student], membership_complete=False, warnings=[],
                attendance=attendance, debtors_count=0)
    calls = []
    class Analytics:
        def __init__(self, supplied):
            assert supplied is session
        def group(self, group_id, **kwargs):
            calls.append((group_id, kwargs))
            return data
    # Exercise the PDF presenter independently of the evolving analytics implementation.
    monkeypatch.setitem(sys.modules, 'app.services.journal_analytics', SimpleNamespace(JournalAnalytics=Analytics))
    yield session, data, calls
    session.close()
    engine.dispose()


@pytest.mark.parametrize('kind', ['curator', 'dean'])
def test_cyrillic_points_and_readonly(report_data, tmp_path, kind):
    session, data, calls = report_data
    before = list(session.connection().exec_driver_sql('SELECT * FROM groups'))
    dump = list(session.connection().connection.driver_connection.iterdump())
    changes = session.connection().exec_driver_sql('SELECT total_changes()').scalar()
    path = build_report(session, tmp_path / f'{kind}.pdf', kind, date(2030, 2, 1),
                        term_id=7, group_ids=[data['id']], offering_ids=[3], start_date=date(2030, 1, 1))
    assert path.read_bytes().startswith(b'%PDF-')
    text = '\n'.join(page.extract_text() for page in PdfReader(path).pages)
    assert 'Иванов Александр' in text and 'Высшая математика' in text
    assert '85.25' in text and 'Страница 1' in text
    assert 'История состава неполна' in text
    if kind == 'curator':
        assert '+1 / -2' in text and '85.25/100' in text
        assert 'Невыполненные обязательные работы' in ' '.join(text.split())
    assert 'Отличные результаты' in text
    excellent_section = text.split('85-100 без долгов и ожидаемых результатов')[1].split('Ограничение:')[0]
    assert 'Иванов Александр' in excellent_section
    assert calls[0][1]['term_id'] == 7 and calls[0][1]['offering_ids'] == [3]
    assert list(session.connection().exec_driver_sql('SELECT * FROM groups')) == before
    assert list(session.connection().connection.driver_connection.iterdump()) == dump
    assert session.connection().exec_driver_sql('SELECT total_changes()').scalar() == changes
    assert not session.new and not session.dirty


def test_long_names_repeated_headers_and_debts(report_data, tmp_path):
    session, data, _ = report_data
    original = data['students'][0]
    data['students'] = [dict(original, id=i, name=f'Студент {i:03} ' + 'Оченьдлиннаяфамилия' * 5,
                             courses=[dict(original['courses'][0], name='Дисциплина ' + 'длинноеназвание' * 12,
                                           debts=[dict(id=1, title='Защита лабораторной работы')])] * 3)
                        for i in range(80)]
    path = build_report(session, tmp_path / 'long.pdf', as_of=date(2030, 2, 1))
    pages = PdfReader(path).pages
    assert len(pages) > 5
    texts = [p.extract_text() for p in pages]
    assert sum('Баллы / максимум' in t for t in texts) > 1
    assert all(f'Страница {i}' in t for i, t in enumerate(texts, 1))
    assert all('2030-02-01' in t for t in texts)
    assert 'Студент 079' in '\n'.join(texts)
    assert 'Защита лабораторной работы' in '\n'.join(texts)


def test_dean_does_not_normalize_or_include_pending(report_data, tmp_path):
    session, data, _ = report_data
    data['students'][0]['courses'][0].update(maximum=Decimal('50'), earned=Decimal('45'), scale100=False)
    text = '\n'.join(p.extract_text() for p in PdfReader(build_report(
        session, tmp_path / 'dean.pdf', kind='dean')).pages)
    excellent_section = text.split('85-100 без долгов и ожидаемых результатов')[1].split('Ограничение:')[0]
    assert 'Иванов Александр' not in excellent_section
    assert 'Нет данных' in excellent_section


def test_invalid_filters_and_empty_selection(report_data, tmp_path):
    session, _, _ = report_data
    with pytest.raises(ValueError):
        build_report(session, tmp_path / 'bad.pdf', kind='other')
    with pytest.raises(ValueError):
        build_report(session, tmp_path / 'bad.pdf', start_date=date(2031, 1, 1), end_date=date(2030, 1, 1))
    path = build_report(session, tmp_path / 'empty.pdf', group_ids=[])
    assert 'Нет групп' in PdfReader(path).pages[0].extract_text()


def test_dean_canonical_means_and_unique_transferred_students(report_data, tmp_path):
    session, data, _ = report_data
    session.add(Group(name='ИВТ-02'))
    session.commit()
    data['courses'] = [dict(id=1, name='Высшая математика', maximum=Decimal('50'),
                            average=Decimal('12.34'), observed=1, students=2, debtors=1)]
    data['students'][0]['courses'][0]['debts'] = [dict(id=9, title='Обязательная работа')]
    text = '\n'.join(p.extract_text() for p in PdfReader(build_report(
        session, tmp_path / 'transferred.pdf', kind='dean')).pages)
    assert '12.34' in text
    assert 'С результатами' in text and 'Известных студентов' in text
    assert 'Уникальных известных студентов: 1; уникальных должников: 1' in ' '.join(text.split())


def test_curator_outstanding_count_and_excellence(report_data, tmp_path):
    session, data, _ = report_data
    original = data['students'][0]
    data['students'].append(dict(original, id=2, name='Петров Борис', courses=[dict(
        original['courses'][0], debts=[dict(id=10, title='Контрольная работа'), dict(id=11, title='Защита')])]))
    text = '\n'.join(p.extract_text() for p in PdfReader(build_report(session, tmp_path / 'count.pdf')).pages)
    assert 'Невыполненные обязательные работы' in ' '.join(text.split())
    assert '+1 / -2\n2' in text
    section = text.split('85-100 без долгов и ожидаемых результатов')[1].split('Ограничение:')[0]
    assert 'Иванов Александр' in section and 'Петров Борис' not in section


def test_single_student_row_larger_than_page(report_data, tmp_path):
    session, data, _ = report_data
    student = data['students'][0]
    original = student['courses'][0]
    student['courses'] = [dict(original, id=i, name=f'Дисциплина {i:03} ' + 'Длинное название курса ' * 8)
                          for i in range(60)]
    path = build_report(session, tmp_path / 'giant_row.pdf', as_of=date(2030, 2, 1))
    pages = PdfReader(path).pages
    texts = [page.extract_text() for page in pages]
    assert len(pages) > 3
    assert sum('Баллы / максимум' in text for text in texts) > 1
    assert all(f'Страница {i}' in text for i, text in enumerate(texts, 1))
    assert 'Дисциплина 059' in '\n'.join(texts)
    assert 'Иванов Александр' in '\n'.join(texts)
