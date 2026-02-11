#!/usr/bin/env python3
"""
Test script to verify feed_id configuration works correctly.
Tests feed_id list filtering (similar to category_id).
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auction_simulator.config import load_config
from auction_simulator.data_extraction import DataExtractor


def test_feed_id():
    """Test feed_id configuration modes."""

    print("=" * 80)
    print("TESTING FEED_ID CONFIGURATION")
    print("=" * 80)
    print()

    # Test 1: Default mode (feed_id list)
    print("Test 1: Default mode (feed_id = ['6500', '6002'])")
    print("-" * 40)
    cfg = load_config('config/local.yaml')
    extractor = DataExtractor(cfg)
    clause = extractor._get_feed_filter_clause()
    print(f"Feed filter clause: {repr(clause)}")

    expected = "AND feed_id IN ('6500', '6002')"
    if clause == expected:
        print("✅ Test 1 PASSED: Default mode returns feed_id filter")
    else:
        print(f"❌ Test 1 FAILED: Expected {repr(expected)}, got {repr(clause)}")
        return False
    print()

    # Test 2: Override to None (all feeds)
    print("Test 2: Override to None (all feeds)")
    print("-" * 40)
    cfg._config['data_extraction'] = {'feed_id': None}
    extractor2 = DataExtractor(cfg)
    clause2 = extractor2._get_feed_filter_clause()
    print(f"Feed filter clause: {repr(clause2)}")

    if clause2 == '':
        print("✅ Test 2 PASSED: None returns empty filter (all feeds)")
    else:
        print(f"❌ Test 2 FAILED: Expected empty string, got {repr(clause2)}")
        return False
    print()

    # Test 3: Custom feed_id list
    print("Test 3: Custom feed_id list ['1234', '5678']")
    print("-" * 40)
    cfg._config['data_extraction'] = {'feed_id': ['1234', '5678']}
    extractor3 = DataExtractor(cfg)
    clause3 = extractor3._get_feed_filter_clause()
    print(f"Feed filter clause: {repr(clause3)}")

    expected3 = "AND feed_id IN ('1234', '5678')"
    if clause3 == expected3:
        print("✅ Test 3 PASSED: Custom feed_id list works correctly")
    else:
        print(f"❌ Test 3 FAILED: Expected {repr(expected3)}, got {repr(clause3)}")
        return False
    print()

    # Test 4: Verify config parameter exists
    print("Test 4: Verify config file contains feed_id parameter")
    print("-" * 40)
    cfg = load_config('config/local.yaml')
    if 'data_extraction' in cfg._config:
        feed_id = cfg._config['data_extraction'].get('feed_id', 'NOT_FOUND')
        print(f"Config feed_id value: {feed_id}")
        if feed_id == ['6500', '6002']:
            print("✅ Test 4 PASSED: Config contains correct default value")
        else:
            print(f"❌ Test 4 FAILED: Expected ['6500', '6002'], got {feed_id}")
            return False
    else:
        print("❌ Test 4 FAILED: 'data_extraction' section not found in config")
        return False
    print()

    print("=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("Feed ID implementation is working correctly:")
    print("  - feed_id: ['6500', '6002'] → Filters to feed_id IN ('6500', '6002')")
    print("  - feed_id: null → No feed_id filter (includes all feeds)")
    print("  - feed_id: ['1234'] → Custom filter")
    print()
    print("Usage in CLI:")
    print("  python -m auction_simulator.cli simulate --feed-id 6500,6002 ...")
    print("  python -m auction_simulator.cli simulate --feed-id '' ...")
    print("  (empty string = all feeds)")
    print()

    return True


if __name__ == '__main__':
    try:
        success = test_feed_id()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
