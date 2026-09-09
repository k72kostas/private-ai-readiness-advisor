from app.components.helpers import enum_label, lines

def test_lines_removes_blanks_and_duplicates():
    assert lines("Alpha\n\n beta \nALPHA") == ["Alpha", "beta"]

def test_enum_label():
    assert enum_label("controlled_prototype") == "Controlled Prototype"
