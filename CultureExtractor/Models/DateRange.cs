namespace CultureExtractor.Models;

public record DateRange(
    DateOnly Start,
    DateOnly End)
{
    public static DateRange All => new(DateOnly.MinValue, DateOnly.MaxValue);   
}
