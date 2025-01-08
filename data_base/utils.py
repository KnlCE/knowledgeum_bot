from typing import List

from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker
from fuzzywuzzy import fuzz
from sqlalchemy import or_
from .models import Note
from sqlalchemy.orm import Session

from data_base.models import catalog, Note

engine = create_engine('sqlite:///data.db')

Session = sessionmaker(bind=engine)
session = Session()


def create_catalog(user_id, name, parent_catalog=None):
    user_id = str(user_id)
    if parent_catalog and not session.scalars(
            select(catalog).where(catalog.id == int(parent_catalog))).first().user_id == user_id:
        return False

    catalog = catalog(user_id=user_id, value=name, parent=int(parent_catalog) if parent_catalog else None)
    session.add(catalog)
    session.commit()
    return catalog


def delete_catalog(user_id, catalog_id):
    user_id = str(user_id)
    if (maker := session.scalars(select(catalog).where(catalog.id == int(catalog_id))).first()).user_id == user_id:
        maker.delete()
        return True
    return False


def create_note(user_id, catalog_id, value):
    with Session() as session:
        note = Note(user_id=str(user_id), value=value, catalog=catalog_id)
        session.add(note)
        session.commit()
    return note


def delete_note(user_id, note_id):
    user_id = str(user_id)
    note = session.scalars(select(Note).where(Note.id == int(note_id))).first()
    if note.get_catalog().user_id == user_id:
        note.delete()
        return True
    return False


def delete_note_pos(user_id, catalog_id, note_pos):
    notes = get_notes(user_id, catalog_id)
    note_id = notes[int(note_pos)]["id"]
    delete_note(user_id, note_id)

def get_root_catalogs(user_id) -> List[catalog]:
    catalogs = session.scalars(select(catalog).filter(and_(catalog.user_id == str(user_id)), catalog.parent == None))
    # catalogs = [i.to_dict() for i in catalogs]
    return catalogs


def get_child_catalogs(user_id, catalog):
    catalogs = session.scalars(select(catalog).where(catalog.user_id == str(user_id)).filter(catalog.parent == int(catalog)))
    # catalogs = [i.to_dict() for i in catalogs]
    return catalogs


def get_path(user_id, catalog):
    catalog = session.scalars(select(catalog).filter(and_(catalog.user_id == str(user_id),
                                                        catalog.id == int(catalog)))).first()
    if catalog.parent:
        return get_path(user_id, catalog.parent) + [catalog.value, ]
    else:
        return [catalog.value, ]


def get_parent_catalog(user_id, catalog):
    catalog = session.scalars(select(catalog).filter(and_(catalog.user_id == str(user_id),
                                                        catalog.id == int(catalog)))).first()
    return catalog.parent


def get_notes_from_location(user_id, location):
    if isinstance(location, dict):
        location = location.get('content', '').strip()
    path = [i for i in location.split("/") if i]
    
    all_catalogs = session.scalars(select(catalog).where(catalog.user_id == user_id)).all()
    best_match = None
    best_ratio = 0
    for catalog in all_catalogs:
        catalog_path = "/".join(get_path(user_id, catalog.id))
        ratio = fuzz.ratio(location.lower(), catalog_path.lower())
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = catalog
    
    notes = []
    if best_match and best_ratio > 70:
        notes = [note.to_dict() for note in best_match.get_notes()]

    if not notes:
        keywords = set(location.lower().split())
        all_notes = session.scalars(select(Note).join(catalog).where(catalog.user_id == user_id)).all()
        for note in all_notes:
            note_text = note.value.lower()
            if any(keyword in note_text for keyword in keywords):
                notes.append(note.to_dict())
    
    return notes

def get_notes(user_id, catalog_id):
    with Session() as session:
        catalog = session.query(catalog).filter_by(id=catalog_id, user_id=user_id).first()
        if catalog:
            notes = session.query(Note).filter_by(catalog=catalog_id, user_id=user_id).all()
            return [note.to_dict() for note in notes]
    return []

def read_notes(user_id, catalog):
    notes = get_notes(user_id, catalog)
    return "\n".join([i["value"] for i in notes])

def get_tree(user_id):
    return "".join([i.tree() for i in get_root_catalogs(user_id)])
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