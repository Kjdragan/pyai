# Pydantic-AI Multi-Agent System

This project is a multi-agent AI system built with Python, Pydantic, and Streamlit. It leverages a team of specialized AI agents to perform a variety of tasks, coordinated by a central orchestrator. The system can be controlled via a command-line interface (CLI) or a user-friendly web interface.

## Features

The system includes the following capabilities:

*   **YouTube Video Analysis**: Provide a YouTube URL to get the video's transcript, title, and other metadata.
*   **Weather Forecasts**: Get the current weather and a 7-day forecast for any location.
*   **Web Research**: Perform research on a given topic using multiple search providers (Tavily and Serper) for comprehensive results.
*   **Report Generation**: Generate structured reports (e.g., in markdown format) based on a topic, using the research agents to gather information.

## How to Run

First, ensure all required Python packages are installed:

```bash
pip install -r requirements.txt
```

You will also need to configure your API keys for the services you intend to use (e.g., OpenAI, Tavily, Serper). Create a `.env` file in the root of the project and add your keys there. See `src/config.py` for the required environment variable names.

### Command-Line Interface (CLI)

You can run the system from the command line using `src/main.py`.

To start an interactive session:
```bash
python src/main.py
```

The application will then prompt you for a request.

You can also pass a query directly:
```bash
python src/main.py --query "Weather in London"
```

### Web Interface

To launch the Streamlit web interface, use the `--web` flag:

```bash
python src/main.py --web
```

This will start a local web server and provide a URL to access the chat-based interface in your browser.

## Project Structure

The project's source code is located in the `src/` directory. Here is a brief overview of the key components:

*   `main.py`: The main entry point for the application. It handles CLI arguments and can launch the CLI or the web interface.
*   `streamlit_app.py`: The Streamlit application that provides the web UI.
*   `agents/`: This directory contains all the specialized AI agents.
    *   `orchestrator_agent.py`: The main agent that receives user queries and delegates tasks to other agents.
    *   `youtube_agent.py`, `weather_agent.py`, `research_tavily_agent.py`, etc.: Specialist agents responsible for specific tasks.
*   `config.py`: Manages configuration and API keys from environment variables.
*   `models.py`: Defines the Pydantic data models used throughout the application for structured data transfer.
*   `logging_config.py`: Configures the logging system, including integration with Logfire for tracing.
*   `utils/`: Contains utility functions and helper classes used by multiple agents.
