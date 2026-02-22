import datetime
from decimal import Decimal

from typing import List

from sqlalchemy import func, ForeignKey, Numeric, BigInteger, create_engine
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship

engine = create_engine('sqlite:///test.db', echo=True)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True)
    cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=10000.00)
    created: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    username: Mapped[str] = mapped_column(nullable=True)

    savings: Mapped[List['Savings']] = relationship(back_populates='user')



class Stock(Base):
    __tablename__ = 'user_savings'

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    stock: Mapped[str] = mapped_column(primary_key=True)
    quantity: Mapped[int] = mapped_column(nullable=False)

    user: Mapped['User'] = relationship(back_populates='savings')

    def __repr__(self):
        return self.__dict__.__repr__()

class Operation(Base):
    __tablename__ = 'history'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    stock: Mapped[str] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[datetime.datetime] = mapped_column(default=func.now())

Base.metadata.create_all(engine)