# spotifyatlas

### A pythonic wrapper for the Spotify web API.

By Leonardo - UmActually

`spotifyatlas` is a straightforward library meant to simplify the process of interacting with **Spotify's web API**. Whether you are trying to programmatically access Spotify features like **search queries**, or automate user tasks like **modifying your playlists**, spotifyatlas has tools for the job. All in a clean, object-oriented style.

Most of the package's functionality is included in the ``SpotifyAPI`` class, which only needs to be initialized with the **credentials** of your client application. This codebase was originally used to retrieve track details for **[Discord bots](https://github.com/UmActually/Papanatas)**, so most of the functions, as of now, revolve around playlists, albums, top tracks of artists, and whatnot.

## Basic Usage

_Refer to the [Installation](#installation) section for information on how to install the package with `pip`._

The first step to interact with the Spotify API is to register a new **application** in the **[Spotify for Developers](https://developer.spotify.com/dashboard/)** page. Worry not: this process is completely free for any Spotify user (with an account).

### Quick Start

With that out of the way, go ahead and initialize a new `SpotifyAPI` object with the credentials of your app (client ID and client secret):

```python
from spotifyatlas import SpotifyAPI
spoti = SpotifyAPI('<my-client-id>', '<my-client-secret>')
```

If you wish to retrieve the **tracks and/or details** of anything in Spotify, the universal `get()` method many times will get you covered.

Try it by pasting the share link of your favorite playlist. It will return a `Playlist` object. the playlist tracks are located in the `tracks` attribute, and you can also access tracks **by index**, as shown below.

```python
from spotifyatlas import SpotifyAPI
spoti = SpotifyAPI('<my-client-id>', '<my-client-secret>')
playlist = spoti.get('https://open.spotify.com/playlist/6xTnvRqIKptVfgcT8gN4Bb')

print(playlist.tracks)
# [<Track name='Goliath' artist='The Mars Volta' id='3bi3Ycf0ZlRHvSg0IxlMwM'>, ... ]

first_track = playlist[0]  # the same as playlist.tracks[0]  
print(first_track)
# Goliath - The Mars Volta
```

A `Track` contains the `name`, `artist`, `album` and `id` of a song. And, as you saw above, `print(track)` will format a track as `'<name> - <artist>'`. You can neatly list the contents of your playlist like this:

```python
for i, track in enumerate(playlist, 1):
    print(i, '-', track)
# 1 - Goliath - The Mars Volta
# 2 - Juicy - 2005 Remaster - The Notorious B.I.G.
# 3 - O Peso da Cruz - Supercombo
# 4 - Count The People (feat. Jessie Reyez & T-Pain) - Jacob Collier
# 5 - Touch - Shura
# ...
```

Similar to `Playlist` and `Track`, you can also find `Album`, `Artist` and `User` structures. *Every one of these is connected to each other* by **attributes**. For example, `track.artist.image_url` will return the image url of the artist of a track, and so will `track.album.tracks[0].artist.image_url`. I confidently assume you won't do it the second way. The increased amount of API requests will take its toll on performance.

### Getting

The following methods offer the same functionality as `get()`, although with a *specific return value*:

- `get_playlist()` for public playlists.

- `get_track()` for tracks.

- `get_artist()` for artists and their top 10 tracks.

- `get_album()` for albums.

- `get_user()` for users.

They all require the `url` or the ID of the element as the first argument.

### Searching

Not everything demands you having the link of the item at hand. To perform **searches**, you can use the following methods:

- `search()` to search normally, with the option to specify result types.

```python
result = spoti.search('susanne sundfor')
top_artist_result = result.artists[0]
print(top_artist_result.name)
# Susanne Sundfør

result = spoti.search('ok human')
top_album_result = result.albums[0]
print(top_album_result.tracks)
# [<Track name='All My Favorite Songs' artist='Weezer' id='6zVhXpiYbJhLJWmLGV9k1r'>, ... ]
```

- `im_feeling_lucky()` if you know in advance exactly what you are looking for. It is essentially the same as `search()` but returns directly the top result of the specified type.

```python
from spotifyatlas import ResultType
result = spoti.im_feeling_lucky('quevedo biza', ResultType.TRACK)
print(result)
# Quevedo: Bzrp Music Sessions, Vol. 52 - Bizarrap
```

- The standalone function `spotifyatlas.advanced_search()` can generate a more [powerful search query](https://support.spotify.com/us/article/search/) that the user can then pass to either of the search methods (or even paste to their actual Spotify client).

```python
from spotifyatlas import ResultType, Genre, advanced_search

overkill_query = advanced_search(
    'juanes',
    album='metallica',
    year=2021,
    genre=Genre.ROCK
)

result = spoti.im_feeling_lucky(overkill_query, ResultType.TRACK)
print(result)
# Enter Sandman - Juanes
```

### User Functionality

These other methods require **user consent**, and thus will result in the **browser** opening for the authorization of your application to act on behalf of the user:

- `get_me()` for details of your own profile.

- `get_private_playlist()` for private playlists you own.

- `create_playlist()` to make a new empty playlist in your library.

- `add_to_playlist()` to add a batch of `Track`s to a playlist.

- `duplicate_playlist()` to duplicate a playlist in your library.

- `clear_playlist()` to remove all the contents of a playlist.

- `rearrange_playlist()` to change the position of a range of tracks.

The last five functions are also available as **methods** of the `Playlist` class. This enables some handy shortcuts like the ones seen in [More Examples](#more-examples).

> Note: authorizing the application in the Spotify authorization page requires a **redirection** page to go to. This library will temporarily **host a local page** on http://localhost:8000 whenever needed. Thus, you **will need to add this URL** to the allowed redirection URLs on the dashboard of your application in the **[Spotify for Developers](https://developer.spotify.com/dashboard/)** site.

The complete list of parameters/arguments of a function can be found in its documentation.

---

## Installation

To install spotifyatlas, use **pip** in the terminal:

**Windows**
```commandline
pip install spotifyatlas
```

**macOS / Linux**
```commandline
python3 -m pip install spotifyatlas
```

---

## More Examples

For the inquisitive user, here are some more code examples out the top of my head:

### 1. Rearrange the tracks of a playlist by artist, alphabetically

```python
from spotifyatlas import SpotifyAPI


def artist_sort_key(track):  
    return track.artist.name.lower()  
    # If you want to hierarchically sort by artist, AND album,  
    # AND track, use this:
    # return (
    #     track.artist.name.lower(),
    #     track.album.name.lower(),
    #     track.name.lower())


MY_PLAYLIST = '<my-playlist-link>'
spoti = SpotifyAPI('<my-client-id>', '<my-client-secret>')

playlist = spoti.get_playlist(MY_PLAYLIST)  
tracks = playlist.tracks  
tracks.sort(key=artist_sort_key)  
  
# make_copy makes a backup of the playlist in your library  
# before removing its contents.  
playlist.clear(make_copy=True)  
playlist.add(tracks)
```

### 2. Find the songs that two playlists have in common, and create a playlist with them

```python
from spotifyatlas import SpotifyAPI

MY_PLAYLIST = '<my-playlist-link>'
MY_FRIENDS_PLAYLIST = '<my-friends-playlist-link>'

spoti = SpotifyAPI('<my-client-id>', '<my-client-secret>')

playlist1 = spoti.get(MY_PLAYLIST)
playlist2 = spoti.get(MY_FRIENDS_PLAYLIST)

# Set theory!!!  
common_tracks = set(playlist1).intersection(set(playlist2))  
for i, track in enumerate(common_tracks, 1):  
    print(i, '-', track)  
  
blend = spoti.create_playlist(  
    name=f'{playlist1.owner.name} + {playlist2.owner.name}',  
    description='I am a blend, I swear')  

blend.add(list(common_tracks))
```

---

## Who Is This Package For

I've created `spotifyatlas` to encourage music lovers and programmers alike, to draw on the elegance of Python automation and **scripting**. If you stumbled upon this package while looking for a way to **extend the user capabilities** in Spotify beyond the user interface, then you are in the right place.

If instead you are looking for an API wrapper for use in a Python **web application**, maybe this package is not the right choice. For starters, the library's functionality is **not asynchronous** (not yet, at least). Perhaps this is okay for a couple of simple tasks, though. And also, as of now, the way I implemented authorization flow is not compatible with a web app (it literally opens a localhost page). This means it would only work with functions that do not require user auth.
