"""Movable draft templates and immutable lesson seating snapshots."""
from uuid import uuid4
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QComboBox, QGraphicsScene, QGraphicsView, QGraphicsRectItem, QGraphicsSimpleTextItem,
    QInputDialog, QMenu, QMessageBox, QListWidget)
from sqlalchemy import select
from app.models import Student, Lesson
from app.models.journal_activity import Classroom, SeatingLayout, BehaviorCategory
from app.services.journal_activity import ActivityService, DEFAULT_CATEGORIES


class SeatItem(QGraphicsRectItem):
    def __init__(self, workspace, seat, student=None, draft=False):
        super().__init__(0, 0, 140, 65)
        self.workspace, self.seat, self.student = workspace, seat, student
        self.setPos(float(seat['x']), float(seat['y']))
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable, draft)
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.setBrush(Qt.GlobalColor.lightGray if student is None else Qt.GlobalColor.cyan)
        label = QGraphicsSimpleTextItem(seat['label'], self)
        label.setPos(5, 4)
        if student:
            name = QGraphicsSimpleTextItem(f'{student.surname}\n{student.first_name}', self)
            name.setScale(min(1.0, 125 / max(name.boundingRect().width(), 1)))
            name.setPos(5, 23)
        self.setToolTip(seat['label'] if student is None else f'{student.surname} {student.first_name}')

    def contextMenuEvent(self, event):
        if not self.workspace.draft:
            self.workspace.seat_menu(self, event.screenPos())

    def mouseDoubleClickEvent(self, event):
        if self.student:
            self.workspace.attendance_requested.emit(self.workspace.lesson_id, self.student.id)
        else:
            super().mouseDoubleClickEvent(event)


class SeatingWorkspace(QWidget):
    attendance_requested = Signal(int, int)
    profile_requested = Signal(int)

    def __init__(self, window, lesson_id=None):
        super().__init__()
        self.window, self.repo, self.lesson_id = window, window.repository, lesson_id
        self.draft = False
        outer = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.lesson = QComboBox()
        self.room = QComboBox()
        self.layout_choice = QComboBox()
        for box in (self.lesson, self.room, self.layout_choice):
            box.setMinimumContentsLength(10)
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            bar.addWidget(box)
        outer.addLayout(bar)
        tools = QGridLayout()
        for index, (title, action) in enumerate([('New room', self.new_room), ('New template', self.new_draft),
                              ('Clone version', self.clone_draft), ('Add seat', self.add_seat),
                              ('Save version', self.save_draft), ('Use for lesson', self.attach),
                              ('New category', self.new_category), ('Correct event', self.correct_event)]):
            button = QPushButton(title)
            button.clicked.connect(action)
            tools.addWidget(button, index // 4, index % 4)
        outer.addLayout(tools)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumSize(240, 160)
        outer.addWidget(self.view, 1)
        self.history = QListWidget()
        self.history.setMaximumHeight(150)
        outer.addWidget(self.history)
        self.lesson.currentIndexChanged.connect(self.change_lesson)
        self.room.currentIndexChanged.connect(self.load_layouts)
        self.reload()

    def action(self, action_name, **kwargs):
        try:
            result = self.repo.activity_action(action_name, **kwargs)
            self.reload()
            return result
        except Exception as exc:
            QMessageBox.warning(self, 'Activity', str(exc))
            return None

    def reload(self):
        for box, model, label in ((self.lesson, Lesson, lambda r: f'{r.date} #{r.id}'),
                                  (self.room, Classroom, lambda r: r.name)):
            old = self.lesson_id if box is self.lesson else box.currentData()
            box.blockSignals(True)
            box.clear()
            for row in self.repo.session.scalars(select(model).order_by(model.id)):
                box.addItem(label(row), row.id)
            index = box.findData(old)
            box.setCurrentIndex(index if index >= 0 else 0)
            box.blockSignals(False)
        self.lesson_id = self.lesson.currentData()
        self.load_layouts()
        self.render()

    def load_layouts(self):
        self.layout_choice.clear()
        for row in self.repo.session.scalars(select(SeatingLayout).where(SeatingLayout.room_id == self.room.currentData()).order_by(SeatingLayout.revision)):
            self.layout_choice.addItem(f'{row.name} v{row.revision}', row.id)

    def change_lesson(self):
        self.lesson_id = self.lesson.currentData()
        self.draft = False
        self.render()

    def render(self):
        self.scene.clear()
        self.history.clear()
        if self.lesson_id is None:
            return
        service = ActivityService(self.repo.session)
        data = service.seating(self.lesson_id)
        occupants = {a.seat_id: self.repo.session.get(Student, a.student_id) for a in data['assignments']}
        for seat in data['seats']:
            self.scene.addItem(SeatItem(self, dict(id=seat.id, label=seat.label, x=seat.x, y=seat.y), occupants.get(seat.id)))
        from app.models.journal_activity import BehaviorEvent, BehaviorCorrection
        for event in self.repo.session.scalars(select(BehaviorEvent).where(BehaviorEvent.lesson_id == self.lesson_id)):
            correction = self.repo.session.scalar(select(BehaviorCorrection).where(BehaviorCorrection.event_id == event.id).order_by(BehaviorCorrection.id.desc()).limit(1))
            student = self.repo.session.get(Student, correction.student_id if correction else event.student_id)
            category = self.repo.session.get(BehaviorCategory, event.category_id)
            self.history.addItem(f'#{event.id} {student.surname} {student.first_name}: {category.name} | {event.occurred_at.isoformat()} | {event.comment}' + (f' | corrected: {correction.reason}' if correction else ''))
            self.history.item(self.history.count()-1).setData(Qt.ItemDataRole.UserRole, event.id)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))

    def new_room(self):
        name, ok = QInputDialog.getText(self, 'Classroom', 'Name')
        if ok:
            self.action('create_room', name=name)

    def new_draft(self):
        self.draft = True
        self.scene.clear()
        self.scene.setSceneRect(0, 0, 1000, 700)

    def clone_draft(self):
        from app.models.journal_activity import Seat
        self.new_draft()
        for s in self.repo.session.scalars(select(Seat).where(Seat.layout_id == self.layout_choice.currentData())):
            self.scene.addItem(SeatItem(self, dict(label=s.label, x=s.x, y=s.y), draft=True))

    def add_seat(self):
        if not self.draft:
            return
        label, ok = QInputDialog.getText(self, 'Seat', 'Label')
        if ok and label.strip():
            self.scene.addItem(SeatItem(self, dict(label=label.strip(), x=20, y=20), draft=True))

    def save_draft(self):
        if not self.draft:
            return
        name, ok = QInputDialog.getText(self, 'Template', 'Version name')
        if ok:
            seats = [dict(label=i.seat['label'], x=i.x(), y=i.y()) for i in self.scene.items() if isinstance(i, SeatItem)]
            if self.action('create_layout', room_id=self.room.currentData(), name=name, seats=seats) is not None:
                self.draft = False

    def attach(self):
        if self.lesson_id and self.layout_choice.currentData():
            self.action('attach_layout', lesson_id=self.lesson_id, layout_id=self.layout_choice.currentData())
            self.draft = False

    def roster_choice(self):
        rows = self.repo.students_for_lesson(self.repo.session.get(Lesson, self.lesson_id))
        labels = [f'{s.surname} {s.first_name} #{s.id}' for s in rows]
        if not labels:
            return None
        label, ok = QInputDialog.getItem(self, 'Student', 'Student', labels, editable=False)
        return rows[labels.index(label)].id if ok else None

    def seat_menu(self, item, position):
        menu = QMenu(self)
        if item.student:
            menu.addAction('Attendance', lambda: self.attendance_requested.emit(self.lesson_id, item.student.id))
            menu.addAction('Profile', lambda: self.profile_requested.emit(item.student.id))
            categories = list(self.repo.session.scalars(select(BehaviorCategory).order_by(BehaviorCategory.name)))
            for name, polarity in DEFAULT_CATEGORIES:
                if name not in {c.name for c in categories}:
                    menu.addAction(name, lambda checked=False, n=name: self.action('record_typical_behavior',
                        student_id=item.student.id, lesson_id=self.lesson_id, name=n, operation_key=uuid4().hex))
            for category in categories:
                menu.addAction(category.name, lambda checked=False, c=category: self.action('record_behavior', student_id=item.student.id,
                    lesson_id=self.lesson_id, category_id=c.id, comment='', source='teacher', operation_key=uuid4().hex))
            menu.addAction('Unassign', lambda: self.change_assignment(item, True))
        else:
            menu.addAction('Assign student', lambda: self.change_assignment(item, False))
        menu.exec(position)

    def change_assignment(self, item, unassign):
        student_id = item.student.id if unassign else self.roster_choice()
        if student_id is None:
            return
        reason, ok = QInputDialog.getText(self, 'Seating history', 'Reason')
        if ok:
            kwargs = dict(lesson_id=self.lesson_id, student_id=student_id, reason=reason, operation_key=uuid4().hex)
            if not unassign:
                kwargs['seat_id'] = item.seat['id']
            self.action('unassign_seat' if unassign else 'assign_seat', **kwargs)

    def new_category(self):
        name, ok = QInputDialog.getText(self, 'Category', 'Name')
        if ok:
            polarity, ok = QInputDialog.getItem(self, 'Category', 'Polarity', ['positive', 'negative'], editable=False)
            if ok:
                self.action('create_category', name=name, polarity=polarity)

    def correct_event(self):
        item = self.history.currentItem()
        if item is None:
            return
        student_id = self.roster_choice()
        reason, ok = QInputDialog.getText(self, 'Correction', 'Reason')
        if ok and student_id:
            self.action('correct_behavior', event_id=item.data(Qt.ItemDataRole.UserRole), student_id=student_id, reason=reason)
