# Product Requirements Document  
**Pydantic-AI Multi-Agent System**

---

## 1. Overview

**Goal:**  
Build a modular, Pydantic-AI-driven multi-agent framework with an **OrchestratorAgent** that dispatches to specialized agents (YouTube, Weather, two Research pipelines, Report Writer), validates all I/O via Pydantic models, and streams results through a Streamlit chat UI.

---

## 2. User Interface  
- **Streamlit Chat App**  
  - Single-page chat interface  
  - User enters a “job” (e.g. “Research X and summarize”)  
  - Orchestrator streams back partial & final responses in real time  

---

## 3. Functional Requirements  

| ID    | Requirement                                                                                                                                     |
|-------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| **FR1** | **Streamlit Chat**: conversational UI to submit jobs and stream back partial/full responses.                                                  |
| **FR2** | **YouTubeAgent**: fetch transcript + metadata for a given URL.                                                                                |
| **FR3** | **WeatherAgent**: retrieve current + 7-day forecast via OpenWeather API.                                                                      |
| **FR4** | **ResearchPipeline1 (Tavily)**  
&nbsp;&nbsp;&nbsp;1. Expand user query → 3 sub-questions (past, present, future).  
&nbsp;&nbsp;&nbsp;2. Parallel Tavily API searches  
&nbsp;&nbsp;&nbsp;3. CleaningAgent → universal research template  
| **FR5** | **ResearchPipeline2 (DuckDuckGo MCP)**  
&nbsp;&nbsp;&nbsp;1. Expand user query → 3 sub-questions  
&nbsp;&nbsp;&nbsp;2. Dispatch each to DuckDuckGo MCP via Pydantic-AI’s MCP client  
&nbsp;&nbsp;&nbsp;3. CleaningAgent → universal research template  
| **FR6** | **ReportWriterAgent**: ingest either `ResearchPipelineModel` or `YouTubeTranscriptModel`, then generate & refine (synthesis + edit loop) reports in styles: comprehensive, top-10, summary. |
| **FR7** | All agent I/O strictly typed via Pydantic models; assembled under a single `MasterOutputModel`.                                               |
| **FR8** | Utilize **Pydantic-AI’s built-in retry** logic on all downstream calls (Tavily, MCP, OpenWeather, YouTube).                                 |
| **FR9** | Single Python entrypoint under the OpenAI SDK drives the OrchestratorAgent.                                                                  |

---

## 4. System Architecture

```
┌───────────────────────────┐
│    Streamlit Chat UI     │
└─────────────┬─────────────┘
              │
   ┌──────────▼──────────┐
   │ OrchestratorAgent   │ ← Pydantic-AI Agent
   │ • dispatch("youtube")       │
   │ • dispatch("weather")       │
   │ • dispatch("research1")     │
   │ • dispatch("research2")     │
   │ • dispatch("report_writer") │
   │ • aggregate outputs         │
   └──────────┬───────────┘
              │
    ┌─────────┴───────────┐
    │  Registered Agents  │
    │                     │
    │  YouTubeAgent       │
    │  WeatherAgent       │
    │  Research1Agent     │
    │  Research2Agent     │
    │  ReportWriterAgent  │
    └─────────────────────┘
```

- **Each pipeline** lives as its own Pydantic-AI Agent class, external to the orchestrator.  
- **OrchestratorAgent** itself is a standalone Pydantic-AI Agent, referencing each by name.

---

## 5. Data Model Hierarchy  

_All sub-models are fields of_ `MasterOutputModel`:

```python
from pydantic import BaseModel, HttpUrl
from typing import List, Dict

class YouTubeTranscriptModel(BaseModel):
    url: HttpUrl
    transcript: str
    metadata: Dict[str, str]

class WeatherData(BaseModel):
    timestamp: str
    temp: float
    description: str

class WeatherModel(BaseModel):
    location: str
    current: WeatherData
    forecast: List[WeatherData]

class ResearchItem(BaseModel):
    query_variant: str             # e.g. “Historical adoption of X”
    raw_results: str
    cleaned: str                   # from CleaningAgent

class ResearchPipelineModel(BaseModel):
    original_query: str
    expanded_queries: List[str]    # length=3
    items: List[ResearchItem]      # length=3
    research_results: str          # unified template output

class ReportGenerationModel(BaseModel):
    style: str                     # "comprehensive", "top_10", "summary"
    prompt_template: str
    draft: str
    final: str                     # after synth+edit loop

class MasterOutputModel(BaseModel):
    youtube: YouTubeTranscriptModel | None
    weather: WeatherModel              | None
    research1: ResearchPipelineModel   | None
    research2: ResearchPipelineModel   | None
    report: ReportGenerationModel      | None
```

---

## 6. Prompting & Expansion Pattern

1. **Few-Shot Expansion**  
   - **Input:** “Impact of AI on healthcare”  
   - **Output Variants:**  
     1. “Historical adoption of AI in healthcare”  
     2. “Current barriers and drivers in AI-powered medicine”  
     3. “Future ethical and regulatory implications of AI in healthcare”

2. **CleaningAgent Template**  
   - **Query:** …  
   - **Main Themes:** …  
   - **Research Data:** …  
   - **Interesting Quotes:** …  
   - **Key Facts:** …  
   - **Executive Summary:** …

---

## 7. Failure & Retry Strategy

- **Use** Pydantic-AI’s built-in retry decorators/configuration on every tool/API call.  
- **Centralize** retry counts & back-off policies in configuration.  
- **On persistent failure**, mark that module’s output as errored in `MasterOutputModel` and continue other workflows.

---

## 8. Configuration

```python
from pydantic import BaseSettings, Field

class Config(BaseSettings):
    openai_api_key: str              = Field(..., description="OpenAI API key")
    openai_model: str                = Field("openai-4.1-mini", description="Default LLM model")
    tavily_api_token: str            = Field(..., description="Tavily API token")
    mcp_server_url: str              = Field(..., description="DuckDuckGo MCP server URL")
    openweather_api_key: str         = Field(..., description="OpenWeather API key")

    class Config:
        env_file = ".env"
```
- `.env` holds secrets & endpoints (excluded from VCS).  
- All agents and the orchestrator load `Config()` at startup.

---

## 9. Dependencies

- **Python ≥ 3.11**  
- **openai** Python SDK (uses `settings.openai_model`)  
- **pydantic** (v2.x)  
- **pydantic-ai** agent framework  
- **tavily-client** (Tavily API)  
- **tavily-mcp** (DuckDuckGo MCP support)  
- **youtube-transcript-api**  
- **pyowm** or custom OpenWeather wrapper  

---

## 10. References

- **Tavily API docs**: https://docs.tavily.com/welcome  
- **Tavily MCP repo**: https://github.com/tavily-ai/tavily-mcp  
- **Pydantic-AI framework**: https://github.com/pydantic/pydantic-ai  
- **YouTube Transcript API**: https://github.com/jdepoix/youtube-transcript-api  
- **OpenWeather API docs**: https://docs.openweather.co.uk/appid  

---

## 11. Next Steps

1. **Streamlit Wireframe**: finalize UI layout & streaming integration.  
2. **MCP Client Setup**: configure DuckDuckGo MCP details.  
3. **Retry Policies**: define per-agent retry/back-off in settings.  
4. **Model Field Descriptions**: enrich Pydantic fields with `Field(..., description="…")`.  

---

*Prepared by Kevin Dragan’s AI team – using Pydantic-AI and OpenAI 4.1 Mini*  
