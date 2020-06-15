using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace jsonbuf
{
    [Serializable]
    public class JsonbufSchema
    {
        public List<EnumDefinition> enums;
    }
    
    [Serializable]
    public class EnumDefinition
    {
        public string name;
        public List<EnumCase> cases;
    }

    [Serializable]
    public class EnumCase
    {
        public string name;
        public int value;
    }
    
    public class EnumSchemaGenerator
    {
        [MenuItem("jsonbuf/生成枚举定义")]
        public static void GenerateSchema()
        {
            var candidates = new List<Type>
            {
                typeof(GameEngine.EAssetCategory),
                typeof(GameEngine.EAssetTag)
            };

            var schema = new JsonbufSchema
            {
                enums = new List<EnumDefinition>()
            };
            
            foreach(var type in candidates)
            {
                var def = new EnumDefinition
                {
                    cases = new List<EnumCase>(),
                    name = type.FullName
                };
                foreach (var value in Enum.GetValues(type))
                {
                    var name = Enum.GetName(type, value);
                    def.cases.Add(new EnumCase
                    {
                        name = name,
                        value = (int)value
                    });
                }
                schema.enums.Add(def);
            }

            using (var stream = new FileStream(string.Format("{0}/jsonbuf.json", Application.dataPath), FileMode.Create))
            {
                var content = JsonUtility.ToJson(schema);
                var bytes = Encoding.UTF8.GetBytes(content);
                stream.Write(bytes, 0, bytes.Length);
            }
        }
    }
}