from textualeffects.widgets import SplashScreen

from oterm.app import splash as splash_mod


def test_module_exports_splash_widget():
    assert isinstance(splash_mod.splash, SplashScreen)


def test_effects_list_non_empty_and_tuples():
    for effect, config in splash_mod.effects:
        assert isinstance(effect, str)
        assert isinstance(config, dict)


def test_logo_contains_expected_art():
    assert "@@@@" in splash_mod.logo
    assert len(splash_mod.logo.splitlines()) > 20
