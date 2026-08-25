#pragma once

#include <array>
#include <cmath>

namespace pytho
{
struct Vec3
{
  double x;
  double y;
  double z;
};

struct DagorTransform
{
  Vec3 right;
  Vec3 up;
  Vec3 forward;
  Vec3 position;
};

inline DagorTransform enu_to_dagor(double east, double up, double north, double heading_deg, double pitch_deg, double roll_deg)
{
  constexpr double degrees_to_radians = 3.14159265358979323846 / 180.0;
  const double heading = heading_deg * degrees_to_radians;
  const double pitch = pitch_deg * degrees_to_radians;
  const double roll = roll_deg * degrees_to_radians;

  const Vec3 level_right{std::cos(heading), 0.0, -std::sin(heading)};
  const Vec3 pitched_up{-std::sin(heading) * std::sin(pitch), std::cos(pitch), -std::cos(heading) * std::sin(pitch)};
  const Vec3 forward{std::sin(heading) * std::cos(pitch), std::sin(pitch), std::cos(heading) * std::cos(pitch)};

  const Vec3 right{
    level_right.x * std::cos(roll) - pitched_up.x * std::sin(roll),
    level_right.y * std::cos(roll) - pitched_up.y * std::sin(roll),
    level_right.z * std::cos(roll) - pitched_up.z * std::sin(roll),
  };
  const Vec3 rotated_up{
    level_right.x * std::sin(roll) + pitched_up.x * std::cos(roll),
    level_right.y * std::sin(roll) + pitched_up.y * std::cos(roll),
    level_right.z * std::sin(roll) + pitched_up.z * std::cos(roll),
  };

  return {right, rotated_up, forward, {east, up, north}};
}
} // namespace pytho
