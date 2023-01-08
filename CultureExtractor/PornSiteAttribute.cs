namespace RipperPlaywright
{
    [AttributeUsage(AttributeTargets.Class, AllowMultiple = true)]
    public class PornSiteAttribute : Attribute
    {
        public string ShortName { get; }

        public PornSiteAttribute(string shortName)
        {
            ShortName = shortName;
        }
    }
}