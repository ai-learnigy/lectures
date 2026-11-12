# ორი Gemini მოდელი, ერთი endpoint — და ხარჯის გათვლა

შენი API პროექტის AI ლაბორატორია იზრდება

## მოთხოვნები

- `AskRequest` + **Model** (არასავალდებულო) → `ChatOptions.ModelId` · `AskResponse` + **Model**, **ElapsedMs**
- დაშვებულია **2 მოდელი** სიიდან: ერთი სწრაფი/იაფი, ერთი ძლიერი; client ერთია
- 3 კითხვა შენს თემაზე, ორივე მოდელზე → შედარების ცხრილი `README.md`-ში
- თვის ხარჯი ორივე მოდელზე: **გაზომილი** ტოკენები × **რეალური** ფასი → `README.md`

## ✓ მზადაა, როცა

ერთი endpoint ორივე მოდელით მუშაობს მხოლოდ `"model"` ველის შეცვლით; README-ში — ცხრილი და ხარჯის ფორმულა

## ⭐ ბონუსი

- ვალიდაცია: დაუშვებელი მოდელი ან Temperature 0–2-ის გარეთ → `400 BadRequest`
- Gemini-ს შეცდომა (key, ლიმიტი) → გასაგები პასუხი და არა 500

## 💡 დეტალები

- მოდელების სახელები და ფასები: [მოდელები](https://ai.google.dev/gemini-api/docs/models) · [ფასები](https://ai.google.dev/gemini-api/docs/pricing)
- `Model`-ის ნაგულისხმევი — ის, რაც `AsIChatClient("...")`-ში წერია; `ElapsedMs` — `Stopwatch`-ით
- ცხრილი: ყოველ კითხვაზე, ორივე მოდელზე — დრო (ms), input/output ტოკენები, ქართულის ხარისხი 1–5
- ხარჯი: აირჩიე შენი პროექტის ერთი AI ფუნქცია, დაუშვი მოთხოვნების რაოდენობა დღეში, აიღე Swagger-ში გაზომილი საშუალო ტოკენები და ორივე მოდელის ფასი pricing გვერდიდან (თითქოს უფასო ლიმიტი ამოიწურა)

## 💡 მინიშნება

client-ს `AsIChatClient("…")`-ში ნაგულისხმევი მოდელი აქვს, მაგრამ ცალკეულ მოთხოვნაში მოდელი შეიძლება შეცვალო `ChatOptions`-ით — ახალი client არ გჭირდება:

```csharp
var options = new ChatOptions { ModelId = "…" };
```

API key — მხოლოდ გარემოს ცვლადში (`GEMINI_API_KEY`), არასდროს კოდში ან Git-ში.

## ამოხსნა

DTO-ები: ახალი ველები ბოლოშია და ნაგულისხმევი მნიშვნელობა აქვთ — ძველი მოთხოვნები ისევ მუშაობს.

```csharp Dtos/AiLab/AskDtos.cs
public record AskRequest(
    string Prompt,
    string? Model = null,
    float? Temperature = null,
    int? MaxOutputTokens = null);

public record AskResponse(
    string Text,
    string Model,
    long? InputTokens,
    long? OutputTokens,
    string? FinishReason,
    long ElapsedMs);
```

მოდელის არჩევა — `ChatOptions`-ით. client ერთია, იცვლება მხოლოდ `ModelId`:

```csharp Controllers/AiLabController.cs !
private const string DefaultModel = "gemini-3.8-flash";
private static readonly string[] AllowedModels = [DefaultModel, "gemini-3.8-pro"];

// Ask-ში:
string model = request.Model ?? DefaultModel;
if (!AllowedModels.Contains(model))
    return BadRequest($"Model: {string.Join(" ან ", AllowedModels)}");

var options = new ChatOptions
{
    ModelId = model,
    Temperature = request.Temperature,
    MaxOutputTokens = request.MaxOutputTokens
};
```

მთლიანი Controller, ბონუსით:

```csharp Controllers/AiLabController.cs
[ApiController]
[Route("api/ai-lab")]
public class AiLabController : ControllerBase
{
    private const string DefaultModel = "gemini-3.8-flash";
    private static readonly string[] AllowedModels = [DefaultModel, "gemini-3.8-pro"];

    private readonly IChatClient _chat = new Client().AsIChatClient(DefaultModel);

    [HttpPost("ask")]
    public async Task<IActionResult> Ask(AskRequest request)
    {
        string model = request.Model ?? DefaultModel;
        if (!AllowedModels.Contains(model))
            return BadRequest($"Model: {string.Join(" ან ", AllowedModels)}");
        if (request.Temperature is < 0 or > 2)
            return BadRequest("Temperature: 0-დან 2-მდე");

        var options = new ChatOptions
        {
            ModelId = model,
            Temperature = request.Temperature,
            MaxOutputTokens = request.MaxOutputTokens
        };

        var stopwatch = Stopwatch.StartNew();
        try
        {
            ChatResponse response = await _chat.GetResponseAsync(request.Prompt, options);

            return Ok(new AskResponse(
                response.Text,
                response.ModelId ?? model,
                response.Usage?.InputTokenCount,
                response.Usage?.OutputTokenCount,
                response.FinishReason?.Value,
                stopwatch.ElapsedMilliseconds));
        }
        catch (Exception ex)
        {
            return StatusCode(503, $"Gemini-მ ვერ უპასუხა: {ex.Message}");
        }
    }
}
```

საჭირო `using`-ები: `System.Diagnostics` (Stopwatch), `Microsoft.Extensions.AI`, `Google.GenAI`.

ხარჯის გათვლის ნიმუში README-სთვის:

```text
ფუნქცია: წიგნის მოკლე აღწერის გენერაცია
მოთხოვნები: 200 დღეში × 30 დღე = 6 000 თვეში
გაზომილი საშუალო: input 180 ტოკენი, output 120 ტოკენი
input:  6 000 × 180 = 1 080 000 ტოკენი = 1.08M
output: 6 000 × 120 =   720 000 ტოკენი = 0.72M
ხარჯი = 1.08 × [input ფასი 1M-ზე] + 0.72 × [output ფასი 1M-ზე]   ← ორივე მოდელზე ცალ-ცალკე
```

```note
მოდელების სახელები (`gemini-3.8-flash`, `gemini-3.8-pro`) აქ ნიმუშია — ზუსტი სახელები მოდელების სიიდან აიღე, ისინი იცვლება. `catch (Exception)` ლაბორატორიისთვის საკმარისია; შეცდომების სწორ დამუშავებას (Retry, 429, Fallback მოდელი) ლექცია 8-ზე ვისწავლით. Gemini-ს მოდელები „ფიქრობენ“ — ფიქრის ტოკენებსაც ვიხდით, ამიტომ output შეიძლება მეტი გამოვიდეს, ვიდრე პასუხის ტექსტი.
```
