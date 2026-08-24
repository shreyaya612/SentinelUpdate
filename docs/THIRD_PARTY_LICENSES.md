# Third-Party Components & Licenses

SentinelUpdate uses only open-source, permissively-licensed third-party
components. No proprietary or restrictively-licensed code is included.

| Component | License | Purpose |
|---|---|---|
| [Flask](https://github.com/pallets/flask) | BSD-3-Clause | Web backend / REST API |
| [google-genai](https://github.com/googleapis/python-genai) | Apache 2.0 | Official Google SDK for the Gemini API |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD-3-Clause | Loads local `.env` configuration |
| Gemini API (`gemini-2.5-flash`) | [Google AI Terms of Service](https://ai.google.dev/gemini-api/terms) | AI explanation & changelog analysis layer — accessed via API, no model weights redistributed |

## AI model disclosure

SentinelUpdate does **not** train or fine-tune any model. It calls Google's
hosted Gemini API (`gemini-2.5-flash`) at inference time via the official
`google-genai` SDK. All rule-based scoring logic (the component that
actually determines the risk score) is original, in-house code and does not
depend on any third-party model or dataset.

## Data use

SentinelUpdate collects and transmits no user data to any third party beyond
what is sent to the Gemini API for explanation generation: package names,
version strings, and (in deep-analysis mode) public changelog text — none of
which is personal or sensitive data. No telemetry, analytics, or tracking is
included in the codebase.