import struct
class BinaryReader:
    __slots__ = ('file', '_read', '_unpack', '_seek', '_tell')
    def __init__(self, file_path: str):
        self.file = open(file_path, 'rb')
        self._read = self.file.read
        self._unpack = __import__('struct').unpack
        self._seek = self.file.seek
        self._tell = self.file.tell
    def __enter__(self):return self
    def __exit__(self, *_):self.file.close()
    def tell(self):return self._tell()
    def seek(self, offset, whence=0):self._seek(offset, whence)
    def seekpad(self, pad, type=0):
        size = self._tell();seek = (pad - (size % pad)) % pad
        if type == 1 and seek == 0:seek += pad
        self._seek(seek, 1) if seek else None
    def i(self, n):return self._unpack(f'<{n}i', self._read(n * 4))
    def I(self, n):return self._unpack(f'<{n}I', self._read(n * 4))
    def h(self, n):return self._unpack(f'<{n}h', self._read(n * 2))
    def H(self, n):return self._unpack(f'<{n}H', self._read(n * 2))
    def f(self, n):return self._unpack(f'<{n}f', self._read(n * 4))
    def B(self, n):return self._unpack(f'<{n}B', self._read(n))
    def b(self, n):return self._unpack(f'<{n}b', self._read(n))
    def raw(self, n):return self._read(n)  # NEW: Read raw bytes without unpacking
    def word(self, length):return self._read(length).split(b'\x00', 1)[0].decode('utf-8', errors='ignore')
