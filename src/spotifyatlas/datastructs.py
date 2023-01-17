from __future__ import annotations

from typing import Optional, Union, List, TYPE_CHECKING
import requests
from .enums import Type
from . import utils
from .baseapi import BaseSpotifyAPI
if TYPE_CHECKING:
    from .spotifyapi import SpotifyAPI


__all__ = ['SpotifyAPIException', 'SpotifyUserAuthException', 'Track', 'Result', 'UserResult', 'SearchResult']


class SpotifyAPIException(Exception):
    """Exception class for errors with the Spotify API, both requests and responses."""

    def __init__(self, r: Optional[requests.Response] = None, message: str = '') -> None:
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
        return f'Track({repr(self.name)}, {repr(self.artist)}, {repr(self.id)})'

    def __str__(self) -> str:
        return f'{self.name} - {self.artist}'

    def __hash__(self) -> int:
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

    def __init__(self, _id: str, _type: Union[Type, str], name: str, author_or_artist: str,
                 tracks: Optional[List[Track]] = None, image_url: Optional[str] = None, *,
                 client_id: Optional[str] = None) -> None:
        if tracks is None and client_id is None:
            raise ValueError('Tracks was set to None. Expected client_id to get tracks later.')
        self.id = _id
        self.type = _type
        self.name = name
        self.author_or_artist = author_or_artist
        self._tracks = tracks
        self.image_url = image_url
        self._client_id = client_id

    @property
    def tracks(self) -> List[Track]:
        """Getter for the result tracks. Sometimes the Result will be initialized
        without tracks. In that case, they will be retreived in here by shamelessly
        accessing a SpotifyAPI object."""
        if self._tracks is None:
            # Sike, BaseSpotifyAPI actually returns the usual class
            # see: baseapi.py
            spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
            self._tracks = spoti.get(self.id, result_type=self.type)._tracks
        return self._tracks

    @property
    def author(self) -> str:
        """Alias for ``author_or_artist``."""
        return self.author_or_artist

    @property
    def artist(self) -> str:
        """Alias for ``author_or_artist``."""
        return self.author_or_artist

    def __bool__(self) -> bool:
        return self._tracks is not None

    def __eq__(self, other: Result) -> bool:
        return self.id == other.id and str(self.type) == str(other.type)

    def __repr__(self) -> str:
        tracks = '' if self._tracks is None else f', {repr(self._tracks)}'
        image_url = '' if self.image_url is None else f', {repr(self.image_url)}'
        return f'Result({repr(self.id)}, {repr(self.type)}, {repr(self.name)}, ' \
               f'{repr(self.author_or_artist)}{tracks}{image_url})'

    def __str__(self) -> str:
        return f'{self.name} - {self.author_or_artist}'


class UserResult:
    """**Represents an user result from the Spotify API.**"""

    def __init__(self, _id: str, display_name: Optional[str], image_url: Optional[str] = None) -> None:
        self.id = _id
        self.display_name = display_name
        self.image_url = image_url

    def __eq__(self, other: UserResult) -> bool:
        return self.id == other.id

    def __repr__(self) -> str:
        image_url = '' if self.image_url is None else f', {repr(self.image_url)}'
        return f'UserResult({repr(self.id)}, {repr(self.display_name)}{image_url})'

    def __str__(self) -> str:
        return f'{self.display_name} - {self.id}'


class SearchResult:
    """**Represents a search result from the Spotify API.**

    The attributes ``albums``, ``artists``, ``playlists``, and ``tracks`` are
    lists that may contain individual ``Result`` objects ordered by relevance.
    The length of each list can vary from zero to twenty.
    """

    def __init__(self, query: str, albums: List[Result], artists: List[Result],
                 playlists: List[Result], tracks: List[Result]) -> None:
        self.query = query
        self.albums = albums
        self.artists = artists
        self.playlists = playlists
        self.tracks = tracks

    def __eq__(self, other: SearchResult) -> bool:
        return self.query == other.query

    def __repr__(self) -> str:
        return f'SearchResult({repr(self.query)}, {repr(self.albums)}, ' \
               f'{repr(self.artists)}, {repr(self.playlists)}, {repr(self.tracks)})'

    def __str__(self) -> str:
        return self.query
