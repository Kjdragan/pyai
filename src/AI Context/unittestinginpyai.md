Unit testing
Writing unit tests for Pydantic AI code is just like unit tests for any other Python code.

Because for the most part they're nothing new, we have pretty well established tools and patterns for writing and running these kinds of tests.

Unless you're really sure you know better, you'll probably want to follow roughly this strategy:

Use pytest as your test harness
If you find yourself typing out long assertions, use inline-snapshot
Similarly, dirty-equals can be useful for comparing large data structures
Use TestModel or FunctionModel in place of your actual model to avoid the usage, latency and variability of real LLM calls
Use Agent.override to replace an agent's model, dependencies, or toolsets inside your application logic
Set ALLOW_MODEL_REQUESTS=False globally to block any requests from being made to non-test models accidentally
Unit testing with TestModel
The simplest and fastest way to exercise most of your application code is using TestModel, this will (by default) call all tools in the agent, then return either plain text or a structured response depending on the return type of the agent.

TestModel is not magic

The "clever" (but not too clever) part of TestModel is that it will attempt to generate valid structured data for function tools and output types based on the schema of the registered tools.

There's no ML or AI in TestModel, it's just plain old procedural Python code that tries to generate data that satisfies the JSON schema of a tool.

The resulting data won't look pretty or relevant, but it should pass Pydantic's validation in most cases. If you want something more sophisticated, use FunctionModel and write your own data generation logic.

Let's write unit tests for the following application code:

weather_app.py

import asyncio
from datetime import date

from pydantic_ai import Agent, RunContext

from fake_database import DatabaseConn
from weather_service import WeatherService

weather_agent = Agent(
    'openai:gpt-4o',
    deps_type=WeatherService,
    system_prompt='Providing a weather forecast at the locations the user provides.',
)


@weather_agent.tool
def weather_forecast(
    ctx: RunContext[WeatherService], location: str, forecast_date: date
) -> str:
    if forecast_date < date.today():
        return ctx.deps.get_historic_weather(location, forecast_date)
    else:
        return ctx.deps.get_forecast(location, forecast_date)


async def run_weather_forecast(
    user_prompts: list[tuple[str, int]], conn: DatabaseConn
):
    """Run weather forecast for a list of user prompts and save."""
    async with WeatherService() as weather_service:

        async def run_forecast(prompt: str, user_id: int):
            result = await weather_agent.run(prompt, deps=weather_service)
            await conn.store_forecast(user_id, result.output)

        # run all prompts in parallel
        await asyncio.gather(
            *(run_forecast(prompt, user_id) for (prompt, user_id) in user_prompts)
        )
Here we have a function that takes a list of (user_prompt, user_id) tuples, gets a weather forecast for each prompt, and stores the result in the database.

We want to test this code without having to mock certain objects or modify our code so we can pass test objects in.

Here's how we would write tests using TestModel:

test_weather_app.py

from datetime import timezone
import pytest

from dirty_equals import IsNow, IsStr

from pydantic_ai import models, capture_run_messages
from pydantic_ai.models.test import TestModel
from pydantic_ai.messages import (
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
    ModelRequest,
)
from pydantic_ai.usage import Usage

from fake_database import DatabaseConn
from weather_app import run_weather_forecast, weather_agent

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


async def test_forecast():
    conn = DatabaseConn()
    user_id = 1
    with capture_run_messages() as messages:
        with weather_agent.override(model=TestModel()):
            prompt = 'What will the weather be like in London on 2024-11-28?'
            await run_weather_forecast([(prompt, user_id)], conn)

    forecast = await conn.get_forecast(user_id)
    assert forecast == '{"weather_forecast":"Sunny with a chance of rain"}'

    assert messages == [
        ModelRequest(
            parts=[
                SystemPromptPart(
                    content='Providing a weather forecast at the locations the user provides.',
                    timestamp=IsNow(tz=timezone.utc),
                ),
                UserPromptPart(
                    content='What will the weather be like in London on 2024-11-28?',
                    timestamp=IsNow(tz=timezone.utc),
                ),
            ]
        ),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name='weather_forecast',
                    args={
                        'location': 'a',
                        'forecast_date': '2024-01-01',
                    },
                    tool_call_id=IsStr(),
                )
            ],
            usage=Usage(
                requests=1,
                request_tokens=71,
                response_tokens=7,
                total_tokens=78,
                details=None,
            ),
            model_name='test',
            timestamp=IsNow(tz=timezone.utc),
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name='weather_forecast',
                    content='Sunny with a chance of rain',
                    tool_call_id=IsStr(),
                    timestamp=IsNow(tz=timezone.utc),
                ),
            ],
        ),
        ModelResponse(
            parts=[
                TextPart(
                    content='{"weather_forecast":"Sunny with a chance of rain"}',
                )
            ],
            usage=Usage(
                requests=1,
                request_tokens=77,
                response_tokens=16,
                total_tokens=93,
                details=None,
            ),
            model_name='test',
            timestamp=IsNow(tz=timezone.utc),
        ),
    ]
Unit testing with FunctionModel
The above tests are a great start, but careful readers will notice that the WeatherService.get_forecast is never called since TestModel calls weather_forecast with a date in the past.

To fully exercise weather_forecast, we need to use FunctionModel to customise how the tools is called.

Here's an example of using FunctionModel to test the weather_forecast tool with custom inputs

test_weather_app2.py

import re

import pytest

from pydantic_ai import models
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from fake_database import DatabaseConn
from weather_app import run_weather_forecast, weather_agent

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


def call_weather_forecast(
    messages: list[ModelMessage], info: AgentInfo
) -> ModelResponse:
    if len(messages) == 1:
        # first call, call the weather forecast tool
        user_prompt = messages[0].parts[-1]
        m = re.search(r'\d{4}-\d{2}-\d{2}', user_prompt.content)
        assert m is not None
        args = {'location': 'London', 'forecast_date': m.group()}
        return ModelResponse(parts=[ToolCallPart('weather_forecast', args)])
    else:
        # second call, return the forecast
        msg = messages[-1].parts[0]
        assert msg.part_kind == 'tool-return'
        return ModelResponse(parts=[TextPart(f'The forecast is: {msg.content}')])


async def test_forecast_future():
    conn = DatabaseConn()
    user_id = 1
    with weather_agent.override(model=FunctionModel(call_weather_forecast)):
        prompt = 'What will the weather be like in London on 2032-01-01?'
        await run_weather_forecast([(prompt, user_id)], conn)

    forecast = await conn.get_forecast(user_id)
    assert forecast == 'The forecast is: Rainy with a chance of sun'
Overriding model via pytest fixtures
If you're writing lots of tests that all require model to be overridden, you can use pytest fixtures to override the model with TestModel or FunctionModel in a reusable way.

Here's an example of a fixture that overrides the model with TestModel:

test_agent.py

import pytest
from weather_app import weather_agent

from pydantic_ai.models.test import TestModel


@pytest.fixture
def override_weather_agent():
    with weather_agent.override(model=TestModel()):
        yield


async def test_forecast(override_weather_agent: None):
    ...
    # test code here
