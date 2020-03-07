import logging
import tempfile
import os

import changegraph
import tests.tools as tools


def _try_build_change_graph(src, dest):
    try:
        with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t1, \
                tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t2:

            t1.writelines(src)
            t1.seek(0)

            t2.writelines(dest)
            t2.seek(0)

            p1 = os.path.realpath(t1.name)
            p2 = os.path.realpath(t2.name)

            return changegraph.build_from_files(p1, p2)
    except:
        return None


def test_for_statement1():
    src = tools.remove_tabs("""
        a = [1,2,3]
        for i in range(len(a)):
            print(i)
    """, tabs=2)
    dest = tools.remove_tabs("""
        a = [4,5,6]
        for i in range(len(a)):
            print(i)
    """, tabs=2)
    assert _try_build_change_graph(src, dest) is not None


# def test_tuple_assign():
#     src = tools.remove_tabs("""
#         a, b = 1, 2
#     """, tabs=2)
#     dest = tools.remove_tabs("""
#         a, b = 2, 1
#     """, tabs=2)
#     assert _try_build_change_graph(src, dest) is not None


def test_var_rename1():
    src = tools.remove_tabs("""
        a = 10
        b = a + 1
    """, tabs=2)
    dest = tools.remove_tabs("""
        d = 12
        b = d + 1
    """, tabs=2)
    cg = _try_build_change_graph(src, dest)
    assert len(cg.nodes) == 8


if __name__ == '__main__':
    test_for_statement1()
    test_var_rename1()
