"""Headless, dependency-free save editing, history, diff and atomic commit."""
from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from field_catalog import get_info
from sol_codec import (SolDocument, SolError, format_value, from_jsonable,
    get_at_path, is_leaf, iter_nodes, load_sol, parse_sol_bytes,
    parse_user_value, path_to_text, serialize_sol, set_at_path,
    to_jsonable, validate_roundtrip, value_kind)


def canonical(value):
    return json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True, allow_nan=True)


def collect_leaves(entries):
    return {path_to_text(p): (p, v) for p, v in iter_nodes(entries) if is_leaf(v)}


def describe_diff(before: SolDocument, after: SolDocument):
    before_map, after_map = collect_leaves(before.entries), collect_leaves(after.entries)
    rows = []
    for path in sorted(before_map.keys() | after_map.keys(), key=str.casefold):
        old = before_map.get(path)
        new = after_map.get(path)
        if old and new and canonical(old[1]) == canonical(new[1]):
            continue
        status = '新增' if old is None else ('删除' if new is None else '改变')
        v = new[1] if new else old[1]
        info = get_info(path)
        rows.append({'path': path, 'category': info.category,
            'label': info.label, 'type': value_kind(v),
            'old': format_value(old[1]) if old else '—',
            'new': format_value(new[1]) if new else '—', 'status': status})
    return rows


def export_rows_csv(rows: list[dict], path: str | Path):
    cols = ['path', 'category', 'label', 'type', 'old', 'new', 'status']
    with Path(path).open('w', encoding='utf-8-sig', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=cols, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


class ChangedOnDiskError(SolError):
    pass


@dataclass
class SaveResult:
    path: Path
    backup: Path | None
    byte_length: int


class EditorSession:
    def __init__(self):
        self.doc: SolDocument | None = None
        self.baseline: SolDocument | None = None
        self.source_hash: str | None = None
        self.source_path: Path | None = None
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self.max_history = 50

    def require_doc(self):
        if self.doc is None:
            raise SolError('尚未打开 SOL 存档。')
        return self.doc

    def open(self, path: str | Path):
        source = Path(path).resolve()
        raw = source.read_bytes()
        doc = parse_sol_bytes(raw, str(source))
        self.doc = doc
        self.baseline = doc.clone()
        self.source_path = source
        self.source_hash = hashlib.sha256(raw).hexdigest()
        self.undo_stack.clear()
        self.redo_stack.clear()

    def snapshot(self):
        d = self.require_doc()
        return copy.deepcopy(d.entries)

    def _push_undo(self):
        self.undo_stack.append(self.snapshot())
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def mutate(self, updates: list[tuple[tuple, object]]):
        doc = self.require_doc()
        if not updates:
            return 0
        before = self.snapshot()
        try:
            for path, value in updates:
                set_at_path(doc.entries, path, copy.deepcopy(value))
            ok, msg = validate_roundtrip(doc)
            if not ok:
                raise SolError(msg)
        except Exception:
            doc.entries = before
            raise
        if canonical(before) == canonical(doc.entries):
            return 0
        self.undo_stack.append(before)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        return len(updates)

    def apply_text(self, path: tuple, text: str):
        doc = self.require_doc()
        old = get_at_path(doc.entries, path)
        if not is_leaf(old):
            raise SolError('对象/数组应展开子字段编辑。')
        return self.mutate([(path, parse_user_value(text, old))])

    def undo(self):
        if not self.undo_stack:
            return False
        doc = self.require_doc()
        self.redo_stack.append(self.snapshot())
        doc.entries = self.undo_stack.pop()
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        doc = self.require_doc()
        self.undo_stack.append(self.snapshot())
        doc.entries = self.redo_stack.pop()
        return True

    def restore_original(self):
        d = self.require_doc()
        if self.baseline and canonical(d.entries) != canonical(self.baseline.entries):
            self._push_undo()
            d.entries = copy.deepcopy(self.baseline.entries)
            return True
        return False

    def reset_path(self, path: tuple):
        if self.baseline is None:
            return False
        original = copy.deepcopy(get_at_path(self.baseline.entries, path))
        return self.mutate([(path, original)])

    def changed_rows(self):
        doc = self.require_doc()
        return describe_diff(self.baseline, doc) if self.baseline else []

    def import_json(self, path: str | Path):
        from sol_codec import load_document_json
        incoming = load_document_json(path)
        active = self.require_doc()
        if (incoming.name, incoming.amf_version) != (active.name, active.amf_version):
            raise SolError('导入文件的 SharedObject 名称或 AMF 版本与当前文件不同。')
        ok, msg = validate_roundtrip(incoming)
        if not ok:
            raise SolError(msg)
        if canonical(active.entries) == canonical(incoming.entries):
            return False
        before = self.snapshot()
        active.entries = copy.deepcopy(incoming.entries)
        self.undo_stack.append(before)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        return True

    def export_json(self, path: str | Path):
        from sol_codec import dump_document_json
        d = self.require_doc().clone()
        # JSON exports never include a machine-local write destination.
        d.source_path = None
        dump_document_json(d, path)

    def save(self, path: str | Path | None = None, *, backup=True, force=False) -> SaveResult:
        doc = self.require_doc()
        target = Path(path).resolve() if path else self.source_path
        if target is None:
            raise SolError('请选择保存路径。')
        if target.suffix.lower() != '.sol':
            raise SolError('目标文件必须使用 .sol 扩展名。')
        if self.source_path == target and target.exists() and self.source_hash and not force:
            disk_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if disk_hash != self.source_hash:
                raise ChangedOnDiskError('文件在打开后已被外部程序更改；请先重新载入或显式确认强制覆盖。')
        ok, msg = validate_roundtrip(doc)
        if not ok:
            raise SolError(f'保存前校验失败：{msg}')
        raw = serialize_sol(doc)
        parsed = parse_sol_bytes(raw)
        if canonical(parsed.entries) != canonical(doc.entries):
            raise SolError('写回预检未通过。')
        target.parent.mkdir(parents=True, exist_ok=True)
        backup_path = None
        if target.exists() and backup:
            backup_dir = target.parent / 'SOLSaveEditor_Backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup_path = backup_dir / f'{target.stem}.{stamp}.sol.bak'
            while backup_path.exists():
                stamp += 'x'
                backup_path = backup_dir / f'{target.stem}.{stamp}.sol.bak'
            shutil.copy2(target, backup_path)
            if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(backup_path.read_bytes()).digest():
                raise SolError('自动备份校验失败，已阻止覆盖。')
        fd, tmp_name = tempfile.mkstemp(prefix='.sol-editor-', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as fp:
                fp.write(raw)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(tmp_name, target)
            disk = load_sol(target)
            if canonical(disk.entries) != canonical(doc.entries):
                raise SolError('落盘重新解析结果不一致。' + (' 备份仍保留。' if backup_path else ''))
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        self.source_path = target
        self.source_hash = hashlib.sha256(raw).hexdigest()
        self.doc.source_path = str(target)
        self.baseline = self.doc.clone()
        self.undo_stack.clear()
        self.redo_stack.clear()
        return SaveResult(target, backup_path, len(raw))


def find_saves() -> list[Path]:
    appdata = os.environ.get('APPDATA')
    if not appdata:
        return []
    base = Path(appdata) / 'Macromedia' / 'Flash Player'
    patterns = ('#SharedObjects/*/localhost/HLB02_Core_*.sol',
                '#SharedObjects/*/*/HLB02_Core_*.sol',
                'localhost/HLB02_Core_*.sol')
    files = set()
    for pattern in patterns:
        try:
            files.update(p.resolve() for p in base.glob(pattern) if p.is_file())
        except OSError:
            continue
    return sorted(files, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
