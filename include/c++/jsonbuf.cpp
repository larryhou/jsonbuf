//
//  jsonbuf.cpp
//  jsonbuf
//
//  Created by larryhou on 2020/6/18.
//  Copyright © 2020 larryhou. All rights reserved.
//

#include "jsonbuf.h"
using namespace jsonbuf;

template<>
void JsonbufStream::write(std::string v)
{
    auto size = std::min(v.size(), (size_t)0xFFFF - 1);
    write<uint16_t>(static_cast<uint16_t>(size));
    __stream->write(v.c_str(), size);
}

template<>
void JsonbufStream::write(const char* v)
{
    if (v == nullptr) { write<int16_t>(-1); return; }
    
    auto size = strlen(v);
    write<uint16_t>(static_cast<uint16_t>(size));
    __stream->write(v, size);
}

template<>
std::string JsonbufStream::read()
{
    auto size = read<uint16_t>();
    if (size == 0 || size == 0xFFFF) {return "";}
    check_buffer(size);
    
    __stream->read(__buf, size);
    memset(__buf + size, 0, 1);
    return __buf;
}

template<>
const char* JsonbufStream::read()
{
    auto size = read<uint16_t>();
    if (size == 0) {return "";}
    if (size == 0xFFFF) {return nullptr;}
    check_buffer(size);
    
    __stream->read(__buf, size);
    memset(__buf + size, 0, 1);
    return __buf;
}
