import sys
import ast
import asttokens
from xml.sax.saxutils import quoteattr


def read_file_to_string(filename):
    f = open(filename, 'rt')
    s = f.read()
    f.close()
    return s


def parse_file(filename):
    tree = asttokens.ASTTokens(read_file_to_string(filename), parse=True).tree

    json_tree = []

    def localize(node, json_node):
        json_node['lineno'] = str(node.first_token.start[0])
        json_node['col'] = str(node.first_token.start[1])
        json_node['end_line_no'] = str(node.last_token.end[0])
        json_node['end_col'] = str(node.last_token.end[1])

    def gen_identifier(identifier, node_type='identifier', node=None):
        pos = len(json_tree)
        json_node = {}
        json_tree.append(json_node)
        json_node['type'] = node_type
        json_node['value'] = identifier
        localize(node, json_node)
        return pos

    def traverse_list(l, node_type = 'list', node = None):
        pos = len(json_tree)
        json_node = {}
        json_tree.append(json_node)
        json_node['type'] = node_type
        localize(node, json_node)
        children = []
        for item in l:
            children.append(traverse(item))
        if (len(children) != 0):
            json_node['children'] = children
        return pos

    def traverse(node):
        pos = len(json_tree)
        json_node = {}
        json_tree.append(json_node)
        json_node['type'] = type(node).__name__
        localize(node, json_node)
        children = []
        if isinstance(node, ast.Name):
            json_node['value'] = node.id
        elif isinstance(node, ast.NameConstant):
            json_node['value'] = node.value
        elif isinstance(node, ast.Constant):
            json_node['value'] = node.value
        elif isinstance(node, ast.Num):
            json_node['value'] = (node.n)
        elif isinstance(node, ast.Str):
            json_node['value'] = node.s
        elif isinstance(node, ast.alias):
            json_node['value'] = (node.name)
            if node.asname:
                children.append(gen_identifier(node.asname, node = node))
        elif isinstance(node, ast.FunctionDef):
            json_node['value'] = (node.name)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                json_node['value'] = node.name
        elif isinstance(node, ast.ClassDef):
            json_node['value'] = (node.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                json_node['value'] = (node.module)
        elif isinstance(node, ast.Global):
            for n in node.names:
                children.append(gen_identifier(n, node = node))
        elif isinstance(node, ast.keyword):
            json_node['value'] = (node.arg)
        elif isinstance(node, ast.arg):
            json_node['value'] = (node.arg)

        # Process children.
        if isinstance(node, ast.For):
            children.append(traverse(node.target))
            children.append(traverse(node.iter))
            children.append(traverse_list(node.body, 'body', node))
            if node.orelse:
                children.append(traverse_list(node.orelse, 'orelse', node))
        elif isinstance(node, ast.If) or isinstance(node, ast.While):
            children.append(traverse(node.test))
            children.append(traverse_list(node.body, 'body', node))
            if node.orelse:
                children.append(traverse_list(node.orelse, 'orelse', node))
        elif isinstance(node, ast.With):
            children.append(traverse_list(node.items, 'items', node))
            children.append(traverse_list(node.body, 'body', node))
        elif isinstance(node, ast.withitem):
            children.append(traverse(node.context_expr))
            if node.optional_vars:
                children.append(traverse(node.optional_vars))
        elif isinstance(node, ast.Try):
            children.append(traverse_list(node.body, 'body', node))
            children.append(traverse_list(node.handlers, 'handlers', node))
            if node.orelse:
                children.append(traverse_list(node.orelse, 'orelse', node))
            if node.finalbody:
                children.append(traverse_list(node.finalbody, 'finalbody', node))
        elif isinstance(node, ast.arguments):
            children.append(traverse_list(node.args, 'args', node))
            children.append(traverse_list(node.defaults, 'defaults', node))
            children.append(traverse_list(node.kwonlyargs, 'defaults', node))
            children.append(traverse_list(node.kw_defaults, 'defaults', node))
            if node.vararg:
                children.append(gen_identifier(node.vararg.arg, 'vararg', node.vararg))
            if node.kwarg:
                children.append(gen_identifier(node.kwarg.arg, 'kwarg', node.kwarg))
        elif isinstance(node, ast.ExceptHandler):
            if node.type:
                children.append(traverse_list([node.type], 'type', node))
            children.append(traverse_list(node.body, 'body', node))
        elif isinstance(node, ast.ClassDef):
            children.append(traverse_list(node.bases, 'bases', node))
            children.append(traverse_list(node.body, 'body', node))
            children.append(traverse_list(node.decorator_list, 'decorator_list', node))
        elif isinstance(node, ast.FunctionDef):
            children.append(traverse(node.args))
            children.append(traverse_list(node.body, 'body', node))
            children.append(traverse_list(node.decorator_list, 'decorator_list', node))
        else:
            # Default handling: iterate over children.
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.expr_context) or isinstance(child, ast.operator) or isinstance(child, ast.boolop) or isinstance(child, ast.unaryop) or isinstance(child, ast.cmpop):
                    # Directly include expr_context, and operators into the type instead of creating a child.
                    json_node['type'] = json_node['type'] + type(child).__name__
                else:
                    children.append(traverse(child))

        if isinstance(node, ast.Attribute):
            children.append(gen_identifier(node.attr, 'attr', node))

        if (len(children) != 0):
            json_node['children'] = children

        return pos

    traverse(tree)
    return json_tree


def json2xml(tree):
    lines = []
    def convert_node(i, indent_level=0):
        node = tree[i]
        line = "\t" * indent_level + "<{}".format(node['type'])
        for key in ['value', 'lineno', 'col', 'end_line_no', 'end_col']:
            if key in node:
                line += (' {}={}'.format(key, quoteattr(str(node[key]))))
        line += ">"
        lines.append(line)
        if "children" in node:
            for child in node["children"]:
                convert_node(int(child), indent_level + 1)
        lines.append("\t" * indent_level + "</" + node["type"] + ">")
        return lines

    return "\n".join(convert_node(0))


def parse(filename):
    try:
        json_tree = parse_file(filename)
        return json2xml(json_tree)

    except (UnicodeEncodeError, UnicodeDecodeError):
        pass


if __name__ == "__main__":
    default_filename = 'src1.py'
    filename = sys.argv[1] if len(sys.argv) > 1 else default_filename

    json_tree = parse_file(filename)
    xml = json2xml(json_tree)

    print(xml)
