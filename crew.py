import json
from datetime import datetime
from crewai import Agent, Task, Crew, Process
from crewai_tools import TavilySearchTool
from langchain_anthropic import ChatAnthropic
from config import settings

# ─── LLM ─────────────────────────────────────────────────────────────────────

llm = ChatAnthropic(
    model="claude-opus-4-6",
    anthropic_api_key=settings.anthropic_api_key,
    temperature=0.7,
)

# ─── Tools ───────────────────────────────────────────────────────────────────

search_tool = TavilySearchTool(api_key=settings.tavily_api_key)

# ─── Agents ──────────────────────────────────────────────────────────────────

scout_agent = Agent(
    role="Local Activities Scout",
    goal=(
        "Find genuinely interesting, high-quality local activities and events "
        "near the user's location that match their stated preferences for today."
    ),
    backstory=(
        "You're the kind of person who always knows what's happening — the hidden "
        "gem restaurant opening, the pop-up art show, the farmer's market with the "
        "incredible smoked fish vendor. You have impeccable taste and you never "
        "recommend something boring. You know {location} well and you search "
        "broadly: local event sites, venue calendars, Eventbrite, Meetup, "
        "local newspapers, and anywhere else good stuff gets listed."
    ),
    tools=[search_tool],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

curator_agent = Agent(
    role="Personal Concierge",
    goal=(
        "Take the raw findings from the scout and curate them into a short, "
        "beautifully presented list of 3–5 options with genuine personality. "
        "Each recommendation should feel like it came from a knowledgeable friend, "
        "not a search engine."
    ),
    backstory=(
        "You have the warmth and taste of the owner of a great boutique — you know "
        "what's worth someone's time and you say so with confidence. You present "
        "options concisely, with a little editorial flair: what makes it special, "
        "any useful logistics (address, cost, time), and why it fits what the person "
        "asked for. You sign off as Morris."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

# ─── Crew factory ────────────────────────────────────────────────────────────

def find_activities(preference: str, location: str, today: str, profile_context: str = "") -> tuple[str, list]:
    """
    Run the crew and return (formatted_message, structured_events_list).
    profile_context is injected into both agents if provided.
    """

    profile_block = f"\n\n{profile_context}" if profile_context else ""

    scout_task = Task(
        description=(
            f"Today is {today}. The user is in {location} and wants to: '{preference}'. "
            f"Search for real, specific events and activities happening today or this week "
            f"near {location} that match this request. "
            f"Find at least 5 candidates with: name, venue, address, time, description, URL. "
            f"Focus on things actually happening — not generic listicles."
            f"{profile_block}"
        ),
        expected_output=(
            "A list of 5+ concrete activities/events with full details: "
            "name, venue, full address, date/time, short description, URL."
        ),
        agent=scout_agent,
    )

    curator_task = Task(
        description=(
            "Take the scout's findings and produce two things:\n\n"
            "1. A friendly Telegram message (use Telegram markdown) presenting the top 3–5 options. "
            "Each option should be numbered, have a bold title, a one-line hook, and the key logistics. "
            f"Where the user profile gives you genuine insight, reference it naturally — "
            f"'given your thing for vintage finds...' or 'this has your name on it' — "
            f"but only when it actually fits. Don't force it.\n"
            "End with: 'Reply with the number of anything that catches your eye and I'll keep track of it for you.'\n\n"
            "2. A JSON block at the very end of your response, enclosed in ```json ... ``` tags, "
            "with a list of the same events in this structure:\n"
            "[\n"
            "  {\n"
            '    "name": "...",\n'
            '    "venue": "...",\n'
            '    "address": "...",\n'
            '    "event_time": "2025-01-15T19:00:00" or null,\n'
            '    "description": "...",\n'
            '    "url": "..."\n'
            "  }\n"
            "]\n\n"
            f"Sign the message as Morris.{profile_block}"
        ),
        expected_output=(
            "A Telegram-formatted message with numbered options, followed by a ```json block "
            "containing the structured event data."
        ),
        agent=curator_agent,
        context=[scout_task],
    )

    crew = Crew(
        agents=[scout_agent, curator_agent],
        tasks=[scout_task, curator_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff(inputs={
        "preference": preference,
        "location": location,
        "today": today,
    })

    raw = str(result)

    # Parse out the JSON block
    events = []
    if "```json" in raw:
        try:
            json_str = raw.split("```json")[1].split("```")[0].strip()
            events = json.loads(json_str)
        except Exception as e:
            print(f"Warning: could not parse events JSON: {e}")

    # The message is everything before the json block
    message = raw.split("```json")[0].strip() if "```json" in raw else raw

    return message, events
