from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import json
import math
import struct


class SolError(Exception):
    pass


class AMF3Error(SolError):
    pass


@dataclass
class SolDocument:
    name: str
    amf_version: int
    entries: OrderedDict[str, Any]
    header_prefix: bytes
    source_path: str | None = None

    def clone(self) -> "SolDocument":
        return from_jsonable(to_jsonable(self))


# ---------- JSON conversion helpers ----------
def to_jsonable(value: Any) -> Any:
    if isinstance(value, SolDocument):
        return {
            "__sol_document__": True,
            "name": value.name,
            "amf_version": value.amf_version,
            "entries": {k: to_jsonable(v) for k, v in value.entries.items()},
            "header_prefix_hex": value.header_prefix.hex(),
            "source_path": value.source_path,
        }
    if isinstance(value, OrderedDict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return value


def from_jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return [from_jsonable(v) for v in value]
    if not isinstance(value, dict):
        return value
    if value.get("__sol_document__"):
        return SolDocument(
            name=str(value["name"]),
            amf_version=int(value.get("amf_version", 3)),
            entries=OrderedDict((k, from_jsonable(v)) for k, v in value["entries"].items()),
            header_prefix=bytes.fromhex(value["header_prefix_hex"]),
            source_path=value.get("source_path"),
        )
    out = OrderedDict()
    for k, v in value.items():
        out[k] = from_jsonable(v)
    return out


def dump_document_json(doc: SolDocument, path: str | Path) -> None:
    Path(path).write_text(json.dumps(to_jsonable(doc), ensure_ascii=False, indent=2), encoding="utf-8")


def load_document_json(path: str | Path) -> SolDocument:
    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    doc = from_jsonable(data)
    if not isinstance(doc, SolDocument):
        raise SolError("JSON 不是本工具导出的 SOL 文档。")
    return doc


# ---------- AMF3 reader ----------
class AMF3Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos
        self.string_refs: list[str] = []
        self.object_refs: list[Any] = []
        self.trait_refs: list[dict[str, Any]] = []

    def read(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise AMF3Error(f"读取越界: pos={self.pos}, n={n}, len={len(self.data)}")
        b = self.data[self.pos:self.pos+n]
        self.pos += n
        return b

    def u8(self) -> int:
        return self.read(1)[0]

    def u29(self) -> int:
        b = self.u8()
        if b < 0x80:
            return b
        value = b & 0x7F
        b = self.u8()
        if b < 0x80:
            return (value << 7) | b
        value = (value << 7) | (b & 0x7F)
        b = self.u8()
        if b < 0x80:
            return (value << 7) | b
        return (((value << 7) | (b & 0x7F)) << 8) | self.u8()

    def s29(self) -> int:
        u = self.u29()
        if u & 0x10000000:
            u -= 0x20000000
        return u

    def string_data(self) -> str:
        u = self.u29()
        if (u & 1) == 0:
            idx = u >> 1
            if idx >= len(self.string_refs):
                raise AMF3Error(f"无效字符串引用 #{idx} @ {self.pos}")
            return self.string_refs[idx]
        byte_len = u >> 1
        if byte_len == 0:
            return ""
        s = self.read(byte_len).decode("utf-8")
        self.string_refs.append(s)
        return s

    def value(self) -> Any:
        return self.value_with_marker(self.u8())

    def value_with_marker(self, marker: int) -> Any:
        if marker == 0x00:  # undefined
            return {"__type__": "undefined"}
        if marker == 0x01:  # null
            return None
        if marker == 0x02:
            return False
        if marker == 0x03:
            return True
        if marker == 0x04:
            return self.s29()
        if marker == 0x05:
            return struct.unpack(">d", self.read(8))[0]
        if marker == 0x06:
            return self.string_data()
        if marker in (0x07, 0x0B):  # XMLDocument / XML
            return self._read_xml("xml_document" if marker == 0x07 else "xml")
        if marker == 0x08:
            return self._read_date()
        if marker == 0x09:
            return self._read_array()
        if marker == 0x0A:
            return self._read_object()
        if marker == 0x0C:
            return self._read_bytearray()
        if marker in (0x0D, 0x0E, 0x0F, 0x10):
            return self._read_vector(marker)
        if marker == 0x11:
            return self._read_dictionary()
        raise AMF3Error(f"不支持的 AMF3 标记 0x{marker:02X} @ {self.pos - 1}")

    def _read_ref_header(self) -> tuple[bool, int]:
        u = self.u29()
        return ((u & 1) == 1, u >> 1)

    def _read_xml(self, kind: str = "xml") -> Any:
        inline, payload = self._read_ref_header()
        if not inline:
            return self.object_refs[payload]
        text = self.read(payload).decode("utf-8")
        obj = OrderedDict([("__type__", kind), ("value", text)])
        self.object_refs.append(obj)
        return obj

    def _read_date(self) -> Any:
        inline, payload = self._read_ref_header()
        if not inline:
            return self.object_refs[payload]
        ms = struct.unpack(">d", self.read(8))[0]
        obj = OrderedDict([("__type__", "date"), ("ms", ms)])
        self.object_refs.append(obj)
        return obj

    def _read_array(self) -> Any:
        u = self.u29()
        if (u & 1) == 0:
            return self.object_refs[u >> 1]
        dense_count = u >> 1
        obj = OrderedDict([
            ("__type__", "array"),
            ("assoc", OrderedDict()),
            ("dense", []),
        ])
        self.object_refs.append(obj)
        assoc = obj["assoc"]
        while True:
            key = self.string_data()
            if key == "":
                break
            assoc[key] = self.value()
        dense = obj["dense"]
        for _ in range(dense_count):
            dense.append(self.value())
        return obj

    def _read_object(self) -> Any:
        u = self.u29()
        if (u & 1) == 0:
            idx = u >> 1
            if idx >= len(self.object_refs):
                raise AMF3Error(f"无效对象引用 #{idx}")
            return self.object_refs[idx]

        if (u & 2) == 0:
            trait_idx = u >> 2
            if trait_idx >= len(self.trait_refs):
                raise AMF3Error(f"无效 traits 引用 #{trait_idx}")
            trait = self.trait_refs[trait_idx]
        else:
            externalizable = bool(u & 4)
            dynamic = bool(u & 8)
            sealed_count = u >> 4
            class_name = self.string_data()
            sealed_names = [self.string_data() for _ in range(sealed_count)]
            trait = {
                "class": class_name,
                "externalizable": externalizable,
                "dynamic": dynamic,
                "sealed_names": sealed_names,
            }
            self.trait_refs.append(trait)

        obj = OrderedDict([
            ("__type__", "object"),
            ("__class__", trait["class"]),
            ("sealed", OrderedDict()),
            ("dynamic", OrderedDict()),
        ])
        self.object_refs.append(obj)

        if trait["externalizable"]:
            raise AMF3Error(f"遇到 externalizable 对象 {trait['class']!r}，当前不支持自动解析。")

        for name in trait["sealed_names"]:
            obj["sealed"][name] = self.value()
        if trait["dynamic"]:
            while True:
                name = self.string_data()
                if name == "":
                    break
                obj["dynamic"][name] = self.value()
        # Preserve the dynamic trait bit only when it differs from what can
        # unambiguously be inferred from the decoded object's shape.
        if trait["dynamic"] != (bool(obj["dynamic"]) or not obj["sealed"]):
            obj["__dynamic__"] = trait["dynamic"]
        return obj

    def _read_bytearray(self) -> Any:
        inline, payload = self._read_ref_header()
        if not inline:
            return self.object_refs[payload]
        raw = self.read(payload)
        obj = OrderedDict([("__type__", "bytearray"), ("hex", raw.hex())])
        self.object_refs.append(obj)
        return obj

    def _read_vector(self, marker: int) -> Any:
        u = self.u29()
        if (u & 1) == 0:
            return self.object_refs[u >> 1]
        count = u >> 1
        fixed = bool(self.u8())
        type_name = None
        type_map = {0x0D: "vector_int", 0x0E: "vector_uint", 0x0F: "vector_double", 0x10: "vector_object"}
        kind = type_map[marker]
        if marker == 0x10:
            type_name = self.string_data()
        obj = OrderedDict([("__type__", kind), ("fixed", fixed), ("type_name", type_name), ("values", [])])
        self.object_refs.append(obj)
        vals = obj["values"]
        for _ in range(count):
            if marker == 0x0D:
                vals.append(struct.unpack(">i", self.read(4))[0])
            elif marker == 0x0E:
                vals.append(struct.unpack(">I", self.read(4))[0])
            elif marker == 0x0F:
                vals.append(struct.unpack(">d", self.read(8))[0])
            else:
                vals.append(self.value())
        return obj

    def _read_dictionary(self) -> Any:
        u = self.u29()
        if (u & 1) == 0:
            return self.object_refs[u >> 1]
        count = u >> 1
        weak = bool(self.u8())
        obj = OrderedDict([("__type__", "dictionary"), ("weak", weak), ("entries", [])])
        self.object_refs.append(obj)
        for _ in range(count):
            obj["entries"].append([self.value(), self.value()])
        return obj


# ---------- AMF3 writer ----------
class AMF3Writer:
    """AMF3 writer.

    The writer intentionally emits inline strings/traits by default. This is fully valid AMF3,
    avoids stale reference-table mistakes after edits, and is more robust for save editing.
    Object references are still emitted when the same in-memory container is encountered twice.
    """

    def __init__(self):
        self.buf = bytearray()
        self.object_ref_by_id: dict[int, int] = {}

    def bytes(self) -> bytes:
        return bytes(self.buf)

    def write(self, b: bytes) -> None:
        self.buf.extend(b)

    def u8(self, v: int) -> None:
        self.buf.append(v & 0xFF)

    def u29(self, value: int) -> None:
        value &= 0x1FFFFFFF
        if value < 0x80:
            self.u8(value)
        elif value < 0x4000:
            self.u8(((value >> 7) & 0x7F) | 0x80)
            self.u8(value & 0x7F)
        elif value < 0x200000:
            self.u8(((value >> 14) & 0x7F) | 0x80)
            self.u8(((value >> 7) & 0x7F) | 0x80)
            self.u8(value & 0x7F)
        else:
            self.u8(((value >> 22) & 0x7F) | 0x80)
            self.u8(((value >> 15) & 0x7F) | 0x80)
            self.u8(((value >> 8) & 0x7F) | 0x80)
            self.u8(value & 0xFF)

    def s29(self, value: int) -> None:
        if not (-0x10000000 <= value <= 0x0FFFFFFF):
            raise AMF3Error(f"AMF3 Integer 超出 29 位范围: {value}")
        if value < 0:
            value += 0x20000000
        self.u29(value)

    def string_data(self, text: str) -> None:
        raw = text.encode("utf-8")
        self.u29((len(raw) << 1) | 1)
        self.write(raw)

    def _write_object_ref_if_seen(self, obj: Any) -> bool:
        oid = id(obj)
        if oid in self.object_ref_by_id:
            self.u29(self.object_ref_by_id[oid] << 1)
            return True
        self.object_ref_by_id[oid] = len(self.object_ref_by_id)
        return False

    def value(self, value: Any) -> None:
        if value is None:
            self.u8(0x01)
            return
        if value is False:
            self.u8(0x02)
            return
        if value is True:
            self.u8(0x03)
            return
        if isinstance(value, int) and not isinstance(value, bool):
            if -0x10000000 <= value <= 0x0FFFFFFF:
                self.u8(0x04)
                self.s29(value)
            else:
                # AMF3 has no wider integer marker; encode numerically as double.
                self.u8(0x05)
                self.write(struct.pack(">d", float(value)))
            return
        if isinstance(value, float):
            self.u8(0x05)
            self.write(struct.pack(">d", value))
            return
        if isinstance(value, str):
            self.u8(0x06)
            self.string_data(value)
            return
        if not isinstance(value, dict):
            raise AMF3Error(f"无法序列化类型: {type(value).__name__}")

        kind = value.get("__type__")
        if kind == "undefined":
            self.u8(0x00)
            return
        if kind == "date":
            self.u8(0x08)
            if self._write_object_ref_if_seen(value):
                return
            self.u29(1)
            self.write(struct.pack(">d", float(value.get("ms", 0.0))))
            return
        if kind in {"xml", "xml_document"}:
            self.u8(0x07 if kind == "xml_document" else 0x0B)
            if self._write_object_ref_if_seen(value):
                return
            raw = str(value.get("value", "")).encode("utf-8")
            self.u29((len(raw) << 1) | 1)
            self.write(raw)
            return
        if kind == "array":
            self.u8(0x09)
            if self._write_object_ref_if_seen(value):
                return
            assoc = value.get("assoc", {}) or {}
            dense = value.get("dense", []) or []
            self.u29((len(dense) << 1) | 1)
            for k, v in assoc.items():
                self.string_data(str(k))
                self.value(v)
            self.string_data("")
            for v in dense:
                self.value(v)
            return
        if kind == "object":
            self.u8(0x0A)
            if self._write_object_ref_if_seen(value):
                return
            sealed = value.get("sealed", {}) or {}
            dynamic = value.get("dynamic", {}) or {}
            class_name = str(value.get("__class__", ""))
            dynamic_flag = bool(value.get("__dynamic__", bool(dynamic) or not sealed))
            trait_header = (len(sealed) << 4) | 0x03 | (0x08 if dynamic_flag else 0)
            self.u29(trait_header)
            self.string_data(class_name)
            for k in sealed.keys():
                self.string_data(str(k))
            for v in sealed.values():
                self.value(v)
            if dynamic_flag:
                for k, v in dynamic.items():
                    self.string_data(str(k))
                    self.value(v)
                self.string_data("")
            return
        if kind == "bytearray":
            self.u8(0x0C)
            if self._write_object_ref_if_seen(value):
                return
            raw = bytes.fromhex(str(value.get("hex", "")))
            self.u29((len(raw) << 1) | 1)
            self.write(raw)
            return
        if kind in {"vector_int", "vector_uint", "vector_double", "vector_object"}:
            marker = {"vector_int": 0x0D, "vector_uint": 0x0E, "vector_double": 0x0F, "vector_object": 0x10}[kind]
            self.u8(marker)
            if self._write_object_ref_if_seen(value):
                return
            vals = value.get("values", []) or []
            self.u29((len(vals) << 1) | 1)
            self.u8(1 if value.get("fixed") else 0)
            if kind == "vector_object":
                self.string_data(str(value.get("type_name") or ""))
            for v in vals:
                if kind == "vector_int":
                    self.write(struct.pack(">i", int(v)))
                elif kind == "vector_uint":
                    self.write(struct.pack(">I", int(v)))
                elif kind == "vector_double":
                    self.write(struct.pack(">d", float(v)))
                else:
                    self.value(v)
            return
        if kind == "dictionary":
            self.u8(0x11)
            if self._write_object_ref_if_seen(value):
                return
            entries = value.get("entries", []) or []
            self.u29((len(entries) << 1) | 1)
            self.u8(1 if value.get("weak") else 0)
            for pair in entries:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise AMF3Error("dictionary entries 必须是 [key, value] 对。")
                self.value(pair[0])
                self.value(pair[1])
            return
        raise AMF3Error(f"未知结构类型: {kind!r}")


# ---------- SharedObject (.sol) ----------
def parse_sol_bytes(data: bytes, source_path: str | None = None) -> SolDocument:
    if len(data) < 37:
        raise SolError("文件过短，不是有效的 Flash SharedObject。")
    if data[:2] != b"\x00\xBF":
        raise SolError("文件头不是 00 BF，不是标准 Flash .sol SharedObject。")
    declared = struct.unpack(">I", data[2:6])[0]
    if declared != len(data) - 6:
        raise SolError(f"SOL 长度字段不匹配：声明 {declared}，实际 {len(data)-6}。")
    if data[6:10] != b"TCSO":
        raise SolError("缺少 TCSO 签名。")

    if len(data) < 18:
        raise SolError("SOL 头损坏。")
    name_len = struct.unpack(">H", data[16:18])[0]
    name_start = 18
    name_end = name_start + name_len
    if name_end + 4 > len(data):
        raise SolError("SharedObject 名称长度越界。")
    try:
        name = data[name_start:name_end].decode("utf-8")
    except UnicodeDecodeError as e:
        raise SolError(f"SharedObject 名称不是 UTF-8: {e}") from e

    # Adobe SOL layout observed here: 3 reserved zero bytes then AMF version byte.
    reserved = data[name_end:name_end+3]
    if reserved != b"\x00\x00\x00":
        raise SolError(f"未知 SOL 头布局：name 后保留字节为 {reserved.hex()}。")
    amf_version = data[name_end+3]
    if amf_version != 3:
        raise SolError(f"当前工具针对 AMF3 SOL；检测到 AMF 版本 {amf_version}。")

    payload_start = name_end + 4
    reader = AMF3Reader(data, payload_start)
    entries: OrderedDict[str, Any] = OrderedDict()
    while reader.pos < len(data):
        key = reader.string_data()
        value = reader.value()
        if reader.pos >= len(data):
            raise SolError(f"变量 {key!r} 后缺少 SharedObject 结束分隔字节。")
        separator = reader.u8()
        if separator != 0:
            raise SolError(f"变量 {key!r} 后分隔字节不是 00，而是 {separator:02X}。")
        entries[key] = value

    return SolDocument(
        name=name,
        amf_version=amf_version,
        entries=entries,
        header_prefix=data[:payload_start],
        source_path=source_path,
    )


def load_sol(path: str | Path) -> SolDocument:
    path = Path(path)
    return parse_sol_bytes(path.read_bytes(), str(path))


def serialize_sol(doc: SolDocument) -> bytes:
    if doc.amf_version != 3:
        raise SolError("只支持写回 AMF3 SharedObject。")
    writer = AMF3Writer()
    for key, value in doc.entries.items():
        writer.string_data(str(key))
        writer.value(value)
        writer.u8(0)
    payload = writer.bytes()
    prefix = bytearray(doc.header_prefix)
    if len(prefix) < 6:
        raise SolError("保存头信息损坏。")
    out = prefix + payload
    out[2:6] = struct.pack(">I", len(out) - 6)
    return bytes(out)


def save_sol(doc: SolDocument, path: str | Path) -> None:
    Path(path).write_bytes(serialize_sol(doc))


def validate_roundtrip(doc: SolDocument) -> tuple[bool, str]:
    try:
        raw = serialize_sol(doc)
        parsed = parse_sol_bytes(raw)
    except Exception as e:
        return False, f"重新编码/解析失败：{e}"
    left = json.dumps(to_jsonable(doc.entries), ensure_ascii=False, sort_keys=True, allow_nan=False)
    right = json.dumps(to_jsonable(parsed.entries), ensure_ascii=False, sort_keys=True, allow_nan=False)
    if left != right:
        return False, "重新解析后的字段树与编辑内容不一致。"
    return True, f"校验通过：{len(doc.entries)} 个顶层字段，输出 {len(raw)} 字节。"


# ---------- tree/path helpers ----------
PathToken = str | int


def value_kind(value: Any) -> str:
    if value is None:
        return "null"
    if value is True or value is False:
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return str(value.get("__type__") or "object")
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def is_leaf(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, dict) and value.get("__type__") in {"undefined", "date", "xml", "xml_document", "bytearray"}:
        return True
    return False


def format_value(value: Any) -> str:
    kind = value_kind(value)
    if kind == "bool":
        return "true" if value else "false"
    if kind == "null":
        return "null"
    if kind == "double":
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return format(value, ".15g")
    if kind == "date":
        ms = float(value.get("ms", 0.0))
        try:
            dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
            return f"{int(ms)} ms | {dt.isoformat()}"
        except Exception:
            return f"{ms} ms"
    if kind == "undefined":
        return "undefined"
    if kind in {"xml", "xml_document"}:
        return str(value.get("value", ""))
    if kind == "bytearray":
        h = str(value.get("hex", ""))
        return h if len(h) <= 80 else h[:80] + "…"
    if isinstance(value, str):
        return value
    return str(value)


def iter_nodes(entries: OrderedDict[str, Any]) -> Iterable[tuple[tuple[PathToken, ...], Any]]:
    def walk(path: tuple[PathToken, ...], value: Any):
        yield path, value
        if isinstance(value, dict):
            kind = value.get("__type__")
            if kind == "object":
                for branch in ("sealed", "dynamic"):
                    sub = value.get(branch, {}) or {}
                    for k, v in sub.items():
                        yield from walk(path + (branch, k), v)
            elif kind == "array":
                assoc = value.get("assoc", {}) or {}
                for k, v in assoc.items():
                    yield from walk(path + ("assoc", k), v)
                dense = value.get("dense", []) or []
                for i, v in enumerate(dense):
                    yield from walk(path + ("dense", i), v)
            elif kind and kind.startswith("vector_"):
                for i, v in enumerate(value.get("values", []) or []):
                    yield from walk(path + ("values", i), v)
            elif kind == "dictionary":
                for i, pair in enumerate(value.get("entries", []) or []):
                    yield from walk(path + ("entries", i, 0), pair[0])
                    yield from walk(path + ("entries", i, 1), pair[1])
            elif kind not in {"date", "xml", "xml_document", "bytearray", "undefined"}:
                for k, v in value.items():
                    if not str(k).startswith("__"):
                        yield from walk(path + (k,), v)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                yield from walk(path + (i,), v)

    for key, value in entries.items():
        yield from walk((key,), value)


def get_at_path(entries: OrderedDict[str, Any], path: tuple[PathToken, ...]) -> Any:
    if not path:
        return entries
    cur: Any = entries[path[0]]
    for token in path[1:]:
        cur = cur[token]
    return cur


def set_at_path(entries: OrderedDict[str, Any], path: tuple[PathToken, ...], new_value: Any) -> None:
    if not path:
        raise SolError("不能替换整个 entries 根节点。")
    if len(path) == 1:
        entries[path[0]] = new_value
        return
    cur: Any = entries[path[0]]
    for token in path[1:-1]:
        cur = cur[token]
    cur[path[-1]] = new_value


def path_to_text(path: tuple[PathToken, ...]) -> str:
    if not path:
        return ""
    out = str(path[0])
    i = 1
    while i < len(path):
        token = path[i]
        if isinstance(token, int):
            out += f"[{token}]"
        elif token in {"dynamic", "sealed", "dense", "assoc", "values", "entries"}:
            # Hide implementation branches where possible, but retain array index structure.
            if token == "dense":
                pass
            elif token == "dynamic":
                pass
            elif token == "sealed":
                pass
            elif token == "assoc":
                out += ".assoc"
            else:
                out += f".{token}"
        else:
            out += f".{token}"
        i += 1
    return out


def parse_user_value(text: str, original: Any) -> Any:
    kind = value_kind(original)
    t = text.strip()
    if kind == "bool":
        low = t.lower()
        if low in {"1", "true", "yes", "on", "是", "开"}:
            return True
        if low in {"0", "false", "no", "off", "否", "关"}:
            return False
        raise SolError("布尔值请输入 true/false 或 1/0。")
    if kind == "int":
        try:
            v = int(t, 0)
        except ValueError as e:
            raise SolError("请输入整数。") from e
        if not (-0x10000000 <= v <= 0x0FFFFFFF):
            raise SolError("AMF3 Integer 必须在 -268435456 ~ 268435455 范围内。")
        return v
    if kind == "double":
        try:
            return float(t)
        except ValueError as e:
            raise SolError("请输入浮点数。") from e
    if kind == "string":
        return text
    if kind == "null":
        if t.lower() in {"null", "none", ""}:
            return None
        raise SolError("null 字段只能保持 null。")
    if kind == "date":
        # Accept milliseconds or ISO datetime.
        if t.lower().endswith("ms"):
            t = t[:-2].strip()
        try:
            ms = float(t)
            out = OrderedDict(original)
            out["ms"] = ms
            return out
        except ValueError:
            pass
        try:
            iso = t.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out = OrderedDict(original)
            out["ms"] = dt.timestamp() * 1000.0
            return out
        except Exception as e:
            raise SolError("日期请输入毫秒时间戳，或 ISO 时间（例如 2026-08-31T00:00:00+08:00）。") from e
    if kind in {"xml", "xml_document"}:
        out = OrderedDict(original)
        out["value"] = text
        return out
    if kind == "bytearray":
        h = "".join(text.split())
        try:
            bytes.fromhex(h)
        except ValueError as e:
            raise SolError("ByteArray 请输入十六进制字节。") from e
        out = OrderedDict(original)
        out["hex"] = h.lower()
        return out
    raise SolError(f"{kind} 是结构节点，请编辑其子项或使用 JSON 导入。")
