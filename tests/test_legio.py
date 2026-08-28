from legio import __version__


def test_version_matches_public_api() -> None:
    assert isinstance(__version__, str)
    assert __version__.count(".") == 2
