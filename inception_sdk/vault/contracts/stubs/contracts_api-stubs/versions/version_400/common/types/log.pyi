class Logger:

    def __init__(self) -> None:
        ...

    def debug(self, message: str):
        ...

    @classmethod
    def instance(cls):
        ...