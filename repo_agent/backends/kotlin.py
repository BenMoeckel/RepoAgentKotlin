"""Kotlin syntax extraction using the bundled fwcd Tree-sitter grammar."""

import re
from bisect import bisect_left, bisect_right
from urllib.parse import quote


def text(node):
    return node.text.decode("utf-8") if node is not None else ""


def child(node, *types):
    return next((c for c in node.named_children if c.type in types), None)


class KotlinBackend:
    language = "kotlin"

    def __init__(self, lsp=None):
        self.lsp = lsp
        try:
            from tree_sitter_language_pack import get_parser
        except ImportError as exc:
            raise RuntimeError(
                'Kotlin support requires: pip install "repoagent[kotlin]"'
            ) from exc
        self.parser = get_parser("kotlin")

    def parse(self, source):
        raw_source = source.encode("utf-8")
        root = self.parser.parse(raw_source).root_node
        inserted = []
        if root.has_error:
            # The bundled grammar misses implicit semicolons before same-line
            # closing braces. Retry with legal whitespace at token boundaries,
            # retaining an offset map so source snippets/positions stay exact.
            braces = []

            def closing_braces(node):
                if node.type == "}":
                    braces.append(node.start_byte)
                for nested in node.children:
                    closing_braces(nested)

            closing_braces(root)
            normalized, cursor = bytearray(), 0
            for position in sorted(set(braces)):
                normalized.extend(raw_source[cursor:position])
                inserted.append(len(normalized))
                normalized.extend(b"\n")
                cursor = position
            normalized.extend(raw_source[cursor:])
            root = self.parser.parse(bytes(normalized)).root_node
        if root.has_error:
            raise ValueError(
                "Kotlin syntax could not be parsed; refusing incomplete documentation"
            )
        symbols = []
        source_lines = source.splitlines(keepends=True)
        line_starts = [0] + [i + 1 for i, b in enumerate(raw_source) if b == 10]

        def original_offset(offset):
            return offset - bisect_left(inserted, offset)

        def position(offset):
            offset = original_offset(offset)
            row = bisect_right(line_starts, offset) - 1
            return row + 1, len(raw_source[line_starts[row] : offset].decode("utf-8"))

        def original_text(node):
            return raw_source[
                original_offset(node.start_byte) : original_offset(node.end_byte)
            ].decode("utf-8")

        kinds = {
            "class_declaration": ("ClassDef", "Class"),
            "object_declaration": ("ClassDef", "Object"),
            "companion_object": ("ClassDef", "Companion object"),
            "function_declaration": ("FunctionDef", "Function"),
            "secondary_constructor": ("FunctionDef", "Constructor"),
            "property_declaration": ("PropertyDef", "Property"),
            "class_parameter": ("PropertyDef", "Property"),
            "type_alias": ("TypeAliasDef", "Type alias"),
        }

        def visit(node, parent=None, inside_function=False):
            current = parent
            is_symbol = node.type in kinds
            # Local variables and destructuring bindings are implementation details.
            if node.type == "property_declaration" and inside_function:
                is_symbol = False
            if (
                node.type == "class_parameter"
                and child(node, "binding_pattern_kind") is None
            ):
                is_symbol = False
            if is_symbol:
                variable = child(node, "variable_declaration")
                name_node = (
                    child(variable, "simple_identifier")
                    if variable
                    else child(node, "simple_identifier", "type_identifier")
                )
                if node.type == "secondary_constructor":
                    name = "constructor"
                elif node.type == "companion_object" and name_node is None:
                    name = "Companion"
                else:
                    name = text(name_node).strip("`")
                if name:
                    code_type, kind = kinds[node.type]
                    if node.type == "class_declaration":
                        if any(c.type == "interface" for c in node.children):
                            kind = "Interface"
                        elif child(node, "enum_class_body"):
                            kind = "Enum class"
                    params_node = child(
                        node, "function_value_parameters", "primary_constructor"
                    )
                    params, parameter_types = [], []
                    if params_node:
                        for param in params_node.named_children:
                            if param.type not in {"parameter", "class_parameter"}:
                                continue
                            param_name = child(param, "simple_identifier")
                            if param_name:
                                params.append(text(param_name).strip("`"))
                                raw = text(param)
                                param_type = re.sub(
                                    r"\s+", "", raw.split(":", 1)[1].split("=", 1)[0]
                                )
                                modifiers = param.prev_named_sibling
                                if (
                                    modifiers
                                    and modifiers.type == "parameter_modifiers"
                                    and "vararg" in text(modifiers)
                                ):
                                    param_type = "vararg " + param_type
                                parameter_types.append(param_type)
                    receiver = text(node.child_by_field_name("receiver"))
                    generics = text(child(node, "type_parameters"))
                    signature = (receiver + "." if receiver else "") + name
                    if code_type == "FunctionDef":
                        signature += generics + "(" + ",".join(parameter_types) + ")"
                    key = quote(signature, safe="().,:<>?* ")
                    symbol_id = (parent["symbol_id"] + "/" if parent else "") + key
                    start, start_column = position(node.start_byte)
                    end, end_column = position(node.end_byte)
                    declaration_line, name_column = (
                        position(name_node.start_byte)
                        if name_node
                        else (start, source_lines[start - 1].find(name))
                    )
                    preceding = raw_source[: original_offset(node.start_byte)].decode(
                        "utf-8"
                    )
                    doc_match = re.search(
                        r"(/\*\*(?:(?!/\*|\*/)[\s\S])*\*/)\s*$", preceding
                    )
                    kdoc = doc_match.group(1) if doc_match else ""
                    code = original_text(node)
                    body = child(node, "function_body")
                    symbol = {
                        "type": code_type,
                        "name": name,
                        "language": "kotlin",
                        "kind": kind,
                        "signature": signature,
                        "symbol_key": key,
                        "symbol_id": symbol_id,
                        "parent_id": parent["symbol_id"] if parent else None,
                        "code_start_line": start,
                        "code_end_line": max(start, end),
                        "code_start_column": start_column,
                        "code_end_column": end_column,
                        "code_start_byte": original_offset(node.start_byte),
                        "code_end_byte": original_offset(node.end_byte),
                        "name_line": declaration_line,
                        "name_column": max(0, name_column),
                        "params": params,
                        "receiver": receiver,
                        "kdoc": kdoc,
                        "parameter_types": parameter_types,
                        "code_content": (kdoc + "\n" if kdoc else "") + code,
                        "have_return": code_type == "FunctionDef"
                        and (
                            (body is not None and text(body).lstrip().startswith("="))
                            or bool(re.search(r"\breturn\b", code))
                        ),
                        "md_content": [],
                    }
                    symbols.append(symbol)
                    current = symbol
            nested_function = inside_function or node.type in {
                "function_declaration",
                "secondary_constructor",
                "lambda_literal",
                "anonymous_initializer",
                "getter",
                "setter",
            }
            if node.type in {
                "class_declaration",
                "object_declaration",
                "companion_object",
            }:
                nested_function = False
            for nested in node.named_children:
                visit(nested, current, nested_function)

        visit(root)
        return symbols

    def references(self, repo_path, file_path, symbol, in_file_only=False):
        # A repository-scoped LSP session is supplied by MetaInfo.parse_reference.
        # Never manufacture semantic relationships by matching names.
        return self.lsp.references(file_path, symbol, in_file_only) if self.lsp else []
