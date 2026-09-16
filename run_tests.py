import asyncio
import sys
import unittest

# Import test functions
from tests.test_debt_simplification import test_simple_three_way_split, test_transitive_debt_simplification
from tests.test_subagents import test_travel_tools_execution, test_vision_tools_execution, test_proactive_concierge_lifecycle
from tests.test_normalization import (
    test_telegram_message_normalization,
    test_telegram_photo_normalization,
    test_whatsapp_message_normalization,
)
from tests.test_companion_pipeline import (
    test_ambient_companion_travel_proposal,
    test_ambient_companion_vision_photo_analysis,
    test_ambient_companion_expense_logging_and_balance,
)
from tests.test_mcp_travel_server import test_travel_mcp_server_stdio
from tests.test_mcp_client import test_mcp_client_tool_discovery, test_mcp_client_tool_invocation
from tests.test_mcp_dynamic_learning import test_dynamic_mcp_skill_learning, test_ambient_companion_skill_query
from tests.test_travelassistant_mcp import (
    test_travelassistant_mcp_servers_loaded,
    test_travelassistant_geocoder,
    test_travelassistant_weather,
    test_travelassistant_finance,
    test_travelassistant_events,
    test_travelassistant_flights_and_hotels,
)

def run_sync_tests():
    print("Running Synchronous Unit & MCP Tests...")
    test_simple_three_way_split()
    print("  ✅ test_simple_three_way_split passed")

    test_transitive_debt_simplification()
    print("  ✅ test_transitive_debt_simplification passed")

    test_travel_tools_execution()
    print("  ✅ test_travel_tools_execution passed")

    test_vision_tools_execution()
    print("  ✅ test_vision_tools_execution passed")

    test_proactive_concierge_lifecycle()
    print("  ✅ test_proactive_concierge_lifecycle passed")

    test_travel_mcp_server_stdio()
    print("  ✅ test_travel_mcp_server_stdio passed")

    test_mcp_client_tool_discovery()
    print("  ✅ test_mcp_client_tool_discovery passed")

    test_mcp_client_tool_invocation()
    print("  ✅ test_mcp_client_tool_invocation passed")

    test_dynamic_mcp_skill_learning()
    print("  ✅ test_dynamic_mcp_skill_learning passed")

    print("\nRunning skarlekar/mcp_travelassistant 6-Server Ecosystem Tests...")
    test_travelassistant_mcp_servers_loaded()
    print("  ✅ test_travelassistant_mcp_servers_loaded passed (All 6 servers connected!)")

    test_travelassistant_geocoder()
    print("  ✅ test_travelassistant_geocoder passed (Coordinates & distance calculation)")

    test_travelassistant_weather()
    print("  ✅ test_travelassistant_weather passed (Weather forecast & alerts)")

    test_travelassistant_finance()
    print("  ✅ test_travelassistant_finance passed (Currency conversion CAD -> USD)")

    test_travelassistant_events()
    print("  ✅ test_travelassistant_events passed (Local event discovery)")

    test_travelassistant_flights_and_hotels()
    print("  ✅ test_travelassistant_flights_and_hotels passed (Google Flights & Hotels)")

async def run_async_tests():
    print("\nRunning Asynchronous Pipeline & Normalization Tests...")
    await test_telegram_message_normalization()
    print("  ✅ test_telegram_message_normalization passed")

    await test_telegram_photo_normalization()
    print("  ✅ test_telegram_photo_normalization passed")

    await test_whatsapp_message_normalization()
    print("  ✅ test_whatsapp_message_normalization passed")

    await test_ambient_companion_travel_proposal()
    print("  ✅ test_ambient_companion_travel_proposal passed")

    await test_ambient_companion_vision_photo_analysis()
    print("  ✅ test_ambient_companion_vision_photo_analysis passed")

    await test_ambient_companion_expense_logging_and_balance()
    print("  ✅ test_ambient_companion_expense_logging_and_balance passed")

    await test_ambient_companion_skill_query()
    print("  ✅ test_ambient_companion_skill_query passed")

if __name__ == "__main__":
    try:
        run_sync_tests()
        asyncio.run(run_async_tests())
        print("\n🎉 ALL 22 TESTS PASSED SUCCESSFULLY (UNIT, MCP ECOSYSTEM & SKILL-LEARNING)!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
