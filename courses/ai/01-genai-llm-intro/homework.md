# ორი პროვაიდერი, ერთი endpoint — და ხარჯის გათვლა

შენი API პროექტის AI ლაბორატორია იზრდება

## მოთხოვნები

- `AskRequest` + **Provider** (`ollama` / `gemini`) · `AskResponse` + **Model**, **ElapsedMs**
- provider-ის მიხედვით — სხვა `IChatClient`; `Ask`-ის კოდი **ერთი** რჩება
- 3 კითხვა შენს თემაზე, ორივე პროვაიდერზე (Ollama და Gemini) → შედარების ცხრილი `README.md`-ში
- თვის ხარჯი: **გაზომილი** ტოკენები × **რეალური** ფასი → `README.md`

## ✓ მზადაა, როცა

ორივე პროვაიდერი მუშაობს მხოლოდ `"provider"` ველის შეცვლით; README-ში — ცხრილი და ხარჯის ფორმულა

## ⭐ ბონუსი

- ვალიდაცია: უცნობი provider ან Temperature 0–2-ის გარეთ → `400 BadRequest`
- Ollama გამორთულია → `503` გასაგები შეტყობინებით და არა 500

## 💡 დეტალები

- `Provider`-ის ნაგულისხმევი მნიშვნელობა — `"ollama"`; `ElapsedMs` — `Stopwatch`-ით
- შედარების ცხრილი: ყოველ კითხვაზე, ორივე პროვაიდერზე — დრო (ms), input/output ტოკენები, ქართულის ხარისხი 1–5
- ხარჯი: აირჩიე შენი პროექტის ერთი AI ფუნქცია, დაუშვი მოთხოვნების რაოდენობა დღეში, აიღე Swagger-ში გაზომილი საშუალო ტოკენები და Gemini-ის მოდელის ფასი მისი pricing გვერდიდან (ai.google.dev/pricing) — თითქოს უფასო ლიმიტი ამოიწურა

## 💡 მინიშნება

ობიექტის შექმნა ცალკე მეთოდში გაიტანე — `switch` expression-ით:

```csharp
private static IChatClient CreateClient(string provider) => provider switch
{
    "ollama" => new OllamaApiClient(...),
    "gemini" => new Client().AsIChatClient(...),
    _ => throw new ArgumentException(...)
};
```

`IChatClient` არის `IDisposable` — თუ client-ს ყოველ მოთხოვნაზე ქმნი, `using` გამოიყენე. API key — მხოლოდ გარემოს ცვლადში (`GEMINI_API_KEY`), არასდროს კოდში ან Git-ში.

## ამოხსნა

DTO-ები: ახალი ველები ბოლოშია და ნაგულისხმევი მნიშვნელობა აქვთ — ძველი მოთხოვნები ისევ მუშაობს.

```csharp Dtos/AiLab/AskDtos.cs
public record AskRequest(
    string Prompt,
    string Provider = "ollama",
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

პროვაიდერის არჩევა — ერთ ადგილას. ეს არის ერთადერთი კოდი, რომელმაც იცის Ollama-ს და Gemini-ის შესახებ:

```csharp Controllers/AiLabController.cs !
private static IChatClient CreateClient(string provider) => provider switch
{
    "ollama" => new OllamaApiClient(
        new Uri("http://localhost:11434"), "llama3.2"),

    "gemini" => new Client()                 // key — GEMINI_API_KEY ცვლადიდან
        .AsIChatClient("gemini-3.8-flash"),

    _ => throw new ArgumentException($"უცნობი პროვაიდერი: {provider}")
};
```

`Ask` — ბონუსით:

```csharp Controllers/AiLabController.cs
[HttpPost("ask")]
public async Task<IActionResult> Ask(AskRequest request)
{
    if (request.Provider is not ("ollama" or "gemini"))
        return BadRequest("Provider: ollama ან gemini");
    if (request.Temperature is < 0 or > 2)
        return BadRequest("Temperature: 0-დან 2-მდე");

    using IChatClient chat = CreateClient(request.Provider);
    var options = new ChatOptions
    {
        Temperature = request.Temperature,
        MaxOutputTokens = request.MaxOutputTokens
    };

    var stopwatch = Stopwatch.StartNew();
    try
    {
        ChatResponse response = await chat.GetResponseAsync(request.Prompt, options);

        return Ok(new AskResponse(
            response.Text,
            response.ModelId ?? request.Provider,
            response.Usage?.InputTokenCount,
            response.Usage?.OutputTokenCount,
            response.FinishReason?.Value,
            stopwatch.ElapsedMilliseconds));
    }
    catch (HttpRequestException)
    {
        return StatusCode(503, "მოდელი მიუწვდომელია — გაშვებულია Ollama?");
    }
}
```

საჭირო `using`-ები: `System.Diagnostics` (Stopwatch), `Microsoft.Extensions.AI`, `OllamaSharp`, `Google.GenAI`. NuGet: `Google.GenAI`.

ხარჯის გათვლის ნიმუში README-სთვის:

```text
ფუნქცია: წიგნის მოკლე აღწერის გენერაცია
მოთხოვნები: 200 დღეში × 30 დღე = 6 000 თვეში
გაზომილი საშუალო: input 180 ტოკენი, output 120 ტოკენი
input:  6 000 × 180 = 1 080 000 ტოკენი = 1.08M
output: 6 000 × 120 =   720 000 ტოკენი = 0.72M
ხარჯი = 1.08 × [input ფასი 1M-ზე] + 0.72 × [output ფასი 1M-ზე]
```

```note
`response.ModelId` ზოგი provider-ისთვის `null`-ია, ამიტომ `?? request.Provider`. ამოხსნაში client ყოველ მოთხოვნაზე იქმნება და `using`-ით იხურება — ეს დროებითი გადაწყვეტაა. ლექცია 3-ზე ორივე client DI-ში დარეგისტრირდება და Controller-ს constructor-ით შემოვა.
```
