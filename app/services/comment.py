"""
Сервис для сущности Comment.
"""
from app.models.comment import Comment
from app.schemas.comment import (
    CommentCreateSchema,
    CommentDeleteSchema,
    CommentFilterSchema,
    CommentUpdateSchema,
)
from app.services.base import BaseService


class CommentService(BaseService[Comment]):
    """
    Сервис подготовки операций над моделью Comment.
    """

    model = Comment
    create_schema = CommentCreateSchema
    select_schema = CommentFilterSchema
    update_schema = CommentUpdateSchema
    delete_schema = CommentDeleteSchema
    schema_fields = frozenset({"student_id", "lesson_id", "data"})
