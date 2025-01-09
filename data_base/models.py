from typing import List

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import sessionmaker

# Создаем подключение к базе данных
engine = create_engine('sqlite:///data.db', echo=True)
Base = declarative_base()

Session = sessionmaker(bind=engine)
session = Session()


class Marker(Base):
    """Базовый класс определяющий маркер."""

    __tablename__ = 'marker'

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(String, nullable=False)
    value = Column(String, nullable=False)
    parent = mapped_column(ForeignKey(f"{__tablename__}.id"), nullable=True)

    def get_childs(self):
        """Получение дочерних маркеров."""
        return session.scalars(select(Marker).filter_by(parent=self.id)).fetchall()

    def get_notes(self):
        """Получение заметок, связанных с маркером."""
        return session.scalars(select(Note).filter_by(marker=self.id)).fetchall()

    def to_dict(self):
        """Преобразование маркера в словарь."""
        return {
            "marker": self.value,
            "id": self.id,
        }

    def tree(self, indent=2):
        data = []
        childs = self.get_childs()
        data.append(f'{" " * indent}{self.value}{"/" if len(childs) else ""}\n')
        for i in childs:
            data.append(i.tree(indent + 2))
            # data.append(f'{" "*indent}{i.tree(indent+2)}\n')
        return "".join(data)

    def delete(self):
        for child in self.get_childs():
            child.delete()

        for notes in self.get_notes():
            notes.delete()

        marker = session.scalars(select(Marker).where(Marker.id == self.id)).first()
        session.delete(marker)
        session.commit()


class Note(Base):
    __tablename__ = 'note'
    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(String, nullable=False)
    value = Column(String, nullable=False)
    marker = Column(Integer, ForeignKey('marker.id'), nullable=True)  # Add this line

    def delete(self):
        note = session.scalars(select(Note).where(Note.id == self.id)).first()
        session.delete(note)
        session.commit()

    def to_dict(self):
        return {
            "value": self.value,
            "id": self.id,
        }



try:
    Base.metadata.create_all(bind=engine)
except:
    pass

if __name__ == '__main__':
    marker1 = Marker(value='Value 1', user_id="12")
    session.add(marker1)
    session.commit()

    marker2 = Marker(value='Value 2', user_id="12", parent=marker1.id)
    session.add(marker2)
    session.commit()

    marker3 = Marker(value='Value 3', user_id="12", parent=marker2.id)
    session.add(marker3)
    session.commit()

    marker4 = Marker(value='Value 4', user_id="12", parent=marker1.id)
    session.add(marker4)
    session.commit()

    marker5 = Marker(value='Value 5', user_id="12", parent=marker4.id)
    session.add(marker5)
    session.commit()
    #
    note1 = Note(value='Value 1', marker=marker4.id)
    session.add(note1)
    session.commit()

    note2 = Note(value='Value 2', marker=marker4.id)
    session.add(note2)
    session.commit()

    # marker1 = Marker(value='Value 1')
    # session.add(marker1)
    # session.commit()
    #
    # marker2 = Marker(value='Value 2', parent=marker1.id)
    # session.add(marker2)
    # session.commit()
