using System;
using System.IO;
using System.Text;

namespace jsonbuf
{
    public class JsonbufWriter: BinaryWriter
    {
        public new void Write(string value)
        {
            if (value == null)
            {
                Write((short)-1);
                return;
            }

            var data = Encoding.UTF8.GetBytes(value);
            if (data.Length >= ushort.MaxValue)
            {
                throw new ArgumentOutOfRangeException();
            }
            
            Write((ushort)data.Length);
            Write(data, 0, data.Length);
        }
    }
}