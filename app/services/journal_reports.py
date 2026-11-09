"""Read-only, Unicode PDF presentation of canonical journal analytics."""

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from sqlalchemy import select
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, LongTable, TableStyle, Spacer

from app.models import Group


def _font():
    name = 'JournalUnicode'
    if name not in pdfmetrics.getRegisteredFontNames():
        candidates = [Path('C:/Windows/Fonts/arial.ttf'),
                      Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            raise RuntimeError('Cyrillic PDF font missing: install Arial or DejaVu Sans.')
        pdfmetrics.registerFont(TTFont(name, str(path)))
    return name


def build_report(session, path, kind='curator', as_of=None, term_id=None,
                 group_ids=None, offering_ids=None, start_date=None, end_date=None) -> Path:
    """Build a report without flush/commit; all numbers originate in JournalAnalytics."""
    from app.services.journal_analytics import JournalAnalytics
    if kind not in ('curator', 'dean'):
        raise ValueError('Unknown report kind')
    as_of = as_of or date.today()
    if start_date and end_date and start_date > end_date:
        raise ValueError('Start date must not exceed end date')
    font = _font()
    style = ParagraphStyle('Journal', fontName=font, fontSize=8, leading=11,
                           splitLongWords=True, spaceAfter=2)
    heading = ParagraphStyle('Heading', parent=style, fontSize=13, leading=17, spaceAfter=9)
    def p(value):
        return Paragraph(escape(str(value if value is not None else 'неизвестно')).replace('\n', '<br/>'), style)
    def number(value):
        return format(Decimal(str(value)), 'f')
    def table(headers, rows, widths):
        result = LongTable([[p(v) for v in headers]] + [[p(v) for v in row] for row in rows],
                           colWidths=widths, repeatRows=1, hAlign='LEFT', splitInRow=1)
        result.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e1e9ed')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#bcc7cc')),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
        return result
    title = 'Отчёт куратора' if kind == 'curator' else 'Отчёт деканата'
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    story = [Paragraph(title, heading), p(f'На дату: {as_of}; сформирован: {generated}'),
             p(f'Семестр: {term_id or "все"}; период: {start_date or "начало"} - {end_date or as_of}')]
    page_size = landscape(A4)
    width = page_size[0] - 64
    with session.no_autoflush:
        query = select(Group).order_by(Group.name, Group.id)
        if group_ids is not None:
            query = query.where(Group.id.in_(group_ids))
        groups = list(session.scalars(query))
        analytics = JournalAnalytics(session)
        unique_students, unique_debtors = set(), set()
        for group in groups:
            data = analytics.group(group.id, term_id=term_id, as_of=as_of,
                                   start_date=start_date, end_date=end_date, offering_ids=offering_ids)
            story.extend([Spacer(1, 12), Paragraph(escape(str(data['name'])), heading)])
            students = sorted(data['students'], key=lambda s: (s['name'].casefold(), s['id']))
            unique_students.update(student['id'] for student in students)
            unique_debtors.update(student['id'] for student in students
                                  if any(course.get('debts') for course in student.get('courses', [])))
            warnings = list(data.get('warnings', []))
            if not data.get('membership_complete', False):
                warnings.append('История состава неполна; итоги относятся только к известным участникам.')
            story.append(p(f'Известных студентов: {len(students)}; должников: {data.get("debtors_count", 0)}'))
            attendance_total = data.get('attendance', {})
            story.append(p('Посещаемость группы (известные записи): ' + ', '.join(
                f'{label}: {attendance_total.get(key, 0)}' for key, label in
                [('present', 'присутствие'), ('late', 'опоздания'), ('excused', 'уважительные'),
                 ('absent', 'отсутствие'), ('unknown', 'неизвестно')])))
            rows, debts, excellent = [], [], []
            for student in students:
                attendance = student['attendance']
                behavior = student.get('behavior', [])
                positive = sum(b.get('polarity') == 'positive' for b in behavior)
                negative = sum(b.get('polarity') == 'negative' for b in behavior)
                courses = student.get('courses', [])
                score = '\n'.join(f'{c["name"]}: {number(c["earned"])}/{number(c["maximum"])} '
                                  f'(остаток {number(c["remaining"])})'
                                  for c in courses) or 'Нет курсов'
                for course in courses:
                    for debt in course.get('debts', []):
                        debts.append([student['name'], course['name'], debt['title']])
                    if (course.get('scale100') and course.get('excellent')
                            and Decimal('85') <= course['earned'] <= Decimal('100')
                            and course['maximum'] == Decimal('100')
                            and not course.get('debts') and not course.get('pending')):
                        excellent.append([student['name'], course['name'], number(course['earned'])])
                if not attendance.get('complete'):
                    warnings.append(f'{student["name"]}: посещаемость неполна.')
                warnings.extend(f'{student["name"]}: {w}' for w in student.get('warnings', []))
                for c in courses:
                    if not c.get('history_complete', False):
                        warnings.append(f'{student["name"]}, {c["name"]}: история результатов неполна.')
                rate = attendance.get('percentage')
                attendance_text = (f'Явка {attendance.get("present", 0)}, опоздания {attendance.get("late", 0)}, '
                                   f'уваж. {attendance.get("excused", 0)}, отсутств. {attendance.get("absent", 0)}, '
                                   f'неизв. {attendance.get("unknown", 0)}; '
                                   f'{number(rate) + "%" if rate is not None and attendance.get("complete") else "нет точного процента"}')
                outstanding = len({(course['id'], debt['id']) for course in courses
                                   for debt in course.get('debts', [])})
                rows.append([student['name'], score, attendance_text, f'+{positive} / -{negative}', outstanding])
            if kind == 'curator':
                story.append(table(['Студент', 'Баллы / максимум по дисциплине', 'Посещаемость', 'Поведение + / -',
                                    'Невыполненные обязательные работы'],
                                   rows or [['Нет данных', '', '', '', '']],
                                   [width*.20, width*.31, width*.27, width*.12, width*.10]))
            else:
                aggregate_rows = [[course['name'], number(course['maximum']),
                                   number(course['average']) if course.get('average') is not None else 'Нет наблюдений',
                                   course['observed'], course['students'], course['debtors']]
                                  for course in data.get('courses', [])]
                story.extend([Spacer(1, 8), p('Средние по известным результатам: без нормализации; выборка только с попытками'),
                              table(['Дисциплина', 'Максимум', 'Среднее', 'С результатами', 'Известных студентов', 'Должников'],
                                    aggregate_rows or [['Нет данных', '', '', '', '', '']],
                                    [width*.32, width*.12, width*.14, width*.14, width*.16, width*.12])])
            story.extend([Spacer(1, 8), p('Задолженности по студентам и дисциплинам'),
                          table(['Студент', 'Дисциплина', 'Задолженность'], debts or [['Нет известных задолженностей', '', '']],
                                [width*.28, width*.32, width*.40])])
            story.extend([Spacer(1, 8), p('Отличные результаты: только шкала 100, 85-100 без долгов и ожидаемых результатов'),
                          table(['Студент', 'Дисциплина', 'Баллы'], excellent or [['Нет данных', '', '']],
                                [width*.4, width*.4, width*.2])])
            for warning in dict.fromkeys(warnings):
                story.append(p(f'Ограничение: {warning}'))
        if kind == 'dean':
            story.extend([Spacer(1, 12), p('Общая сводка выбранных групп (уникальные ID, без повторного учёта переводов)'),
                          p(f'Уникальных известных студентов: {len(unique_students)}; '
                            f'уникальных должников: {len(unique_debtors)}')])
    if not groups:
        story.append(p('Нет групп по выбранным фильтрам.'))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    def footer(canvas, doc):
        canvas.setFont(font, 8)
        canvas.drawString(32, page_size[1]-22, f'{title} | {as_of} | {generated}')
        canvas.drawRightString(page_size[0]-32, 20, f'Страница {doc.page}')
    SimpleDocTemplate(str(path), pagesize=page_size, leftMargin=32, rightMargin=32,
                      topMargin=40, bottomMargin=36, title=title, author='DigitalDiaryApp').build(
                          story, onFirstPage=footer, onLaterPages=footer)
    return path
