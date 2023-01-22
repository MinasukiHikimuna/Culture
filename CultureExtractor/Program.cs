using CultureExtractor.Interfaces;
using Serilog;

namespace CultureExtractor;

class PlaywrightExample
{
    public static async Task Main(string[] args)
    {
        try
        {
            if (System.Diagnostics.Debugger.IsAttached)
            {
                args = new string[] { "czechvr", "download-scenes" };
            }

            using var log = new LoggerConfiguration()
                .WriteTo.Console()
                    .MinimumLevel.Verbose()
                .CreateLogger();
            Log.Logger = log;

            Log.Information("Culture Extractor");

            string shortName = args[0];
            var browserSettings = new BrowserSettings(false);

            // var downloadOptions = DownloadConditions.All(PreferredDownloadQuality.Phash);
            var downloadOptions = DownloadConditions.All(PreferredDownloadQuality.Best) with { PerformerShortName = "401-alexis-crystal" };

            var jobType = args[1] switch
            {
                "scrape-scenes" => JobType.ScrapeScenes,
                "download-scenes" => JobType.DownloadScenes,
                "upsize-scenes" => JobType.UpsizeDownloadedScenes,
                _ => throw new NotImplementedException($"Unknown job type {args[1]}")
            };

            var repository = new Repository(new SqliteContext());
            var site = await repository.GetSiteAsync(shortName);
            var networkRipper = new NetworkRipper(repository);

            switch (jobType)
            {
                case JobType.ScrapeScenes:
                    await networkRipper.ScrapeScenesAsync(site, browserSettings);
                    break;
                case JobType.DownloadScenes:
                    await networkRipper.DownloadScenesAsync(site, browserSettings, downloadOptions);
                    break;
                case JobType.UpsizeDownloadedScenes:
                    var fileNames = new List<string>
                    {
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal & Isabella Chrystin - Czech VR - 2017-04-01 - Where is the map.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal & Isabella Chrystin - Czech VR - 2017-04-03 - Lesbian pirates in action.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal - Czech VR - 2017-03-11 - Baking with Alexis.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal - Czech VR - 2019-06-22 - Kinky Toy.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal, Charlie Red, Jenifer Jane & Stacy Cruz - Czech VR - 2019-04-22 - Easter Race.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal, Charlie Red, Olivia Sparkle & Rika Fane - Czech VR - 2022-12-21 - A Christmas Dream Part 1.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal, Charlie Red, Olivia Sparkle & Rika Fane - Czech VR - 2022-12-23 - A Christmas Dream Part 2.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal, Lexi Dona & Anie Darling - Czech VR - 2017-08-05 - Naughty Bride with Friends.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alexis Crystal, Venera Maxima & Emma Button - Czech VR - 2020-06-13 - Quarantine Rent.mp4",
                        @"I:\Storage Evaluation\Czech VR\Alissa Foxy, Isabela De Laa & Lilly Bella - Czech VR - 2022-11-07 - Lesbian Threesome.mp4",
                        @"I:\Storage Evaluation\Czech VR\Amber Deen & Arteya - Czech VR - 2018-09-08 - Cock as a Learning Tool.mp4",
                        @"I:\Storage Evaluation\Czech VR\Amy Amor - Czech VR - 2021-11-13 - Tail Wagging.mp4",
                        @"I:\Storage Evaluation\Czech VR\Anna Claire Clouds - Czech VR - 2020-11-11 - Hostel Mix-Up.mp4",
                        @"I:\Storage Evaluation\Czech VR\Anna de Ville - Czech VR - 2018-08-25 - Sexy Moving.mp4",
                        @"I:\Storage Evaluation\Czech VR\Anna de Ville - Czech VR - 2021-04-24 - Virtual VR Babe.mp4",
                        @"I:\Storage Evaluation\Czech VR\Antonia Sainz & Emylia Argan - Czech VR - 2020-06-27 - It Began With VR.mp4",
                        @"I:\Storage Evaluation\Czech VR\Antonia Sainz & Nessie Blue - Czech VR - 2021-03-20 - Accidental Cheating - Intentional Threesome.mp4",
                        @"I:\Storage Evaluation\Czech VR\Antonia Sainz - Czech VR - 2022-10-22 - Horny First Date.mp4",
                        @"I:\Storage Evaluation\Czech VR\Antonia Sainz, Billie Star & Kristy Black - Czech VR - 2021-04-17 - Anal Heaven.mp4",
                        @"I:\Storage Evaluation\Czech VR\Candice Demellza & Nikki Hill - Czech VR - 2022-01-01 - Call Girl Threesome.mp4",
                        @"I:\Storage Evaluation\Czech VR\Casey Nice & Jessika Night - Czech VR - 2021-09-11 - Fun in the Pool.mp4",
                        @"I:\Storage Evaluation\Czech VR\Casey Nice - Czech VR - 2021-03-13 - Stay and Watch!.mp4",
                        @"I:\Storage Evaluation\Czech VR\Casey Nice - Czech VR - 2022-10-29 - Trick or Treat.mp4",
                        @"I:\Storage Evaluation\Czech VR\Casey Nice, Jolee Love & Lucy Heart - Czech VR - 2020-10-03 - Meet my Horny Friends.mp4",
                        @"I:\Storage Evaluation\Czech VR\Charlie Red, Anna Rose & Sabrisse Aaliyah - Czech VR - 2021-05-26 - Girl on Girl… on Girl!.mp4",
                        @"I:\Storage Evaluation\Czech VR\Cindy Shine & Mia Trejsi - Czech VR - 2022-11-05 - Who Looks Better.mp4",
                        @"I:\Storage Evaluation\Czech VR\Cindy Shine - Czech VR - 2020-08-01 - Ass Pounding.mp4",
                        @"I:\Storage Evaluation\Czech VR\Claudia Mac - Czech VR - 2021-11-27 - Horny Preggo.mp4",
                        @"I:\Storage Evaluation\Czech VR\Eva Brown - Czech VR - 2022-01-10 - Fun in Bath.mp4",
                        @"I:\Storage Evaluation\Czech VR\Frida Sante & Georgie Lyall - Czech VR - 2018-07-07 - Slutty Wife and Sexy Helper.mp4",
                        @"I:\Storage Evaluation\Czech VR\Georgie Lyall - Czech VR - 2019-05-11 - Sexy Receptionist.mp4",
                        @"I:\Storage Evaluation\Czech VR\Gina Gerson, Casey Nice & Renata Fox - Czech VR - 2019-05-04 - Russian Foursome.mp4",
                        @"I:\Storage Evaluation\Czech VR\Holly Molly - Czech VR - 2022-12-12 - Hornier Than Tired.mp4",
                        @"I:\Storage Evaluation\Czech VR\Jayla De Angelis - Czech VR - 2021-12-18 - Erection Time!.mp4",
                        @"I:\Storage Evaluation\Czech VR\Jayla De Angelis - Czech VR - 2022-05-28 - Mending Broken Heart.mp4",
                        @"I:\Storage Evaluation\Czech VR\Jenny Doll & Stacy Cruz - Czech VR - 2020-12-23 - Christmas Wood.mp4",
                        @"I:\Storage Evaluation\Czech VR\Josephine Jackson - Czech VR - 2020-02-01 - Shower Tease.mp4",
                        @"I:\Storage Evaluation\Czech VR\Katy Rose & Veronica Leal - Czech VR - 2019-10-19 - Garden Mini-Golf.mp4",
                        @"I:\Storage Evaluation\Czech VR\Kinuski - Czech VR - 2021-05-15 - So! Many! Orgasms!.mp4",
                        @"I:\Storage Evaluation\Czech VR\Koko Amaris & Megan Venturi - Czech VR - 2022-07-09 - Let's Take it Inside.mp4",
                        @"I:\Storage Evaluation\Czech VR\Koko Amaris - Czech VR - 2022-01-08 - Dressed to Play.mp4",
                        @"I:\Storage Evaluation\Czech VR\Koko Amaris, Tina Kay & Josephine Jackson - Czech VR - 2019-12-07 - Playing it Cool.mp4",
                        @"I:\Storage Evaluation\Czech VR\Lexi Dona - Czech VR - 2021-08-16 - Bathtub Romance.mp4",
                        @"I:\Storage Evaluation\Czech VR\Linda Sweet - Czech VR - 2019-05-25 - The Escort Girl.mp4",
                        @"I:\Storage Evaluation\Czech VR\Lovita Fate & Sybil - Czech VR - 2021-12-22 - A Sweet Surprise.mp4",
                        @"I:\Storage Evaluation\Czech VR\Lovita Fate, Alexis Crystal, Ashley Ocean & Freya Dee - Czech VR - 2019-08-14 - From Fishing to Heaven 1.mp4",
                        @"I:\Storage Evaluation\Czech VR\Lovita Fate, Alexis Crystal, Ashley Ocean & Freya Dee - Czech VR - 2019-08-17 - From Fishing to Heaven 2.mp4",
                        @"I:\Storage Evaluation\Czech VR\Lovita Fate, Alexis Crystal, Isabela De Laa, Sofia Lee, Jennifer Mendez, Jenny Wild & Lexi Dona - Czech VR - 2021-11-03 - Magnificent Seven Part 1.mp4",
                        @"I:\Storage Evaluation\Czech VR\Lovita Fate, Alexis Crystal, Isabela De Laa, Sofia Lee, Jennifer Mendez, Jenny Wild & Lexi Dona - Czech VR - 2021-11-06 - Magnificent Seven Part 2.mp4",
                        @"I:\Storage Evaluation\Czech VR\Lucy Heart - Czech VR - 2020-01-29 - Sleeping Beauty.mp4",
                        @"I:\Storage Evaluation\Czech VR\Olivia Sparkle, Rika Fane, Antonia Sainz & Lucky Bee - Czech VR - 2022-04-16 - Easter Game Part 1.mp4",
                        @"I:\Storage Evaluation\Czech VR\Olivia Sparkle, Rika Fane, Antonia Sainz & Lucky Bee - Czech VR - 2022-04-18 - Easter Game Part 2.mp4",
                        @"I:\Storage Evaluation\Czech VR\Rebecca Volpetti - Czech VR - 2022-09-24 - Reward for a Trip.mp4",
                        @"I:\Storage Evaluation\Czech VR\Stacy Cruz - Czech VR - 2019-02-02 - Professional Slut.mp4",
                        @"I:\Storage Evaluation\Czech VR\Stacy Cruz - Czech VR - 2020-05-02 - Penthouse Sex.mp4",
                        @"I:\Storage Evaluation\Czech VR\Stacy Cruz - Czech VR - 2022-08-06 - Feeling Hot.mp4",
                        @"I:\Storage Evaluation\Czech VR\Sybil - Czech VR - 2020-01-11 - I Love Your Hands.mp4",
                        @"I:\Storage Evaluation\Czech VR\Sybil, Lexi Dona & Daphne Angel - Czech VR - 2017-05-01 - Dream like never before.mp4",
                        @"I:\Storage Evaluation\Czech VR\Veronica Leal - Czech VR - 2018-11-24 - Squirting Concubine.mp4",
                        @"I:\Storage Evaluation\Czech VR\Veronica Leal - Czech VR - 2019-06-01 - Boner for Breakfast.mp4",
                        @"I:\Storage Evaluation\Czech VR\Veronica Leal - Czech VR - 2020-09-19 - Tending Garden.mp4",
                        @"I:\Storage Evaluation\Czech VR\Vinna Reed - Czech VR - 2020-06-20 - Horny from Shower.mp4",
                    };
                    await networkRipper.UpsizeScenesAsync(site, browserSettings, downloadOptions, fileNames);
                    break;
                default:
                    throw new NotImplementedException($"Unknown job type {jobType}");
            }
        }
        catch (Exception ex)
        {
            Log.Error(ex.ToString(), ex);
        }
    }
}
