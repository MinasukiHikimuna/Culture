namespace CultureExtractor.Exceptions;

public enum ExtractorRetryMode
{
    Retry,
    Skip,
    Abort
}

public class ExtractorException : Exception
{
    public ExtractorRetryMode ExtractorRetryMode { get; }

    public ExtractorException()
    {
    }

    public ExtractorException(string message)
        : base(message)
    {
    }

    public ExtractorException(string message, Exception inner)
        : base(message, inner)
    {
    }

    public ExtractorException(ExtractorRetryMode extractorRetryMode, string message)
    : this(message)
    {
        ExtractorRetryMode = extractorRetryMode;
    }

    public ExtractorException(ExtractorRetryMode extractorRetryMode, string message, Exception inner)
        : this(message, inner)
    {
        ExtractorRetryMode = extractorRetryMode;
    }
}
