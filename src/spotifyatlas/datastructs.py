from __future__ import annotations

from typing import Optional, List
import requests
from . import utils


__all__ = ['Track']


class SpotifyAPIException(Exception):
    """Exception class for errors with the Spotify API, both requests and responses."""

    def __init__(self, r: Optional[requests.Response] = None, message: str = ''):
        if r is None and not message:
            super().__init__(
                'There was an unknown error with the current '
                'request, or in the Spotify servers.')
            return
        if r is None:
            super().__init__(message)
            return
        if message:
            message += ' '
        message += f'Status code: {r.status_code}. Server responded with: {r.text}'
        super().__init__(message)


class SpotifyUserAuthException(Exception):
    """Exception class for errors in the process of requesting the user's authorization."""
    pass


class Track:
    """**Represents a Spotify track.**"""

    @classmethod
    def from_id(cls, _id: str) -> Track:
        """Initialize with only the ID."""
        return cls('Unknown Track', 'Unknown Artist', utils.id_from_url(_id))

    @classmethod
    def from_url(cls, url: str) -> Track:
        """Initialize with the track's URL. This will not retreive name and artist."""
        return cls.from_id(url)

    def __init__(self, name: str, artist: str, _id: str) -> None:
        """**Represents a Spotify track.**

        If you want to manually initiolize an object, keep
        in mind that the ID of the track is the most important attribute in the end. The
        Spotify API is mostly based on URIs when handling tracks in playlists, which, in
        turn, contain the track ID. You can find a track's ID inside the share link of a
        song, after the last '/' and before the query params '?'.

        :param name: the name of the track
        :param artist: the first artist's name
        :param _id: the ID of the song
        """
        self.name = name
        self.artist = artist
        self.id = _id

    @property
    def uri(self) -> str:
        return f'spotify:track:{self.id}'

    def __eq__(self, other: Track) -> bool:
        return self.id == other.id

    def __repr__(self) -> str:
        name = self.name.replace('\'', '\\\'')
        artist = self.artist.replace('\'', '\\\'')
        return f'Track(\'{name}\', \'{artist}\', \'{self.id}\')'

    def __str__(self) -> str:
        return f'{self.name} - {self.artist}'

    def __hash__(self):
        return hash(self.id)


class Result:
    """**The return value of many SpotifyAPI methods. Wraps everything in a single object.**

    In the case of collections (playlists, albums), the track list is stored in ``tracks``.
    ``name`` and ``author_or_artist`` holds the creator of the collection. With individual
    tracks, the only difference is that ``tracks`` is a list with only one value. With
    artists, ``tracks`` will include its top tracks, and ``name`` and ``author_or_artist``
    will be interchangeable.

    There are some cases (namely, empty playlists) where the ``image_url`` attribute will
    be ``None``.

    This class is not intended to be used manually.
    """

    def __init__(self, tracks: List[Track], name: str, author_or_artist: str, _id: str,
                 image_url: Optional[str] = None):
        self.tracks = tracks
        self.name = name
        self.author_or_artist = author_or_artist
        self.id = _id
        self.image_url = image_url

    def __repr__(self):
        name = self.name.replace('\'', '\\\'')
        author_or_artist = self.author_or_artist.replace('\'', '\\\'')
        image_url = '' if self.image_url is None else f', \'{self.image_url}\''
        return f'Result({repr(self.tracks)}, \'{name}\', \'{author_or_artist}\'{image_url})'

    def __str__(self):
        return f'{self.name} - {self.author_or_artist}'


class TrackResult(Result):
    """**Represents a track result from the Spotify API.**"""

    # This class is almost identical to the base (Result) but
    # exists mainly for the sake of duck typing: to forward the artist
    # property, so it functions also like a Track.

    @property
    def track(self) -> Track:
        return self.tracks[0]

    @property
    def artist(self) -> str:
        return self.author_or_artist
