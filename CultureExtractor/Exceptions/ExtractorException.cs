using System;

namespace CultureExtractor.Exceptions;

public class ExtractorException : Exception
{
    public bool ShouldRetry { get; }

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

    public ExtractorException(bool shouldRetry, string message)
    : this(message)
    {
        ShouldRetry = shouldRetry;
    }

    public ExtractorException(bool shouldRetry, string message, Exception inner)
        : this(message, inner)
    {
        ShouldRetry = shouldRetry;
    }
}
