"""Flat-layout compatibility loader for the IDP application.

The runtime source files live directly in this directory. This module exposes
that flat source as the ``idp_pegawai`` package without creating a nested
``idp_pegawai/`` directory.
"""
import importlib.util
from pathlib import Path

_package_dir = Path(__file__).resolve().parent
_source = _package_dir / "__init__.py"

# ``idp_pegawai.py`` is a flat-layout package loader, so Python initially
# gives it a module spec whose parent is empty.  Install a package-shaped spec
# before executing the real package initializer; otherwise relative imports
# emit ``ImportWarning: __package__ != __spec__.parent`` during pytest
# collection.
__path__ = [str(_package_dir)]
__spec__ = importlib.util.spec_from_file_location(
    __name__, str(_source), submodule_search_locations=[str(_package_dir)]
)
__package__ = __spec__.parent
exec(compile(_source.read_bytes(), str(_source), "exec"), globals(), globals())
