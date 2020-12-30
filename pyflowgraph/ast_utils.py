import ast
from log import logger

def get_node_key(node):
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.arg):
        return node.arg
    elif isinstance(node, ast.Attribute):
        node_key = node.attr
        curr_node = node.value

        while isinstance(curr_node, ast.Attribute):
            node_key = f'{curr_node.attr}.{node_key}'
            curr_node = curr_node.value

        return f'{curr_node.id}.{node_key}' if isinstance(curr_node, ast.Name) else None
    elif isinstance(node, ast.FunctionDef):
        return node.name
    elif isinstance(node, ast.Call):
        return get_node_key(node.func)
    else:
        logger.error(f"ast_utils: get_node_key node = {node}, line = {node.first_token.line}")
        return "Expr"


def get_node_full_name(node):
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.arg):
        return node.arg
    elif isinstance(node, ast.Attribute):
        var_id = node.attr
        curr_node = node.value
        while isinstance(curr_node, ast.Attribute) \
                or isinstance(curr_node, ast.Call) and isinstance(curr_node.func, ast.Attribute):

            if isinstance(curr_node, ast.Attribute):
                var_id = curr_node.attr + '.' + var_id
                curr_node = curr_node.value
            else:
                var_id = curr_node.func.attr + '()' + '.' + var_id
                curr_node = curr_node.func.value
        if isinstance(curr_node, ast.Call):
            id = curr_node.func.id + '()'
        else:
            try:
                id = curr_node.id
            except:
                id = get_node_full_name(curr_node)
        return id + '.' + var_id
    elif isinstance(node, ast.FunctionDef):
        return node.name
    elif isinstance(node, ast.Subscript):
        return f'{get_node_full_name(node.value)}[.]'
    elif isinstance(node, ast.Index):
        return get_node_full_name(node.value)
    elif isinstance(node, ast.Slice):
        items = ['.' for item in [node.lower, node.step, node.upper] if item]
        return ':'.join(items)
    elif isinstance(node, ast.Constant):
        return '.'
    elif isinstance(node, ast.Tuple):
        str = ",".join(['.' for item in node.elts])
        return f"({str})"
    elif isinstance(node, ast.List):
        str = ",".join(['.' for item in node.elts])
        return f"[{str}]"
    elif isinstance(node, ast.Dict):
        str = ",".join(['.' for item in node.elts])
        return "{" + str + "}"
    elif isinstance(node, ast.UnaryOp):
        return "UnaryOp(.)"
    elif isinstance(node, ast.Call):
        str = ",".join(['.' for item in node.args])
        id = node.func.id if hasattr(node.func, 'id') else node.func.attr
        return f"{id}({str})"
    elif isinstance(node, ast.BinOp):
        return "BinOp(.,.)"
    elif isinstance(node, ast.BoolOp):
        return "BoolOp(.,.)"
    elif isinstance(node, ast.Compare):
        return "Compare(.,.)"
    elif isinstance(node, ast.ExtSlice):
        return ",".join(['.' for item in node.dims])
    elif isinstance(node, ast.Starred):
        return f"*{get_node_full_name(node.value)}"
    else:
        logger.error(f"get_node_full_name_error, expr written instead: Unable to proceed node = {node}, line = {node.first_token.line}")
        return "Expr"

def get_node_short_name(node):
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.arg):
        return node.arg
    elif isinstance(node, ast.Attribute):
        return node.attr
    elif isinstance(node, ast.FunctionDef):
        return node.name
    elif isinstance(node, ast.Call):
        return get_node_short_name(node.func)
    elif isinstance(node, ast.Subscript):
        return get_node_short_name(node.value) + '[.]'
    elif isinstance(node, ast.Call):
        return get_node_short_name(node.func)
    else:
        logger.error(f"ast_utils: get_node_short_name node = {node}, line = {node.first_token.line}")
        return "Expr"