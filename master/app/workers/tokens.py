"""Tokens temporales de incorporación (los que lleva el QR)."""
import secrets
import time
from typing import Callable, Dict


class Tokens:
    def __init__(self, ttl_s: float, reloj: Callable[[], float] = time.time):
        self.ttl_s, self.reloj = ttl_s, reloj
        self._vence: Dict[str, float] = {}

    def crear(self) -> str:
        """Token nuevo. Los anteriores siguen vigentes hasta que expiren (varios celulares pueden usar el mismo QR)."""
        self._limpiar()
        t = secrets.token_urlsafe(6)
        self._vence[t] = self.reloj() + self.ttl_s
        return t

    def valido(self, token: str) -> bool:
        self._limpiar()
        return token in self._vence

    def _limpiar(self):
        ahora = self.reloj()
        for t in [t for t, v in self._vence.items() if v <= ahora]:
            del self._vence[t]
