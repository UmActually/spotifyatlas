from __future__ import annotations

from typing import Optional, Union, List, Iterator, TYPE_CHECKING
import itertools
import requests
from .enums import ResultType
from . import utils
from .baseapi import BaseSpotifyAPI
if TYPE_CHECKING:
    from .spotifyapi import SpotifyAPI


__all__ = ['SpotifyAPIException', 'SpotifyUserAuthException', 'Track',
           'TrackCollection', 'Playlist', 'Album', 'Artist', 'User', 'SearchResult']


_OptStr = Optional[str]


class SpotifyAPIException(Exception):
    """Exception class for errors with the Spotify API, both requests and responses."""

    def __init__(self, r: Optional[requests.Response] = None, message: str = '') -> None:
        self.response = r
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
        """Initialize with only the ID. This will not retreive track details."""
        return cls(utils.get_id(_id))

    @classmethod
    def from_url(cls, url: str) -> Track:
        """Initialize with the track's URL. This will not retreive track details."""
        return cls.from_id(url)

    def __init__(self, _id: str, name: _OptStr = None, artist: Optional[Artist] = None,
                 album: Optional[Album] = None, *, client_id: _OptStr = None) -> None:
        """**Represents a Spotify track.**

        If you want to manually initiolize an object, keep
        in mind that the ID of the track is the most important attribute in the end. The
        Spotify API is mostly based on URIs when handling tracks in playlists, which, in
        turn, contain the track ID. You can find a track's ID inside the share link of a
        song, after the last '/' and before the query params '?'.
        """
        self.id = _id
        self.name = name
        self.artist = artist
        self._album = album
        self._client_id = client_id

    @property
    def album(self) -> Optional[Album]:
        if self._album is None and self._client_id:
            # Sike, BaseSpotifyAPI actually returns the usual class
            # see: baseapi.py
            spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
            self._album = spoti.get_album_from_track(self)
        return self._album

    @property
    def url(self) -> str:
        return f'https://open.spotify.com/track/{self.id}'

    @property
    def uri(self) -> str:
        return f'spotify:track:{self.id}'

    def __eq__(self, other: Track) -> bool:
        return self.id == other.id

    def __repr__(self) -> str:
        return f'<{self.__class__.__qualname__} ' \
               f'name={repr(self.name)} ' \
               f'artist={repr(self.artist.name)} ' \
               f'id={repr(self.id)}>'

    def __str__(self) -> str:
        return f'{self.name} - {self.artist.name}'

    def __hash__(self) -> int:
        return hash(self.id)


class TrackCollection:
    """**Base class for track collections (playlists, albums, and artists).**

    This class is not intended to be used manually.
    """

    def __init__(self, _id: str, name: str, image_url: _OptStr = None,
                 tracks: Optional[List[Track]] = None, *, client_id: _OptStr = None) -> None:
        self.id = _id
        self.type = None
        self.name = name
        self._image_url = image_url
        self._tracks = tracks
        self._client_id = client_id

    def _get_tracks(self, force_update: bool = False) -> List[Track]:
        """Getter for the result tracks. Sometimes the TrackCollection will be initialized
        without tracks. In that case, they will be retreived in here by shamelessly
        accessing a SpotifyAPI object."""

        if force_update or self._client_id and self._tracks is None:
            spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
            # noinspection PyProtectedMember
            self._tracks = spoti.get(self)._tracks
        return self._tracks

    @property
    def url(self) -> str:
        return f'https://open.spotify.com/{self.type}/{self.id}'

    @property
    def uri(self) -> str:
        return f'spotify:{self.type}:{self.id}'

    @property
    def image_url(self) -> _OptStr:
        """There are some cases (namely, empty playlists) where the
        ``image_url`` property will always be ``None``."""
        if self._image_url is None:
            spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
            self._image_url = spoti.get(self)._image_url
        return self._image_url

    def __getitem__(self, index: Union[int, slice]) -> Track:
        return self._get_tracks()[index]

    def __len__(self) -> int:
        return len(self._get_tracks())

    def __iter__(self):
        return iter(self._get_tracks())

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other: TrackCollection) -> bool:
        return self.id == other.id and str(self.type) == str(other.type)

    def __repr__(self) -> str:
        if isinstance(self, Playlist):
            owner_or_artist = f' owner={repr(self.owner.name)}'
        elif isinstance(self, Album):
            owner_or_artist = f' artist={repr(self.artist.name)}'
        else:
            owner_or_artist = ''
        return f'<{self.__class__.__qualname__} ' \
               f'name={repr(self.name)}{owner_or_artist} id={repr(self.id)}>'

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.id)


class Playlist(TrackCollection):
    """**Represents a Spotify playlist.**"""

    def __init__(self, _id: str, name: str, owner: User, image_url: _OptStr = None,
                 tracks: Optional[List[Track]] = None, *, client_id: _OptStr = None) -> None:
        super(Playlist, self).__init__(_id, name, image_url, tracks, client_id=client_id)
        self.type = ResultType.PLAYLIST
        self.owner = owner

    @property
    def tracks(self) -> List[Track]:
        return self._get_tracks()

    def update_tracks(self) -> List[Track]:
        """Updates tracks in-place and also returns the new track list."""
        return self._get_tracks(force_update=True)

    def add(self, tracks: List[Track], *, position: int = 0) -> None:
        """**Add a list of tracks to a Spotify playlist.**

        The playlist must belong to you, or be collaborative.

        This also updates the ``tracks`` attribute in the ``Playlist`` object. To insert a
        track or list of tracks at the end of a playlist, see ``append()`` and ``extend()``
        methods.

        :param tracks: a list of ``Track``, containing the tracks to add
        :param position: the index (starting at 0) where the tracks will be inserted
        :return: ``None``
        """
        spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
        spoti.add_to_playlist(self, tracks, position=position)
        if self._tracks is None:
            self._tracks = tracks.copy()
        else:
            self._tracks = self._tracks[:position] + tracks + self._tracks[position:]

    def clear(self, *, make_copy: bool = False) -> Playlist:
        """**Remove ALL the songs of the playlist.**

        The playlist must belong to you, or be collaborative.

        If you use this method to automatically rearrange or update the tracks in a playlist,
        I **strongly** recommend that you make a copy of the playlist before anything, by setting
        ``make_copy`` to ``True``. Although unlikely, it is possible that the API request succeeds
        when clearing the playlist, and then fails while putting the tracks back.

        :param make_copy: whether to back up the playlist before clearing it
        :return: the ``Playlist`` as it was before being modified
        """
        spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
        # Can throw exception, so call the function before updating self
        resp = spoti.clear_playlist(self, make_copy=make_copy)
        if self._tracks:
            # Not using clear(), a user may be using the playlist tracks
            # outside this function
            self._tracks = []
        return resp

    def duplicate(self) -> Playlist:
        """**Create a new playlist in your library, with the same tracks.**

        :return: the new ``Playlist`` object
        """
        spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
        return spoti.duplicate_playlist(self)

    def append(self, track: Track) -> None:
        """**Add a track to the end of a Spotify playlist.**

        The playlist must belong to you, or be collaborative.

        This also updates the ``tracks`` attribute in the ``Playlist`` object. To insert a
        list of tracks at the end of a playlist, see ``extend()`` method.

        :param track: the track to add
        :return: ``None``
        """
        self.add([track], position=len(self))

    def extend(self, tracks: List[Track]) -> None:
        """**Add a list of tracks to the end of a Spotify playlist.**

        The playlist must belong to you, or be collaborative. This also updates the
        ``tracks`` attribute in the ``Playlist`` object.

        :param tracks: a list of ``Track``, containing the tracks to add
        :return: ``None``
        """
        self.add(tracks, position=len(self))

    def rearrange(self, range_start: int, range_length: int, insert_before: int) -> None:
        """**Change the position of a track, or range of tracks in a playlist.**

        The playlist must belong to you, or be collaborative. All indexes start at zero.
        This also updates the ``tracks`` attribute in the ``Playlist`` object.

        :param range_start: the index of the first track of your selection
        :param range_length: the size of the selection
        :param insert_before: insert the selection before the track at this index
        :return: ``None``
        """
        spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
        spoti.rearrange_playlist(self, range_start, range_length, insert_before)
        if self._tracks is None:
            self.update_tracks()
        elif self._tracks:
            _slice = self._tracks[range_start:(range_start + range_length)]
            del self._tracks[range_start:(range_start + range_length)]
            self._tracks = \
                self._tracks[:insert_before] + _slice + self._tracks[insert_before:]

    def __str__(self) -> str:
        return f'{self.name} - {self.owner.name}'


class Album(TrackCollection):
    """**Represents a Spotify album.**"""

    def __init__(self, _id: str, name: str, artist: Artist,
                 image_url: _OptStr = None, tracks: Optional[List[Track]] = None, *,
                 client_id: _OptStr = None) -> None:
        super(Album, self).__init__(_id, name, image_url, tracks, client_id=client_id)
        self.type = ResultType.ALBUM
        self.artist = artist

    @property
    def tracks(self) -> List[Track]:
        return self._get_tracks()

    def __str__(self) -> str:
        return f'{self.name} - {self.artist.name}'


class Artist(TrackCollection):
    """**Represents a Spotify artist, alongside its top 10 tracks.**"""

    def __init__(self, _id: str, name: str, image_url: _OptStr = None,
                 top_tracks: Optional[List[Track]] = None, *, client_id: _OptStr = None) -> None:
        super(Artist, self).__init__(_id, name, image_url, top_tracks, client_id=client_id)
        self.type = ResultType.ARTIST

    @property
    def top_tracks(self) -> List[Track]:
        return self._get_tracks()

    def update_top_tracks(self) -> List[Track]:
        """Updates tracks in-place and also returns the new track list."""
        return self._get_tracks(force_update=True)


class User:
    """**Represents a Spotify user.**"""

    def __init__(self, _id: str, name: _OptStr, image_url: _OptStr = None, *,
                 client_id: _OptStr = None) -> None:
        self.id = _id
        self.name = name
        self._image_url = image_url
        self._client_id = client_id

    @property
    def url(self) -> str:
        return f'https://open.spotify.com/user/{self.id}'

    @property
    def image_url(self) -> str:
        if self._client_id and not self._image_url:
            spoti: SpotifyAPI = BaseSpotifyAPI(self._client_id, '')
            self._image_url = spoti.get_user(self)._image_url
        return self._image_url

    @property
    def uri(self) -> str:
        return f'spotify:user:{self.id}'

    def __eq__(self, other: User) -> bool:
        return self.id == other.id

    def __repr__(self) -> str:
        return f'<{self.__class__.__qualname__} ' \
               f'name={repr(self.name)} id={repr(self.id)}>'

    def __str__(self) -> str:
        return f'{self.name}'


class SearchResult:
    """**Represents a search result from the Spotify API.**

    The attributes ``albums``, ``artists``, ``playlists``, and ``tracks`` are
    lists that may contain individual ``Track`` or ``TrackCollection`` objects
    ordered by relevance. The length of each list can vary from zero to twenty.
    """

    def __init__(self, query: str, albums: List[Album], artists: List[Artist],
                 playlists: List[Playlist], tracks: List[Track]) -> None:
        self.query = query
        self.albums = albums
        self.artists = artists
        self.playlists = playlists
        self.tracks = tracks

    def flatten(self) -> Iterator[Union[Album, Artist, Playlist, Track]]:
        """**Make a single iterator out of all the search result lists (breadth-first).**

        Returns an iterator that yields values from every list equally in order of
        popularity. For example, if all lists have twenty items, this iterator would
        result in ``(album1, artist1, playlist1, track1, album2, artist2, ... ,
        playlist20, track20)``.

        The lists of a ``SearchResult`` object, however, may have different lengths.
        This iterator always will return the next available element, until all
        lists are exhausted.

        This method is implicitly called if you iterate over this class, like when
        using a for loop.
        """

        return filter(  # unholy itertools one-liner alert
            lambda x: x is not None,
            itertools.chain(*itertools.zip_longest(
                self.albums, self.artists, self.playlists, self.tracks,
                fillvalue=None)))

    def chain(self) -> Iterator[Union[Album, Artist, Playlist, Track]]:
        """**Make a single iterator out of all the search result lists (depth-first).**

        Returns an iterator that yields values from every list, one list after the other.
        For example, if all lists have twenty items, this iterator would result in
        ``(album1, album2, album3, ... , album20, artist1, artist2, artist3, ... ,
        track20)``.

        The lists of a ``SearchResult`` object, however, may have different lengths.
        This iterator always will return the next available element, until all
        lists are exhausted.
        """

        return itertools.chain(self.albums, self.artists, self.playlists, self.tracks)

    def __len__(self) -> int:
        return sum(map(len, (self.albums, self.artists, self.playlists, self.tracks)))

    def __iter__(self) -> Iterator[Union[Album, Artist, Playlist, Track]]:
        return self.flatten()

    def __eq__(self, other: SearchResult) -> bool:
        return self.query == other.query

    def __repr__(self) -> str:
        return f'<{self.__class__.__qualname__} query={repr(self.query)}>'

    def __str__(self) -> str:
        return self.query
