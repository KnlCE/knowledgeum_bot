from typing import List

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, select, Table, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import mapped_column, relationship, Mapped
from sqlalchemy.orm import sessionmaker

# Создаем подключение к базе данных
engine = create_engine('sqlite:///data.db', echo=True)
Base = declarative_base()

Session = sessionmaker(bind=engine)
session = Session()


# Определяем класс catalog
class Catalog(Base):
    __tablename__ = 'catalog'

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(String, nullable=False)
    value = Column(String, nullable=False)
    parent = mapped_column(ForeignKey(f"{__tablename__}.id"), nullable=True)

    def get_childs(self):
        return session.scalars(select(catalog).filter_by(parent=self.id)).fetchall()

    def get_notes(self):
        return session.scalars(select(Note).filter_by(catalog=self.id)).fetchall()

    def to_dict(self):
        return {
            "catalog": self.value,
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

        catalog = session.scalars(select(catalog).where(catalog.id == self.id)).first()
        session.delete(catalog)
        session.commit()


class Note(Base):
    __tablename__ = 'note'
    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(String, nullable=False)
    value = Column(String, nullable=False)
    catalog = Column(Integer, ForeignKey('catalog.id'), nullable=True)  # Add this line

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
    catalog1 = catalog(value='Value 1', user_id="12")
    session.add(catalog1)
    session.commit()

    catalog2 = catalog(value='Value 2', user_id="12", parent=catalog1.id)
    session.add(catalog2)
    session.commit()

    catalog3 = catalog(value='Value 3', user_id="12", parent=catalog2.id)
    session.add(catalog3)
    session.commit()

    catalog4 = catalog(value='Value 4', user_id="12", parent=catalog1.id)
    session.add(catalog4)
    session.commit()

    catalog5 = catalog(value='Value 5', user_id="12", parent=catalog4.id)
    session.add(catalog5)
    session.commit()
    #
    note1 = Note(value='Value 1', catalog=catalog4.id)
    session.add(note1)
    session.commit()

    note2 = Note(value='Value 2', catalog=catalog4.id)
    session.add(note2)
    session.commit()

    # catalog1 = catalog(value='Value 1')
    # session.add(catalog1)
    # session.commit()
    #
    # catalog2 = catalog(value='Value 2', parent=catalog1.id)
    # session.add(catalog2)
    # session.commit()
