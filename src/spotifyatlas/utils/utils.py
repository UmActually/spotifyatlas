from typing import Optional, Union, Tuple, List, Dict
from ..enums import Genre


__all__ = ['id_from_url', 'add_params_to_url', 'parse_url_params', 'advanced_search']


def id_from_url(url: str) -> str:
    """Extract the ID from a Spotify share link."""
    if url.startswith('https://open.spotify.com/'):
        return url.split('/')[-1].split('?')[0]
    if url.isalnum():
        return url
    raise ValueError('Spotify URL or ID not valid.')


def add_params_to_url(base_url: str, params: Dict[str, str]) -> str:
    """Translate a dict to a query string, which is added to ``base_url``."""
    pairs: List[str] = []
    for key, value in params.items():
        pairs.append(str(key) + '=' + str(value))
    return base_url + '?' + '&'.join(pairs)


def parse_url_params(url: str) -> Dict[str, str]:
    """Translate the URL's query string to a dict of parameters."""
    params_str = url[2:]
    resp = {}
    for pair in params_str.split('&'):
        try:
            key, value = pair.split('=')
            resp[key] = value
        except ValueError:
            pass
    return resp


def _advanced_search(**kwargs) -> str:
    """This function exists in order to iterate through the arguments of the real
    advanced_search() function."""

    options: List[str] = []
    try:
        query = kwargs.pop('q')
        if query is not None:
            options.append(query)
    except KeyError:
        pass
    for name, value in kwargs.items():
        if value is None:
            continue
        # for hipster and new params
        # 'is True' is needed to actually test being boolean
        elif value is True:
            value = name
            name = 'tag'
        # for a year range
        elif isinstance(value, tuple):
            value = f'{value[0]}-{value[1]}'
        options.append(f'{name}:{value}')

    if not options:
        return ''
    return ' '.join(options)


# Boilerplate code alert
def advanced_search(
        q: Optional[str] = None, *,
        album: Optional[str] = None,
        artist: Optional[str] = None,
        track: Optional[str] = None,
        year: Optional[Union[int, Tuple[int, int]]] = None,
        upc: Optional[int] = None,
        hipster: Optional[bool] = None,
        new: Optional[bool] = None,
        isrc: Optional[str] = None,
        genre: Optional[Union[str, Genre]] = None
) -> str:
    """**Returns a search query string that includes the specified filters.**

    :param q: the query (not a filter)
    :param album: filter for a particular album name
    :param artist: filter for a particular artist name
    :param track: filter for a particular track name
    :param year: filter for a particular year (pass a tuple for an inclusive range)
    :param upc: the Universal Product Code of an album
    :param hipster: filter for albums with lowest 10% popularity
    :param new: filter for albums from the past two weeks
    :param isrc: the International Standard Recording Code of a track
    :param genre: filter for a particular genre (using spotifyatlas.Genre recommended)
    :return:
    """
    return _advanced_search(
        q=q, album=album, artist=artist, track=track, year=year,
        upc=upc, hipster=hipster, new=new, isrc=isrc, genre=genre)
