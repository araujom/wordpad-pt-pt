#!/usr/bin/env python3
"""Build a Portuguese (Portugal) WordPad MUI from the en-US reference file."""

from __future__ import annotations

import argparse
import json
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import lief
import pefile


LANG_PT_PT = 0x0816
DS_SETFONT = 0x00000040
MF_POPUP = 0x0010
MF_END = 0x0080
PLACEHOLDER_RE = re.compile(r"%(?:\d+|[a-zA-Z]|%)")


def align4(value: int) -> int:
    return (value + 3) & ~3


def read_wstr(data: bytes, offset: int) -> tuple[str, int]:
    chars: list[int] = []
    while True:
        value = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        if value == 0:
            return bytes(struct.pack("<" + "H" * len(chars), *chars)).decode(
                "utf-16le"
            ), offset
        chars.append(value)


def pack_wstr(value: str) -> bytes:
    return value.encode("utf-16le") + b"\0\0"


@dataclass
class VarField:
    kind: str
    value: str | int | None


def read_var(data: bytes, offset: int) -> tuple[VarField, int]:
    first = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    if first == 0:
        return VarField("none", None), offset
    if first == 0xFFFF:
        value = struct.unpack_from("<H", data, offset)[0]
        return VarField("ordinal", value), offset + 2

    chars = [first]
    while True:
        value = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        if value == 0:
            raw = struct.pack("<" + "H" * len(chars), *chars)
            return VarField("string", raw.decode("utf-16le")), offset
        chars.append(value)


def pack_var(value: VarField) -> bytes:
    if value.kind == "none":
        return b"\0\0"
    if value.kind == "ordinal":
        return struct.pack("<HH", 0xFFFF, int(value.value))
    if value.kind == "string":
        return pack_wstr(str(value.value))
    raise ValueError(f"Unsupported variable field kind: {value.kind}")


@dataclass
class DialogItem:
    help_id: int
    ex_style: int
    style: int
    x: int
    y: int
    cx: int
    cy: int
    item_id: int
    window_class: VarField
    title: VarField
    creation_data: bytes


@dataclass
class Dialog:
    version: int
    signature: int
    help_id: int
    ex_style: int
    style: int
    x: int
    y: int
    cx: int
    cy: int
    menu: VarField
    window_class: VarField
    title: VarField
    font: tuple[int, int, int, int, str] | None
    items: list[DialogItem] = field(default_factory=list)


def parse_dialog(data: bytes) -> Dialog:
    (
        version,
        signature,
        help_id,
        ex_style,
        style,
        item_count,
        x,
        y,
        cx,
        cy,
    ) = struct.unpack_from("<HHIIIHhhhh", data, 0)
    if signature != 0xFFFF:
        raise ValueError("Only DIALOGEX resources are supported")
    offset = struct.calcsize("<HHIIIHhhhh")
    menu, offset = read_var(data, offset)
    window_class, offset = read_var(data, offset)
    title, offset = read_var(data, offset)
    font = None
    if style & DS_SETFONT:
        point_size, weight, italic, charset = struct.unpack_from("<HHBB", data, offset)
        offset += struct.calcsize("<HHBB")
        typeface, offset = read_wstr(data, offset)
        font = (point_size, weight, italic, charset, typeface)

    items: list[DialogItem] = []
    for _ in range(item_count):
        offset = align4(offset)
        (
            item_help_id,
            item_ex_style,
            item_style,
            item_x,
            item_y,
            item_cx,
            item_cy,
            item_id,
        ) = struct.unpack_from("<IIIhhhhI", data, offset)
        offset += struct.calcsize("<IIIhhhhI")
        item_class, offset = read_var(data, offset)
        item_title, offset = read_var(data, offset)
        extra_size = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        creation_data = data[offset : offset + extra_size]
        offset += extra_size
        items.append(
            DialogItem(
                item_help_id,
                item_ex_style,
                item_style,
                item_x,
                item_y,
                item_cx,
                item_cy,
                item_id,
                item_class,
                item_title,
                creation_data,
            )
        )

    return Dialog(
        version,
        signature,
        help_id,
        ex_style,
        style,
        x,
        y,
        cx,
        cy,
        menu,
        window_class,
        title,
        font,
        items,
    )


def build_dialog(dialog: Dialog) -> bytes:
    output = bytearray(
        struct.pack(
            "<HHIIIHhhhh",
            dialog.version,
            dialog.signature,
            dialog.help_id,
            dialog.ex_style,
            dialog.style,
            len(dialog.items),
            dialog.x,
            dialog.y,
            dialog.cx,
            dialog.cy,
        )
    )
    output.extend(pack_var(dialog.menu))
    output.extend(pack_var(dialog.window_class))
    output.extend(pack_var(dialog.title))
    if dialog.font is not None:
        point_size, weight, italic, charset, typeface = dialog.font
        output.extend(struct.pack("<HHBB", point_size, weight, italic, charset))
        output.extend(pack_wstr(typeface))

    for item in dialog.items:
        output.extend(b"\0" * (align4(len(output)) - len(output)))
        output.extend(
            struct.pack(
                "<IIIhhhhI",
                item.help_id,
                item.ex_style,
                item.style,
                item.x,
                item.y,
                item.cx,
                item.cy,
                item.item_id,
            )
        )
        output.extend(pack_var(item.window_class))
        output.extend(pack_var(item.title))
        output.extend(struct.pack("<H", len(item.creation_data)))
        output.extend(item.creation_data)
    return bytes(output)


@dataclass
class MenuItem:
    flags: int
    item_id: int | None
    text: str
    children: list["MenuItem"] = field(default_factory=list)


def parse_menu_level(data: bytes, offset: int) -> tuple[list[MenuItem], int]:
    items: list[MenuItem] = []
    while True:
        flags = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        item_id = None
        if not flags & MF_POPUP:
            item_id = struct.unpack_from("<H", data, offset)[0]
            offset += 2
        text, offset = read_wstr(data, offset)
        children: list[MenuItem] = []
        if flags & MF_POPUP:
            children, offset = parse_menu_level(data, offset)
        items.append(MenuItem(flags, item_id, text, children))
        if flags & MF_END:
            return items, offset


def parse_menu(data: bytes) -> tuple[int, bytes, list[MenuItem]]:
    version, header_size = struct.unpack_from("<HH", data, 0)
    header = data[4 : 4 + header_size]
    items, _ = parse_menu_level(data, 4 + header_size)
    return version, header, items


def build_menu_level(items: Iterable[MenuItem]) -> bytes:
    output = bytearray()
    for item in items:
        output.extend(struct.pack("<H", item.flags))
        if not item.flags & MF_POPUP:
            output.extend(struct.pack("<H", int(item.item_id)))
        output.extend(pack_wstr(item.text))
        if item.flags & MF_POPUP:
            output.extend(build_menu_level(item.children))
    return bytes(output)


def build_menu(version: int, header: bytes, items: list[MenuItem]) -> bytes:
    return struct.pack("<HH", version, len(header)) + header + build_menu_level(items)


def parse_string_block(data: bytes) -> list[str]:
    strings: list[str] = []
    offset = 0
    for _ in range(16):
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        size = length * 2
        strings.append(data[offset : offset + size].decode("utf-16le"))
        offset += size
    if offset != len(data):
        raise ValueError("Unexpected trailing bytes in string-table resource")
    return strings


def build_string_block(strings: list[str]) -> bytes:
    if len(strings) != 16:
        raise ValueError("A string-table block must contain 16 entries")
    output = bytearray()
    for value in strings:
        encoded = value.encode("utf-16le")
        output.extend(struct.pack("<H", len(encoded) // 2))
        output.extend(encoded)
    return bytes(output)


@dataclass
class MessageEntry:
    message_id: int
    flags: int
    text: str


@dataclass
class MessageBlock:
    low_id: int
    high_id: int
    entries: list[MessageEntry]


def parse_message_table(data: bytes) -> list[MessageBlock]:
    block_count = struct.unpack_from("<I", data, 0)[0]
    blocks: list[MessageBlock] = []
    for index in range(block_count):
        low_id, high_id, offset = struct.unpack_from("<III", data, 4 + index * 12)
        entries: list[MessageEntry] = []
        for message_id in range(low_id, high_id + 1):
            length, flags = struct.unpack_from("<HH", data, offset)
            raw = data[offset + 4 : offset + length]
            encoding = "utf-16le" if flags & 1 else "cp1252"
            text = raw.decode(encoding).rstrip("\0")
            entries.append(MessageEntry(message_id, flags, text))
            offset += length
        blocks.append(MessageBlock(low_id, high_id, entries))
    return blocks


def build_message_table(blocks: list[MessageBlock]) -> bytes:
    header_size = 4 + len(blocks) * 12
    payload = bytearray()
    headers = bytearray(struct.pack("<I", len(blocks)))
    for block in blocks:
        offset = header_size + len(payload)
        headers.extend(struct.pack("<III", block.low_id, block.high_id, offset))
        for entry in block.entries:
            encoding = "utf-16le" if entry.flags & 1 else "cp1252"
            terminator = b"\0\0" if entry.flags & 1 else b"\0"
            encoded = entry.text.encode(encoding) + terminator
            length = align4(4 + len(encoded))
            payload.extend(struct.pack("<HH", length, entry.flags))
            payload.extend(encoded)
            payload.extend(b"\0" * (length - 4 - len(encoded)))
    return bytes(headers + payload)


@dataclass
class VersionBlock:
    key: str
    value_type: int
    value: bytes
    children: list["VersionBlock"] = field(default_factory=list)


def parse_version_block(data: bytes, start: int = 0) -> tuple[VersionBlock, int]:
    total_length, value_length, value_type = struct.unpack_from("<HHH", data, start)
    if total_length == 0:
        raise ValueError("Invalid zero-length version block")
    key, offset = read_wstr(data, start + 6)
    offset = align4(offset)
    value_size = value_length * 2 if value_type == 1 else value_length
    value = data[offset : offset + value_size]
    offset = align4(offset + value_size)
    end = start + total_length
    children: list[VersionBlock] = []
    while offset + 2 <= end:
        child_length = struct.unpack_from("<H", data, offset)[0]
        if child_length == 0:
            break
        child, next_offset = parse_version_block(data, offset)
        children.append(child)
        offset = align4(next_offset)
    return VersionBlock(key, value_type, value, children), end


def build_version_block(block: VersionBlock) -> bytes:
    output = bytearray(b"\0" * 6)
    output.extend(pack_wstr(block.key))
    output.extend(b"\0" * (align4(len(output)) - len(output)))
    output.extend(block.value)
    output.extend(b"\0" * (align4(len(output)) - len(output)))
    for child in block.children:
        output.extend(build_version_block(child))
        output.extend(b"\0" * (align4(len(output)) - len(output)))
    value_length = len(block.value) // 2 if block.value_type == 1 else len(block.value)
    struct.pack_into("<HHH", output, 0, len(output), value_length, block.value_type)
    return bytes(output)


def translate_var(field: VarField, text_map: dict[str, str]) -> None:
    if field.kind == "string" and field.value:
        field.value = required_translation(text_map, str(field.value), "dialog/menu text")


def translate_menu_items(items: Iterable[MenuItem], text_map: dict[str, str]) -> None:
    for item in items:
        if item.text:
            item.text = required_translation(text_map, item.text, "menu text")
        translate_menu_items(item.children, text_map)


def validate_placeholders(source: str, target: str, context: str) -> None:
    if sorted(PLACEHOLDER_RE.findall(source)) != sorted(PLACEHOLDER_RE.findall(target)):
        raise ValueError(f"Placeholder mismatch for {context}: {source!r} -> {target!r}")


def required_translation(mapping: dict[str, str], source: str, context: str) -> str:
    if source not in mapping:
        raise KeyError(f"Missing {context} translation for {source!r}")
    target = mapping[source]
    validate_placeholders(source, target, context)
    return target


def get_resource_kind(node: lief.PE.ResourceNode) -> str | int:
    return node.name if node.has_name else node.id


def update_version(block: VersionBlock, translations: dict[str, str]) -> None:
    if block.key == "040904B0":
        block.key = "081604B0"
    if block.key in translations and block.value_type == 1:
        source = block.value.decode("utf-16le").rstrip("\0")
        target = translations[block.key]
        validate_placeholders(source, target, f"version field {block.key}")
        block.value = pack_wstr(target)
    if block.key == "Translation" and len(block.value) >= 4:
        _, code_page = struct.unpack_from("<HH", block.value, 0)
        block.value = struct.pack("<HH", LANG_PT_PT, code_page) + block.value[4:]
    for child in block.children:
        update_version(child, translations)


def update_checksum(path: Path) -> None:
    image = pefile.PE(str(path))
    image.OPTIONAL_HEADER.CheckSum = image.generate_checksum()
    image.write(str(path))


def build(source: Path, translations_path: Path, output: Path) -> None:
    translations = json.loads(translations_path.read_text(encoding="utf-8"))
    string_map: dict[str, str] = translations["string_table"]
    text_map: dict[str, str] = translations["text"]
    message_map: dict[str, str] = translations["messages"]
    version_map: dict[str, str] = translations["version"]

    binary = lief.PE.parse(str(source))
    if binary is None or not binary.has_resources:
        raise ValueError(f"Not a resource-bearing PE file: {source}")

    seen_strings: set[str] = set()
    seen_messages: set[str] = set()
    for type_node in binary.resources.childs:
        resource_type = get_resource_kind(type_node)
        for name_node in type_node.childs:
            for language_node in name_node.childs:
                language_node.id = LANG_PT_PT
                content = bytes(language_node.content)

                if resource_type == "MUI":
                    marker = "en-US".encode("utf-16le")
                    replacement = "pt-PT".encode("utf-16le")
                    if content.count(marker) != 1:
                        raise ValueError("Unexpected MUI language-name layout")
                    language_node.content = content.replace(marker, replacement)
                elif resource_type == 4:
                    menu_version, menu_header, items = parse_menu(content)
                    translate_menu_items(items, text_map)
                    language_node.content = build_menu(menu_version, menu_header, items)
                elif resource_type == 5:
                    dialog = parse_dialog(content)
                    translate_var(dialog.title, text_map)
                    for item in dialog.items:
                        translate_var(item.title, text_map)
                    language_node.content = build_dialog(dialog)
                elif resource_type == 6:
                    strings = parse_string_block(content)
                    base_id = (name_node.id - 1) * 16
                    for index, source_text in enumerate(strings):
                        if not source_text:
                            continue
                        string_id = str(base_id + index)
                        if string_id not in string_map:
                            raise KeyError(
                                f"Missing string-table translation for ID {string_id}: {source_text!r}"
                            )
                        target = string_map[string_id]
                        validate_placeholders(source_text, target, f"string ID {string_id}")
                        strings[index] = target
                        seen_strings.add(string_id)
                    language_node.content = build_string_block(strings)
                elif resource_type == 11:
                    blocks = parse_message_table(content)
                    for block in blocks:
                        for entry in block.entries:
                            message_id = str(entry.message_id)
                            if message_id not in message_map:
                                raise KeyError(
                                    f"Missing message-table translation for ID {message_id}: {entry.text!r}"
                                )
                            target = message_map[message_id]
                            validate_placeholders(
                                entry.text, target, f"message ID {message_id}"
                            )
                            entry.text = target
                            seen_messages.add(message_id)
                    language_node.content = build_message_table(blocks)
                elif resource_type == 16:
                    version, end = parse_version_block(content)
                    if end != len(content):
                        raise ValueError("Unexpected trailing bytes in version resource")
                    update_version(version, version_map)
                    language_node.content = build_version_block(version)

    unused_strings = set(string_map) - seen_strings
    unused_messages = set(message_map) - seen_messages
    if unused_strings:
        raise ValueError(f"Unknown string-table IDs in translation: {sorted(unused_strings)}")
    if unused_messages:
        raise ValueError(f"Unknown message-table IDs in translation: {sorted(unused_messages)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    binary.write(str(output))
    update_checksum(output)


def resource_topology(binary: lief.PE.Binary) -> list[tuple[str, tuple[tuple[str, int], ...]]]:
    result: list[tuple[str, tuple[tuple[str, int], ...]]] = []
    for type_node in binary.resources.childs:
        names = tuple(
            (str(get_resource_kind(name_node)), len(name_node.childs))
            for name_node in type_node.childs
        )
        result.append((str(get_resource_kind(type_node)), names))
    return result


def version_blocks(block: VersionBlock) -> Iterable[VersionBlock]:
    yield block
    for child in block.children:
        yield from version_blocks(child)


def verify(path: Path, source: Path, translations_path: Path) -> None:
    translations = json.loads(translations_path.read_text(encoding="utf-8"))
    binary = lief.PE.parse(str(path))
    if binary is None or not binary.has_resources:
        raise ValueError("Generated MUI is not a valid PE resource file")
    source_binary = lief.PE.parse(str(source))
    if source_binary is None or not source_binary.has_resources:
        raise ValueError("Source MUI is not a valid PE resource file")
    if resource_topology(binary) != resource_topology(source_binary):
        raise ValueError("Generated MUI resource topology differs from the source")

    languages: set[int] = set()
    mui_content = b""
    strings: dict[str, str] = {}
    messages: dict[str, str] = {}
    translated_texts = set(translations["text"].values())
    version: VersionBlock | None = None
    for type_node in binary.resources.childs:
        resource_type = get_resource_kind(type_node)
        for name_node in type_node.childs:
            for language_node in name_node.childs:
                languages.add(language_node.id)
                content = bytes(language_node.content)
                if resource_type == "MUI":
                    mui_content = content
                elif resource_type == 4:
                    _, _, items = parse_menu(content)
                    pending = list(items)
                    while pending:
                        item = pending.pop()
                        if item.text and item.text not in translated_texts:
                            raise ValueError(f"Unexpected menu text: {item.text!r}")
                        pending.extend(item.children)
                elif resource_type == 5:
                    dialog = parse_dialog(content)
                    fields = [dialog.title] + [item.title for item in dialog.items]
                    for field in fields:
                        if (
                            field.kind == "string"
                            and field.value
                            and field.value not in translated_texts
                        ):
                            raise ValueError(f"Unexpected dialog text: {field.value!r}")
                elif resource_type == 6:
                    values = parse_string_block(content)
                    base_id = (name_node.id - 1) * 16
                    for index, value in enumerate(values):
                        if value:
                            strings[str(base_id + index)] = value
                elif resource_type == 11:
                    for block in parse_message_table(content):
                        for entry in block.entries:
                            messages[str(entry.message_id)] = entry.text
                elif resource_type == 16:
                    version, end = parse_version_block(content)
                    if end != len(content):
                        raise ValueError("Unexpected trailing bytes in generated version resource")
    if languages != {LANG_PT_PT}:
        raise ValueError(f"Unexpected resource languages: {sorted(languages)}")
    if strings != translations["string_table"]:
        raise ValueError("Generated string-table resources do not match the translation")
    if messages != translations["messages"]:
        raise ValueError("Generated message-table resources do not match the translation")
    if "pt-PT".encode("utf-16le") not in mui_content:
        raise ValueError("Generated MUI metadata does not identify pt-PT")
    if "en-US".encode("utf-16le") in mui_content:
        raise ValueError("Generated MUI metadata still identifies en-US")
    if version is None:
        raise ValueError("Generated MUI has no version resource")
    blocks = list(version_blocks(version))
    if not any(block.key == "081604B0" for block in blocks):
        raise ValueError("Generated version resource does not identify pt-PT")
    for key, expected in translations["version"].items():
        matches = [block for block in blocks if block.key == key]
        if len(matches) != 1:
            raise ValueError(f"Unexpected version-field count for {key}")
        actual = matches[0].value.decode("utf-16le").rstrip("\0")
        if actual != expected:
            raise ValueError(f"Generated version field {key} does not match")

    image = pefile.PE(str(path))
    expected = image.generate_checksum()
    if image.OPTIONAL_HEADER.CheckSum != expected:
        raise ValueError("Generated MUI has an invalid PE checksum")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("en-US/wordpad.exe.mui"))
    parser.add_argument(
        "--translations", type=Path, default=Path("translations/pt-PT.json")
    )
    parser.add_argument("--output", type=Path, default=Path("pt-PT/wordpad.exe.mui"))
    args = parser.parse_args()
    build(args.source, args.translations, args.output)
    verify(args.output, args.source, args.translations)
    print(f"Built and verified {args.output}")


if __name__ == "__main__":
    main()
