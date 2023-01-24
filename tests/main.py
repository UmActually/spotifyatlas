import os
from spotifyatlas import SpotifyAPI

spoti = SpotifyAPI(
    os.environ.get('CLIENT_ID'),
    os.environ.get('CLIENT_SECRET'))
