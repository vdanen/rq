from . import basics
from . import tag
from . import binary
from . import source

__version__ = '0.8'

# we don't want output buffering
# from http://stackoverflow.com/questions/107705/python-output-buffering
class Unbuffered:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)

import sys
sys.stdout=Unbuffered(sys.stdout)
