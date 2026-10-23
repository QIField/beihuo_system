# -*- coding:utf-8 -*-
"""
个人记事本 - 数据访问层

职责：只负责 crmapp_notepad 表的查询与写入，不做业务编排。
"""

from sqlalchemy import or_

from app.models.orm_models import NotepadNote
from app.models.orm_models.base_models import BaseModels
from app.utils.orm.session import get_engine


class NotepadRepository:

    _table_ensured = False

    @classmethod
    def ensure_table(cls):
        """幂等建表（IF NOT EXISTS），每进程只执行一次。"""
        if cls._table_ensured:
            return
        BaseModels.metadata.create_all(
            get_engine(),
            tables=[NotepadNote.__table__],
        )
        cls._table_ensured = True

    @staticmethod
    def list_by_user(session, user_id, keyword=None):
        """本人笔记，按更新时间倒序；keyword 模糊匹配标题和内容。"""
        query = session.query(NotepadNote).filter(NotepadNote.user_id == user_id)
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(or_(
                NotepadNote.title.like(like),
                NotepadNote.content.like(like),
            ))
        return query.order_by(NotepadNote.updated_time.desc(), NotepadNote.id.desc()).all()

    @staticmethod
    def get_by_id(session, note_id):
        return session.query(NotepadNote).filter(NotepadNote.id == note_id).first()

    @staticmethod
    def create(session, user_id, username, title, content):
        note = NotepadNote(
            user_id=user_id,
            username=username,
            title=title,
            content=content,
        )
        session.add(note)
        session.flush()
        return note

    @staticmethod
    def update_fields(session, note, title, content):
        note.title = title
        note.content = content
        session.flush()
        return note

    @staticmethod
    def delete(session, note):
        session.delete(note)
        session.flush()
