from . import _modidx,showdoc
__all__ = ['nbdev_lookup', 'version']
nbdev_lookup = showdoc.NbdevLookup(_modidx.d)
version = _modidx.d['settings']['version']

