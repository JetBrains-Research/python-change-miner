import pyflowgraph


def main():
    # sys.setrecursionlimit(10000)

    fg = pyflowgraph.build_from_file(file_path='examples/1.py', build_closure=False)
    pyflowgraph.export_graph_image(fg)


if __name__ == '__main__':
    main()
