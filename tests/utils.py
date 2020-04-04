def format_src(src):
    base_line = src.split('\n')[0]
    if not base_line:
        base_line = src.split('\n')[1]

    spaces = len(base_line) - len(base_line.lstrip(' '))

    result = ''
    key = ''.join([' ' for _ in range(spaces)])
    for line in src.split('\n'):
        line = line.replace(key, '', 1)
        result += line + '\n'
    return result
