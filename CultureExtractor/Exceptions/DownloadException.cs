using System;

namespace CultureExtractor.Exceptions;

public class DownloadException : Exception
{
    public bool ShouldRetry { get; }

    public DownloadException()
    {
    }

    public DownloadException(string message)
        : base(message)
    {
    }

    public DownloadException(string message, Exception inner)
        : base(message, inner)
    {
    }

    public DownloadException(bool shouldRetry, string message)
    : this(message)
    {
        ShouldRetry = shouldRetry;
    }

    public DownloadException(bool shouldRetry, string message, Exception inner)
        : this(message, inner)
    {
        ShouldRetry = shouldRetry;
    }
}
