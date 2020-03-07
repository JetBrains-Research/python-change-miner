def remove_tabs(src, tabs=1):
    result = ''
    key = ''.join(['    ' for _ in range(tabs)])
    for line in src.split('\n'):
        line = line.replace(key, '', 1)
        result += line + '\n'
    return result
