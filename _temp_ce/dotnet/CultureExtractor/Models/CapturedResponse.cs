using Microsoft.Playwright;

namespace CultureExtractor.Models;

public record CapturedResponse(string Name, IResponse Response);