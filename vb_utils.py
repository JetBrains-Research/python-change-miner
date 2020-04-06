def merge_dict(d1, d2):
    for k, v in d2.items():
        d1[k] = v
    return d1


def deep_merge_dict(d1, d2):
    for k, v in d2.items():
        v1 = d1.get(k)
        v2 = d2.get(k)

        new_v = deep_merge(v1, v2)
        d1[k] = new_v
    return d1


def deep_merge(v1, v2):
    if isinstance(v1, list) and isinstance(v2, list):
        v1 += v2
    elif isinstance(v1, dict) and isinstance(v2, dict):
        v1 = deep_merge_dict(v1, v2)
    elif isinstance(v1, set) and isinstance(v2, set):
        v1 = v1.union(v2)
    else:
        return v2
    return v1


def filter_list(lst, condition, post_condition_fn=None):
    i = 0
    while i < len(lst) - 1:
        j = i + 1
        while j < len(lst):
            if condition(i, j):
                if post_condition_fn:
                    post_condition_fn(i, j)
                del lst[j]
            else:
                j += 1
        i += 1


class LineReader:
    def __init__(self, content):
        self.line_pos_arr = []
        self.content = content

        self._parse(content)

    def _parse(self, content):
        self.line_pos_arr.append(0)
        for ch_num in range(len(content)):
            if content[ch_num] == '\n':
                self.line_pos_arr.append(ch_num)

    # consider both start with 1
    def get_pos(self, line, col):
        return self.line_pos_arr[line - 1] + col - 1


def split_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]
