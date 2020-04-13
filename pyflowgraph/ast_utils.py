import ast


def get_var_full_name(node):  # todo: subscript in attr :(
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

        var_id = (curr_node.id if not isinstance(curr_node, ast.Call) else curr_node.func.id + '()') + '.' + var_id
        return var_id
    elif isinstance(node, ast.FunctionDef):
        return node.name
    else:
        raise ValueError


def get_var_short_name(node):
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.arg):
        return node.arg
    elif isinstance(node, ast.Attribute):
        return node.attr
    elif isinstance(node, ast.FunctionDef):
        return node.name
    else:
        raise ValueError
