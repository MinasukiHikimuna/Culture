using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;
using CultureExtractor.Models;
using Serilog;

namespace CultureExtractor;

public class VideoHashes : IFileMetadata
{
    [JsonPropertyName("duration")]
    public int Duration { get; }
    [JsonPropertyName("phash")]
    public string PHash { get; }
    [JsonPropertyName("oshash")]
    public string OSHash { get; }
    [JsonPropertyName("md5")]
    public string MD5 { get; }

    public VideoHashes(int duration, string phash, string oshash, string md5)
    {
        Duration = duration;
        PHash = phash;
        OSHash = oshash;
        MD5 = md5;
    }
}

public static class Hasher
{
    public static VideoHashes? Phash(string path)
    {
        string commandPath;
        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            commandPath = "videohashes-windows-amd64.exe";
        }
        else if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
        {
            commandPath = "videohashes-linux-amd64";
        }
        else if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
        {
            commandPath = "videohashes-darwin-amd64";
        }
        else
        {
            throw new InvalidOperationException("Unknown operating system!");
        }

        // Start the process and set its start information
        var arguments = $"-md5 -json {path}";
        ProcessStartInfo startInfo = new()
        {
            FileName = commandPath,
            Arguments = arguments,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            CreateNoWindow = true
        };

        // Start the process and read its output
        using var process = Process.Start(startInfo);
        if (process == null)
        {
            throw new InvalidOperationException($"Could not start process {commandPath} {arguments}!");
        }
        
        var output = process.StandardOutput.ReadToEnd();

        try
        {
            var videoHashes = JsonSerializer.Deserialize<VideoHashes>(output);
            return videoHashes;
        }
        catch (JsonException ex)
        {
            Log.Warning($"Could not hash file {path}.", ex);
            return null;
        }
    }
}
