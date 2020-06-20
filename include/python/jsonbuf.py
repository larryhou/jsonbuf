import io, struct

class JsonbufStream(object):
    def __init__(self):
        self.__stream = io.BytesIO()

    def read_bool(self):
        v, = struct.unpack('b', self.__stream.read(1))
        return v != 0

    def read_int8(self):
        v, = struct.unpack('b', self.__stream.read(1))
        return v

    def read_uint8(self):
        v, = struct.unpack('B', self.__stream.read(1))
        return v

    def read_int16(self):
        v, = struct.unpack('<h', self.__stream.read(2))
        return v

    def read_uint16(self):
        v, = struct.unpack('<H', self.__stream.read(2))
        return v

    def read_int32(self):
        v, = struct.unpack('<i', self.__stream.read(4))
        return v

    def read_uint32(self):
        v, = struct.unpack('<I', self.__stream.read(4))
        return v

    def read_int64(self):
        v, = struct.unpack('<q', self.__stream.read(8))
        return v

    def read_uint64(self):
        v, = struct.unpack('<Q', self.__stream.read(8))
        return v

    def read_float(self):
        v, = struct.unpack('<f', self.__stream.read(4))
        return v

    def read_double(self):
        v, = struct.unpack('<d', self.__stream.read(8))
        return v

    def read_string(self):
        size = self.read_uint16()
        if size == 0xFFFF: return None
        if size == 0: return ''
        return self.__stream.read(size)

    def write_bool(self, v):
        self.__stream.write(struct.pack('b', 1 if v else 0))

    def write_int8(self, v):
        self.__stream.write(struct.pack('b', v))

    def write_uint8(self, v):
        self.__stream.write(struct.pack('B', v))

    def write_int16(self, v):
        self.__stream.write(struct.pack('<h', v))

    def write_uint16(self, v):
        self.__stream.write(struct.pack('<H', v))

    def write_int32(self, v):
        self.__stream.write(struct.pack('<i', v))

    def write_uint32(self, v):
        self.__stream.write(struct.pack('<I', v))

    def write_int64(self, v):
        self.__stream.write(struct.pack('<q', v))

    def write_uint64(self, v):
        self.__stream.write(struct.pack('<Q', v))

    def write_float(self, v):
        self.__stream.write(struct.pack('<f', v))

    def write_double(self, v):
        self.__stream.write(struct.pack('<d', v))

    def write_string(self, v):
        if v is None:
            self.write_int16(-1)
            return
        size = min(len(v), 0xFFFF - 1)
        self.write_uint16(size)
        return self.__stream.write(v)


class IJsonbuf(object):
    def deserialize(self, decoder): # type: (JsonbufStream)->None
        pass

    def serialize(self, encoder): # type: (JsonbufStream)->None
        pass






