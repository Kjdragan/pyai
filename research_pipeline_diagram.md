# Research Pipeline Diagram

```mermaid
graph TD
    %% Main components
    User[User Input] --> Orchestrator[Orchestrator Agent]
    Orchestrator --> JobParser[Job Request Parser]
    
    %% Job type determination
    JobParser --> JobType{Job Type?}
    
    %% YouTube branch
    JobType -->|YouTube| YouTube[YouTube Agent]
    YouTube --> TranscriptFetch[Fetch Transcript]
    TranscriptFetch --> TranscriptModel[YouTube Transcript Model]
    
    %% Weather branch
    JobType -->|Weather| Weather[Weather Agent]
    Weather --> WeatherAPI[OpenWeather API]
    WeatherAPI --> WeatherModel[Weather Model]
    
    %% Research branch - main focus
    JobType -->|Research| Research{Research Pipeline}
    Research --> QueryExpansion[Query Expansion<br>Past/Present/Future]
    
    %% Parallel research paths
    QueryExpansion --> TavilyPath[Tavily Research Path]
    QueryExpansion --> DuckDuckGoPath[DuckDuckGo Research Path]
    
    %% Tavily research flow
    TavilyPath --> TavilyAgent[Tavily Research Agent]
    TavilyAgent --> TavilyAPI[Tavily API<br>Advanced Search]
    TavilyAPI --> TavilyResults[Tavily Results<br>Filtering & Scoring]
    
    %% DuckDuckGo research flow
    DuckDuckGoPath --> DDGAgent[DuckDuckGo Research Agent]
    DDGAgent --> DDGSearch[DuckDuckGo Search API]
    DDGSearch --> DDGResults[DDG Results<br>Filtering & Scoring]
    
    %% Results aggregation
    TavilyResults --> ResearchAggregation[Research Results Aggregation]
    DDGResults --> ResearchAggregation
    ResearchAggregation --> ResearchModel[Research Pipeline Model]
    
    %% Report generation
    JobType -->|Report| ReportWriter[Report Writer Agent]
    TranscriptModel --> ReportWriter
    WeatherModel --> ReportWriter
    ResearchModel --> ReportWriter
    ReportWriter --> ReportGeneration[Report Generation<br>GPT-4o-mini]
    ReportGeneration --> ReportModel[Report Model]
    
    %% Final output
    TranscriptModel --> MasterOutput[Master Output Model]
    WeatherModel --> MasterOutput
    ResearchModel --> MasterOutput
    ReportModel --> MasterOutput
    MasterOutput --> StreamingUpdates[Streaming Updates to UI]
    
    %% Styling
    classDef agent fill:#f9d5e5,stroke:#333,stroke-width:2px
    classDef model fill:#eeeeee,stroke:#333,stroke-width:1px
    classDef api fill:#d5f9e5,stroke:#333,stroke-width:1px
    classDef process fill:#e5d5f9,stroke:#333,stroke-width:1px
    
    class Orchestrator,YouTube,Weather,TavilyAgent,DDGAgent,ReportWriter agent
    class TranscriptModel,WeatherModel,ResearchModel,ReportModel,MasterOutput model
    class TavilyAPI,WeatherAPI,DDGSearch api
    class QueryExpansion,ResearchAggregation,ReportGeneration process
```

## Research Pipeline Flow Description

1. **User Input Processing**:
   - Orchestrator Agent receives user query
   - Job Request Parser determines job type (YouTube, Weather, Research, Report)

2. **Research Pipeline** (Main Focus):
   - Query Expansion: Original query expanded into 3 sub-questions (past, present, future)
   - Parallel Research Paths:
     - **Tavily Research Path**:
       - Advanced search with relevance scoring
       - Raw content extraction for better precision
       - Results filtered by relevance score (>0.5)
     - **DuckDuckGo Research Path**:
       - Web search with snippet extraction
       - Results filtered and ranked

3. **Results Processing**:
   - Research results aggregated from both paths
   - Structured into ResearchPipelineModel
   - Passed to Report Writer Agent

4. **Report Generation**:
   - Report Writer Agent synthesizes information
   - Formats according to requested style (comprehensive, top_10, summary)
   - Creates final report using GPT-4o-mini

5. **Output Delivery**:
   - All results combined in MasterOutputModel
   - Streaming updates sent to UI
