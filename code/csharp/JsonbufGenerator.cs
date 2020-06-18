using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using GameEngine;
using UnityEditor;
using UnityEngine;

namespace jsonbuf
{
    public class JsonbufGenerator
    {
        [MenuItem("jsonbuf/生成桥接配置")]
        public static void GenerateSchema()
        {
            var enums = new List<Type>
            {
                typeof(EAssetCategory),
                typeof(EAssetTag),
                typeof(AssetSplitLevel),
                typeof(AssetModuleDynamicType)
            };

            var classes = new List<Type>
            {
                typeof(Vector2),
                typeof(Vector3),
                typeof(Vector4),
            };
            
            const string indent = "    ";
            
            var data = new StringBuilder();
            data.AppendLine("<jsonbuf>");

            #region 枚举定义
            data.Append(indent);
            data.AppendLine("<enums>");
            foreach(var type in enums)
            {
                data.Append(indent);
                data.Append(indent);
                data.AppendLine(string.Format("<enum name=\"{0}\" namespace=\"{1}\">", type.Name, type.Namespace));
                foreach (var value in Enum.GetValues(type))
                {
                    var name = Enum.GetName(type, value);
                    data.Append(indent);
                    data.Append(indent);
                    data.Append(indent);
                    data.AppendLine(string.Format("<case value=\"{1}\" name=\"{0}\"/>", name, (int)value));
                }
                data.Append(indent);
                data.Append(indent);
                data.AppendLine("</enum>");
            }
            data.Append(indent);
            data.AppendLine("</enums>");
            #endregion

            #region 类型引用
            data.Append(indent);
            data.AppendLine("<classes>");
            foreach(var type in classes)
            {
                data.Append(indent);
                data.Append(indent);
                data.AppendLine(string.Format("<class name=\"{0}\" namespace=\"{1}\"/>", type.Name, type.Namespace));
            }
            data.Append(indent);
            data.AppendLine("</classes>");
            #endregion
            
            data.AppendLine("</jsonbuf>");
            using (var stream = new FileStream(string.Format("{0}/jsonbuf.xml", Application.dataPath), FileMode.Create))
            {
                var content = data.ToString();
                var bytes = Encoding.UTF8.GetBytes(content);
                stream.Write(bytes, 0, bytes.Length);
            }
        }
    }
}