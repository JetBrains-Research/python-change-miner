import pyflowgraph
from tests import utils


def test_graph_building():
    _build_var_decl()
    _build_var_decl_ref()
    _build_variable_tuple_decl()
    _build_attribute_assign()
    _build_attribute_call()
    _build_attribute_refs_test()
    _build_attribute_ref_after_call()
    # _build_subscript_fn_call()


def _build_fg(src):
    return pyflowgraph.build_from_source(utils.format_src(src))


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


def _build_attribute_assign():
    fg = _build_fg("""
        self.field.value = 4
    """)
    labels = {n.label for n in fg.nodes}
    expected_labels = {'START', 'value', '4', '='}
    assert labels == expected_labels


def _build_attribute_call():
    fg = _build_fg("""
        self.o.fn()
    """)
    labels = {n.label for n in fg.nodes}
    expected_labels = {'START', 'fn'}
    assert labels == expected_labels


def _build_attribute_ref_after_call():
    fg = _build_fg("""
        self.o.fn().param
    """)
    assert True


def _build_attribute_refs_test():
    fg = _build_fg("""
        self.field.value = 20
        value = 14
        a = (self.field.value, value)
    """)
    assert True


def _build_subscript_fn_call():
    fg = _build_fg("""
        arr = []
        arr[0]()
    """)
    assert True


def _build_subscript_assign():
    fg = _build_fg("""
        arr = []
        k = 0, i = 0
        arr[i] = k
    """)
    assert True


if __name__ == '__main__':
    test_graph_building()
