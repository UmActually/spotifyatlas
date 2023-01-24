import os
import unittest
from spotifyatlas import SpotifyAPI, SpotifyAPIException, ResultType, \
    Playlist, Track, Artist, Album, User
from spotifyatlas.baseapi import BaseSpotifyAPI


TEST_PLAYLIST = 'https://open.spotify.com/playlist/33gG2ngzEwFHUkD77WBb57'
TEST_PLAYLIST_NOT_OWNED = 'https://open.spotify.com/playlist/3apif2tZ5ChpAQnC7ISyAF'
TEST_TRACK = 'https://open.spotify.com/track/5fwSHlTEWpluwOM0Sxnh5k'
TEST_ARTIST = 'https://open.spotify.com/artist/25uiPmTg16RbhZWAqwLBy5'
TEST_ALBUM = 'https://open.spotify.com/album/2I0LPpmyvAwnXvCuBf3Pcy'
TEST_USER = 'https://open.spotify.com/user/leocoronag'

CLIENT_ID = os.environ.get('CLIENT_ID', None)
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', None)


class TestSpotifyAPI(unittest.TestCase):
    spoti = None
    playlist = None
    og_tracks = None

    @classmethod
    def setUpClass(cls) -> None:
        assert CLIENT_ID is not None
        assert CLIENT_SECRET is not None
        cls.spoti = SpotifyAPI(CLIENT_ID, CLIENT_SECRET)

        # In order to do the auth flow, de una vez
        cls.spoti.get_me()

        cls.playlist = cls.spoti.get(TEST_PLAYLIST)
        cls.track = cls.spoti.get(TEST_TRACK)
        cls.artist = cls.spoti.get(TEST_ARTIST)
        cls.album = cls.spoti.get(TEST_ALBUM)
        cls.user = cls.spoti.get(TEST_USER)

        cls.og_tracks = cls.playlist.tracks.copy()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.playlist.clear()
        cls.playlist.update_tracks()
        cls.playlist.add(cls.og_tracks)

    def test_object_identity(self) -> None:
        spoti = SpotifyAPI(CLIENT_ID, CLIENT_SECRET)
        base = BaseSpotifyAPI(CLIENT_ID, CLIENT_SECRET)
        self.assertIs(self.spoti, spoti)
        self.assertIs(self.spoti, base)

    def test_get(self) -> None:
        result = self.spoti.get(TEST_PLAYLIST)
        self.assertIsInstance(result, Playlist)
        result = self.spoti.get(result)
        self.assertIsInstance(result, Playlist)

        with self.assertRaises(ValueError):
            self.spoti.get('https://open.spotify.com/badurl/fakeid')
        with self.assertRaises(ValueError):
            self.spoti.get('fakeid')
        with self.assertRaises(ValueError):
            self.spoti.get('non_alnum_fake_id', result_type=ResultType.PLAYLIST)

        # todo: I am not entirely sure if all IDs have the same length,
        # but it is possible to validate length in utils.get_id().
        # Cases like the following would not make it into the request
        # and throw a value error.
        with self.assertRaises(SpotifyAPIException):
            self.spoti.get('fakeid', result_type=ResultType.PLAYLIST)

    def test_get_playlist(self) -> None:
        self.assertIsInstance(self.playlist, Playlist)
        self.assertEqual(self.playlist, self.spoti.get_playlist(TEST_PLAYLIST))
        self.assertEqual(self.playlist, self.spoti.get_private_playlist(TEST_PLAYLIST))
        self.assertEqual(self.playlist.url, TEST_PLAYLIST)

        self.assertEqual(self.playlist.name, 'spotifyatlas testing')
        self.assertEqual(len(self.playlist), 101)

    def test_get_track(self) -> None:
        self.assertIsInstance(self.track, Track)
        self.assertEqual(self.track, self.spoti.get_track(TEST_TRACK))
        self.assertEqual(self.track.url, TEST_TRACK)

        # Pepas - Farruko
        self.assertEqual(self.track.name, 'Pepas')

    def test_get_artist(self) -> None:
        self.assertIsInstance(self.artist, Artist)
        self.assertEqual(self.artist, self.spoti.get_artist(TEST_ARTIST))
        self.assertEqual(self.artist.url, TEST_ARTIST)

        # Charli XCX
        self.assertEqual(self.artist.name, 'Charli XCX')
        self.assertEqual(len(self.artist), 10)

    def test_get_album(self) -> None:
        self.assertIsInstance(self.album, Album)
        self.assertEqual(self.album, self.spoti.get_album(TEST_ALBUM))
        self.assertEqual(self.album.url, TEST_ALBUM)

        # Butterfly 3000 - King Gizzard & The Lizard Wizard
        self.assertEqual(self.album.name, 'Butterfly 3000')
        self.assertEqual(len(self.album), 10)

    def test_get_user(self) -> None:
        self.assertIsInstance(self.user, User)
        self.assertEqual(self.user, self.spoti.get_user(TEST_USER))
        self.assertEqual(self.user.url, TEST_USER)

        # Yo merengues
        self.assertEqual(self.user.name, 'Leo Corona')

    def test_type_mixup(self) -> None:
        with self.assertRaises(SpotifyAPIException):
            self.spoti.get_album(TEST_ARTIST)

    def test_search(self) -> None:
        result = self.spoti.search('hello')
        # There's no chance in hell that this query gives me less than 20 per type
        self.assertEqual(len(result), 80)
        self.assertIsInstance(result.playlists[0], Playlist)
        self.assertIsInstance(result.tracks[0], Track)
        self.assertIsInstance(result.artists[0], Artist)
        self.assertIsInstance(result.albums[0], Album)

        with self.assertRaises(NotImplementedError):
            self.spoti.search('world', result_types=[ResultType.USER])

    def test_im_feeling_lucky(self) -> None:
        for result_type in (ResultType.PLAYLIST, ResultType.TRACK, ResultType.ARTIST, ResultType.ALBUM):
            result = self.spoti.im_feeling_lucky('!', result_type)
            try:
                self.assertEqual(result.type, result_type)
            except AttributeError:
                self.assertIsInstance(result, Track)

    def test_modify_playlist(self) -> None:
        with self.assertRaises(SpotifyAPIException):
            self.spoti.clear_playlist(TEST_PLAYLIST_NOT_OWNED)

        playlist = self.playlist
        tracks = playlist.tracks.copy()

        self.spoti.clear_playlist(playlist)

        playlist.update_tracks()
        self.assertEqual(len(playlist), 0)

        self.spoti.add_to_playlist(playlist, [tracks[32]])
        playlist.update_tracks()
        self.assertEqual(len(playlist), 1)
        self.assertEqual(playlist[0].artist.name, 'Lorde')

        tracks.sort(key=lambda t: t.artist.name.lower())
        playlist.extend(tracks)
        self.assertGreater(len(playlist), 100)
