from oterm.ollamaclient import parse_ollama_parameters


def test_parse_empty_string():
    assert parse_ollama_parameters("") == {}


def test_parse_single_numeric():
    assert parse_ollama_parameters("temperature 0.3") == {"temperature": 0.3}


def test_parse_string_value_literal_eval_fallback():
    # "mirostat_tau 5" -> int via literal_eval
    assert parse_ollama_parameters("mirostat_tau 5") == {"mirostat_tau": 5}


def test_unknown_key_is_dropped():
    assert parse_ollama_parameters("not_a_real_option 1") == {}


def test_repeated_key_becomes_list():
    params = parse_ollama_parameters("stop one\nstop two\nstop three")
    assert params == {"stop": ["one", "two", "three"]}


def test_value_that_fails_literal_eval_kept_as_string():
    # bare word that isn't a python literal falls through the except
    params = parse_ollama_parameters("stop abc")
    assert params == {"stop": "abc"}


def test_blank_lines_ignored():
    params = parse_ollama_parameters("\ntemperature 0.1\n\n")
    assert params == {"temperature": 0.1}
