"""
Пакет моделей проекта.

Импорты из этого файла обеспечивают регистрацию всех ORM-моделей
в `Base.metadata`.
"""
from app.models.attendance import Attendance
from app.models.base import Base
from app.models.comment import Comment
from app.models.group import Group
from app.models.group_membership import GroupMembership
from app.models.lesson import Lesson
from app.models.lesson_participant import LessonParticipant
from app.models.mark import Mark
from app.models.schedule import Schedule
from app.models.schedule_group_link import ScheduleGroupLink
from app.models.student import Student
from app.models.academic import (
    AcademicYear, AcademicTerm, Discipline, CourseOffering, CourseOfferingGroup,
    TeachingModule, AcademicSelection,
)
from app.models.education import (
    AssessmentEvent, AssessmentAttempt, Consultation, ConsultationVisit, LabWork,
    ChecklistVersion, ChecklistCriterion, CriterionAnswer, ResultCorrection,
    EventCancellation, AttendanceRevision, NonTeachingDay, LessonDisposition,
    IndividualPlan, PlanStage, PlanEntry, TeachingAudit,
)
from app.models.journal_activity import (Classroom, SeatingLayout, Seat, LessonLayout,
                                         SeatAssignment, BehaviorCategory, BehaviorEvent, BehaviorCorrection)
from app.models.attendance_proof import ProofDocument, ProofChunk

__all__ = [
    "Base",
    "Group",
    "GroupMembership",
    "Student",
    "Schedule",
    "ScheduleGroupLink",
    "Lesson",
    "LessonParticipant",
    "Attendance",
    "Mark",
    "Comment",
    "AcademicYear", "AcademicTerm", "Discipline", "CourseOffering",
    "CourseOfferingGroup", "TeachingModule", "AcademicSelection",
    "AssessmentEvent", "AssessmentAttempt", "Consultation", "ConsultationVisit", "LabWork",
    "ChecklistVersion", "ChecklistCriterion", "CriterionAnswer", "ResultCorrection",
    "EventCancellation", "AttendanceRevision", "NonTeachingDay", "LessonDisposition",
    "IndividualPlan", "PlanStage", "PlanEntry", "TeachingAudit",
    "Classroom", "SeatingLayout", "Seat", "LessonLayout", "SeatAssignment",
    "BehaviorCategory", "BehaviorEvent", "BehaviorCorrection", "ProofDocument", "ProofChunk",
]
