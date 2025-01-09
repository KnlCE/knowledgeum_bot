from typing import List

from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker
from fuzzywuzzy import fuzz
from sqlalchemy.orm import Session

from data_base.models import Marker, Note

engine = create_engine('sqlite:///data.db')

Session = sessionmaker(bind=engine)
session = Session()


def create_marker(user_id, name, parent_marker=None):
    """Функция для создания маркера."""
    user_id = str(user_id)
    if parent_marker and not session.scalars(
            select(Marker).where(Marker.id == int(parent_marker))).first().user_id == user_id:
        return False

    marker = Marker(user_id=user_id, value=name, parent=int(parent_marker) if parent_marker else None)
    session.add(marker)
    session.commit()
    return marker


def delete_marker(user_id, marker_id):
    """Удаление маркера."""
    user_id = str(user_id)
    if (maker := session.scalars(select(Marker).where(Marker.id == int(marker_id))).first()).user_id == user_id:
        maker.delete()
        return True
    return False


def create_note(user_id, marker_id, value):
    """Создание заметки."""
    with Session() as session:
        note = Note(user_id=str(user_id), value=value, marker=marker_id)
        session.add(note)
        session.commit()
    return note


def delete_note(user_id, note_id):
    """Удаление заметки."""
    user_id = str(user_id)
    note = session.scalars(select(Note).where(Note.id == int(note_id))).first()
    if note.get_marker().user_id == user_id:
        note.delete()
        return True
    return False


def delete_note_pos(user_id, marker_id, note_pos):
    """Удаление заметки по позиции в списке."""
    notes = get_notes(user_id, marker_id)
    note_id = notes[int(note_pos)]["id"]
    delete_note(user_id, note_id)

def get_root_markers(user_id) -> List[Marker]:
    """Получение корневых маркеров пользователя."""
    markers = session.scalars(select(Marker).filter(and_(Marker.user_id == str(user_id)), Marker.parent == None))
    # markers = [i.to_dict() for i in markers]
    return markers


def get_child_markers(user_id, marker):
    """Получение дочерних маркеров для конкретного маркера."""
    markers = session.scalars(select(Marker).where(Marker.user_id == str(user_id)).filter(Marker.parent == int(marker)))
    # markers = [i.to_dict() for i in markers]
    return markers


def get_path(user_id, marker):
    """Получение полного пути к маркеру."""
    marker = session.scalars(select(Marker).filter(and_(Marker.user_id == str(user_id),
                                                        Marker.id == int(marker)))).first()
    if marker.parent:
        return get_path(user_id, marker.parent) + [marker.value, ]
    else:
        return [marker.value, ]


def get_parent_marker(user_id, marker):
    """Получение родительского маркера."""
    marker = session.scalars(select(Marker).filter(and_(Marker.user_id == str(user_id),
                                                        Marker.id == int(marker)))).first()
    return marker.parent


def get_notes_from_location(user_id, location):
    """Получение заметок по местоположению."""
    if isinstance(location, dict):
        location = location.get('content', '').strip()
    path = [i for i in location.split("/") if i]
    
    all_markers = session.scalars(select(Marker).where(Marker.user_id == user_id)).all()
    best_match = None
    best_ratio = 0
    for marker in all_markers:
        marker_path = "/".join(get_path(user_id, marker.id))
        ratio = fuzz.ratio(location.lower(), marker_path.lower())
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = marker
    
    notes = []
    if best_match and best_ratio > 70:
        notes = [note.to_dict() for note in best_match.get_notes()]

    if not notes:
        keywords = set(location.lower().split())
        all_notes = session.scalars(select(Note).join(Marker).where(Marker.user_id == user_id)).all()
        for note in all_notes:
            note_text = note.value.lower()
            if any(keyword in note_text for keyword in keywords):
                notes.append(note.to_dict())
    
    return notes

def get_notes(user_id, marker_id):
    with Session() as session:
        marker = session.query(Marker).filter_by(id=marker_id, user_id=user_id).first()
        if marker:
            notes = session.query(Note).filter_by(marker=marker_id, user_id=user_id).all()
            return [note.to_dict() for note in notes]
    return []

def read_notes(user_id, marker):
    notes = get_notes(user_id, marker)
    return "\n".join([i["value"] for i in notes])

def get_tree(user_id):
    return "".join([i.tree() for i in get_root_markers(user_id)])
def update_note(user_id, note_id, new_text):
    with Session() as session:
        note = session.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if note:
            note.value = new_text
            session.commit()
            return True
        return False


if __name__ == '__main__':
    print(get_tree("12"))