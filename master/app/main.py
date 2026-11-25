"""Arranque del Master.  Desde la carpeta master/:

    python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
"""
from . import config
from .coordinador import Coordinador
from .storage.sqlite import SqliteStorage
from .transport.api import crear_app

app = crear_app(Coordinador(storage=SqliteStorage(config.BASE_DE_DATOS)))
