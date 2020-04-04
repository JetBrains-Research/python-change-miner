import os
import tempfile
import json

import tests.utils as utils
from external import gumtree


def _try_build_gumtree_and_get_diff(src, dest):
    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as tmp1, \
            tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as tmp2:
        tmp1.writelines(src)
        tmp1.seek(0)

        tmp2.writelines(dest)
        tmp2.seek(0)

        gt1 = gumtree.build_from_file(os.path.realpath(tmp1.name))
        gt2 = gumtree.build_from_file(os.path.realpath(tmp2.name))

        matches, actions = gumtree.get_matches_and_actions(os.path.realpath(tmp1.name), os.path.realpath(tmp2.name))

    return gt1, gt2, matches, actions


def _try_build_gumtree(src):
    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as tmp:
        tmp.writelines(src)
        tmp.seek(0)

        gt = gumtree.build_from_file(os.path.realpath(tmp.name))

    return gt
#
#
# def test_assign():
#     src = utils.remove_tabs("""
#         a, b, [c, d] = 1, 2, [3, 4]
#     """, tabs=2)
#
#     gt = _try_build_gumtree(src)
#     assert True


# def test_tuple_assign_order_changed():
#     src = tools.remove_tabs("""
#         a, b = 1, 2
#     """, tabs=2)
#     dest = tools.remove_tabs("""
#         a, b = 2, 1
#     """, tabs=2)
#     gt1, gt2, matches = _try_build_gumtree_and_match(src, dest)
#     assert False  # incorrect matching


# def test_tuple_assign_changed():
#     src = utils.remove_tabs("""
#         a, b = 1, 2
#     """, tabs=2)
#     dest = utils.remove_tabs("""
#         a, b = 3, test()
#     """, tabs=2)
#     gt1, gt2, matches = _try_build_gumtree_and_match(src, dest)
#     assert True


def test_matches():
    src = utils.format_src("""
        a = self.get_value()
        print(a)
    """, )
    dest = utils.format_src("""
        a2 = self.get_value()
        if a2 is not None:
            print(a2)
    """)

    gt1, gt2, matches, actions = _try_build_gumtree_and_get_diff(src, dest)

    def matches_sort_fn(e):
        return e['src'] * 10000 + e['dest']
    matches = sorted(matches, key=matches_sort_fn)

    print(json.dumps(gt1._data, indent=2, sort_keys=True))
    print(json.dumps(gt2._data, indent=2, sort_keys=True))
    print(json.dumps(matches, indent=2, sort_keys=True))
    print(json.dumps(actions, indent=2, sort_keys=True))

    assert matches == sorted([
        {"dest": 4, "src": 4}, {"dest": 9, "src": 6}, {"dest": 3, "src": 3}, {"dest": 1, "src": 1},
        {"dest": 2, "src": 2}, {"dest": 11, "src": 8}, {"dest": 15, "src": 10}, {"dest": 5, "src": 5},
        {"dest": 0, "src": 0}, {"dest": 10, "src": 7}], key=matches_sort_fn)


if __name__ == '__main__':
    # test_assign()
    # test_tuple_assign_changed()
    test_matches()
