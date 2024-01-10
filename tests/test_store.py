from oterm.utils import int_to_semantic_version, semantic_version_to_int


def test_sqlite_user_version():
    version = "0.1.5"
    assert semantic_version_to_int(version) == 261
    assert int_to_semantic_version(261) == version

    version = "0.0.0"
    assert semantic_version_to_int(version) == 0
    assert int_to_semantic_version(0) == version

    version = "255.255.255"
    assert semantic_version_to_int(version) == 16777215
    assert int_to_semantic_version(16777215) == version
