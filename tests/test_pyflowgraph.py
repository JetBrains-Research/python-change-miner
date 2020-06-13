import pyflowgraph
from tests import utils


def test_graph_building():
    _build_var_decl()
    _build_var_decl_ref()
    _build_variable_tuple_decl()
    _build_attribute_call()
    _build_attribute_refs_test()
    _build_attribute_ref_after_call()
    _build_while()


def _build_fg(src, build_closure=True):
    return pyflowgraph.build_from_source(utils.format_src(src), build_closure=build_closure)


def _build_var_decl():
    assert _build_fg("""
        a = 1
    """) is not None


def _build_var_decl_ref():
    assert _build_fg("""
        a = 1
        b = a
    """) is not None


def _build_variable_tuple_decl():
    fg = _build_fg("""
        a = (1, 2, 3)
    """)
    assert len(fg.nodes) == 7  # start, var, assign, lit, lit, lit, tpl


def _build_attribute_call():
    fg = _build_fg("""
        self.o.fn()
    """)
    labels = {n.label for n in fg.nodes}
    expected_labels = {'START', 'self', 'self.o', 'self.o.fn', 'fn'}
    assert labels == expected_labels


def _build_attribute_refs_test():
    fg = _build_fg("""
        self.field.value = 20
        value = 14
        a = (self.field.value, value)
    """)
    labels = {n.label for n in fg.nodes}
    expected_labels = {'=', 'self', 'self.field', '14', 'START', 'Tuple', 'value', 'self.field.value', 'a'}
    assert labels == expected_labels


def _build_attribute_ref_after_call():
    fg = _build_fg("""
        self.o.fn().param = 14
        print(self.o.fn().param)
    """)
    labels = {n.label for n in fg.nodes}
    expected_labels = {'self.o.fn', 'fn', 'START', 'self', 'self.o', 'self.o.fn().param', 'print'}
    assert labels == expected_labels


def _build_while():
    fg = _build_fg("""
        i = 0
        while i < 10:
            i += 1
        print(i)
    """)
    labels = {n.label for n in fg.nodes}
    expected_labels = {'0', 'Lt', '=', 'START', 'i', 'while', '10', 'print'}
    assert labels == expected_labels


def test_controls_switching():
    _test_if()
    _test_if_return()
    _test_if_else()
    _test_if_return_else()
    _test_if_else_return()
    _test_if_if_return()
    _test_for()


def _find_after_print(fg):
    lit = fg.find_node_by_label('after')
    result = None
    for e in lit.out_edges:
        if e.node_to.label == 'print':
            result = e.node_to
    return result


def _test_if():
    fg = _build_fg("""
        a = 10
        if a < 10:          
            print('inner')
        print('after')
    """)
    p = _find_after_print(fg)
    # expected = T control start
    control, branch_kind = p.control_branch_stack[-1]
    assert (control.label, branch_kind) == ('START', True)


def _test_if_return():
    fg = _build_fg("""
        a = 10
        if a < 10:
            print('inner')
            return
        print('after')
    """)
    p = _find_after_print(fg)
    # expected = F control if
    control, branch_kind = p.control_branch_stack[-1]
    assert (control.label, branch_kind) == ('if', False)


def _test_if_else():
    fg = _build_fg("""
        a = 10
        if a < 10:
            print('inner')
        else:
            print('inner2')
        print('after')
    """)
    p = _find_after_print(fg)
    # expected = T control start
    control, branch_kind = p.control_branch_stack[-1]
    assert (control.label, branch_kind) == ('START', True)


def _test_if_return_else():
    fg = _build_fg("""
            a = 10
            if a < 10:
                print('inner')
                return
            else:
                print('inner2')
            print('after')
        """)
    p = _find_after_print(fg)
    # expected = F control if
    control, branch_kind = p.control_branch_stack[-1]
    assert (control.label, branch_kind) == ('if', False)


def _test_if_else_return():
    fg = _build_fg("""
            a = 10
            if a < 10:
                print('inner')
            else:
                print('inner2')
                return
            print('after')
        """)
    p = _find_after_print(fg)
    # expected = T control if
    control, branch_kind = p.control_branch_stack[-1]
    assert (control.label, branch_kind) == ('if', True)


def _test_if_if_return():
    fg = _build_fg("""
        a = 10
        if a > 10:
            if a > 100:
                return
    
        print('after')
    """)
    p = _find_after_print(fg)
    # expected = F control if1, F control if2
    control, branch_kind = p.control_branch_stack[-1]
    assert (control.label, branch_kind) == ('if', False)


def _test_for():
    fg = _build_fg("""
        arr = [1, 2, 3]
        for _ in arr:
            print('inner')
        
        print('after')
    """)
    p = _find_after_print(fg)
    control, branch_kind = p.control_branch_stack[-1]
    assert (control.label, branch_kind) == ('START', True)


def test_closure():
    _test_return_in_ifs_closure()


def _test_return_in_ifs_closure():
    fg = _build_fg("""
        a = 10
        if a > 10:
            if a > 200:
                if a > 100:
                    pass
                else:
                    return
    
        print('test')
        print('test2')
    """)
    return_node = fg.find_node_by_label('return')

    kind_to_cnt = {True: 0, False: 0}
    for e in return_node.in_edges:
        if isinstance(e, pyflowgraph.models.ControlEdge):
            kind_to_cnt[e.branch_kind] += 1

    assert kind_to_cnt[True] == 6 and kind_to_cnt[False] == 2


if __name__ == '__main__':
    test_graph_building()
    test_controls_switching()
    test_closure()
