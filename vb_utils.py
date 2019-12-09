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
