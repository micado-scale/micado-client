import functools

from ..exceptions import MicadoException

def check_launch(func):
    """Check launcher has created and connected to API

    """
    @functools.wraps(func)
    def inner(self, *args, **kwargs):
        if getattr(self, "launcher", None) and not self.api:
            raise MicadoException("Launcher not yet connected to API")
        return func(self, *args, **kwargs)
    return inner