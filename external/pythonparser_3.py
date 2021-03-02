#!/usr/bin/env python3.8

# Copyright (c) Raychev, V., Bielik, P., and Vechev, M. (see https://eth-sri.github.io/py150)
# Copyright (c) Victor Quach (see https://github.com/Varal7/pythonparser)
# Copyright (c) Aniskov N.


import argparse
import ast
import json as json
from typing import Dict, List, Union
from xml.sax.saxutils import quoteattr

import asttokens

JsonNodeType = Dict[str, Union[str, List[int]]]


def read_file_to_string(filename: str) -> str:
    """
    :param filename: path to file
    :return: string with file content
    """
    with open(filename, 'rt') as f:
        content = f.read()
    return content


def parse_file(filename: str) -> List[JsonNodeType]:
    """
    Produces XML in special for GumTree 2.x library
     format -- merge value_type and import_level into node type
     (Example: <Constant value="5" value_type="int"> in standard format will become
               <Constant-int value="5"> in that format)

    :param filename: file with python3 code to be parsed
    XML in special for GumTree 2.x library
     format -- merge value_type and import_level into node type
     (Example: <Constant value="5" value_type="int"> in standard format will become
               <Constant-int value="5"> in that format)
    :return: tree in json format
    """
    tree = asttokens.ASTTokens(read_file_to_string(filename), parse=True).tree

    json_tree = []

    def localize(py_node: ast.AST, json_node: JsonNodeType) -> None:
        if py_node is None:
            return

        location_attributes = (['first_token', 'last_token'],
                               ['lineno', 'col_offset', 'end_lineno', 'end_col_offset'])
        if all(hasattr(py_node, location_attr) for location_attr in location_attributes[0]):
            json_node['lineno'] = str(py_node.first_token.start[0])
            json_node['col'] = str(py_node.first_token.start[1])
            json_node['end_line_no'] = str(py_node.last_token.end[0])
            json_node['end_col'] = str(py_node.last_token.end[1])
        elif all(hasattr(py_node, location_attr) for location_attr in location_attributes[1]):
            json_node['lineno'] = str(py_node.lineno)
            json_node['col'] = str(py_node.col_offset)
            json_node['end_line_no'] = str(py_node.end_lineno)
            json_node['end_col'] = str(py_node.end_col_offset)
        else:
            raise RuntimeError(f'Failed to localize {type(py_node).__name__} node. '
                               f'Not enough location attributes for localization')

    def gen_identifier(identifier: str, node_type: str = 'identifier', py_node: ast.AST = None) -> int:
        pos = len(json_tree)
        json_node = {}
        json_tree.append(json_node)
        json_node['type'] = node_type
        json_node['value'] = identifier
        localize(py_node, json_node)
        return pos

    def traverse_list(py_ast_nodes: List[ast.AST], node_type: str = 'list', py_node: ast.AST = None) -> int:
        pos = len(json_tree)
        json_node = {}
        json_tree.append(json_node)
        json_node['type'] = node_type
        localize(py_node, json_node)
        children = []
        for item in py_ast_nodes:
            children.append(traverse(item))
        if len(children) != 0:
            json_node['children'] = children
        return pos

    def create_child(py_node_child: ast.AST, node_type: str, py_node: ast.AST = None):
        pos = len(json_tree)
        json_node = {}
        json_tree.append(json_node)
        json_node['type'] = node_type
        localize(py_node, json_node)
        if py_node_child is not None:
            json_node['children'] = [traverse(py_node_child)]
        return pos

    def traverse(py_node: ast.AST) -> Union[JsonNodeType, int]:
        pos = len(json_tree)
        json_node = {}
        json_tree.append(json_node)
        json_node['type'] = type(py_node).__name__
        localize(py_node, json_node)
        children = []

        if isinstance(py_node, ast.Name):
            json_node['value'] = py_node.id

        elif isinstance(py_node, ast.NameConstant):
            json_node['value'] = py_node.value
            json_node['type'] += '-' + type(py_node.value).__name__

        elif isinstance(py_node, ast.Constant):
            json_node['value'] = py_node.value
            json_node['type'] += '-' + type(py_node.value).__name__

        elif isinstance(py_node, ast.Num):
            json_node['value'] = py_node.n
            json_node['type'] += '-' + type(py_node.n).__name__

        elif isinstance(py_node, ast.Str):
            json_node['value'] = py_node.s

        elif isinstance(py_node, ast.alias):
            json_node['value'] = py_node.name
            if py_node.asname:
                children.append(gen_identifier(py_node.asname, py_node=py_node))

        elif isinstance(py_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            json_node['value'] = py_node.name

        elif isinstance(py_node, ast.ExceptHandler):
            if py_node.name:
                json_node['value'] = py_node.name

        elif isinstance(py_node, ast.ClassDef):
            json_node['value'] = py_node.name

        elif isinstance(py_node, ast.ImportFrom):
            if py_node.module:
                json_node['value'] = py_node.module
                json_node['type'] += '-' + str(py_node.level)

        elif isinstance(py_node, (ast.Global, ast.Nonlocal)):
            for n in py_node.names:
                children.append(gen_identifier(n, py_node=py_node))

        elif isinstance(py_node, ast.keyword):
            json_node['value'] = py_node.arg
            json_node['type'] += '-' + type(py_node.arg).__name__

        elif isinstance(py_node, ast.arg):
            json_node['value'] = py_node.arg

        # Process children.
        if isinstance(py_node, (ast.For, ast.AsyncFor)):
            children.append(traverse(py_node.target))
            children.append(traverse(py_node.iter))
            children.append(traverse_list(py_node.body, 'body', py_node))
            if py_node.orelse:
                children.append(traverse_list(py_node.orelse, 'orelse', py_node))

        elif isinstance(py_node, ast.If) or isinstance(py_node, ast.While):
            children.append(traverse(py_node.test))
            children.append(traverse_list(py_node.body, 'body', py_node))
            if py_node.orelse:
                children.append(traverse_list(py_node.orelse, 'orelse', py_node))

        elif isinstance(py_node, (ast.With, ast.AsyncWith)):
            children.append(traverse_list(py_node.items, 'items', py_node))
            children.append(traverse_list(py_node.body, 'body', py_node))

        elif isinstance(py_node, ast.withitem):
            children.append(traverse(py_node.context_expr))
            if py_node.optional_vars:
                children.append(traverse(py_node.optional_vars))

        elif isinstance(py_node, ast.Try):
            children.append(traverse_list(py_node.body, 'body', py_node))
            children.append(traverse_list(py_node.handlers, 'handlers', py_node))
            if py_node.orelse:
                children.append(traverse_list(py_node.orelse, 'orelse', py_node))
            if py_node.finalbody:
                children.append(traverse_list(py_node.finalbody, 'finalbody', py_node))

        elif isinstance(py_node, ast.arguments):
            children.append(traverse_list(py_node.posonlyargs, 'posonlyargs', py_node))
            children.append(traverse_list(py_node.args, 'args', py_node))
            children.append(traverse_list(py_node.kwonlyargs, 'kwonlyargs', py_node))
            children.append(traverse_list(py_node.kw_defaults, 'kw_defaults', py_node))
            children.append(traverse_list(py_node.defaults, 'defaults', py_node))
            if py_node.vararg:
                children.append(gen_identifier(py_node.vararg.arg, 'vararg', py_node.vararg))
            if py_node.kwarg:
                children.append(gen_identifier(py_node.kwarg.arg, 'kwarg', py_node.kwarg))

        elif isinstance(py_node, ast.ExceptHandler):
            if py_node.type:
                children.append(traverse_list([py_node.type], 'type', py_node))
            children.append(traverse_list(py_node.body, 'body', py_node))

        elif isinstance(py_node, ast.ClassDef):
            children.append(traverse_list(py_node.bases, 'bases', py_node))
            children.append(traverse_list(py_node.keywords, 'keywords', py_node))
            children.append(traverse_list(py_node.body, 'body', py_node))
            children.append(traverse_list(py_node.decorator_list, 'decorator_list', py_node))

        elif isinstance(py_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            children.append(traverse(py_node.args))
            children.append(traverse_list(py_node.body, 'body', py_node))
            children.append(traverse_list(py_node.decorator_list, 'decorator_list', py_node))

        elif isinstance(py_node, ast.Slice):
            children.append(create_child(py_node.lower, 'lower', py_node))
            children.append(create_child(py_node.step, 'step', py_node))
            children.append(create_child(py_node.upper, 'upper', py_node))

        elif py_node is not None:
            # Default handling: iterate over children.
            for child in ast.iter_child_nodes(py_node):
                if isinstance(child, ast.expr_context) or\
                   isinstance(child, ast.operator) or\
                   isinstance(child, ast.boolop) or\
                   isinstance(child, ast.unaryop) or\
                   isinstance(child, ast.cmpop):
                    # Directly include expr_context, and operators into the type instead of creating a child.
                    json_node['type'] = json_node['type'] + '_' + type(child).__name__
                else:
                    children.append(traverse(child))

        if isinstance(py_node, ast.Attribute):
            children.append(gen_identifier(py_node.attr, 'attr', py_node))

        if len(children) != 0:
            json_node['children'] = children

        return pos

    traverse(tree)
    return json_tree


def json2xml(tree: List[JsonNodeType]) -> str:
    """
    :param tree: tree in json format produced by parser
    :type tree: list of dicts
    :return: xml file as string
    """
    lines = []

    def convert_node(i: int, indent_level: int = 0) -> List[str]:
        node = tree[i]
        line = '\t' * indent_level + '<{}'.format(node['type'])
        for key in ['value', 'lineno', 'col', 'end_line_no', 'end_col']:
            if key in node:
                line += (' {}={}'.format(key, quoteattr(str(node[key]))))
        line += '>'
        lines.append(line)
        if 'children' in node:
            for child in node['children']:
                convert_node(int(child), indent_level + 1)
        lines.append('\t' * indent_level + '</' + node['type'] + '>')
        return lines

    return '\n'.join(convert_node(0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse python3 file')
    parser.add_argument('filename', type=str, help='Filename')
    parser.add_argument('-f', '--format', choices=['xml', 'json'], help='Print format', default='xml')

    args = parser.parse_args()

    parsed_json_tree = parse_file(args.filename)

    if args.format == 'json':
        print(json.dumps(parsed_json_tree, separators=(',', ':'), ensure_ascii=False))
    else:
        xml = json2xml(parsed_json_tree)
        print(xml)



