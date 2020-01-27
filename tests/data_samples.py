gumtree_t1 = {
    "root": {
        "type": "-1984916852",
        "typeLabel": "Module",
        "pos": "1",
        "length": "5",
        "children": [
            {
                
                "type": "1970629903",
                "typeLabel": "Assign",
                "pos": "1",
                "length": "5",
                "children": [
                    {
                        
                        "type": "-1068200714",
                        "label": "a",
                        "typeLabel": "NameStore",
                        "pos": "1",
                        "length": "1",
                        "children": []
                    },
                    {
                        
                        "type": "78694",
                        "label": "3",
                        "typeLabel": "Num",
                        "pos": "5",
                        "length": "1",
                        "children": []
                    }
                ]
            }
        ]
    }
}

src_gumtree_t2 = """
a = 33
if a > 10:
    print("a > 10")
else:
    print("a <= 10")
c = a + 11
print("gumtree test is over with a =" + a)
"""

gumtree_t2 = {
    "root": {
        "type": "-1984916852",
        "typeLabel": "Module",
        "pos": "1",
        "length": "119",
        "children": [
            {
                "type": "1970629903",
                "typeLabel": "Assign",
                "pos": "1",
                "length": "6",
                "children": [
                    {
                        "type": "-1068200714",
                        "label": "a",
                        "typeLabel": "NameStore",
                        "pos": "1",
                        "length": "1",
                        "children": []
                    },
                    {
                        "type": "78694",
                        "label": "33",
                        "typeLabel": "Num",
                        "pos": "5",
                        "length": "2",
                        "children": []
                    }
                ]
            },
            {
                "type": "2365",
                "typeLabel": "If",
                "pos": "8",
                "length": "57",
                "children": [
                    {
                        "type": "591249554",
                        "typeLabel": "CompareGt",
                        "pos": "11",
                        "length": "6",
                        "children": [
                            {
                                "type": "1904990769",
                                "label": "a",
                                "typeLabel": "NameLoad",
                                "pos": "11",
                                "length": "1",
                                "children": []
                            },
                            {
                                "type": "78694",
                                "label": "10",
                                "typeLabel": "Num",
                                "pos": "15",
                                "length": "2",
                                "children": []
                            }
                        ]
                    },
                    {
                        
                        "type": "3029410",
                        "typeLabel": "body",
                        "pos": "8",
                        "length": "57",
                        "children": [
                            {
                                
                                "type": "2174485",
                                "typeLabel": "Expr",
                                "pos": "23",
                                "length": "15",
                                "children": [
                                    {
                                        
                                        "type": "2092670",
                                        "typeLabel": "Call",
                                        "pos": "23",
                                        "length": "15",
                                        "children": [
                                            {
                                                
                                                "type": "1904990769",
                                                "label": "print",
                                                "typeLabel": "NameLoad",
                                                "pos": "23",
                                                "length": "5",
                                                "children": []
                                            },
                                            {
                                                
                                                "type": "83473",
                                                "label": "a > 10",
                                                "typeLabel": "Str",
                                                "pos": "29",
                                                "length": "8",
                                                "children": []
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        
                        "type": "-1008733796",
                        "typeLabel": "orelse",
                        "pos": "8",
                        "length": "57",
                        "children": [
                            {
                                
                                "type": "2174485",
                                "typeLabel": "Expr",
                                "pos": "49",
                                "length": "16",
                                "children": [
                                    {
                                        
                                        "type": "2092670",
                                        "typeLabel": "Call",
                                        "pos": "49",
                                        "length": "16",
                                        "children": [
                                            {
                                                
                                                "type": "1904990769",
                                                "label": "print",
                                                "typeLabel": "NameLoad",
                                                "pos": "49",
                                                "length": "5",
                                                "children": []
                                            },
                                            {
                                                
                                                "type": "83473",
                                                "label": "a <= 10",
                                                "typeLabel": "Str",
                                                "pos": "55",
                                                "length": "9",
                                                "children": []
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                
                "type": "1970629903",
                "typeLabel": "Assign",
                "pos": "67",
                "length": "10",
                "children": [
                    {
                        
                        "type": "-1068200714",
                        "label": "c",
                        "typeLabel": "NameStore",
                        "pos": "67",
                        "length": "1",
                        "children": []
                    },
                    {
                        
                        "type": "985538137",
                        "typeLabel": "BinOpAdd",
                        "pos": "71",
                        "length": "6",
                        "children": [
                            {
                                
                                "type": "1904990769",
                                "label": "a",
                                "typeLabel": "NameLoad",
                                "pos": "71",
                                "length": "1",
                                "children": []
                            },
                            {
                                
                                "type": "78694",
                                "label": "11",
                                "typeLabel": "Num",
                                "pos": "75",
                                "length": "2",
                                "children": []
                            }
                        ]
                    }
                ]
            },
            {
                
                "type": "2174485",
                "typeLabel": "Expr",
                "pos": "78",
                "length": "42",
                "children": [
                    {
                        
                        "type": "2092670",
                        "typeLabel": "Call",
                        "pos": "78",
                        "length": "42",
                        "children": [
                            {
                                
                                "type": "1904990769",
                                "label": "print",
                                "typeLabel": "NameLoad",
                                "pos": "78",
                                "length": "5",
                                "children": []
                            },
                            {
                                
                                "type": "985538137",
                                "typeLabel": "BinOpAdd",
                                "pos": "84",
                                "length": "35",
                                "children": [
                                    {
                                        
                                        "type": "83473",
                                        "label": "gumtree test is over with a =",
                                        "typeLabel": "Str",
                                        "pos": "84",
                                        "length": "31",
                                        "children": []
                                    },
                                    {
                                        
                                        "type": "1904990769",
                                        "label": "a",
                                        "typeLabel": "NameLoad",
                                        "pos": "118",
                                        "length": "1",
                                        "children": []
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
}

gumtree_matches = [
    {
        "src": 2,
        "dest": 2
    },
    {
        "src": 1,
        "dest": 1
    },
    {
        "src": 3,
        "dest": 28
    },
    {
        "src": 0,
        "dest": 0
    }
]


# TODO: make tests
#     lr = LineReader("""a  =  33
# b = 14 + a
# c = 4
#
# if a == 4:
#     a += 45
#
# b = 13 + c
# """)
#     print(lr.lines)
