#!/usr/bin/env python3
"""Filas/ledgers operacionais Zydon — funções compartilhadas.

Objetivo: evitar cada cron reimplementar load/save/append de JSON crítico.
As filas continuam nos mesmos arquivos para compatibilidade, mas escrita passa por
lock atômico sempre que este módulo é usado.
"""
from __future__ import annotations

import fcntl
import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

ROOT = Path('/root/.hermes/zydon-prospeccao')
CONTROL = ROOT / 'controle'
WPP_ENVIOS = CONTROL / 'wpp_envios.json'
AGENDA_QUEUE = CONTROL / 'agenda_queue.json'
MQL_PIPELINE_QUEUE = CONTROL / 'mql_pipeline_queue.json'
MQL_EXECUTION_QUEUE = CONTROL / 'mql_execution_queue.json'
RUNTIME = CONTROL / 'runtime' / 'queue_locks'

QUEUE_REGISTRY = {
    'wpp_envios': WPP_ENVIOS,
    'agenda_queue': AGENDA_QUEUE,
    'mql_pipeline_queue': MQL_PIPELINE_QUEUE,
    'mql_execution_queue': MQL_EXECUTION_QUEUE,
}


def _lock_path(path: Path) -> Path:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    safe = str(path).replace('/', '__')
    return RUNTIME / f'{safe}.lock'


@contextmanager
def locked_path(path: str | Path):
    path = Path(path)
    lp = _lock_path(path)
    with lp.open('a+') as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def load_json(path: str | Path, default: Any):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path: str | Path, data: Any):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f'.tmp.{int(time.time()*1000)}')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def update_json_locked(path: str | Path, default: Any, updater: Callable[[Any], Any]):
    path = Path(path)
    with locked_path(path):
        data = load_json(path, default)
        new_data = updater(data)
        if new_data is None:
            new_data = data
        save_json(path, new_data)
        return new_data


def normalize_envios(data: Any) -> dict:
    if isinstance(data, dict):
        arr = data.get('envios')
        if isinstance(arr, list):
            return data
        return {'envios': [v for v in data.values() if isinstance(v, dict)]}
    if isinstance(data, list):
        return {'envios': data}
    return {'envios': []}


def append_wpp_envio_locked(row: dict, path: str | Path = WPP_ENVIOS):
    """Único dono de escrita do ledger compartilhado de WhatsApp.

    Preserva o schema histórico {"envios": [...]} e serializa read-modify-write
    com flock para impedir lost update entre crons concorrentes.
    """
    def upd(data):
        data = normalize_envios(data)
        data.setdefault('envios', []).append(dict(row or {}))
        return data
    return update_json_locked(path, {'envios': []}, upd)


# Compatibilidade: callers antigos continuam chamando append_wpp_envio, mas o
# símbolo aponta para o dono único central. Testes garantem identidade.
append_wpp_envio = append_wpp_envio_locked


def replace_wpp_envios_locked(rows: list[dict], path: str | Path = WPP_ENVIOS):
    """Substitui a lista do ledger sob lock, preservando schema histórico.

    Necessário para callers legados que calculam uma lista inteira e chamam
    save_wpp(items). O lock impede que esse write pise em outro cron no meio do
    read-modify-write do próprio caller.
    """
    def upd(_data):
        return {'envios': [dict(r or {}) for r in (rows or [])]}
    return update_json_locked(path, {'envios': []}, upd)


def update_agenda_item(key: str, mutator: Callable[[dict], None], path: str | Path = AGENDA_QUEUE):
    """Atualiza item da agenda queue por key sob lock."""
    def upd(data):
        if not isinstance(data, dict):
            data = {'items': []}
        items = data.setdefault('items', [])
        for item in items:
            if isinstance(item, dict) and str(item.get('key') or '') == str(key):
                mutator(item)
                break
        return data
    return update_json_locked(path, {'items': []}, upd)
