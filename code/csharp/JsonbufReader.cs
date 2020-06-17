using System.IO;
using System.Text;

namespace jsonbuf
{
    public class JsonbufReader: BinaryReader
    {
        public JsonbufReader(Stream input) : base(input)
        {
            
        }
        
        public JsonbufReader(Stream input, Encoding encoding) : base(input, encoding)
        {
            
        }

        public new string ReadString()
        {
            var size = ReadUInt16();
            if (size == ushort.MaxValue)
            {
                return null;
            }
            
            if (size == 0)
            {
                return string.Empty;
            }

            return Encoding.UTF8.GetString(ReadBytes(size));
        }
    }
}