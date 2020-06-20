//
//  jsonbuf.h
//  jsonbuf
//
//  Created by larryhou on 2020/6/18.
//  Copyright © 2020 larryhou. All rights reserved.
//

#ifndef jsonbuf_h
#define jsonbuf_h

#include <iostream>
#include <string>

namespace jsonbuf {

class JsonbufStream
{
    std::iostream *__stream;
    size_t __buf_size;
    char* __buf;
    
public:
    JsonbufStream(std::iostream *stream): JsonbufStream(stream, 256) {}
    JsonbufStream(std::iostream *stream, size_t size): __stream(stream)
    {
        __buf = new char[size];
        __buf_size = size;
    }
    
    void check_buffer(size_t size)
    {
        static const size_t PAGE_SIZE = 4 << 10;
        if (size > __buf_size)
        {
            if (size >= PAGE_SIZE)
            {
                __buf_size = (size / PAGE_SIZE) * PAGE_SIZE + (size % PAGE_SIZE == 0 ? 0 : PAGE_SIZE);
            }
            else
            {
                __buf_size <<= 1;
            }
            
            delete [] __buf;
            __buf = new char[__buf_size];
        }
    }
    
    template<class T>
    void write(T v);
    
    template<class T>
    T read();
    
    template<> void write(std::string v);
    template<> void write(const char* v);

    template<> std::string read();
    template<> const char* read();
    
    ~JsonbufStream()
    {
        __stream = nullptr;
        delete [] __buf;
    }
};

template<typename T> void JsonbufStream::write(T v)
{
    auto ptr = (char*)&v;
    __stream->write(ptr, sizeof(T));
}

template<typename T> T JsonbufStream::read()
{
    __stream->read(__buf, sizeof(T));
    return *(T *)__buf;
}

class IJsonbuf
{
public:
    virtual void deserialize(JsonbufStream& decoder) = 0;
    virtual void serialize(JsonbufStream& encoder) = 0;
};

}

#endif /* jsonbuf_h */
