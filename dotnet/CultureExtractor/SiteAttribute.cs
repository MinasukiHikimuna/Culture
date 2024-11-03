namespace CultureExtractor;

[AttributeUsage(AttributeTargets.Class, AllowMultiple = true)]
public class SiteAttribute : Attribute
{
    public string ShortName { get; }

    public SiteAttribute(string shortName)
    {
        ShortName = shortName;
    }
}