options indenting = 2
options no_global_variables = false
options persistent_heap
options no_unused_block_arguments = false
options no_unused_function_arguments = false

require ecs
require DagorSystem
require PythoFrameWs
require daslib/json_boost

struct PythoPosition
  east : float
  up : float
  north : float

struct PythoAttitude
  heading : float
  pitch : float
  roll : float

struct PythoEntity
  id : string
  entityClass : string
  assetId : string
  positionM : PythoPosition
  attitudeDeg : PythoAttitude
  status : string
  visible : bool = true

struct PythoTrack
  id : string
  positionM : PythoPosition
  confidence : float

struct PythoEvent
  id : string
  eventType : string
  positionM : PythoPosition
  success : bool

struct PythoFrame
  schemaVersion : int
  runId : string
  sequence : int
  simTimeSec : float
  coordinateFrame : string
  entities : array<PythoEntity>
  tracks : array<PythoTrack>
  events : array<PythoEvent>

var active_run_id = ""
var last_sequence = -1
var rendered_entities : table<string; EntityId>
var retired_run_ids : table<string; bool>

def change_run(run_id : string)
  if active_run_id == run_id
    return
  if !empty(active_run_id)
    retired_run_ids |> insert(active_run_id, true)
  for _, eid in keys(rendered_entities), values(rendered_entities)
    destroyEntity(eid)
  clear(rendered_entities)
  active_run_id = run_id
  last_sequence = -1

def make_enu_transform(position : PythoPosition; attitude : PythoAttitude) : float3x4
  let radians = 0.017453292519943295f
  let heading = attitude.heading * radians
  let pitch = attitude.pitch * radians
  let roll = attitude.roll * radians

  let level_right = float3(cos(heading), 0.f, -sin(heading))
  let pitched_up = float3(-sin(heading) * sin(pitch), cos(pitch), -cos(heading) * sin(pitch))
  let forward = float3(sin(heading) * cos(pitch), sin(pitch), cos(heading) * cos(pitch))
  let right = level_right * cos(roll) - pitched_up * sin(roll)
  let up = level_right * sin(roll) + pitched_up * cos(roll)

  var transform : float3x4
  transform[0] = right
  transform[1] = up
  transform[2] = forward
  transform[3] = float3(position.east, position.up, position.north)
  return transform

def template_for_entity(entity : PythoEntity) : string
  if entity.assetId == "uav_orion"
    return "pytho_uas_orion"
  if entity.assetId == "mq_1l_usa"
    return "pytho_uas_mq1"
  if entity.assetId == "nasams_fcs"
    return "pytho_response_nasams"
  if entity.assetId == "range_watch_tower"
    return "pytho_sensor_tower"
  if entity.assetId == "cargo_ship_liberty"
    return "pytho_ship_liberty"
  if entity.entityClass == "multirotor"
    return "pytho_uas_multirotor"
  if entity.entityClass == "sensor"
    return "pytho_sensor"
  if entity.entityClass == "ground-vehicle"
    return "pytho_ground_vehicle"
  if entity.entityClass == "ship"
    return "pytho_ship"
  if entity.entityClass == "effect"
    return "pytho_response_effect"
  return "pytho_uas"

def is_successful_effect(event : PythoEvent) : bool
  return event.success && (event.eventType == "response_effect" || event.eventType == "intercept" || event.eventType == "attack")

def template_for_effect(event : PythoEvent) : string
  return event.eventType == "attack" ? "pytho_penetration_effect" : "pytho_response_effect"

def status_for_effect(event : PythoEvent) : string
  return event.eventType == "attack" ? "penetrated" : "neutralized"

def upsert_render_entity(key : string; template_name : string; transform : float3x4;
                         asset_id : string; status : string; visible : bool)
  if key_exists(rendered_entities, key)
    let eid = rendered_entities[key]
    query(eid) <| $ [es] (var transform aka current_transform : float3x4&;
                           var pytho__status : das_string&;
                           var pytho__visible : bool&)
      current_transform = transform
      pytho__status := status
      pytho__visible = visible
    return

  let eid = createEntity(template_name) <| $(var init)
    init |> set("transform", transform)
    init |> set("pytho__id", key)
    init |> set("pytho__asset_id", asset_id)
    init |> set("pytho__status", status)
    init |> set("pytho__visible", visible)
  rendered_entities |> insert(key, eid)

def set_track_confidence(key : string; confidence : float)
  if !key_exists(rendered_entities, key)
    return
  let eid = rendered_entities[key]
  query(eid) <| $ [es] (var pytho__confidence : float&)
    pytho__confidence = confidence

def apply_frame_root(root : JsonValue const?)
  let frame = from_JV(root, type<PythoFrame>)
  if empty(frame.runId) || frame.sequence < 0 || frame.coordinateFrame != "ENU"
    logerr("[PYTHO] frame identity mismatch")
    return
  if length(frame.entities) > 2000
    logerr("[PYTHO] frame exceeds 2000 entities")
    return
  var render_count = 0
  for entity in frame.entities
    if entity.visible
      render_count++
  render_count += length(frame.tracks)
  for effect in frame.events
    if is_successful_effect(effect)
      render_count++
  if render_count > 2000
    logerr("[PYTHO] frame exceeds 2000 rendered ECS entities")
    return
  if key_exists(retired_run_ids, frame.runId)
    return
  change_run(frame.runId)
  if frame.sequence <= last_sequence
    return

  var present : table<string; bool>
  for entity in frame.entities
    if empty(entity.id) || !entity.visible
      continue
    present |> insert(entity.id, true)
    upsert_render_entity(entity.id, template_for_entity(entity), make_enu_transform(entity.positionM, entity.attitudeDeg),
      entity.assetId, entity.status, entity.visible)

  for track in frame.tracks
    if empty(track.id)
      continue
    let key = "track:{track.id}"
    present |> insert(key, true)
    upsert_render_entity(key, "pytho_track", make_enu_transform(track.positionM, PythoAttitude()),
      "track_marker", "active", true)
    set_track_confidence(key, track.confidence)

  for effect in frame.events
    if empty(effect.id) || !is_successful_effect(effect)
      continue
    let key = "effect:{effect.id}"
    present |> insert(key, true)
    upsert_render_entity(key, template_for_effect(effect), make_enu_transform(effect.positionM, PythoAttitude()),
      effect.eventType, status_for_effect(effect), true)

  var stale : array<string>
  for key, _ in keys(rendered_entities), values(rendered_entities)
    if !key_exists(present, key)
      stale |> push(key)
  for key in stale
    destroyEntity(rendered_entities |> get_value(key))
    erase(rendered_entities, key)

  last_sequence = frame.sequence
  print("[PYTHO] frame={frame.sequence} time={frame.simTimeSec} entities={length(frame.entities)} tracks={length(frame.tracks)}")

def receive_transport_message(message : string)
  var error = ""
  var root = read_json(message, error)
  if root == null
    return
  if !empty(error)
    logerr("[PYTHO] invalid frame JSON: {error}")
    unsafe
      delete root
    return
  if (root?.schemaVersion ?? 0) != 1
    logerr("[PYTHO] rejected unsupported schema")
    unsafe
      delete root
    return
  let message_type = root?["type"] ?? ""
  if message_type != "frame"
    unsafe
      delete root
    return
  apply_frame_root(root)
  unsafe
    delete root

[es(tag=render, no_order)]
def pytho_frame_client_es(info : UpdateStageInfoAct)
  if !pytho_ws_start()
    return
  pytho_ws_poll()
  let message = pytho_ws_take_message()
  if !empty(message)
    receive_transport_message(message)
