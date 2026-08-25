#include "../src/enu_transform.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace
{
void expect_near(double actual, double expected, const char *label)
{
  if (std::abs(actual - expected) > 1e-9)
  {
    std::fprintf(stderr, "%s: expected %.9f, got %.9f\n", label, expected, actual);
    std::exit(1);
  }
}
}

int main()
{
  const auto north = pytho::enu_to_dagor(10.0, 20.0, 30.0, 0.0, 0.0, 0.0);
  expect_near(north.forward.x, 0.0, "north forward x");
  expect_near(north.forward.z, 1.0, "north forward z");
  expect_near(north.position.x, 10.0, "east position");
  expect_near(north.position.y, 20.0, "up position");
  expect_near(north.position.z, 30.0, "north position");

  const auto east = pytho::enu_to_dagor(110.0, 20.0, 30.0, 90.0, 0.0, 0.0);
  expect_near(east.forward.x, 1.0, "east forward x");
  expect_near(east.forward.z, 0.0, "east forward z");
  expect_near(east.position.x - north.position.x, 100.0, "100 meter east delta");

  const auto climb = pytho::enu_to_dagor(0.0, 0.0, 0.0, 0.0, 30.0, 0.0);
  expect_near(climb.forward.y, 0.5, "positive pitch");

  const auto roll = pytho::enu_to_dagor(0.0, 0.0, 0.0, 0.0, 0.0, 30.0);
  expect_near(roll.right.y, -0.5, "positive right-wing-down roll");

  std::puts("ENU transform tests passed");
  return 0;
}
