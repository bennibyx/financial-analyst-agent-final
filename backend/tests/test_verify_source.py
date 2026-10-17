from agents.verify_source import number_in_source


def test_rejects_number_that_is_only_a_prefix():
    assert not number_in_source(18, "Revenue reached 180 million.")


def test_rejects_integer_inside_different_decimal():
    assert not number_in_source(18, "Revenue reached 18.5 million.")


def test_accepts_standalone_number():
    assert number_in_source(18, "Revenue reached 18 million.")


def test_accepts_number_with_trailing_punctuation():
    assert number_in_source(18, "Revenue reached 18.")


def test_accepts_thousands_separator():
    assert number_in_source(26000, "Revenue reached 26,000 million.")
