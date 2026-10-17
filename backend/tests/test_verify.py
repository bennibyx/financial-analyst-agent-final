from agents.verify import number_in_quote


def test_rejects_number_that_is_only_a_prefix():
    assert not number_in_quote(18, "Revenue reached 180 million.")


def test_accepts_standalone_number():
    assert number_in_quote(18, "Revenue reached 18 million.")


def test_rejects_integer_inside_different_decimal():
    assert not number_in_quote(18, "Revenue reached 18.5 million.")


def test_accepts_matching_decimal():
    assert number_in_quote(18.5, "Revenue reached 18.5 million.")


def test_accepts_number_with_trailing_punctuation():
    assert number_in_quote(18, "Revenue reached 18.")
