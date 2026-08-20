import importlib


def test_m1_facade_exports_claimspace_api():
    legacy = importlib.import_module("m1")
    claimspace = importlib.import_module("m1.claimspace")

    assert legacy.reset is claimspace.reset
    assert legacy.load_m1 is claimspace.load_m1


def test_legacy_submodules_forward_to_claimspace():
    browser = importlib.import_module("m1.browser")
    runtime = importlib.import_module("m1.runtime")
    claimspace_runtime = importlib.import_module("m1.claimspace.runtime")

    assert browser.main is importlib.import_module("m1.claimspace.browser").main
    assert runtime.reset is claimspace_runtime.reset


def test_network_package_is_available_without_claimspace_state():
    network = importlib.import_module("m1.network")

    assert network.__name__ == "m1.network"
