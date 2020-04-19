import tempfile
import os

import changegraph
import tests.utils as utils


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


def _get_label_to_node_cnt(cg):
    label_to_node_cnt = {}
    for node in cg.nodes:
        cnt = label_to_node_cnt.get(node.original_label, 0) + 1
        label_to_node_cnt[node.original_label] = cnt
    return label_to_node_cnt


def test_for_statement1():
    src = utils.format_src("""
        a = [1,2,3]
        for i in range(len(a)):
            print(i)
    """)
    dest = utils.format_src("""
        a = [4,5,6]
        for i in range(len(a)):
            print(i)
    """)
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
    src = utils.format_src("""
        a = 10
        b = a + 1
    """)
    dest = utils.format_src("""
        d = 12
        b = d + 1
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'a': 2,
        'd': 2,
        '10': 1,
        '12': 1,
        '=': 2
    }


def test_var_attr_assign():
    src = utils.format_src("""
        def test(self):
            a = self.attr.field
    """)
    dest = utils.format_src("""
        def test(self):
            a = self.attr2.field
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'field': 2
    }


def test_var_attr_call_assign():
    src = utils.format_src("""
        def test(self):
            a = self.attr.call()
    """)
    dest = utils.format_src("""
        def test(self):
            a = self.attr.call2()
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'call': 1,
        'call2': 1
    }


def test_var_attr_call_attr_assign():
    src = utils.format_src("""
        def test(self):
            a = self.attr.call().val
    """)
    dest = utils.format_src("""
        def test(self):
            a = self.attr.call().val2
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'val': 1,
        'val2': 1
    }


def test_complex_example1():
    return  # GumTree mapping failed, the upper assign is considered as moved
    src = utils.format_src("""
        def __init__(self, data_format='default', **kwargs):
            super(_GlobalPooling2D, self).__init__(**kwargs)
            if data_format == 'default':
                data_format = K.image_data_format()
            self.data_format = data_format
            self.input_spec = [InputSpec(ndim=4)]
    """)
    dest = utils.format_src("""
        def __init__(self, data_format=None, **kwargs):
            super(_GlobalPooling2D, self).__init__(**kwargs)
            self.data_format = conv_utils.normalize_data_format(data_format)
            self.input_spec = [InputSpec(ndim=4)]
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'data_format': 5+3,
        'if': 1+0,
        '=': 2+1,
        'Eq': 1+0,
        'default': 2+0,
        'None': 0+1,
        'image_data_format': 1+0,
        'normalize_data_format': 0+1
    }


def test_complex_example2():
    src = utils.format_src("""
        def m():
            self.a.b.c.d.e = self.get_value()
            print(self.a.b.c.d.e)
    """)
    dest = utils.format_src("""
        def m():
            self.a.b.c.d.e = self.get_value()
            if self.a.b.c.d.e is not None:
                print(self.a.b.c.d.e)
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'e': 0+2,
        'IsNot': 0+1,
        'if': 0+1,
        'None': 0+1
    }


def test_complex_example3():
    src = utils.format_src("""
        def remove_interface_permanent(zone, interface):
            fw_zone = fw.config().getZoneByName(zone)
            fw_settings = fw_zone.getSettings()
            fw_settings.removeInterface(interface)
            fw_zone.update(fw_settings)
    """)
    dest = utils.format_src("""
        def remove_interface_permanent(zone, interface):
            fw_zone, fw_settings = get_fw_zone_settings(zone)
            fw_settings.removeInterface(interface)
            update_fw_settings(fw_zone, fw_settings)
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'getZoneByName': 1+0,
        'getSettings': 1+0,
        'update': 1+0,
        'get_fw_zone_settings': 0+1,
        '=': 2+1,
        'fw_zone': 1+2,
        'fw_settings': 2+2,
        'update_fw_settings': 0+1
    }


def test_complex_example4():
    src = utils.format_src("""
        def get_a():
            a = int(input())
        
            print(a)
            return a
    """)
    dest = utils.format_src("""
        def get_a():
            a = int(input())
            if a > 100:
                print('overdraft')
                return None
        
            print(a)
            return a
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'if': 0+1,
        'print': 0+1,
        'Gt': 0+1,
        'a': 2,
        'return': 0+1,
        'None': 0+1,
        'overdraft': 0+1,
        '100': 0+1
    }


def test_complex_example5():
    src = utils.format_src("""
        def test_create_output(self):
            graph.add_node(Dense(32, 16), name='dense1', input='input1')
    """)
    dest = utils.format_src("""
        def test_create_output(self):
            graph.add_node(Dense(16, input_shape=(32,)), name='dense1', input='input1')
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'Dense': 1+1,
        '16': 1+1,
        '32': 1+1,
        'Tuple': 1,
        'input_shape': 1
    }


def test_complex_example6():
    src = utils.format_src("""
        def test_separable_conv_2d():
            def b():
                print('hello')
            print2(b)
    """)
    dest = utils.format_src("""
        def test_separable_conv_2d():
            def a():
                print('hello')
            print(a)
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'print': 1+0,
        'print2': 0+1,
        'a': 2,
        'b': 2
    }


def test_complex_example7():
    src = utils.format_src("""
        def test_usecols_list(self, ext):
            df1 = self.get_exceldf('test1', ext, 'Sheet1', index_col=0, usecols=[0, 2, 3])
            df2 = self.get_exceldf('test1', ext, 'Sheet2', skiprows=[1], index_col=0, usecols=[0, 2, 3])
    """)
    dest = utils.format_src("""
        def test_usecols_list(self, ext):
            df1 = pd.read_excel('test1' + ext, 'Sheet1', index_col=0, usecols=[0, 2, 3])
            df2 = pd.read_excel('test1' + ext, 'Sheet2', skiprows=[1], index_col=0, usecols=[0, 2, 3])
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'get_exceldf': 2+0,
        'test1': 2+2,
        'read_excel': 0+2,
        'ext': 3+3,
        'add': 0+2
    }


def test_complex_example8():
    src = utils.format_src("""
        def test_sequences(self):
            self.assertTrue(func(np.array(dtype=np.int32)) < np.array([[1], [0]]))
    """)
    dest = utils.format_src("""
        def test_sequences(self):
            input_data = np.array(dtype=np.int32)
            expected = np.array([[1], [0]])
            output = func(input_data)
            self.assertTrue(np.all(output == expected))
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        'assertTrue': 1+1,
        'all': 0+1,
        'expected': 0+2,
        'output': 0+2,
        '=': 0+3,
        'func': 1+1,
        'Lt': 1+0,
        'Eq': 0+1,
        'input_data': 2
    }


def test_complex_example9():
    src = utils.format_src("""
        def _real_extract(self):
            video_id = '1'
            video_info_webpage = self._download_webpage(
                'base_url' + video_id, video_id,
                note=u'Downloading video info page')
            video_info = xml.etree.ElementTree.fromstring(video_info_webpage)
    """)
    dest = utils.format_src("""
        def _real_extract(self):
            video_id = '1'
            video_info = self._download_xml(
                'base_url' + video_id, video_id,
                note=u'Downloading video info page')
    """)
    cg = _try_build_change_graph(src, dest)
    assert _get_label_to_node_cnt(cg) == {
        '_download_webpage': 1+0,
        'video_info_webpage': 2+0,
        'fromstring': 1+0,
        '_download_xml': 0+1,
        'video_info': 1+1,
        '=': 2+1
    }


if __name__ == '__main__':
    test_complex_example9()
    test_complex_example8()
    test_complex_example7()
    test_complex_example6()
    test_complex_example5()
    test_complex_example4()
    test_complex_example3()
    test_complex_example2()
    test_complex_example1()

    test_var_attr_call_attr_assign()
    test_var_attr_call_assign()
    test_var_attr_assign()
    test_var_rename1()
    test_for_statement1()
