namespace RipperPlaywright
{
    [AttributeUsage(AttributeTargets.Class)]
    public class PornNetworkAttribute : Attribute
    {
        public string ShortName { get; }

        public PornNetworkAttribute(string shortName)
        {
            ShortName = shortName;
        }
    }
}
