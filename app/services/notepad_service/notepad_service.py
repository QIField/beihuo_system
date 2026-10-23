# -*- coding:utf-8 -*-
"""
个人记事本 - 业务编排层

职责：字段校验、数据归属校验、增删改查编排。
规则：所有读写都限定在当前登录用户范围内，非本人笔记一律拒绝。
"""

from app.utils.orm.session import orm_session
from .notepad_repository import NotepadRepository

MAX_TITLE_LEN = 50
MAX_CONTENT_LEN = 5000


class NotepadServiceError(Exception):
    pass


class NotepadService:

    @staticmethod
    def list_notes(user_id, keyword=None):
        NotepadRepository.ensure_table()
        keyword = NotepadService._clean_keyword(keyword)
        with orm_session() as session:
            rows = NotepadRepository.list_by_user(session, user_id, keyword)
            return [row.to_dict() for row in rows]

    @staticmethod
    def create_note(user_id, username, title, content):
        NotepadRepository.ensure_table()
        title, content = NotepadService._validate_fields(title, content)
        with orm_session() as session:
            note = NotepadRepository.create(
                session, user_id=user_id, username=username,
                title=title, content=content,
            )
            return note.to_dict()

    @staticmethod
    def update_note(user_id, note_id, title, content):
        NotepadRepository.ensure_table()
        title, content = NotepadService._validate_fields(title, content)
        with orm_session() as session:
            note = NotepadService._get_owned_note(session, user_id, note_id)
            NotepadRepository.update_fields(session, note, title, content)
            return note.to_dict()

    @staticmethod
    def delete_note(user_id, note_id):
        NotepadRepository.ensure_table()
        with orm_session() as session:
            note = NotepadService._get_owned_note(session, user_id, note_id)
            NotepadRepository.delete(session, note)
        return True

    # ------------------------------------------------------------------
    @staticmethod
    def _get_owned_note(session, user_id, note_id):
        note = NotepadRepository.get_by_id(session, note_id)
        if not note:
            raise NotepadServiceError('笔记不存在或已删除')
        if note.user_id != user_id:
            raise NotepadServiceError('无权操作该笔记')
        return note

    @staticmethod
    def _validate_fields(title, content):
        title = (title or '').strip()
        content = (content or '').strip()
        if not content:
            raise NotepadServiceError('笔记内容不能为空')
        if len(title) > MAX_TITLE_LEN:
            raise NotepadServiceError(f'标题最多 {MAX_TITLE_LEN} 字')
        if len(content) > MAX_CONTENT_LEN:
            raise NotepadServiceError(f'内容最多 {MAX_CONTENT_LEN} 字')
        return title or None, content

    @staticmethod
    def _clean_keyword(keyword):
        keyword = (keyword or '').strip()
        return keyword or None
