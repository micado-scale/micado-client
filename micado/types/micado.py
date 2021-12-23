from dataclasses import dataclass

@dataclass
class MicadoInfo:
    """For storing MiCADO node information."""
    id: str
    ip: str