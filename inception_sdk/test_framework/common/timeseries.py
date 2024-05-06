class TimeSeries(list):
    def __init__(self, items, return_on_empty=None):
        super().__init__(items)
        self.return_on_empty = return_on_empty

    def at(self, timestamp, inclusive=True):
        for entry in reversed(self):
            if entry[0] <= timestamp:
                if inclusive or entry[0] < timestamp:
                    return entry[1]

        if self.return_on_empty is not None:
            return self.return_on_empty

        raise ValueError("No value in timeseries")

    def before(self, timestamp):
        return self.at(timestamp, inclusive=False)

    def latest(self):
        if not self:
            if self.return_on_empty is not None:
                return self.return_on_empty
            raise ValueError("No value in timeseries")
        return self[-1][1]

    def all(self):
        return [item for item in self]
