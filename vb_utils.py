def merge_dict(d1, d2):
    for k, v in d2.items():
        d1[k] = v
    return d1


def deep_merge_dict(d1, d2):
    for k, v in d2.items():
        if isinstance(d1.get(k), list) and isinstance(d2.get(k), list):
            d1[k] += d2[k]
        elif isinstance(d1.get(k), dict) and isinstance(d2.get(k), dict):
            d1[k] = deep_merge_dict(d1[k], d2[k])
        elif isinstance(d1.get(k), set) and isinstance(d2.get(k), set):
            d1[k] = d1[k].union(d2[k])
        else:
            d1[k] = v
    return d1


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
