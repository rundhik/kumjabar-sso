"""Flat-layout compatibility loader for the IDP application.

The runtime source files live directly in this directory. This module exposes
that flat source as the ``idp_pegawai`` package without creating a nested
``idp_pegawai/`` directory.
"""
import importlib.util
import sys
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

# Pre-publish this package as ``app`` before executing the initializer so
# any early import of ``app.*`` does not create a second module tree with
# a second SQLAlchemy instance. This is the root cause of
# ``RuntimeError: The current Flask app is not registered with this
# 'SQLAlchemy' instance`` on POST /imports/batches.
sys.modules.setdefault("app", sys.modules[__name__])
sys.modules.setdefault("app.idp_pegawai", sys.modules[__name__])

exec(compile(_source.read_bytes(), str(_source), "exec"), globals(), globals())

# Publish idp_pegawai.* as app.* and app.idp_pegawai.* so every import
# identity (idp_pegawai, app, app.idp_pegawai) shares the SAME module
# objects and the SAME SQLAlchemy instance (models/base.py).
for _k, _v in list(sys.modules.items()):
    if _k == "idp_pegawai" or _k.startswith("idp_pegawai."):
        _a1 = _k.replace("idp_pegawai", "app", 1)
        sys.modules.setdefault(_a1, _v)
        if _k != "idp_pegawai":
            _a2 = _k.replace("idp_pegawai.", "app.idp_pegawai.", 1)
            sys.modules.setdefault(_a2, _v)
    elif _k == "app" or _k.startswith("app."):
        # reverse: if something was loaded as app.* first, mirror to idp_pegawai
        if _k == "app":
            sys.modules.setdefault("idp_pegawai", _v)
        elif _k.startswith("app.idp_pegawai."):
            _i = _k.replace("app.idp_pegawai.", "idp_pegawai.", 1)
            sys.modules.setdefault(_i, _v)
        elif _k.startswith("app.") and not _k.startswith("app.idp_pegawai."):
            _i2 = _k.replace("app.", "idp_pegawai.", 1)
            sys.modules.setdefault(_i2, _v)
