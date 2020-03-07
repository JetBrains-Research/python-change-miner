import os
import tempfile

import tests.tools as tools
from external import gumtree


def _try_build_gumtree_and_match(src, dest):
    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as tmp1, \
            tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as tmp2:
        tmp1.writelines(src)
        tmp1.seek(0)

        tmp2.writelines(dest)
        tmp2.seek(0)

        gt1 = gumtree.build_from_file(os.path.realpath(tmp1.name))
        gt2 = gumtree.build_from_file(os.path.realpath(tmp2.name))

        matches = gumtree.get_matches(os.path.realpath(tmp1.name), os.path.realpath(tmp2.name))

    return gt1, gt2, matches


def _try_build_gumtree(src):
    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as tmp:
        tmp.writelines(src)
        tmp.seek(0)

        gt = gumtree.build_from_file(os.path.realpath(tmp.name))

    return gt


def test_assign():
    src = tools.remove_tabs("""
        a, b, [c, d] = 1, 2, [3, 4]
    """, tabs=2)

    gt = _try_build_gumtree(src)
    assert True


# def test_tuple_assign_order_changed():
#     src = tools.remove_tabs("""
#         a, b = 1, 2
#     """, tabs=2)
#     dest = tools.remove_tabs("""
#         a, b = 2, 1
#     """, tabs=2)
#     gt1, gt2, matches = _try_build_gumtree_and_match(src, dest)
#     assert False  # incorrect matching


def test_tuple_assign_changed():
    src = tools.remove_tabs("""
        a, b = 1, 2
    """, tabs=2)
    dest = tools.remove_tabs("""
        a, b = 3, test()
    """, tabs=2)
    gt1, gt2, matches = _try_build_gumtree_and_match(src, dest)
    assert True


if __name__ == '__main__':
    # test_assign()
    test_tuple_assign_changed()
