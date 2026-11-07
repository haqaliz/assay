from importlib.metadata import version

import assay


def test_the_module_version_matches_the_installed_package():
    assert assay.__version__ == version("assayhq")
