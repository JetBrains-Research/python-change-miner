import patterns.search


def test_merge_intervals():
    intervals = [
        [723, 730], [133, 138], [909, 914],
        [124, 131], [900, 907], [767, 774],
        [175, 180], [820, 825], [166, 173],
        [811, 818], [721, 918], [80, 226],
        [217, 222], [91, 96], [864, 870],
        [208, 215], [82, 89], [855, 862],
        [732, 737], [925, 928], [776, 781]
    ]

    result = patterns.search.Miner.merge_intervals(intervals)
    assert result == [[80, 226], [721, 918], [925, 928]]


if __name__ == '__main__':
    test_merge_intervals()
