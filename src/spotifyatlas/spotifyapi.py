from __future__ import annotations

import urllib.parse
from typing import Any, Optional, Union, \
    Tuple, List, Dict, Iterator, Callable
from importlib import resources
import datetime
import random
import base64
import json
import functools
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser

import requests

from . import utils
from .enums import ResultType
# noinspection PyProtectedMember
from .datastructs import \
    SpotifyAPIException, SpotifyUserAuthException, Track, \
    TrackCollection, Playlist, Album, Artist, User, SearchResult,\
    _OptStr
from .baseapi import BaseSpotifyAPI

# if TYPE_CHECKING:
#     spoti = ...
#     spotifyatlas = ...


__all__ = ['SpotifyAPI']


_redirect_page = resources.read_text("spotifyatlas.resources", "redirectpage.html")
# _AnyTrack = Union[Track, Result]
_LiterallyAnything = Union[Playlist, Album, Artist, Track, User]
_AlmostAnything = Union[Playlist, Album, Artist, Track]


class SpotifyAPI(BaseSpotifyAPI):
    """**The meat-and-potatoes of this package.**

    It is required that you create an app in Spotify for Developers (it's free!) to use this
    wrapper class. Then, initialize the Spotify API class with the credentials of your application:

        >>> spoti = SpotifyAPI('<my-client-id>', '<my-client-secret>')
        >>> result = spoti.get('https://open.spotify.com/playlist/3wrUHfvsdnjiZ0kFJLvFOK')
        >>> result.tracks
        [<Track name='Run' artist='Collective Soul' id='3HxX5qcaz2phmsJVPskugD'>, ... ]

    There are some methods that require an extra permission grant from the user, i.e., whenever the
    program will do modifications in behalf of. Using these methods will result in the Spotify app
    authorization page being open in the browser. See README for more info.
    """

    # The point of collecting all the primary functions in a single class is in order to share
    # many important attributes (mostly credentials, tokens and such).

    @staticmethod
    def _get_image_url(item: dict) -> _OptStr:
        """Return an optional image URL, with the JSON result of a request."""
        try:
            images = item['images']
        except KeyError:
            images = item['album']['images']
        try:
            return images[0]['url']
        except IndexError:
            return

    @staticmethod
    def _get_class_from_enum(_type: ResultType) -> type:
        """Used to get the right constructor when iterating over specified types
        in the _search() method."""
        if _type == ResultType.PLAYLIST:
            return Playlist
        if _type == ResultType.ARTIST:
            return Artist
        return Album

    @staticmethod
    def _requires_user_auth(func: Callable) -> Callable:
        """Decorator that prepends a method with the user authorization flow."""
        @functools.wraps(func)
        def wrapper(self: SpotifyAPI, *args, **kwargs):
            if not self._user_access_code:
                self._prompt_user_auth()
                self._request_user_token()
            return func(self, *args, **kwargs)

        return wrapper

    def __init__(self, client_id: str, client_secret: str, *, market: str = 'US') -> None:
        """**Initialize the SpotifyAPI class.**

        :param client_id: the client ID of your application
        :param client_secret: the client secret of your application
        :param market: optionally, specify the market (like for artist's top tracks)
        """

        if client_id in super(SpotifyAPI, self)._instances:
            return

        if not client_id or not client_secret:
            raise ValueError(
                'Client credentials (a client ID and a client secret) are needed to access the Spotify API. '
                'Visit https://developer.spotify.com/documentation/general/guides/authorization/app-settings/ '
                'for information on how to create an app in Spotify for developers.')

        self.client_id = client_id
        self.client_secret = client_secret
        self.market = market

        client_creds = f'{self.client_id}:{self.client_secret}'
        self._client_creds_b64: str = base64.b64encode(client_creds.encode()).decode()

        self._token = ''
        self._user_token = ''
        self._user_refresh_token = ''
        self._user_access_code = ''
        self._expires = datetime.datetime.now()
        self._user_expires = datetime.datetime.now()
        self._prefer_user_token = False

        super(SpotifyAPI, self)._instances[client_id] = self

    def get(self, url: Union[str, _LiterallyAnything, TrackCollection], *,
            result_type: Optional[Union[ResultType, str]] = None) -> _LiterallyAnything:
        """**Universal method to retreive the details of something in Spotify.**

        :param url: the URL of the playlist, track, album, artist, or user
        :param result_type: when passing an ID instead of an URL, specify a ResultType.
        :return: a ``Playlist``, ``Album``, ``Artist``, ``Track``, or ``User`` object.
        """

        invalid = False
        try:
            if url.startswith('https://open.spotify.com/'):
                kind = url.split('/')[3]
            else:
                invalid = result_type is None
                kind = str(result_type)
        except AttributeError:
            invalid = url.type is None
            kind = str(url.type)

        if not invalid:
            if kind == 'playlist':
                return self.get_playlist(url)
            if kind == 'track':
                return self.get_track(url)
            if kind == 'artist':
                return self.get_artist(url)
            if kind == 'album':
                return self.get_album(url)
            if kind == 'user':
                return self.get_user(url)

        raise ValueError('Spotify URL not valid. Please ensure the URL starts with '
                         'https://open.spotify.com/ or specify a result type.')

    def _parse_result(self, items: List[dict], track_list: List[Track], *,
                      _artist: Optional[Artist] = None, _album: Optional[Album] = None) -> None:
        """Parse the resulting JSON of a request for a playlist, track, album, or artist's
        tracks. Optionally receive an artist and an album for when these attributes are
        the same in all tracks."""

        if _artist is not None:
            artist = _artist
        if _album is not None:
            album = _album

        for item in items:
            try:
                track = item['track']
            except KeyError:
                track = item
            _id = track['id']
            name = track['name']
            if _artist is None:
                artist = Artist(
                    track['artists'][0]['id'], track['artists'][0]['name'], None,
                    client_id=self.client_id)
            if _album is None:
                # noinspection PyUnboundLocalVariable
                album = Album(
                    track['album']['id'], track['album']['name'], artist,
                    SpotifyAPI._get_image_url(track), client_id=self.client_id)

            # noinspection PyUnboundLocalVariable
            track_list.append(Track(
                _id, name, artist, album, client_id=self.client_id))

    def _get_playlist_slice(self, url: str) -> Tuple[List[Dict], _OptStr]:
        """Continue fetching the tracks of a playlist, in the case it has more than 100."""

        params = {'fields': 'next,items(track(id,name,artists(id,name),album(id,name,images)))'}
        headers = self._user_auth_headers() if self._prefer_user_token else self._auth_headers()
        r = requests.get(url, params=params, headers=headers)
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving a section of the playlist\'s tracks.')

        result = r.json()
        return result['items'], result['next']

    def get_playlist(self, url: Union[str, Playlist]) -> Playlist:
        """**Get the tracks and details of a public playlist.**

        This function only retrieves information of public playlists. For a private playlist of
        your account, use ``get_private_playlist()``.

        :param url: the URL or ID of the playlist
        :return: a ``Playlist``
        """

        params = {'fields': 'name,owner(id,display_name,images),images,tracks(next,items('
                            'track(id,name,artists(id,name),album(id,name,images))))'}
        playlist_id = utils.get_id(url)

        playlist: List[Track] = []

        headers = self._user_auth_headers() if self._prefer_user_token else self._auth_headers()
        r = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}',
                         params=params, headers=headers)
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving initial playlist tracks.')

        result = r.json()
        tracks = result['tracks']
        items = tracks['items']
        image_url = SpotifyAPI._get_image_url(result)

        owner = result['owner']
        owner = User(owner['id'], owner['display_name'], client_id=self.client_id)

        _next = tracks['next']
        self._parse_result(items, playlist)
        while _next is not None:
            items, _next = self._get_playlist_slice(_next)
            self._parse_result(items, playlist)

        return Playlist(
            playlist_id, result['name'], owner, image_url, playlist, client_id=self.client_id)

    @_requires_user_auth
    def get_private_playlist(self, url: Union[str, Playlist]) -> Playlist:
        """**Get the tracks and details of a public or private playlist.** Private playlists
        must belong to you, or have you as collaborator.

        :param url: the URL or ID of the album
        :return: a ``Result``
        """
        self._prefer_user_token = True
        resp = self.get_playlist(url)
        self._prefer_user_token = False
        return resp

    @functools.lru_cache(maxsize=10)
    def get_track(self, url: Union[str, Track]) -> Track:
        """**Get the details of a track.**

        :param url: the URL or ID of the track
        :return: a ``Track``
        """

        track_id = utils.get_id(url)

        r = requests.get(f'https://api.spotify.com/v1/tracks/{track_id}', headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving track details.')

        result = r.json()
        track: List[Track] = []
        self._parse_result([result], track)

        return track[0]

    @functools.lru_cache(maxsize=10)
    def get_artist(self, url: Union[str, Artist]) -> Artist:
        """**Get the top 10 tracks and details of an artist.**

        :param url: the URL or ID of the artist
        :return: an ``Artist``
        """

        artist_id = utils.get_id(url)

        r = requests.get(f'https://api.spotify.com/v1/artists/{artist_id}', headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving artist details.')

        result = r.json()
        name = result['name']
        image_url = SpotifyAPI._get_image_url(result)

        r = requests.get(f'https://api.spotify.com/v1/artists/{artist_id}/top-tracks',
                         params={'market': self.market}, headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving artist top tracks.')

        result = r.json()
        top_tracks: List[Track] = []

        resp = Artist(artist_id, name, image_url, top_tracks, client_id=self.client_id)

        # There are cases where it's not the same artist thoughout the artist's top tracks.
        # (in a feature, for example)
        same_artist = not any(track['artists'][0]['id'] != artist_id for track in result['tracks'])

        self._parse_result(result['tracks'], top_tracks, _artist=resp if same_artist else None)

        return resp

    def _get_album_slice(self, url: str) -> Tuple[List[Dict], _OptStr]:
        """Continue fetching the tracks of an album, in the (RARE) case it has more than 100."""

        r = requests.get(url, headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving a section of the album\'s tracks.')

        result = r.json()
        return result['items'], result['next']

    @functools.lru_cache(maxsize=10)
    def get_album(self, url: Union[str, Album]) -> Album:
        """**Get the tracks and details of an album.**

        :param url: the URL or ID of the album
        :return: an ``Album``
        """

        album_id = utils.get_id(url)

        album: List[Track] = []

        # Primera slice y request
        r = requests.get(f'https://api.spotify.com/v1/albums/{album_id}', headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving initial album tracks.')

        result = r.json()
        tracks = result['tracks']
        items = tracks['items']
        _next = tracks['next']
        name = result['name']
        artist_id = result['artists'][0]['id']

        artist = Artist(
            artist_id, result['artists'][0]['name'], client_id=self.client_id)
        resp = Album(
            album_id, name, artist, SpotifyAPI._get_image_url(result), album,
            client_id=self.client_id)

        same_artist = not any(track['artists'][0]['id'] != artist_id for track in items)

        # Each of the album's tracks will have the same album object, which is
        # also the return value of this function.
        self._parse_result(
            items, album, _artist=artist if same_artist else None, _album=resp)
        while _next is not None:
            items, _next = self._get_album_slice(_next)
            self._parse_result(
                items, album, _artist=artist if same_artist else None, _album=resp)

        return resp

    def get_album_from_track(self, url: Union[str, Track]) -> Album:
        """**Get the album of a track.**

        This functionality is automatic with ``Track`` objects, with the
        ``album`` property.

        :param url: the URL or ID of the track
        :return: an ``Album``
        """
        try:
            # noinspection PyProtectedMember
            album = url._album
            if album is not None:
                return album
        except AttributeError:
            pass

        track_id = utils.get_id(url)

        r = requests.get(f'https://api.spotify.com/v1/tracks/{track_id}', headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving track details.')

        result = r.json()
        album_id = result['album']['id']
        return self.get_album(album_id)

    def get_user(self, url: Union[str, User]) -> User:
        """**Get the details of a user.**

        :param url: the URL or ID of the user
        :return: a ``User``
        """
        user_id = utils.get_id(url)

        r = requests.get(f'https://api.spotify.com/v1/users/{user_id}', headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving user details.')

        response = r.json()
        return User(
            user_id, response['display_name'], SpotifyAPI._get_image_url(response),
            client_id=self.client_id)

    @_requires_user_auth
    def get_me(self) -> User:
        """**Get the details of the own user.**

        :return: a ``User``
        """
        r = requests.get(f'https://api.spotify.com/v1/me', headers=self._user_auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving user details.')

        response = r.json()
        return User(
            response['id'], response['display_name'], SpotifyAPI._get_image_url(response),
            client_id=self.client_id)

    def _search(self, query: str, result_types: Optional[List[ResultType]] = None,
                feeling_lucky: bool = False) -> Union[SearchResult, Optional[_AlmostAnything]]:
        """**Underlying function for search() and im_feeling_lucky().**

        I avoided merging those two methods in a single function to make a clearer
        difference between the return types and the necessity to pass an expected result
        type in ``im_feeling_lucky()``.
        """

        if not query:
            # No clue of what to search was given. This is your punishment.
            query = 'Never Gonna Give You Up'

        params: Dict[str, str] = {'q': urllib.parse.quote(query)}
        if result_types:
            if any(t in result_types for t in (
                    ResultType.USER, ResultType.SHOW, ResultType.EPISODE, ResultType.AUDIOBOOK)):
                raise NotImplementedError(
                    'Searching for users, shows, episodes, or audiobooks is not supported yet.')
        else:
            result_types = [ResultType.ALBUM, ResultType.ARTIST, ResultType.PLAYLIST, ResultType.TRACK]

        params['type'] = ','.join(map(str, result_types))
        full_url = utils.add_params_to_url('https://api.spotify.com/v1/search', params)

        r = requests.get(full_url, headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while performing search.')

        result: Dict[str, Any] = r.json()
        kwargs: Dict[str, Any] = {}

        def iterate_results(_type: ResultType) -> Iterator[dict]:
            _items = result[f'{_type}s']['items']
            if feeling_lucky:
                return iter(_items[:1])
            return iter(_items)

        if ResultType.TRACK in result_types:
            tracks = []
            for track in iterate_results(ResultType.TRACK):
                artist = Artist(
                    track['artists'][0]['id'], track['artists'][0]['name'],
                    client_id=self.client_id)
                tracks.append(Track(
                    track['id'], track['name'], artist,
                    Album(track['album']['id'], track['album']['name'], artist,
                          SpotifyAPI._get_image_url(track['album']), client_id=self.client_id),
                    client_id=self.client_id))
            kwargs['tracks'] = tracks

        if ResultType.ARTIST in result_types:
            artists = []
            for artist in iterate_results(ResultType.ARTIST):
                artists.append(Artist(
                    artist['id'], artist['name'], SpotifyAPI._get_image_url(artist),
                    client_id=self.client_id))
            kwargs['artists'] = artists

        if ResultType.PLAYLIST in result_types:
            playlists = []
            for playlist in iterate_results(ResultType.PLAYLIST):
                playlists.append(Playlist(
                    playlist['id'], playlist['name'],
                    User(playlist['owner']['id'], playlist['owner']['display_name'],
                         client_id=self.client_id),
                    SpotifyAPI._get_image_url(playlist), client_id=self.client_id))
            kwargs['playlists'] = playlists

        if ResultType.ALBUM in result_types:
            albums = []
            for album in iterate_results(ResultType.ALBUM):
                albums.append(Album(
                    album['id'], album['name'],
                    Artist(album['artists'][0]['id'], album['artists'][0]['name'],
                           client_id=self.client_id),
                    SpotifyAPI._get_image_url(album), client_id=self.client_id))
            kwargs['albums'] = albums

        if feeling_lucky:
            try:
                return kwargs[f'{result_types[0]}s'][0]
            except IndexError:
                return
        return SearchResult(query, **kwargs)

    def search(self, query: str, *, result_types: Optional[List[ResultType]] = None) -> SearchResult:
        """**Perform a search with a given query.** If you know exactly what you're
        searching for, consider using ``im_feeling_lucky()`` instead.

        You can use ``spotifyatlas.advanced_search()`` to generate a super specific
        query string, and pass it to the query parameter here. Keep in mind that some
        filters from ``advanced_search()`` may be shadowed if the user specifies
        ``result_types`` here.

        :param query: the search query string
        :param result_types: list of expected result types to optionally limit search
        :return: a ``SearchResult``

        >>> result = spoti.search('susanne sundfor')
        >>> top_artist_result = result.artists[0]
        >>> top_artist_result.name
        'Susanne Sundfør'
        >>> top_artist_result.top_tracks
        [<Track name='Stay Awhile' artist='Röyksopp' id='4wCZOU5q8Xlir3MBux8WzO'>, ... ]
        """
        return self._search(query, result_types)

    def im_feeling_lucky(self, query: str, result_type: ResultType) -> Optional[_AlmostAnything]:
        """**Perform a search and get the top result of the specified type.**
        I don't know if Google still has this feature, but it's a cool name
        nonetheless.

        :param query: the search query string
        :param result_type: the expected result type (this isn't automatic)
        :return: Optionally, a ``Playlist``, ``Album``, ``Artist``, or ``Track``
        object.

        >>> result = spoti.im_feeling_lucky('song machine', spotifyatlas.ResultType.ALBUM)
        >>> result.artist
        <Artist name='Gorillaz' id='3AA28KZvwAUcZuOKwyblJQ'>
        >>> result.tracks
        [<Track name='Strange Timez (feat. Robert Smith)' artist='Gorillaz' ... , ... ]
        """
        return self._search(query, [result_type], True)

    @_requires_user_auth
    def add_to_playlist(self, url: Union[str, Playlist], tracks: List[Track], position: int = 0) -> None:
        """**Add a list of tracks to a playlist.**

        The playlist must belong to you, or be collaborative. You can also add tracks
        from a playlist object with ``playlist.add()``.

        :param url: the URL or ID of the playlist.
        :param tracks: a list of ``Track``, containing the tracks to add
        :param position: the index (starting at 0) where the tracks will be inserted
        :return: ``None``
        """
        playlist_id = utils.get_id(url)

        uris: List[str] = []
        last_pos = position

        def add_slice() -> None:
            headers = self._user_auth_headers(content_type='application/json')
            data = json.dumps({'uris': uris, 'position': last_pos})
            uris.clear()

            r = requests.post(
                f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers, data=data)
            if r.status_code >= 400:
                raise SpotifyAPIException(r, 'Error ocurred while adding a batch of tracks to the playlist.')

        for i, track in enumerate(tracks, 1):
            uris.append(track.uri)
            if i % 100 == 0:
                add_slice()
                uris.clear()
                last_pos = i

        if len(uris) != 0:
            add_slice()

    @_requires_user_auth
    def clear_playlist(self, url: Union[str, Playlist], *, make_copy: bool = False) -> Playlist:
        """**Remove ALL the songs in a playlist.**

        The playlist must belong to you, or be collaborative.

        If you use this method to automatically rearrange or update the tracks in a playlist,
        I **strongly** recommend that you make a copy of the playlist before anything, by setting
        ``make_copy`` to ``True``. Although unlikely, it is possible that the API request succeeds
        when clearing the playlist, and then fails while putting the tracks back. You can also
        clear from a playlist object with ``playlist.clear()``.

        :param url: the URL or ID of the playlist
        :param make_copy: whether to back up the playlist before clearing it
        :return: the ``Playlist`` as it was before being modified
        """
        if make_copy:
            self.duplicate_playlist(url)

        playlist_id = utils.get_id(url)

        resp = self.get_private_playlist(url)
        tracks = resp.tracks
        uris: List[Dict[str, str]] = []

        def clear_slice() -> None:
            headers = self._user_auth_headers(content_type='application/json')
            data = json.dumps({'tracks': uris})
            r = requests.delete(
                f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers, data=data)
            if r.status_code >= 400:
                raise SpotifyAPIException(r, 'Error ocurred while removing a batch of tracks from the playlist.')

        for i, track in enumerate(tracks, 1):
            uris.append({'uri': track.uri})
            if i % 100 == 0:
                clear_slice()
                uris.clear()

        if len(uris) != 0:
            clear_slice()

        return resp

    @_requires_user_auth
    def rearrange_playlist(self, url: Union[str, Playlist], range_start: int, range_length: int,
                           insert_before: int) -> None:
        """**Change the position of a track, or range of tracks in a playlist.**

        The playlist must belong to you, or be collaborative. All indexes start at zero.

        :param url: the URL or ID of the playlist
        :param range_start: the index of the first track of your selection
        :param range_length: the size of the selection
        :param insert_before: insert the selection before the track at this index
        :return: ``None``
        """
        playlist_id = utils.get_id(url)

        headers = self._user_auth_headers(content_type='application/json')
        data = json.dumps({
            'range_start': range_start,
            'insert_before': insert_before,
            'range_length': range_length
        })

        r = requests.put(
            f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', data=data, headers=headers)
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while changing the order of the tracks.')

    @_requires_user_auth
    def create_playlist(self, name: str, *, description: _OptStr = None, public: bool = True,
                        collaborative: bool = False) -> Playlist:
        """**Create a new playlist for the user.**

        :param name: the name of the new playlist
        :param description: optionally, a description
        :param public: whether to make the playlist visible to any user
        :param collaborative: whether to make the playlist collaborative (this sets ``pubilc`` to ``False``)
        :return: the new ``Playlist`` object
        """

        user_id = self.get_me().id
        data = {
            'name': name,
            'public': public,
            'collaborative': collaborative
        }
        if collaborative:
            data['public'] = False
        if description:
            data['description'] = description

        r = requests.post(
            f'https://api.spotify.com/v1/users/{user_id}/playlists', data=json.dumps(data),
            headers=self._user_auth_headers(content_type='application/json'))
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while creating playlist.')

        result = r.json()
        owner = result['owner']
        owner = User(owner['id'], owner['display_name'], client_id=self.client_id)

        return Playlist(result['id'], result['name'], owner, client_id=self.client_id)

    @_requires_user_auth
    def duplicate_playlist(self, url: Union[str, Playlist]) -> Playlist:
        """**Create a new playlist with the same tracks as the received playlist URL.**

        :param url: the playlist to copy
        :return: the new ``Playlist`` object
        """
        playlist = self.get_private_playlist(url)
        new_playlist = self.create_playlist(playlist.name + ' copy', public=False)
        self.add_to_playlist(new_playlist.id, playlist.tracks)
        return new_playlist

    def get_genres(self) -> List[str]:
        """**Gets all available genre seeds.**"""
        r = requests.get(
            'https://api.spotify.com/v1/recommendations/available-genre-seeds',
            headers=self._auth_headers(content_type='application/json'))
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while fetching genre seeds.')

        return r.json()['genres']

    def _auth_headers(self, content_type: _OptStr = None) -> Dict[str, str]:
        """Returns the authorization headers for many requests to the API.
        If necessary, token is updated.
        """
        if datetime.datetime.now() > self._expires:
            self.update_token()
        headers = {'Authorization': f'Bearer {self._token}'}
        if content_type is not None:
            headers['Content-Type'] = content_type
        return headers

    def _user_auth_headers(self, content_type: _OptStr = None) -> Dict[str, str]:
        """Returns the authorization headers for to the API that need user
        permissions. If necessary, token is updated.
        """
        if datetime.datetime.now() > self._user_expires:
            self.update_user_token()
        headers = {'Authorization': f'Bearer {self._user_token}'}
        if content_type is not None:
            headers['Content-Type'] = content_type
        return headers

    def update_token(self) -> None:
        """Update the Bearer token by sending a grant request with the client credentials."""

        headers = {'Authorization': f'Basic {self._client_creds_b64}'}
        data = {'grant_type': 'client_credentials'}

        r = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=data)
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while updating the app\'s Bearer token.')

        response = r.json()
        self._token = response['access_token']

        now = datetime.datetime.now()
        self._expires = now + datetime.timedelta(seconds=response['expires_in'])

    def update_user_token(self) -> None:
        """Update the user Bearer token by sending a grant request."""

        if self._user_refresh_token:
            self._refresh_user_token()
        else:
            self._request_user_token()

    def _request_user_token(self) -> None:
        """Request the user Bearer token with the authorization code provided by the user
        authorization page.
        """

        params = {
            'grant_type': 'authorization_code',
            'code': self._user_access_code,
            'redirect_uri': 'http://localhost:8000'
        }

        full_url = utils.add_params_to_url('https://accounts.spotify.com/api/token', params)
        headers = {'Authorization': f'Basic {self._client_creds_b64}',
                   'Content-Type': 'application/x-www-form-urlencoded'}

        r = requests.post(full_url, headers=headers)
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while requesting Bearer token after user login.')

        response = r.json()
        self._user_token = response['access_token']
        self._user_refresh_token = response['refresh_token']

        now = datetime.datetime.now()
        self._user_expires = now + datetime.timedelta(seconds=response['expires_in'])

    def _refresh_user_token(self) -> None:
        """Update the user Bearer token by using the previous refresh token."""

        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self._user_refresh_token,
        }

        full_url = utils.add_params_to_url('https://accounts.spotify.com/api/token', params)
        headers = {'Authorization': f'Basic {self._client_creds_b64}'}

        r = requests.post(full_url, headers=headers)
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while refreshing the user\'s Bearer token.')

        response = r.json()
        self._user_token = response['access_token']

        now = datetime.datetime.now()
        self._user_expires = now + datetime.timedelta(seconds=response['expires_in'])

    def _prompt_user_auth(self) -> None:
        """Open the Spotify authorization page in the default browser. The user is then
        redirected to a local web page, which is, by default, http://localhost:8000.
        Clicking 'accept', will generate an access code for the application to request
        a user token and use the API on behalf of the user.
        """

        state = str(random.random())
        full_url = utils.add_params_to_url('https://accounts.spotify.com/authorize', {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': 'http://localhost:8000',
            'state': state,
            'scope': 'playlist-modify-private playlist-modify-public'
        })
        params = {}

        # noinspection PyPep8Naming
        class RedirectPage(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                nonlocal params
                params = utils.parse_url_params(self.path)
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(bytes(_redirect_page, 'utf-8'))

            def log_message(self, *args: Any) -> None:
                return

        server = HTTPServer(("127.0.0.1", 8000), RedirectPage)
        webbrowser.open_new_tab(full_url)
        server.handle_request()
        server.server_close()

        if state != params['state']:
            raise SpotifyUserAuthException(
                'The security "state" number that was generated randomly did not match '
                'with the received parameter after redirecting to local page. Please try '
                'authorizing Spotify again.')

        try:
            self._user_access_code = params['code']
        except KeyError:
            error = params['error']
            if error == 'access_denied':
                raise SpotifyUserAuthException(
                    'The user denied authorizing the application. User authorization '
                    'is needed for some API actions, like modifying playlists.')
            else:
                raise SpotifyAPIException(
                    message='Unknown error occured while asking the user for authorization.')

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other: SpotifyAPI) -> bool:
        return self.client_id == other.client_id

    def __repr__(self) -> str:
        return f'<SpotifyAPI client_id={repr(self.client_id)}>'

    def __hash__(self) -> int:
        return hash(self._client_creds_b64)
