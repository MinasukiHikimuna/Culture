using Microsoft.CognitiveServices.Speech;
using Microsoft.CognitiveServices.Speech.Audio;
using Xabe.FFmpeg;

namespace CultureExtractor.CaptchaBuster;

public enum CaptchaReason
{
    RecognizedSpeech,
    NoMatch,
    Canceled
}

public record CaptchaResult(CaptchaReason CaptchaReason, string Text);

public class CaptchaBusterImplementation
{
    // This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"
    static string speechKey = "b8e98853a1d0402987508effed5299c4";
    static string speechRegion = "swedencentral";

    public async Task<CaptchaResult> SolveCaptchaAsync(string pathMp3)
    {
        string output = Path.Combine(Path.GetTempPath(), Guid.NewGuid() + ".wav");
        var snippet = await FFmpeg.Conversions.FromSnippet.Convert(pathMp3, output);
        IConversionResult result = await snippet.Start();

        var speechConfig = SpeechConfig.FromSubscription(speechKey, speechRegion);
        speechConfig.SpeechRecognitionLanguage = "en-US";

        using var audioConfig = AudioConfig.FromWavFileInput(output);
        using var speechRecognizer = new SpeechRecognizer(speechConfig, audioConfig);

        var speechRecognitionResult = await speechRecognizer.RecognizeOnceAsync();

        switch (speechRecognitionResult.Reason)
        {
            case ResultReason.RecognizedSpeech:
                return new CaptchaResult(CaptchaReason.RecognizedSpeech, speechRecognitionResult.Text);
            case ResultReason.NoMatch:
                return new CaptchaResult(CaptchaReason.NoMatch, string.Empty);
            case ResultReason.Canceled:
                var cancellation = CancellationDetails.FromResult(speechRecognitionResult);

                var errorMessage = $"CANCELED: Reason={cancellation.Reason}";
                if (cancellation.Reason == CancellationReason.Error)
                {
                    errorMessage += $"ErrorCode={cancellation.ErrorCode} ErrorDetails={cancellation.ErrorDetails} Did you set the speech resource key and region values?";
                }

                return new CaptchaResult(CaptchaReason.Canceled, errorMessage);
            default:
                throw new Exception("What the fuck just happened");
        }
    }
} 
