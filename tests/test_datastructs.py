import os
import unittest
from spotifyatlas import SpotifyAPI


TEST_PLAYLIST = 'https://open.spotify.com/playlist/64RWbvkb4Q00ZROlpd6ItU'
TEST_TRACK = 'https://open.spotify.com/track/5fwSHlTEWpluwOM0Sxnh5k'
TEST_ARTIST = 'https://open.spotify.com/artist/25uiPmTg16RbhZWAqwLBy5'
TEST_ALBUM = 'https://open.spotify.com/album/2I0LPpmyvAwnXvCuBf3Pcy'
TEST_ALBUM_COLLAB = 'https://open.spotify.com/album/7N32mF0BlA3BOhlSyCiHgf'
TEST_USER = 'https://open.spotify.com/user/leocoronag'

CLIENT_ID = os.environ.get('CLIENT_ID', None)
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', None)


class TestDataStructs(unittest.TestCase):
    spoti = None
    playlist = None

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

    def test_property_equivalence(self) -> None:
        # The memories of trees in algoritmos class start rushing back
        self.assertEqual(self.track.artist, self.track.album.artist)
        self.assertEqual(self.track.artist, self.track.album[0].artist)
        self.assertEqual(self.track.artist, self.track.artist[0].artist)
        self.assertEqual(self.album, self.album[0].album)
        self.assertEqual(self.album, self.spoti.get_album_from_track(self.album[0]))
        self.assertEqual(self.album.artist, self.album[0].artist)
        self.assertEqual(self.album.artist, self.album[0].album.artist)
        self.assertEqual(self.playlist.owner, self.user)
        self.assertEqual(self.playlist.owner.image_url, self.user.image_url)

    def test_property_identity(self) -> None:
        self.assertIs(self.track.artist, self.track.album.artist)
        self.assertIs(self.track.artist._client_id, self.track._client_id)

        artist = self.album.artist
        # This is not always true though, some albums have different artists in their tracks
        self.assertTrue(all(track.artist is artist for track in self.album))

        # The same here
        if all(track.artist == self.artist for track in self.artist):
            self.assertTrue(all(track.artist is self.artist for track in self.artist))

        # Now, testing album with different artists in its tracks
        # Metallica blacklist
        album = self.spoti.get_album(TEST_ALBUM_COLLAB)
        self.assertFalse(all(track.artist is artist for track in album))
