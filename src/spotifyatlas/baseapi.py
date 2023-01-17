from __future__ import annotations
from typing import Dict
from weakref import WeakValueDictionary


__all__ = ['BaseSpotifyAPI']


class BaseSpotifyAPI:
    """**Do not mind this class.** There are only two purposes for this base class.

    One, to have a dictionary that stores every SpotifyAPI instance, avoiding
    unnecesary copies when SpotifyAPI is called with an already existing client ID.

    Two, this was the least obscure way I found to avoid a circular import between
    spotifyapi.py and datastructs.py. Now I can get access to the SpotifyAPI class
    from within a module that spotifyapi.py itself imports."""

    # Weak ref dict prevents objects from never being GC'd from existence.
    _instances: Dict[str, BaseSpotifyAPI] = WeakValueDictionary()

    def __new__(cls, *args, **kwargs):
        try:
            return cls._instances[args[0]]
        except KeyError:
            return object.__new__(cls)
