"""
:Authors: Leonardo Corona Garza
:Version: 0.1.0

spotifyatlas
============

A pythonic wrapper for the Spotify web API.
-------------------------------------------

**By Leonardo - UmActually**

``spotifyatlas`` is a straightforward library meant to simplify the process of interacting with **Spotify's web API**.
Whether you are trying to automate the process of **search queries**, or **modifying your playlists**, spotifyatlas has
tools for your scripting (or webdev) needs, all in a clean, object-oriented style.

Basic Usage
-----------

Initialize a ``SpotifyAPI`` object with the credentials of your app. If you wish to retrieve the **tracks and/or
details** of anything in Spotify, the universal ``get()`` method many times will get you covered. Try it by pasting the
share link of your favorite playlist. It will return a ``Result``: the playlist tracks are located in the
``tracks`` attribute.

    >>> from spotifyatlas import SpotifyAPI
    >>> spoti = SpotifyAPI('<my-client-id>', '<my-client-secret>')
    >>> result = spoti.get('https://open.spotify.com/playlist/6xTnvRqIKptVfgcT8gN4Bb')
    >>> print(result.tracks)
    [Track('Goliath', 'The Mars Volta', '3bi3Ycf0ZlRHvSg0IxlMwM'), ... ]

The following methods offer the same functionality, although more specific:

- ``get_playlist()`` for public playlists.

- ``get_track()`` for tracks.

- ``get_artist()`` for artists and their top 10 tracks in the US.

- ``get_album()`` for albums.

All four require the ``url`` or the ID of the element as the first argument.

These other methods require **user consent**, and thus will result in the **browser** opening for the authorization of
your application to act on behalf of the user:

- ``get_private_playlist()`` for private playlists you own.

- ``add_to_playlist()`` to add a batch of ``Track``s to a playlist.

- ``clear_playlist()`` to remove all the contents of a playlist.

- ``rearrange_playlist()`` to change the position of a range of tracks.

*Note: authorizing the application in the Spotify authorization page requires a redirection page to go to. By default,
this library will temporarily host a local page on http://localhost:8000. Thus, you will need to add this URL to the
allowed redirection URLs on the dashboard of your application in the Spotify for Developers site.*

The complete list of parameters/arguments of a function can be found in its documentation.
"""

from .spotifyapi import *
from .datastructs import *
from . import utils
