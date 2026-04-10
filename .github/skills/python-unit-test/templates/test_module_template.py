import pytest

from module_name import function_name


def test_function_name_happy_path():
    result = function_name(input_value="ok")
    assert result == "expected"


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("", "fallback"),
        (None, "fallback"),
    ],
)
def test_function_name_edge_cases(input_value, expected):
    result = function_name(input_value=input_value)
    assert result == expected
