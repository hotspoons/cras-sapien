
from abc import abstractmethod

# A generic socket interface to be plugged into any graph node that
# requires external interaction. This should look more or less like
# a TCP socket and websocket
class GenericSocket:
    @abstractmethod
    def send(message: str | bytes | bytearray | memoryview) -> None:
        raise Exception("If using sockets for I/O, you need to provide an implementation of GenericSocket to AutomataDependencies")
    
    @abstractmethod
    def recv() -> str:
        raise Exception("If using sockets for I/O, you need to provide an implementation of GenericSocket to AutomataDependencies")
