from __future__ import annotations

from typing import Any, Optional, Union, Tuple, List, Dict, Callable
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
# noinspection PyProtectedMember
from .datastructs import \
    SpotifyAPIException, SpotifyUserAuthException, Track, Result, TrackResult


__all__ = ['SpotifyAPI']


_redirect_page = resources.read_text("spotifyatlas.resources", "redirectpage.html")
_AnyTrack = Union[Track, TrackResult]


class SpotifyAPI:
    """**The meat-and-potatoes of this package.**

    It is required that you create an app in Spotify for Developers (it's free!) to use this
    wrapper class.

    The point of collecting all the primary functions in a single class is in order to share many
    important attributes (mostly credentials, tokens and such). There are some methods that require
    an extra permission grant from the user, i.e., whenever the program will do modifications in
    behalf of. Using these methods will result in the Spotify app authorization page being open in
    the browser.

    It is mandatory to use the Spotify API with the credentials of your application:

        >>> spoti = SpotifyAPI('your-app-client-id', 'your-app-client-secret')
        >>> result = spoti.get('https://open.spotify.com/playlist/3wrUHfvsdnjiZ0kFJLvFOK')
        >>> result.tracks
        [Track('Run', 'Collective Soul', '3HxX5qcaz2phmsJVPskugD'), ... ]
    """

    @staticmethod
    def _parse_result(result: List[dict], track_list: List[Track]) -> None:
        """Parse the resulting JSON of a request for a playlist, track, album, or artist's top tracks."""
        for item in result:
            try:
                track = item['track']
            except KeyError:
                track = item
            name = track['name']
            artist = track['artists'][0]['name']
            _id = track['id']
            track_list.append(Track(name, artist, _id))

    @staticmethod
    def _get_image_from_result(result: dict) -> Optional[str]:
        """Return an optional image URL, with the JSON result of a request."""
        try:
            images = result['images']
        except KeyError:
            images = result['album']['images']
        try:
            return images[0]['url']
        except IndexError:
            return

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

    def __init__(self, client_id: str, client_secret: str) -> None:
        """**Initialize the SpotifyAPI class.**

        :param client_id: the client ID of your application
        :param client_secret: the client secret of your application
        """

        if not client_id or not client_secret:
            raise ValueError(
                'Client credentials (a client ID and a client secret) are needed to access the Spotify API. '
                'Visit https://developer.spotify.com/documentation/general/guides/authorization/app-settings/ '
                'for information on how to create an app in Spotify for developers.')

        self.client_id = client_id
        self.client_secret = client_secret

        client_creds = f'{self.client_id}:{self.client_secret}'
        self._client_creds_b64: str = base64.b64encode(client_creds.encode()).decode()

        self._token = ''
        self._user_token = ''
        self._user_refresh_token = ''
        self._user_access_code = ''
        self._expires = datetime.datetime.now()
        self._user_expires = datetime.datetime.now()
        self._prefer_user_token = False

    def get(self, url: str) -> Result:
        """**Universal method to retreive the tracks and details of something in Spotify.**

        :param url: the URL of the playlist, track, album, or artist
        :return: a ``Result``
        """

        if not url.startswith('https://open.spotify.com/'):
            raise ValueError('Spotify URL not valid. Please ensure the '
                             'URL starts with https://open.spotify.com/.')
        kind = url.split('/')[3]
        if kind == 'playlist':
            return self.get_playlist(url)
        if kind == 'track':
            return self.get_track(url)
        if kind == 'artist':
            return self.get_artist(url)
        if kind == 'album':
            return self.get_album(url)

    def _get_playlist_slice(self, url: str) -> Tuple[List[Dict], Optional[str]]:
        """Continue fetching the tracks of a playlist, in the case it has more than 100."""

        params = {'fields': 'next,items(track(name,id,artists.name))'}
        headers = self._user_auth_headers() if self._prefer_user_token else self._auth_headers()
        r = requests.get(url, params=params, headers=headers)
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving a section of the playlist\'s tracks.')

        result = r.json()
        return result['items'], result['next']

    def get_playlist(self, url: str) -> Result:
        """**Get the tracks and details of a playlist.**

        This function only retrieves information of public playlists. For a private playlist of
        your account, use ``get_private_playlist()``.

        :param url: the URL or ID of the playlist
        :return: a ``Result``
        """

        params = {'fields': 'name,owner.display_name,images.url,tracks(next,items(track(name,id,artists.name)))'}
        playlist_id = utils.id_from_url(url)

        playlist: List[Track] = []

        headers = self._user_auth_headers() if self._prefer_user_token else self._auth_headers()
        r = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}',
                         params=params, headers=headers)
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving initial playlist tracks.')

        result = r.json()
        tracks = result['tracks']
        items = tracks['items']
        _next = tracks['next']
        SpotifyAPI._parse_result(items, playlist)

        while _next is not None:
            items, _next = self._get_playlist_slice(_next)
            SpotifyAPI._parse_result(items, playlist)

        return Result(
            playlist, result['name'], result['owner']['display_name'], playlist_id,
            SpotifyAPI._get_image_from_result(result))

    def get_track(self, url: str) -> TrackResult:
        """**Get the details of a track.**

        :param url: the URL or ID of the track
        :return: a ``Result``
        """

        track_id = utils.id_from_url(url)

        r = requests.get(f'https://api.spotify.com/v1/tracks/{track_id}', headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving track details.')

        result = r.json()
        name = result['name']
        artist = result['artists'][0]['name']
        image_url = SpotifyAPI._get_image_from_result(result)

        return TrackResult(
            [Track(name, artist, track_id)], name, artist, track_id, image_url)

    def get_artist(self, url: str) -> Result:
        """**Get the top 10 tracks and details of an artist.**

        :param url: the URL or ID of the artist
        :return: a ``Result``
        """

        artist_id = utils.id_from_url(url)

        r = requests.get(f'https://api.spotify.com/v1/artists/{artist_id}', headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving artist details.')

        result = r.json()
        name = result['name']
        image_url = SpotifyAPI._get_image_from_result(result)

        r = requests.get(f'https://api.spotify.com/v1/artists/{artist_id}/top-tracks',
                         params={'market': 'US'}, headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving artist top tracks.')

        result = r.json()
        top_tracks: List[Track] = []
        SpotifyAPI._parse_result(result['tracks'], top_tracks)

        return Result(top_tracks, name, name, artist_id, image_url)

    def _get_album_slice(self, url: str) -> Tuple[List[Dict], Optional[str]]:
        """Continue fetching the tracks of an album, in the (RARE) case it has more than 100."""

        r = requests.get(url, headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving a section of the album\'s tracks.')

        result = r.json()
        return result['items'], result['next']

    def get_album(self, url: str) -> Result:
        """**Get the tracks and details of an album.**

        :param url: the URL or ID of the album
        :return: a ``Result``
        """

        album_id = utils.id_from_url(url)

        album: List[Track] = []

        # Primera slice y request
        r = requests.get(f'https://api.spotify.com/v1/albums/{album_id}', headers=self._auth_headers())
        if r.status_code >= 400:
            raise SpotifyAPIException(r, 'Error ocurred while retrieving initial album tracks.')

        result = r.json()
        tracks = result['tracks']
        items = tracks['items']
        _next = tracks['next']
        SpotifyAPI._parse_result(items, album)

        # Otras slices
        while _next is not None:
            items, _next = self._get_album_slice(_next)
            SpotifyAPI._parse_result(items, album)

        return Result(
            album, result['name'], result['artists'][0]['name'], album_id,
            SpotifyAPI._get_image_from_result(result))

    @_requires_user_auth
    def get_private_playlist(self, url: str) -> Result:
        """**Get the tracks and details of a private playlist that belongs to you.**

        :param url: the URL or ID of the album
        :return: a ``Result``
        """
        self._prefer_user_token = True
        result = self.get_playlist(url)
        self._prefer_user_token = False
        return result

    @_requires_user_auth
    def add_to_playlist(self, url: str, tracks: List[_AnyTrack], position: int = 0) -> None:
        """**Add a list of tracks to a playlist.**

        The playlist must belong to you, or be collaborative.

        :param url: the URL or ID of the playlist.
        :param tracks: a list of Track, containing the tracks to add
        :param position: the index (starting at 0) where the tracks will be inserted
        :return: ``None``
        """
        playlist_id = utils.id_from_url(url)

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
    def clear_playlist(self, url: str) -> Result:
        """**Remove ALL the songs in a playlist.**

        The playlist must belong to you, or be collaborative.

        If you use this method to automatically rearrange or update the tracks in a playlist,
        I **strongly** recommend that you make a copy of the playlist before anything. Although
        unlikely, it is possible that the API request succeeds when clearing the playlist, and
        then fails while putting the tracks back.

        :param url: the URL or ID of the playlist
        :return: ``None``
        """
        playlist_id = utils.id_from_url(url)

        result = self.get_private_playlist(url)
        tracks = result.tracks
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

        return result

    @_requires_user_auth
    def rearrange_playlist(self, url: str, range_start: int, range_length: int, insert_before: int) -> None:
        """**Change the position of a track, or range of tracks in a playlist.**

        The playlist must belong to you, or be collaborative. All indexes start at zero.

        :param url: the URL or ID of the playlist
        :param range_start: the index of the first track of your selection
        :param range_length: the size of the selection
        :param insert_before: insert the selection before the track at this index
        :return: ``None``
        """
        playlist_id = utils.id_from_url(url)

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

    def _auth_headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        """Returns the authorization headers for many requests to the API.
        If necessary, token is updated.
        """
        if datetime.datetime.now() > self._expires:
            self.update_token()
        headers = {'Authorization': f'Bearer {self._token}'}
        if content_type is not None:
            headers['Content-Type'] = content_type
        return headers

    def _user_auth_headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
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
