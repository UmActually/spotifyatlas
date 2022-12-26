from typing import List, Dict


__all__ = ['id_from_url', 'add_params_to_url', 'parse_url_params']


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
