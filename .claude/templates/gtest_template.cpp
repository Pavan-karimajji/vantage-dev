// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: <COMPONENT>
/// @file
/// @brief Unit test — mirrors one file under src/component/ (skills/gtest_patterns.md).
/// @author <Name> <email>

#include <gtest/gtest.h>

#include "component/<name>/<name>.hpp"

namespace adas::<ns> {
namespace {

// Test pure component logic in isolation: build ReqPorts by hand, call exec(dtS),
// assert on ProPorts. No middleware, no disk, allocation-light fixtures.
TEST(<Name>Test, <Behavior>) {
  <Name>ReqPorts reqPorts;
  <Name>ProPorts proPorts;
  <Name> algo(reqPorts, proPorts);

  // arrange reqPorts...
  algo.exec(0.02 /*dtS*/);
  // EXPECT_...(proPorts...);
}

}  // namespace
}  // namespace adas::<ns>
