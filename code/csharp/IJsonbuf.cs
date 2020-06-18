using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace jsonbuf
{
    public interface IJsonbuf
    {
        void Serialize(JsonbufWriter encoder);
        void Deserialize(JsonbufReader decoder);
    }
}
