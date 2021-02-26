from requests.exceptions import HTTPError


class MicadoException(Exception):
    """Base class for exceptions"""

class MicadoAPIException(MicadoException):
    """Class for API exceptions"""

def detailed_raise_for_status(resp):
    """Invoke raise_for_status on a Response object and add message

    Args:
        resp (Response): requests.Response object

    Raises:
        Exception: MicadoException or the original HTTPError
    """
    try:
        resp.raise_for_status()
    except HTTPError as e:
        if resp.text:
            raise MicadoAPIException(
                resp.json().get("message", resp.text)
            ) from None
        else:
            raise e
