#import <Foundation/Foundation.h>

#include <cstdio>
#include <cmath>
#include <cstdlib>

namespace
{
bool is_number(id value)
{
  return [value isKindOfClass:[NSNumber class]] &&
    CFGetTypeID((__bridge CFTypeRef)value) != CFBooleanGetTypeID();
}

bool is_nonempty_string(id value)
{
  return [value isKindOfClass:[NSString class]] && [value length] > 0;
}

bool read_position(NSDictionary *entity, NSString **error)
{
  id value = entity[@"positionM"];
  if (![value isKindOfClass:[NSDictionary class]])
  {
    *error = @"entity.positionM must be an object";
    return false;
  }

  NSDictionary *position = (NSDictionary *)value;
  if (!is_number(position[@"east"]) || !is_number(position[@"up"]) || !is_number(position[@"north"]))
  {
    *error = @"entity.positionM must contain numeric east, up, and north values";
    return false;
  }
  return true;
}

bool read_attitude(NSDictionary *entity, NSString **error)
{
  id value = entity[@"attitudeDeg"];
  if (value == nil)
    return true;
  if (![value isKindOfClass:[NSDictionary class]])
  {
    *error = @"entity.attitudeDeg must be an object when present";
    return false;
  }
  NSDictionary *attitude = (NSDictionary *)value;
  if (!is_number(attitude[@"heading"]) || !is_number(attitude[@"pitch"]) || !is_number(attitude[@"roll"]))
  {
    *error = @"entity.attitudeDeg must contain numeric heading, pitch, and roll values";
    return false;
  }
  return true;
}

bool validate_frame(NSDictionary *frame, NSString **error)
{
  id schemaVersion = frame[@"schemaVersion"];
  if (!is_number(schemaVersion) || [schemaVersion integerValue] != 1)
  {
    *error = @"schemaVersion must be 1";
    return false;
  }
  if (![frame[@"type"] isEqual:@"frame"])
  {
    *error = @"type must be frame";
    return false;
  }
  if (!is_nonempty_string(frame[@"runId"]))
  {
    *error = @"runId must be a non-empty string";
    return false;
  }
  double sequence = [frame[@"sequence"] doubleValue];
  if (!is_number(frame[@"sequence"]) || sequence < 0 || std::floor(sequence) != sequence)
  {
    *error = @"sequence must be a non-negative integer";
    return false;
  }
  if (!is_number(frame[@"simTimeSec"]) || [frame[@"simTimeSec"] doubleValue] < 0.0)
  {
    *error = @"simTimeSec must be a non-negative number";
    return false;
  }
  if (![frame[@"coordinateFrame"] isEqual:@"ENU"])
  {
    *error = @"coordinateFrame must be ENU";
    return false;
  }

  id entitiesValue = frame[@"entities"];
  if (![entitiesValue isKindOfClass:[NSArray class]])
  {
    *error = @"entities must be an array";
    return false;
  }
  NSArray *entities = (NSArray *)entitiesValue;
  if ([entities count] > 2000)
  {
    *error = @"entities exceeds the 2000-object client limit";
    return false;
  }
  NSSet *entityClasses = [NSSet setWithObjects:@"fixed-wing", @"multirotor", @"sensor", @"ground-vehicle", @"ship", @"effect", nil];
  NSSet *statuses = [NSSet setWithObjects:@"active", @"neutralized", @"penetrated", @"complete", @"offline", nil];
  NSMutableSet *entityIds = [NSMutableSet setWithCapacity:[entities count]];
  for (id value in entities)
  {
    if (![value isKindOfClass:[NSDictionary class]])
    {
      *error = @"each entity must be an object";
      return false;
    }
    NSDictionary *entity = (NSDictionary *)value;
    if (!is_nonempty_string(entity[@"id"]) || !is_nonempty_string(entity[@"assetId"]) ||
        ![entityClasses containsObject:entity[@"entityClass"]] || ![statuses containsObject:entity[@"status"]] ||
        !read_position(entity, error) || !read_attitude(entity, error))
    {
      if (*error == nil)
        *error = @"entity fields do not match the v1 contract";
      return false;
    }
    if ([entityIds containsObject:entity[@"id"]])
    {
      *error = @"entity ids must be unique within a frame";
      return false;
    }
    [entityIds addObject:entity[@"id"]];
  }

  id tracks = frame[@"tracks"];
  if (tracks != nil && ![tracks isKindOfClass:[NSArray class]])
  {
    *error = @"tracks must be an array when present";
    return false;
  }
  for (id value in (NSArray *)(tracks ?: @[]))
  {
    if (![value isKindOfClass:[NSDictionary class]])
    {
      *error = @"each track must be an object";
      return false;
    }
    NSDictionary *track = (NSDictionary *)value;
    double confidence = [track[@"confidence"] doubleValue];
    if (!is_nonempty_string(track[@"id"]) || !read_position(track, error) ||
        !is_number(track[@"confidence"]) || confidence < 0.0 || confidence > 1.0)
    {
      if (*error == nil)
        *error = @"track fields do not match the v1 contract";
      return false;
    }
  }
  return true;
}

int process_line(const char *line, size_t length)
{
  NSData *data = [NSData dataWithBytes:line length:length];
  NSError *jsonError = nil;
  id parsed = [NSJSONSerialization JSONObjectWithData:data options:0 error:&jsonError];
  if (![parsed isKindOfClass:[NSDictionary class]])
  {
    const char *message = jsonError ? [[jsonError localizedDescription] UTF8String] : "root must be an object";
    std::fprintf(stderr, "invalid frame: %s\n", message);
    return 2;
  }

  NSDictionary *frame = (NSDictionary *)parsed;
  NSString *validationError = nil;
  if (!validate_frame(frame, &validationError))
  {
    std::fprintf(stderr, "invalid frame: %s\n", [validationError UTF8String]);
    return 2;
  }

  NSArray *entities = frame[@"entities"];
  NSUInteger activeCount = 0;
  for (NSDictionary *entity in entities)
    if ([entity[@"status"] isEqual:@"active"])
      ++activeCount;
  NSArray *tracks = frame[@"tracks"];

  std::printf("frame sequence=%lld time=%.3f entities=%lu active=%lu tracks=%lu\n",
    [frame[@"sequence"] longLongValue], [frame[@"simTimeSec"] doubleValue],
    (unsigned long)[entities count], (unsigned long)activeCount, (unsigned long)[tracks count]);
  return 0;
}
} // namespace

int main()
{
  @autoreleasepool
  {
    char *line = nullptr;
    size_t capacity = 0;
    ssize_t length = 0;
    int result = 0;
    while ((length = getline(&line, &capacity, stdin)) >= 0)
    {
      while (length > 0 && (line[length - 1] == '\n' || line[length - 1] == '\r'))
        --length;
      if (length == 0)
        continue;
      result = process_line(line, static_cast<size_t>(length));
      if (result != 0)
        break;
    }
    std::free(line);
    return result;
  }
}
