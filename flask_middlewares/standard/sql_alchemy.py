from abc import ABC
from typing import Callable

from flask_middlewares import Middleware
from flask_sqlalchemy import SQLAlchemy


class SQLAlchemyMiddleware(Middleware, ABC):
    def __init__(self, database: SQLAlchemy):
        self.database = database


class SQLAlchemySessionFinisherMiddleware(SQLAlchemyMiddleware):
    def call_route(self, route: Callable, *args, **kwargs) -> any:
        try:
            result = route(*args, **kwargs)
            self.database.session.commit()

            return result

        except Exception as error:
            self.database.session.rollback()

            raise error