using CommandLine;

namespace CultureExtractor;

/* FIX 1:
[20:34:00 ERR] Microsoft.EntityFrameworkCore.DbUpdateException: An error occurred while saving the entity changes. See the inner exception for details.
 ---> System.InvalidOperationException: The instance of entity type 'DownloadEntity' cannot be tracked because another instance with the same key value for {'Id'} is already being tracked. When attaching existing entities, ensure that only one entity instance with a given key value is attached. Consider using 'DbContextOptionsBuilder.EnableSensitiveDataLogging' to see the conflicting key values.
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.IdentityMap`1.ThrowIdentityConflict(InternalEntityEntry entry)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.IdentityMap`1.Add(TKey key, InternalEntityEntry entry, Boolean updateDuplicate)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.IdentityMap`1.Add(TKey key, InternalEntityEntry entry)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.IdentityMap`1.Add(InternalEntityEntry entry)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.StateManager.UpdateIdentityMap(InternalEntityEntry entry, IKey key)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.NavigationFixer.KeyPropertyChanged(InternalEntityEntry entry, IProperty property, IEnumerable`1 containingPrincipalKeys, IEnumerable`1 containingForeignKeys, Object oldValue, Object newValue)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.InternalEntityEntryNotifier.KeyPropertyChanged(InternalEntityEntry entry, IProperty property, IEnumerable`1 keys, IEnumerable`1 foreignKeys, Object oldValue, Object newValue)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.ChangeDetector.DetectKeyChange(InternalEntityEntry entry, IProperty property)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.ChangeDetector.PropertyChanged(InternalEntityEntry entry, IPropertyBase propertyBase, Boolean setModified)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.InternalEntityEntry.SetProperty(IPropertyBase propertyBase, Object value, Boolean isMaterialization, Boolean setModified, Boolean isCascadeDelete, CurrentValueType valueType)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.InternalEntityEntry.SetStoreGeneratedValue(IProperty property, Object value, Boolean setModified)
   at Microsoft.EntityFrameworkCore.Update.ColumnModification.set_Value(Object value)
   at Microsoft.EntityFrameworkCore.Update.ModificationCommand.PropagateResults(RelationalDataReader relationalReader)
   at Microsoft.EntityFrameworkCore.Update.AffectedCountModificationCommandBatch.ConsumeResultSetAsync(Int32 startCommandIndex, RelationalDataReader reader, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.Update.AffectedCountModificationCommandBatch.ConsumeAsync(RelationalDataReader reader, CancellationToken cancellationToken)
   --- End of inner exception stack trace ---
   at Microsoft.EntityFrameworkCore.Update.AffectedCountModificationCommandBatch.ConsumeAsync(RelationalDataReader reader, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.Update.ReaderModificationCommandBatch.ExecuteAsync(IRelationalConnection connection, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.Update.ReaderModificationCommandBatch.ExecuteAsync(IRelationalConnection connection, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.Update.Internal.BatchExecutor.ExecuteAsync(IEnumerable`1 commandBatches, IRelationalConnection connection, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.Update.Internal.BatchExecutor.ExecuteAsync(IEnumerable`1 commandBatches, IRelationalConnection connection, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.Update.Internal.BatchExecutor.ExecuteAsync(IEnumerable`1 commandBatches, IRelationalConnection connection, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.StateManager.SaveChangesAsync(IList`1 entriesToSave, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.ChangeTracking.Internal.StateManager.SaveChangesAsync(StateManager stateManager, Boolean acceptAllChangesOnSuccess, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.DbContext.SaveChangesAsync(Boolean acceptAllChangesOnSuccess, CancellationToken cancellationToken)
   at Microsoft.EntityFrameworkCore.DbContext.SaveChangesAsync(Boolean acceptAllChangesOnSuccess, CancellationToken cancellationToken)
   at CultureExtractor.Repository.GetOrCreatePerformersAsync(IEnumerable`1 performers, SiteEntity siteEntity) in C:\Github\CultureExtractor\CultureExtractor\Repository.cs:line 262
   at CultureExtractor.Repository.UpsertScene(Scene scene) in C:\Github\CultureExtractor\CultureExtractor\Repository.cs:line 161
   at CultureExtractor.NetworkRipper.DownloadGivenScenesAsync(Site site, BrowserSettings browserSettings, DownloadConditions downloadConditions, IList`1 matchingScenes) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 352
 */


/*
 * FIX 2:
[17:38:58 INF] Page 69/69 contains 7 scenes
[17:39:08 INF] Scraped scene: {"Site": "Kink", "SubSite": "Hogtied", "ShortName": "4", "ReleaseDate": "1998-09-21", "Name": "Olivia", "Url": "https://www.kink.com/shoot/4"}

<--- Last few GCs --->

[76264:000001A74E1A74B0] 28943951 ms: Mark-sweep 4043.4 (4144.0) -> 4041.0 (4143.8) MB, 1683.8 / 0.0 ms  (average mu = 0.980, current mu = 0.874) allocation failure scavenge might not succeed
[76264:000001A74E1A74B0] 28945614 ms: Mark-sweep 4041.4 (4144.0) -> 4041.4 (4144.3) MB, 1661.7 / 0.0 ms  (average mu = 0.954, current mu = 0.000) allocation failure scavenge might not succeed


<--- JS stacktrace --->

FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
 1: 00007FF7BE290AAF v8::internal::CodeObjectRegistry::~CodeObjectRegistry+124015
 2: 00007FF7BE21C866 v8::internal::wasm::WasmCode::safepoint_table_offset+64182
 3: 00007FF7BE21D8E2 v8::internal::wasm::WasmCode::safepoint_table_offset+68402
 4: 00007FF7BEB51CE4 v8::Isolate::ReportExternalAllocationLimitReached+116
 5: 00007FF7BEB3C2AD v8::SharedArrayBuffer::Externalize+781
 6: 00007FF7BE9DF88C v8::internal::Heap::EphemeronKeyWriteBarrierFromCode+1468
 7: 00007FF7BE9DC9A4 v8::internal::Heap::CollectGarbage+4244
 8: 00007FF7BE9DA320 v8::internal::Heap::AllocateExternalBackingStore+2000
 9: 00007FF7BE9F8030 v8::internal::FreeListManyCached::Reset+1408
10: 00007FF7BE9F86E5 v8::internal::Factory::AllocateRaw+37
11: 00007FF7BEA0DDBB v8::internal::FactoryBase<v8::internal::Factory>::NewRawOneByteString+75
12: 00007FF7BE7F15FB v8::internal::String::SlowFlatten+395
13: 00007FF7BE55C11B v8::internal::WasmTableObject::Fill+603
14: 00007FF7BEB5BA86 v8::String::Utf8Length+22
15: 00007FF7BE134533 v8::base::Mutex::Mutex+36067
16: 00007FF7BE138D78 v8::internal::MicrotaskQueue::microtasks_policy+10280
17: 00007FF7BE1385EF v8::internal::MicrotaskQueue::microtasks_policy+8351
18: 00007FF7BEB0C6A6 v8::internal::Builtins::code_handle+172806
19: 00007FF7BEB0C299 v8::internal::Builtins::code_handle+171769
20: 00007FF7BEB0C55C v8::internal::Builtins::code_handle+172476
21: 00007FF7BEB0C3C0 v8::internal::Builtins::code_handle+172064
22: 00007FF7BEBDFAA1 v8::internal::SetupIsolateDelegate::SetupHeap+494641
23: 000001A74FE85D44
[17:39:21 ERR] Caught following exception while scraping /shoot/3: Microsoft.Playwright.PlaywrightException: Process exited
   at Microsoft.Playwright.Transport.Connection.InnerSendMessageToServerAsync[T](String guid, String method, Object args) in /_/src/Playwright/Transport/Connection.cs:line 185
   at Microsoft.Playwright.Transport.Connection.WrapApiCallAsync[T](Func`1 action, Boolean isInternal) in /_/src/Playwright/Transport/Connection.cs:line 488
   at Microsoft.Playwright.Core.Page.CloseAsync(PageCloseOptions options) in /_/src/Playwright/Core/Page.cs:line 458
   at CultureExtractor.NetworkRipper.ScrapeSceneAsync(IndexScene currentRelease, ISiteScraper siteScraper, Site site, SubSite subSite, IPage page, ScrapeOptions scrapeOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 198
   at CultureExtractor.NetworkRipper.<>c__DisplayClass9_2.<<ScrapeScenePageAsync>b__5>d.MoveNext() in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 139
--- End of stack trace from previous location ---
   at Polly.ResilienceStrategy.<>c.<<ExecuteAsync>b__3_0>d.MoveNext()
[17:39:24 ERR] Caught following exception while scraping /shoot/3: Microsoft.Playwright.PlaywrightException: Process exited
   at Microsoft.Playwright.Transport.Connection.InnerSendMessageToServerAsync[T](String guid, String method, Object args) in /_/src/Playwright/Transport/Connection.cs:line 185
   at Microsoft.Playwright.Transport.Connection.WrapApiCallAsync[T](Func`1 action, Boolean isInternal) in /_/src/Playwright/Transport/Connection.cs:line 488
   at Microsoft.Playwright.Core.BrowserContext.NewPageAsync() in /_/src/Playwright/Core/BrowserContext.cs:line 280
   at CultureExtractor.NetworkRipper.ScrapeSceneAsync(IndexScene currentRelease, ISiteScraper siteScraper, Site site, SubSite subSite, IPage page, ScrapeOptions scrapeOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 167
   at CultureExtractor.NetworkRipper.<>c__DisplayClass9_2.<<ScrapeScenePageAsync>b__5>d.MoveNext() in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 139
--- End of stack trace from previous location ---
   at Polly.ResilienceStrategy.<>c.<<ExecuteAsync>b__3_0>d.MoveNext()
[17:39:27 ERR] Caught following exception while scraping /shoot/3: Microsoft.Playwright.PlaywrightException: Process exited
   at Microsoft.Playwright.Transport.Connection.InnerSendMessageToServerAsync[T](String guid, String method, Object args) in /_/src/Playwright/Transport/Connection.cs:line 185
   at Microsoft.Playwright.Transport.Connection.WrapApiCallAsync[T](Func`1 action, Boolean isInternal) in /_/src/Playwright/Transport/Connection.cs:line 488
   at Microsoft.Playwright.Core.BrowserContext.NewPageAsync() in /_/src/Playwright/Core/BrowserContext.cs:line 280
   at CultureExtractor.NetworkRipper.ScrapeSceneAsync(IndexScene currentRelease, ISiteScraper siteScraper, Site site, SubSite subSite, IPage page, ScrapeOptions scrapeOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 167
   at CultureExtractor.NetworkRipper.<>c__DisplayClass9_2.<<ScrapeScenePageAsync>b__5>d.MoveNext() in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 139
--- End of stack trace from previous location ---
   at Polly.ResilienceStrategy.<>c.<<ExecuteAsync>b__3_0>d.MoveNext()
[17:39:30 ERR] Caught following exception while scraping /shoot/3: Microsoft.Playwright.PlaywrightException: Process exited
   at Microsoft.Playwright.Transport.Connection.InnerSendMessageToServerAsync[T](String guid, String method, Object args) in /_/src/Playwright/Transport/Connection.cs:line 185
   at Microsoft.Playwright.Transport.Connection.WrapApiCallAsync[T](Func`1 action, Boolean isInternal) in /_/src/Playwright/Transport/Connection.cs:line 488
   at Microsoft.Playwright.Core.BrowserContext.NewPageAsync() in /_/src/Playwright/Core/BrowserContext.cs:line 280
   at CultureExtractor.NetworkRipper.ScrapeSceneAsync(IndexScene currentRelease, ISiteScraper siteScraper, Site site, SubSite subSite, IPage page, ScrapeOptions scrapeOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 167
   at CultureExtractor.NetworkRipper.<>c__DisplayClass9_2.<<ScrapeScenePageAsync>b__5>d.MoveNext() in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 139
--- End of stack trace from previous location ---
   at Polly.ResilienceStrategy.<>c.<<ExecuteAsync>b__3_0>d.MoveNext()
[17:39:34 ERR] Microsoft.Playwright.PlaywrightException: Process exited
   at Microsoft.Playwright.Transport.Connection.InnerSendMessageToServerAsync[T](String guid, String method, Object args) in /_/src/Playwright/Transport/Connection.cs:line 185
   at Microsoft.Playwright.Transport.Connection.WrapApiCallAsync[T](Func`1 action, Boolean isInternal) in /_/src/Playwright/Transport/Connection.cs:line 488
   at Microsoft.Playwright.Core.BrowserContext.NewPageAsync() in /_/src/Playwright/Core/BrowserContext.cs:line 280
   at CultureExtractor.NetworkRipper.ScrapeSceneAsync(IndexScene currentRelease, ISiteScraper siteScraper, Site site, SubSite subSite, IPage page, ScrapeOptions scrapeOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 167
   at CultureExtractor.NetworkRipper.<>c__DisplayClass9_2.<<ScrapeScenePageAsync>b__5>d.MoveNext() in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 139
--- End of stack trace from previous location ---
   at Polly.ResilienceStrategy.<>c.<<ExecuteAsync>b__3_0>d.MoveNext()
--- End of stack trace from previous location ---
   at Polly.ResilienceStrategy.ExecuteAsync(Func`2 callback, CancellationToken cancellationToken)
   at CultureExtractor.NetworkRipper.ScrapeScenePageAsync(Site site, SubSite subSite, ScrapeOptions scrapeOptions, ISiteScraper siteScraper, IPage page, Int32 totalPages, Int32 currentPage) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 137
   at CultureExtractor.NetworkRipper.ScrapeScenesInternalAsync(Site site, SubSite subSite, ScrapeOptions scrapeOptions, ISiteScraper siteScraper, IPage page, Int32 totalPages) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 77
   at CultureExtractor.NetworkRipper.ScrapeSubSiteScenesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions, ISubSiteScraper subSiteScraper) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 58
   at CultureExtractor.NetworkRipper.ScrapeScenesAsync(Site site, BrowserSettings browserSettings, ScrapeOptions scrapeOptions) in C:\Github\CultureExtractor\CultureExtractor\NetworkRipper.cs:line 33
   at CultureExtractor.CultureExtractorConsoleApp.RunScrapeAndReturnExitCode(ScrapeOptions opts) in C:\Github\CultureExtractor\CultureExtractor\CultureExtractorConsoleApp.cs:line 43

C:\Github\CultureExtractor\CultureExtractor\bin\Debug\net7.0\CultureExtractor.exe (process 92948) exited with code 0.
To automatically close the console when debugging stops, enable Tools->Options->Debugging->Automatically close the console when debugging stops.
Press any key to close this window . . .
*/

class Program
{
    static void Main(string[] args)
    {
        if (System.Diagnostics.Debugger.IsAttached)
        {
            var siteShortName = "sexart";
            // var subSiteShortName = "sex-and-submission";

            /*args = new string[] {
                "scrape",
                "--site-short-name", siteShortName,
                "--visible-browser",
                "--full"
            };*/
            args = new string[] {
                // /*
                "scrape",
                "--site-short-name", siteShortName,
                // "--sub-site-short-name", subSiteShortName,
                "--full",
                // "--guest-mode",
                "--reverse-order",
                "--browser-mode", "Visible",
                // "--max-scenes", "1000",
                // "--from", "2020-01-01",
                // "--to", "2020-12-31",
                "--verbose",
                // */
                
                /*
                "download",
                "--site-short-name", siteShortName,
                // "--sub-site-short-name", subSiteShortName,
                // "--scenes", "0231105/PULSATION",
                "--performers", "Alexis Crystal",
                "--reverse-order",
                "--browser-mode", "Visible",
                // "--max-scenes", "1000"
                // "--best",
                // "--downloaded-file-names", "Kink - Ultimate Surrender - 2009-03-17 - #6165 - Ami The Valkyrie Emerson (1-2) vs Madison The Butcher (1-0) - Madison Young & Ami Emerson.mp4", "Kink - Ultimate Surrender - 2009-07-07 - #6737 - SUMMER VENGEANCE TOURNAMENT MATCH UP! AMI EMERSON VS TIA LING - Tia Ling & Ami Emerson.mp4", "Kink - Ultimate Surrender - 2009-07-14 - #6814 - SUMMER VENGEANCE TOURNAMENT MATCH UP! AMBER RAYNE VS BELLA ROSSI - Amber Rayne & Bella Rossi.mp4", "Kink - Ultimate Surrender - 2009-08-11 - #6931 - SUMMER VENGEANCE TOURNAMENT MATCH UP! AMI EMERSON VS VENDETTA - Ami Emerson & Vendetta.mp4", "Kink - Ultimate Surrender - 2009-09-22 - #7283 - The Dragon (0-0) vs Jesse The Cheerleader Cox (0-0) - DragonLily & Jessie Cox.mp4", "Kink - Ultimate Surrender - 2009-09-29 - #7284 - Amber Rogue Rayne (0-0) vs Ashley The Fairy Jane (0-0) - Amber Rayne & Ashley Jane.mp4", "Kink - Ultimate Surrender - 2010-01-05 - #7944 - The Dragons vs The Goddesses Round 1 of the Semi-Finals Match up. - Ariel X, Ami Emerson, Holly Heart & Wenona.mp4", "Kink - Ultimate Surrender - 2010-01-12 - #7945 - The Dragons vs The Goddesses Round 2 of the Semi-Finals Match up. - Ariel X, Ami Emerson, Holly Heart & Wenona.mp4", "Kink - Ultimate Surrender - 2010-01-15 - #7678 - Trina Passion Michaels (0-0) vs Jesse The Cheerleader Cox (0-0) - Trina Michaels & Jessie Cox.mp4", "Kink - Ultimate Surrender - 2010-01-19 - #7946 - The Dragons vs The Goddesses Round 3 of the Semi-Finals Match up. - Ariel X, Ami Emerson, Holly Heart & Wenona.mp4", "Kink - Public Disgrace - 2012-06-22 - #23365 - Hot Blonde Fucked and Humiliated in Public - Lorelei Lee, Mark Davis & Ash Hollywood.mp4", "Kink - Sex And Submission - 2010-02-19 - #7518 - Sasha Knox - Mark Davis & Sasha Knox.mp4", "Kink - Sex And Submission - 2012-05-11 - #21163 - Maid To Suffer Punished and Fucked by her Employers! - Mickey Mod, Mark Davis, Lizzy London & Francesca Le.mp4", "Kink - Sex And Submission - 2012-05-18 - #21167 - Sadistic Therapy Delusional Patient gets Harsh Sexual Treatment - James Deen & Ash Hollywood.mp4", "Kink - Sex And Submission - 2012-06-22 - #24263 - Captured in the Woods A Featured Presentation Two Beautiful Blondes Brutally Fucked in the Wild - James Deen, Penny Pax & Anikka Albrite.mp4", "Kink - Sex And Submission - 2012-11-30 - #27062 - College Girl Ravished - Mr. Pete & Ash Hollywood.mp4", "Kink - Sex And Submission - 2014-09-26 - #36230 - The Adulteress - Steve Holmes & Penny Pax.mp4", "Kink - Sex And Submission - 2016-03-18 - #39659 - Penny Pax Anal Obsession - Penny Pax & Tommy Pistol.mp4", "Kink - Sex And Submission - 2016-06-24 - #40349 - My Slutty Sister - Penny Pax, Seth Gamble & Nicole Clitman.mp4", "Kink - Sex And Submission - 2016-08-19 - #40652 - A Slave's Love - Derrick Pierce & Nora Riley.mp4", "Kink - Sex And Submission - 2017-05-05 - #42137 - Captive Slut - John Strong & Penny Pax.mp4", "Kink - Sex And Submission - 2018-04-20 - #43305 - Anal Revenge - Penny Pax & Charles Dera.mp4", "Kink - Sex And Submission - 2018-09-21 - #43664 - Penny's Anal Embezzlement - Penny Pax & Stirling Cooper.mp4", "Kink - Sex And Submission - 2019-11-22 - #45388 - Kept Secrets Kate Kennedy and Stirling Cooper's Dark Fantasies - Stirling Cooper & Kate Kennedy.mp4", "Kink - Sex And Submission - 2020-01-17 - #45468 - Submissive Wife Kinky Anal Couple Explores Limits When No Means Yes - Penny Pax & Seth Gamble.mp4", "Kink - Sex And Submission - 2020-02-14 - #45512 - Hostile Takeover Boss Bitch Demi Sutra Dominated by Company Partner - Seth Gamble & Demi Sutra.mp4", "Kink - The Training Of O - 2012-10-26 - #25397 - Training Anikka Albrite - Day 1 - Anikka Albrite & Maestro Stefanos.mp4", "Kink - The Training Of O - 2012-11-23 - #25398 - Opening up Anikka Albrite Day Two - Anikka Albrite & Aiden Starr.mp4", "Kink - The Training Of O - 2012-12-14 - #25399 - Training Anikka Albright Day 3 - Anikka Albrite & Soma Snakeoil (Goddess Soma).mp4", "Kink - The Training Of O - 2012-12-28 - #25787 - Training Anikka Albrite, Day 4 - Derrick Pierce & Anikka Albrite.mp4", "Kink - The Training Of O - 2013-03-08 - #28386 - The Training of an Anal Slut, Day Two - Penny Pax & Owen Gray.mp4", "Kink - The Training Of O - 2015-10-23 - #39091 - Anal Sex Slave Penny Pax In Service - John Strong & Penny Pax.mp4", "Kink - The Training Of O - 2016-01-08 - #39302 - Slave Training Dallas Black - John Strong & Dallas Black.mp4", "Kink - The Training Of O - 2016-02-12 - #39663 - Nora Riley's Anal Slave Training - Owen Gray & Nora Riley.mp4", "Kink - The Upper Floor - 2010-02-08 - #8164 - Slave Review Holly Heart on the Upper Floor - Cherry Torn, Sarah Shevon & Holly Heart.mp4", "Kink - The Upper Floor - 2010-03-16 - #8398 - Sasha Knox Slave Review - Maestro, Cherry Torn, Bella Rossi & Sasha Knox.mp4", "Kink - The Upper Floor - 2010-11-24 - #9966 - House Supper and Slave Initiation - Holly Heart & Jessie Cox.mp4", "Kink - The Upper Floor - 2010-12-15 - #10722 - Dom's Dinner Party! - Maestro, Cherry Torn, Holly Heart, Jessie Cox & Kait Snow.mp4", "Kink - The Upper Floor - 2013-08-23 - #32146 - Showing Off the Newest Anal Sex House Slave - Casey Calvert, Bill Bailey & Alani Pi.mp4", "Kink - The Upper Floor - 2013-09-13 - #33977 - Beautiful Cock Suckers Petition the House - Mickey Mod, Penny Pax & Bella Rossi.mp4", "Kink - The Upper Floor - 2013-09-20 - #33978 - Beautiful Cock Suckers, Part Two - Mickey Mod, Penny Pax & Bella Rossi.mp4", "Kink - The Upper Floor - 2013-11-22 - #34340 - Masquerade Orgy with Nine Slaves,100 Horny Guests, Part Two - Maestro, Mickey Mod, Dylan Ryan, Penny Pax, Owen Gray, Simone Sonay, Beretta James, Casey Calvert, Nikki Darling, Bella Rossi, P....mp4", "Kink - The Upper Floor - 2013-12-06 - #34517 - Masquerade Orgy with Nine Slaves,100 Horny Guests, Part Three - Maestro, Mickey Mod, Dylan Ryan, Penny Pax, Owen Gray, Simone Sonay, Beretta James, Casey Calvert, Nikki Darling, Bella Rossi,....mp4", "Kink - The Upper Floor - 2014-01-31 - #34507 - Anal Slave Broken in by Gorgeous Chanel Preston - Angel Allwood, Bill Bailey & Chanel Preston.mp4", "Kink - The Upper Floor - 2014-04-25 - #35198 - Training the Ass Licking Fluffer - Tommy Pistol, Casey Calvert & Zoey Monroe.mp4", "Kink - The Upper Floor - 2014-05-09 - #35199 - The New Maid - Penny Pax, Xander Corvus & Jenna Ashley.mp4", "Kink - The Upper Floor - 2014-05-23 - #35202 - Initiating Aleksa Nicole - Karlo Karrera, Angel Allwood & Aleksa Nicole.mp4", "Kink - The Upper Floor - 2014-08-22 - #36030 - Big Titted Gold Digger Seduced into Submission - Erik Everhard, Summer Brielle & Christie Stevens.mp4", "Kink - The Upper Floor - 2014-09-19 - #36224 - Cock Service by Two Hot MILF Slaves - Ramon Nomar, Cherie DeVille & Shay Fox.mp4", "Kink - The Upper Floor - 2014-11-14 - #37046 - Costume Anal Orgy, Part One - Ramon Nomar, Penny Pax, Simone Sonay, Bill Bailey, Christie Stevens, Yhivi & Aiden Starr.mp4", "Kink - The Upper Floor - 2014-11-21 - #36723 - The Reluctant Slave - John Strong, Veruca James & Dakota Skye.mp4", "Kink - The Upper Floor - 2014-12-05 - #37047 - Costume Anal Orgy Part 2 - Ramon Nomar, Penny Pax, Simone Sonay, Bill Bailey, Christie Stevens, Yhivi & Aiden Starr.mp4", "Kink - The Upper Floor - 2014-12-12 - #36725 - Two Gorgeous Slaves Fight For Cock - Dahlia Sky, Bill Bailey & Sovereign Syre.mp4", "Kink - The Upper Floor - 2015-01-23 - #36605 - The Sex Toy and the New Maid - Ramon Nomar, Christie Stevens & Kasey Warner.mp4", "Kink - The Upper Floor - 2015-04-10 - #37661 - To Honor & Obey Virginal fiance trained for Sexual Slavehood - Tommy Pistol, Cadence Lux & Dani Daniels.mp4", "Kink - The Upper Floor - 2015-05-15 - #37851 - The Nympho Maid Dreams of Anal Ravaging - John Strong, Dahlia Sky & Cassidy Klein.mp4", "Kink - The Upper Floor - 2015-05-29 - #37852 - Chanel Preston's Anal Submission - Marco Banderas, Chanel Preston & Bianca Breeze.mp4", "Kink - The Upper Floor - 2015-09-25 - #38872 - Afternoon Delight Twin Set of Sex Slaves Well Used - Tommy Pistol, Bella Rossi & Dani Daniels.mp4", "Kink - The Upper Floor - 2015-10-16 - #39109 - Nerdy College Girl Turned Depraved Anal Slave - Dahlia Sky, Xander Corvus & Nickey Huntsman.mp4", "Kink - The Upper Floor - 2015-11-13 - #39111 - 18 year old Submissive Secretary Takes Her Punishment - Ramon Nomar, Mona Wales & Gina Valentina.mp4", "Kink - The Upper Floor - 2016-03-04 - #39335 - Slutty Slave Anal Orgy - John Strong, Marco Banderas, Penny Pax, Goldie Glock, Audrey Holiday, Aiden Starr & Aidra Fox.mp4", "Kink - The Upper Floor - 2016-04-29 - #40242 - The Steward's Birthday Slave Orgy - Mickey Mod, Marco Banderas, Veruca James, Nora Riley, Aiden Starr, Bobbi Dylan & Sydney Cole.mp4", "Kink - The Upper Floor - 2016-06-03 - #39851 - Tax Day The Slave and The Bad Girl's Anal Punishment - Dahlia Sky, Axel Aces & Zoey Laine.mp4", "Kink - The Upper Floor - 2016-06-10 - #40276 - The Anal Initiation of Dallas Black - John Strong, Rachael Madori & Dallas Black.mp4", "Kink - The Upper Floor - 2016-06-24 - #40243 - 100 Orgasm Slave Girl Orgy - Mickey Mod, Marco Banderas, Veruca James, Nora Riley, Aiden Starr, Bobbi Dylan & Sydney Cole.mp4", "Kink - The Upper Floor - 2016-10-04 - #40977 - Slave Orgy Unchained - Mickey Mod, Marco Banderas, Kira Noir, Bella Rossi, Mona Wales, Lilith Luxe & Aiden Starr.mp4", "Kink - The Upper Floor - 2017-04-28 - #41932 - The Final Upper Floor Orgy P. 1 - Cherry Torn, Ramon Nomar, Nora Riley & Aiden Starr.mp4", "Kink - The Upper Floor - 2017-06-27 - #41933 - Armory Upper Floor Finale Part 2 Nora's Debasement - Cherry Torn, Ramon Nomar, Nora Riley & Aiden Starr.mp4", "Kink - The Upper Floor - 2017-07-25 - #41934 - The Final Armory BDSM Orgy with a huge group orgasm! - Cherry Torn, Ramon Nomar, Nora Riley & Aiden Starr.mp4", "Kink - The Upper Floor - 2018-07-13 - #43572 - Uncollared Anal Cum Sluts Serve Swingers Ball - Ramon Nomar, Kendra Spade, Aiden Starr & Riley Reyes.mp4", "Kink - TS Pussy Hunters - 2012-06-01 - #22866 - Venus Lux - FIRST EVER SCENE - With a Fucking that Leaves Kaylee Breathless - Kaylee Hilton & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2012-08-10 - #24662 - Break In & Pay with Your Pussy Ts Venus Lux teaches a rookie a Lesson - Casey Cumz & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2012-09-07 - #24661 - Besties Fucking for the First Time After Venus Reveals her Secret Cock - Phoenix Askani & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2012-11-02 - #26323 - Hottest Fucking of Ts Cock in a Tight Pussy - Maia Davis & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2012-12-14 - #27084 - Sex-A-Gram - Alisha Adams & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2013-02-08 - #28990 - Energize a Penis onto Her Beautiful Latex Covered Crotch Sci-Fi SEX - Venus Lux & Caprice Capone.mp4", "Kink - TS Pussy Hunters - 2013-04-26 - #30196 - Fantasy Re-Enactment of Real Life Events TS Venus Seduces a ClassMate - Zoey Monroe & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2013-05-24 - #31366 - A Willingness to be Fucked TS Venus Hunts Another Pussy and ASS - Bella Wilde & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2013-07-19 - #31846 - Shower Hunter Jerking off under a towel REVEALS Her COCK - Venus Lux & Leah Cortez.mp4", "Kink - TS Pussy Hunters - 2013-08-23 - #32873 - What's Russian for Suck my Cock First Time Girl Fucked By TS Teacher - Mona Wales & Franchezka.mp4", "Kink - TS Pussy Hunters - 2013-09-06 - #31828 - Hey Neighbour, Lend me some Sugar. Just stick you cock in it first - Bella Rossi & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2013-11-01 - #34108 - Spanish Exchange Program Teacher Caught Masturbating - Luna Light & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2013-11-22 - #34109 - Bound PussyTS Venus Lux Fucks A tied up Pussy Cums Twice All over Her - Jessie Parker & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2013-12-13 - #34118 - Christmas Can Go Fuck Itself Or She can Fuck the Xmas Elf wher Cock - Mona Wales & Franchezka.mp4", "Kink - TS Pussy Hunters - 2014-01-24 - #34671 - Dirty Mind games Back Stage at the Miss America Pageant - Krissy Lynn & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-02-28 - #34672 - Space, The Final Frontier For Fucking - Venus Lux and Gia DiMarco - Gia DiMarco & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-03-14 - #34838 - MILF MAID Fucking the Help on the Kitchen Table. - Angel Allwood & Natassia Dreams.mp4", "Kink - TS Pussy Hunters - 2014-03-21 - #34836 - TS Venus Makes Darling say Awe with Her Cock in this Medical Role Play - Dee Williams & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-04-18 - #35175 - Venus Lux Gives a Bondage Lesson to New Kink Employee! - Mia Little & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-05-16 - #35513 - Hot and Dirty Party Sex with Tiffany Starr and Mona Wales - Mona Wales & Tiffany Starr.mp4", "Kink - TS Pussy Hunters - 2014-06-20 - #35761 - MILF Mother of the Bride Banged by Her Daughter's TS Lover - whoa! - Simone Sonay & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-08-08 - #35760 - Steamy Sauna, Hot Shower & Locker Room Sex with Venus Lux & Roxy Raye - Roxy Raye & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-08-29 - #35979 - Darling is Vaniity's Cock Mop. - Dee Williams & Vaniity.mp4", "Kink - TS Pussy Hunters - 2014-09-12 - #36182 - Venus Lux Takes Uses Her Cock to Solve Fight with Her MILF Neighbour - Syren de Mer & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-10-10 - #36186 - Plastic Surgeon Seduction - Venus Feels UP her Patient! - Amy Faye & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-10-17 - #35973 - Shoe Ladies Foot Fucking, Cock Sucking, Fingering, Squirting& Cumming - Mona Wales & Brenda Von Tease.mp4", "Kink - TS Pussy Hunters - 2014-11-07 - #36661 - Day dream of ATM and cream-pies for the Bitchy Big Tittied Blonde Boss - Alura Jenson & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2014-11-20 - #36747 - ULTIMATE SURRENDER & TSPUSSYHUNTERS DEBUT GIRL ON TS GIRL WRESTLING! - Bella Rossi, Mia Little, Jessica Fox & Kelly Klaymour.mp4", "Kink - TS Pussy Hunters - 2014-11-21 - #36748 - The Wrestling tag match Winners take Their PRIZE in the Sex Round! - Bella Rossi, Mia Little, Jessica Fox & Kelly Klaymour.mp4", "Kink - TS Pussy Hunters - 2015-01-16 - #37034 - Not in My Club -Natassia Dreams Schools Mona on the art of Rock n Roll - Mona Wales & Natassia Dreams.mp4", "Kink - TS Pussy Hunters - 2015-02-06 - #37295 - Swinger Party Private room with Venus Lux and Jessica Taylor - Venus Lux & Jessica Taylor.mp4", "Kink - TS Pussy Hunters - 2015-03-06 - #37502 - Ultimate Sex Fight Championship Bout! Winner fucks Loser Any WAY! - Holly Heart & Jessy Dubai.mp4", "Kink - TS Pussy Hunters - 2015-04-24 - #37937 - Sauna Stranger Surprise - Holly Heart & Natassia Dreams.mp4", "Kink - TS Pussy Hunters - 2015-07-03 - #38240 - Ultimate Sex Fight Championship with Kelly Klaymour and Mona Wales - Mona Wales & Kelly Klaymour.mp4", "Kink - TS Pussy Hunters - 2015-07-17 - #38615 - Venus Lux Seduces an Alt Tattoo Girl in her own studio. - Jessica Creepshow & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2015-08-14 - #38562 - Big Tittie Blond Nympho Milf Needs cock NOW - Alura Jenson & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2015-09-18 - #38722 - Dominated by a Sex Doll with Tits and Cock - Cherry Torn & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2015-09-22 - #38003 - Backstage Cat fight turns into hard core TS cock sucking and fucking - Mona Wales & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2015-09-25 - #38244 - Sexy Maids cleaning after a sex party start a sex party of their own - Angel Allwood & Kelly Klaymour.mp4", "Kink - TS Pussy Hunters - 2015-10-23 - #38866 - Chemistry Students accidentally discover the love potient - Ivy Addams & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2015-10-30 - #38862 - Scream!!!! with Orgasms. - Angel Allwood & TS Foxxy.mp4", "Kink - TS Pussy Hunters - 2015-12-25 - #39346 - A very Anal Xmas - Arabelle Raphael & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2016-01-08 - #39243 - Horny Electricians get their hands dirty - Penny Barber & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2016-02-12 - #39535 - TS Freya Wynn takes on Voluptuous Angel Allood for a sex fight - Angel Allwood & Freya Wynn.mp4", "Kink - TS Pussy Hunters - 2016-02-26 - #39344 - Great Fucking Pitch - Mona Wales & Kelli Lox.mp4", "Kink - TS Pussy Hunters - 2016-03-04 - #39369 - Coupon for a spa day leaves Nora Riley with a nice Facial - Nora Riley & Empress Taryn.mp4", "Kink - TS Pussy Hunters - 2016-04-29 - #39648 - fashionista Gets a Stylist Cream Pie in her Pussy From a Hot TS model - Charlotte Sartre & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2016-05-27 - #39816 - Strippers work on moves together and fuck each other's brains out - London River & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2016-07-08 - #40205 - LARP comic book Fans fuck and suck ass pussy and cock - Mona Wales & Isabella Sorrenti.mp4", "Kink - TS Pussy Hunters - 2016-07-22 - #40483 - AVN AWard Winning Stars Fuck in Sinn Sage's first Penis Experience - Sinn Sage & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2016-08-15 - #40465 - Elegant White Party turns into a bondage fuck fest in the bathroom - Sophia Grace & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2016-09-26 - #40582 - Angel Allwood is the gift that keeps on giving and receiving head - Angel Allwood, Jessica Fox & Kelli Lox.mp4", "Kink - TS Pussy Hunters - 2017-07-03 - #40113 - Evil Dungeon mistress gets her Dick fucked off by the perfect slaves - Cherry Torn, Mona Wales & Kelly Klaymour.mp4", "Kink - TS Pussy Hunters - 2017-08-14 - #42404 - The Evil Genie With a Weenie seduces Violet Monroe with her cock - Violet Monroe & Venus Lux.mp4", "Kink - TS Pussy Hunters - 2017-11-20 - #42461 - TS Cock Extracts Information Out Of Spies - Mona Wales & Chanel Santini.mp4", "Kink - TS Pussy Hunters - 2018-07-16 - #43518 - CamGirls After Hours Kelli Lox fucks submissive co-worker Mona Wales - Mona Wales & Kelli Lox.mp4", "Kink - TS Pussy Hunters - 2019-02-25 - #44132 - Starlet Punishment Maya Kendrick Learns a Hard Lesson from Jenna Creed - Maya Kendrick & Jenna Creed.mp4", "Kink - TS Pussy Hunters - 2019-04-22 - #44313 - Natalie Mars and Riley Reyes Hog Wild - Riley Reyes & Natalie Mars.mp4", "Kink - TS Pussy Hunters - 2019-06-17 - #44553 - Nightmare Nurse Ella Hollywood Fucks Nurse Cherie DeVille - Cherie DeVille & Ella Hollywood.mp4", "Kink - TS Pussy Hunters - 2019-07-15 - #44479 - Backdoor Burglars - Skylar Snow & Kayleigh Coxx.mp4", "Kink - TS Pussy Hunters - 2019-07-29 - #44816 - Twisted Intervention Korra Del Rio Turns the Tables on Mona Wales - Mona Wales & Korra Del Rio.mp4", "Kink - TS Pussy Hunters - 2019-08-12 - #44640 - Submissive Protocol Natassia Dreams Creates Perfect Doll Ana Foxxx - Ana Foxxx & Natassia Dreams.mp4", "Kink - TS Pussy Hunters - 2019-08-26 - #44639 - Caged Heat Maya Kendrick turns the tables on her boss Lianna Lawson - Maya Kendrick & Lianna Lawson.mp4", "Kink - TS Pussy Hunters - 2020-01-13 - #45366 - The Subletter Casey Kisses Fucks Maya Kendrick to Many Anal Orgasms - Maya Kendrick & Casey Kisses.mp4", "Kink - TS Pussy Hunters - 2020-03-23 - #45625 - The Smut Peddlers Part One Casey Kisses and Chanel Preston - Chanel Preston & Casey Kisses.mp4", "Kink - TS Pussy Hunters - 2020-04-20 - #45627 - The Smut Peddlers Part Three Korra Del Rio and Skylar Snow - Skylar Snow & Korra Del Rio.mp4", "Kink - TS Seduction - 2012-06-27 - #23420 - Welcome The Newest Ts Dom - Venus Marks her Man and then Shoves Her Cock in His Ass - Mike Panic & Venus Lux.mp4", "Kink - TS Seduction - 2013-01-09 - #27850 - Feature UpdateThe Dom Next Door Turns Sting Operation into Threesome - Chad Diamond, Nicki Hunter & Venus Lux.mp4", "Kink - TS Seduction - 2013-01-23 - #27853 - Ball Torment and Real BTS fucking with a Classic Ts Seduction Set-up - Lance Hart & Venus Lux.mp4", "Kink - TS Seduction - 2013-03-13 - #29632 - TS Venus and her Giant Cum Load - Seducing Her Body Guard - Alex Adams & Venus Lux.mp4", "Kink - TS Seduction - 2013-04-17 - #30473 - ONE OF THE HOTTEST, MOST ORGASM DENIAL & HUGE POP SHOTS SCENES EVER! - Blake & Venus Lux.mp4", "Kink - TS Seduction - 2013-05-15 - #29634 - Revenge Fuck Venus Kills Jealousy wHer Cock & Her Ex-BF's Tight Hole - Andrew Blue & Venus Lux.mp4", "Kink - TS Seduction - 2013-06-05 - #30900 - TS THREESOME SEDUCING & FUCKING THE BLACKMAILING COLLEGE DEAN - Sebastian Keys, Francesca Le & Venus Lux.mp4", "Kink - TS Seduction - 2013-11-13 - #31322 - Not Every Dungeon is Dark Real Life POV wTS Venus Lux in YOUR HOUSE - Connor Patricks & Venus Lux.mp4", "Kink - TS Seduction - 2014-04-09 - #35174 - Venus Lux gives an anal cream pie to a cocky professional athlete! - Reed Jameson & Venus Lux.mp4", "Kink - TS Seduction - 2014-04-23 - #35352 - Happy Anniversary Baby The Girlfriend Hires the Dom for the Boyfriend - Mona Wales, Tony Orlando & TS Foxxy.mp4", "Kink - TS Seduction - 2014-09-30 - #35168 - BONUS VENUS LUX POV SHOOT - SHE FUCKS YOU! - Venus Lux & Joey Rico.mp4", "Kink - TS Seduction - 2014-10-22 - #36660 - Venus Lux; The Final Affair - Will Havoc & Venus Lux.mp4", "Kink - TS Seduction - 2014-12-03 - #36957 - Take Your Blackmail and SHOVE IT UP YOUR ass on the end of My Cock - Alexander Gustavo & Venus Lux.mp4", "Kink - TS Seduction - 2015-01-07 - #36958 - Sexual Identity Experiment Venus Lux in Hospital Threesome Feature! - Bella Rossi, Sam Solo & Venus Lux.mp4", "Kink - TS Seduction - 2015-02-18 - #37296 - Anger Management Therapy - VENUS LUX Fucks & gets Fucked! - Abel Archer & Venus Lux.mp4", "Kink - TS Seduction - 2015-08-05 - #38589 - Mistress Venus Lux and Her Dominating Cock! - Sergeant Miles & Venus Lux.mp4", "Kink - TS Seduction - 2015-08-26 - #38736 - Venus Lux and Her Seductive Cock! - DJ & Venus Lux.mp4", "Kink - TS Seduction - 2015-09-16 - #38925 - Venus Lux Breaks In The Newbie On Her Solid Cock - Javier LoveTongue & Venus Lux.mp4", "Kink - TS Seduction - 2015-11-19 - #39282 - Bad Ass Boss Lady Venus Lux Gives DJ a Thorough Review! - DJ & Venus Lux.mp4", "Kink - TS Seduction - 2015-12-23 - #39425 - Oral Fixations with Venus Lux - Jay West & Venus Lux.mp4", "Kink - TS Seduction - 2016-03-23 - #39855 - Delivery Man Worships Feet and Gets Fucked - Sebastian Keys & Venus Lux.mp4", "Kink - TS Seduction - 2016-06-15 - #40535 - Spit Balling TS Cum For Couples - DJ, Danielle Foxx & Venus Lux.mp4", "Kink - TS Seduction - 2016-08-16 - #40726 - Hot for Nurse! Dr. Lux Treats Patient with Dose of Thick Cock! - Shawn Fox & Venus Lux.mp4", "Kink - TS Seduction - 2016-09-27 - #41075 - Goddess Venus Punishes Arrogant Boy Toy - Reed Jameson & Venus Lux.mp4", "Kink - TS Seduction - 2016-11-08 - #41183 - Huge Fat Load Of TS Cum For A Politician - D. Arclyte & Venus Lux.mp4", "Kink - TS Seduction - 2016-12-13 - #41510 - Her Willing Slave - Mike Panic & Venus Lux.mp4", "Kink - TS Seduction - 2017-01-03 - #41485 - Slutty TA gets T&A from DTF Ts School Administrator VENUS LUX! NSFW!!! - Artemis Faux & Venus Lux.mp4", "Kink - TS Seduction - 2017-02-07 - #41585 - Venus Lux Takes Down The Building Manager - Rick Fantana & Venus Lux.mp4", "Kink - TS Seduction - 2017-03-07 - #41736 - Cramming Anatomy 101 With Venus Lux - Tony Orlando, Mercy West & Venus Lux.mp4", "Kink - TS Seduction - 2017-10-17 - #42613 - Sensual Domme Venus Lux Gets Worshiped and Fucks Her Obedient Slave - Ruckus & Venus Lux.mp4", "Kink - Ultimate Surrender - 2005-05-03 - #2799 - The Spider (0-0) vs. The Sexinator (0-1) - Princess Donna Dolore & Jessica Sexin.mp4", "Kink - Ultimate Surrender - 2005-06-21 - #2915 - The Spider (1-0) vs. Firestorm (0-0) - Princess Donna Dolore & Nicole Scott.mp4", "Kink - Ultimate Surrender - 2005-11-29 - #3251 - The Spider vs. Kat - Princess Donna Dolore & Kat.mp4", "Kink - Ultimate Surrender - 2006-02-28 - #3438 - The Amazon (2-5) The Grappler (0-0) - Dee Williams & Hollie Stevens.mp4", "Kink - Ultimate Surrender - 2006-04-04 - #3458 - The Dragon (13-4) The Grappler (0-1) - Dee Williams & DragonLily.mp4", "Kink - Ultimate Surrender - 2006-04-14 - #3371 - The Pirate (10-1) J.J. (0-0) - Justine Joli & Nina.mp4", "Kink - Ultimate Surrender - 2006-05-09 - #3530 - The Grappler (0-2) Kat (0-3) - Dee Williams & Kat.mp4", "Kink - Ultimate Surrender - 2006-06-13 - #3698 - The Grappler (1-2) The Scorpion (0-1) - Annie Cruz & Dee Williams.mp4", "Kink - Ultimate Surrender - 2006-07-04 - #3665 - The Deceptacon (1-1) The Grappler (2-2) - Dee Williams & Julie Night.mp4", "Kink - Ultimate Surrender - 2006-07-25 - #3667 - The Ninja (18-2) The Grappler (3-2) - Dee Williams & Crimson Ninja.mp4", "Kink - Ultimate Surrender - 2006-08-01 - #3699 - The Jester (1-3) The Grappler (3-3) - Dee Williams & Dana DeArmond.mp4", "Kink - Ultimate Surrender - 2006-08-22 - #3746 - The Grappler (4-3) The Goddess (5-2) - Dee Williams & Isis Love.mp4", "Kink - Ultimate Surrender - 2006-10-03 - #3969 - The Pirate(0-0) The Killer(0-0) - Bobbi Starr & Nina.mp4", "Kink - Ultimate Surrender - 2006-10-10 - #3989 - The Grappler(0-0) The Green Machine(0-0) - Dee Williams & Shannon Kelly.mp4", "Kink - Ultimate Surrender - 2006-11-14 - #3999 - The Jester (2-5) The Killer (0-1) - Bobbi Starr & Dana DeArmond.mp4", "Kink - Ultimate Surrender - 2006-12-26 - #4068 - The Killer (1-1) Rogue (0-0) - Amber Rayne & Bobbi Starr.mp4", "Kink - Ultimate Surrender - 2006-12-29 - #4091 - The Dragon (18-5) ranked 3rd The Grappler (5-4) ranked 5th - Dee Williams & DragonLily.mp4", "Kink - Ultimate Surrender - 2007-01-30 - #4112 - The Dragon (20-5) Ranked 3rd The Slayer (0-2) Not Ranked - DragonLily & Sammie Rhodes.mp4", "Kink - Ultimate Surrender - 2007-03-13 - #4289 - The Killer (3-1) Ranked 6th Blondie (0-1) Ranked 12th - Sarah Jane Ceylon & Bobbi Starr.mp4", "Kink - Ultimate Surrender - 2007-07-03 - #4393 - TAG TEAM The Goddess & The Killer vs The Gymnast & The Tsunami - Bobbi Starr, Isis Love, Wenona & Christina Aguchi.mp4", "Kink - Ultimate Surrender - 2007-08-03 - #4667 - SPECIAL WEEKEND EXTRA BONUS UPDATE. Porn Legend Ginger Lynn Bobbi Starr The Killer - Bobbi Starr & Ginger Lynn.mp4", "Kink - Ultimate Surrender - 2007-10-02 - #4761 - Bobbie Starr The Killer (4-1) vs Smokie Flame The Phoenix (0-0) - Bobbi Starr & Smokie Flame.mp4", "Kink - Ultimate Surrender - 2007-12-18 - #4960 - Vendetta (13-3) Ranked 1st vs Samantha Sin  The Python Not ranked - Samantha Sin & Vendetta.mp4", "Kink - Ultimate Surrender - 2008-01-29 - #5018 - Ariel X The Assassin (5-2) vs Samantha Sin The Python (0-1) - Samantha Sin & Ariel X.mp4", "Kink - Ultimate Surrender - 2008-03-04 - #5060 - Annie Cruz The Scorpion (1-5) vs Samantha Sin The Python (0-2) - Samantha Sin & Annie Cruz.mp4", "Kink - Ultimate Surrender - 2008-04-01 - #5188 - Samantha Sin The Python (1-2) vs Sarah Jane CeylonBlondie(1-5) - Sarah Jane Ceylon & Samantha Sin.mp4", "Kink - Ultimate Surrender - 2008-06-03 - #5418 - SUMMER VENGEANCE CONTINUES! This is the second elimination match of the first round. - Samantha Sin & Sabrina Fox.mp4", "Kink - Ultimate Surrender - 2008-07-01 - #5465 - SUMMER VENGEANCE CONTINUES! This is the second elimination match of the second round. - Samantha Sin & Brix.mp4", "Kink - Ultimate Surrender - 2008-07-08 - #5544 - SUMMER VENGEANCE CONTINUES! This is the third elimination match of the second round. - Amber Rayne & Dia Zerva.mp4", "Kink - Ultimate Surrender - 2008-10-07 - #5797 - Ariel X The Assassin (1-0) vs Ami Emerson The Valkyrie (0-0) - Ariel X & Ami Emerson.mp4", "Kink - Ultimate Surrender - 2008-11-25 - #5890 - Samantha Sin The Python (0-0) vs Penny Play The Tarrasque (0-0) - Samantha Sin & Penny Barber.mp4", "Kink - Ultimate Surrender - 2008-12-09 - #5959 - Vendetta (2-0) vs Ami The Valkyrie Emerson (0-1) - Ami Emerson & Vendetta.mp4", "Kink - Ultimate Surrender - 2009-02-03 - #6121 - Hollie Stevens The Amazon (1-1) vs Ami Emerson The Valkyrie (0-1) - Hollie Stevens & Ami Emerson.mp4", "Kink - Ultimate Surrender - 2009-02-24 - #6169 - Amber Rogue Rayne (0-0) vs Sinn  The Natural Sage (0-0) - Amber Rayne & Sinn Sage.mp4",
                // "--from", "2020-01-01",
                // "--to", "2020-12-31",
                "--verbose",
                "--best",
                */
                
                /*
                "migrate",
                "--site-short-name", siteShortName,
                */
            };
        }
        
        // Use this for EF migrations:
        /*
        var host = AppHostFactory.CreateHost(args, "sexart");
        var cultureExtractor = AppHostFactory.CreateCultureExtractorConsoleApp(host);
        cultureExtractor.ExecuteConsoleApp(args);
        */
        
        // Use this when running the application:
        // /*
        var options = (BaseOptions) Parser.Default.ParseArguments<ScrapeOptions, DownloadOptions, MigrateOptions>(args).Value;
        var host = AppHostFactory.CreateHost(args, options?.SiteShortName ?? string.Empty);
        var cultureExtractor = AppHostFactory.CreateCultureExtractorConsoleApp(host);
        cultureExtractor.ExecuteConsoleApp(args);
        // */
    }
}

public class BaseOptions
{
    [Option(
        Default = false,
        HelpText = "Prints all messages to standard output.")]
    public bool Verbose { get; set; }
    
    [Option("site-short-name", Required = true, HelpText = "Site short name")]
    public string SiteShortName { get; set; }
}

public class SiteOptions : BaseOptions
{
    [Option("sub-site-short-name", Required = false, HelpText = "Sub site short name")]
    public string SubSite { get; set; }

    [Option("browser-mode",
      Default = BrowserMode.Headless,
      HelpText = "Browser mode (Headless, ClassicHeadless, Visible)")]
    public BrowserMode BrowserMode { get; set; }

    [Option("browser-channel", Required = false, HelpText = "Browser channel")]
    public string? BrowserChannel { get; set; }

    [Option("max-scenes", Default = int.MaxValue, HelpText = "How many scenes to process")]
    public int MaxReleases { get; set; }

    [Option("reverse-order", Required = false, HelpText = "Scrape/download scenes in reverse order (i.e. from latest to oldest)")]
    public bool ReverseOrder { get; set; }
}

[Verb("scrape", HelpText = "Scrape")]
public class ScrapeOptions : SiteOptions
{
    [Option(
      "full",
      Default = false,
      HelpText = "Full scrape including update existing scenes")]
    public bool FullScrape { get; set; }

    [Option(
      "guest-mode",
      Default = false,
      HelpText = "Uses guest mode for scraping (i.e. doesn't require subscription)")]
    public bool GuestMode { get; set; }

    [Option(
      "full-scrape-last-updated",
      Default = null,
      HelpText = "Full scrape including update existing scenes")]
    public DateTime? FullScrapeLastUpdated { get; set; }

    [Option("reverse-order", Required = false, HelpText = "Scrape scenes in reverse order (i.e. from latest to oldest)")]
    public bool ReverseOrder { get; set; }
}

[Verb("download", HelpText = "Download")]
public class DownloadOptions : SiteOptions
{
    [Option("from", Required = false, HelpText = "From date")]
    public string FromDate { get; set; }

    [Option("to", Required = false, HelpText = "To date")]
    public string ToDate { get; set; }

    [Option("best", Required = false, HelpText = "Use best quality")]
    public bool BestQuality { get; set; }

    [Option("releases", Required = false, HelpText = "One or more release UUIDs to download")]
    public IEnumerable<string> ReleaseUuids { get; set; }

    [Option("performers", Required = false, HelpText = "One or more performers to download")]
    public IEnumerable<string> Performers { get; set; }

    [Option("downloaded-file-names", Required = false, HelpText = "Downloaded file names which should be re-downloaded with best quality")]
    public IEnumerable<string> DownloadedFileNames { get; set; }
}

[Verb("migrate", HelpText = "Migrate")]
public class MigrateOptions : BaseOptions
{
}
