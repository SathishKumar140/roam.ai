import os
import shutil
from pathlib import Path
from src.skills.loader import SkillsLoader, parse_skill_md, validate_skill_name
from src.agents.deep_companion import create_ambient_companion
from src.skills.mcp_skill_learner import connect_external_mcp_server


def test_agent_skills_validation_rules():
    """Validates that skill names follow Agent Skills constraints."""
    # Valid names
    valid_names = ["flight-search", "hotel-finder-v2", "mcp-travel", "math-101"]
    for name in valid_names:
        is_val, err = validate_skill_name(name, name)
        assert is_val, f"Expected '{name}' to be valid, got error: {err}"

    # Invalid names (must match folder name, lowercase alphanumeric + single hyphens)
    assert not validate_skill_name("FlightSearch", "FlightSearch")[0]
    assert not validate_skill_name("flight--search", "flight--search")[0]
    assert not validate_skill_name("-flight-search", "-flight-search")[0]
    assert not validate_skill_name("flight-search", "different-folder")[0]
    print("  ✅ test_agent_skills_validation_rules passed")


def test_subagent_isolated_skills_loading():
    """Validates that each subagent receives only its isolated skill set."""
    travel_skills = SkillsLoader.load_skills_from_sources(["./skills/travel-skills/"])
    assert "flight-search" in travel_skills
    assert "hotel-finder" in travel_skills
    assert "weather-forecasting" in travel_skills
    assert "itinerary-synthesis" in travel_skills
    # Ensure travel does not have vision or expense skills
    assert "venue-facade-scouting" not in travel_skills
    assert "debt-simplification" not in travel_skills

    vision_skills = SkillsLoader.load_skills_from_sources(["./skills/vision-skills/"])
    assert "venue-facade-scouting" in vision_skills
    assert "menu-receipt-ocr" in vision_skills
    assert "flight-search" not in vision_skills

    expense_skills = SkillsLoader.load_skills_from_sources(["./skills/expense-skills/"])
    assert "debt-simplification" in expense_skills
    assert "currency-conversion" in expense_skills

    concierge_skills = SkillsLoader.load_skills_from_sources(["./skills/concierge-skills/"])
    assert "departure-state-machine" in concierge_skills
    assert "group-polling" in concierge_skills

    meta_skills = SkillsLoader.load_skills_from_sources(["./skills/meta-skills/"])
    assert "mcp-acquisition" in meta_skills

    global_skills = SkillsLoader.load_skills_from_sources(["./skills/global/"])
    assert "ambient-arbitration" in global_skills
    assert "channel-formatting" in global_skills

    print("  ✅ test_subagent_isolated_skills_loading passed")


def test_progressive_disclosure_prompt_and_tool():
    """Validates progressive disclosure prompt generation and lazy markdown retrieval."""
    travel_skills = SkillsLoader.load_skills_from_sources(["./skills/travel-skills/"])
    prompt = SkillsLoader.format_skills_system_prompt(travel_skills, ["./skills/travel-skills/"])

    assert "## 🧠 Skills System (Progressive Disclosure)" in prompt
    assert "`flight-search`" in prompt
    assert "search_flights" in prompt

    # Verify lazy instruction retrieval tool
    read_tool = SkillsLoader.create_skill_inspection_tool(travel_skills)
    instructions = read_tool.invoke({"skill_name": "flight-search"})
    assert "# Flight Search Skill" in instructions
    assert "search_flights(departure_id, arrival_id" in instructions

    # Test unknown skill
    err = read_tool.invoke({"skill_name": "non-existent-skill"})
    assert "Error: Skill 'non-existent-skill' not found" in err

    print("  ✅ test_progressive_disclosure_prompt_and_tool passed")


def test_dynamic_mcp_skill_folder_creation():
    """Validates that connecting to an external MCP server dynamically writes a valid SKILL.md folder."""
    # Test dynamic registration
    res = connect_external_mcp_server.invoke({
        "server_name": "test_currency_hub",
        "command": "python3",
        "args_json": "[\"-m\", \"src.mcp.travelassistant.finance_server\"]"
    })
    assert "Registered standard skill at" in res

    skill_path = Path("skills/meta-skills/mcp-test-currency-hub/SKILL.md")
    assert skill_path.is_file(), "Generated SKILL.md file must exist"

    # Verify generated SKILL.md parses with SkillsLoader
    meta = parse_skill_md(skill_path)
    assert meta is not None
    assert meta["name"] == "mcp-test-currency-hub"
    assert "convert_currency" in meta["allowed_tools"]

    # Clean up test skill folder
    if skill_path.parent.is_dir():
        shutil.rmtree(skill_path.parent)

    print("  ✅ test_dynamic_mcp_skill_folder_creation passed")


async def test_ambient_companion_skills_query():
    """Validates that ambient_companion responds to skill discovery and skill instruction queries."""
    companion = create_ambient_companion()

    # Query loaded skills
    res = await companion.ainvoke({
        "text": "What skills do you have?",
        "sender_name": "Dave"
    })
    output = res.get("output", "")
    assert "DeepAgents Skills Library" in output
    assert "travel_specialist" in output
    assert "flight-search" in output
    assert "expense_specialist" in output
    assert "debt-simplification" in output

    # Query reading a specific skill
    res_skill = await companion.ainvoke({
        "text": "Inspect skill flight-search instructions",
        "sender_name": "Dave"
    })
    output_skill = res_skill.get("output", "")
    assert "# Flight Search Skill" in output_skill
    assert "search_flights" in output_skill

    print("  ✅ test_ambient_companion_skills_query passed")


if __name__ == "__main__":
    import asyncio
    test_agent_skills_validation_rules()
    test_subagent_isolated_skills_loading()
    test_progressive_disclosure_prompt_and_tool()
    test_dynamic_mcp_skill_folder_creation()
    asyncio.run(test_ambient_companion_skills_query())
    print("\n🎉 ALL DEEPAGENTS SKILLS TESTS PASSED!")
