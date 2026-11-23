-- Shared by earlier fragments (load order: harness/runtime_source.py MANIFEST).
local info_id, info_type, move_denom = H._ns.info_id, H._ns.info_type, H._ns.move_denom
local short, step_costs = H._ns.short, H._ns.step_costs

-- ActivityTypes by the engine's own names (raw ints otherwise mean nothing to a caller), the words units() reads
-- through H.unit_activity. ACTIVITY_SLEEP is both a sleep and a fortify; `hold` (H.unit_hold_state) says which
-- (GitLab #176: "SLEEP_OR_FORTIFY" here and "SLEEP" in the unit list described one warrior two ways).
local ACTIVITY_NAMES = { [0] = "AWAKE", [1] = "HOLD", [2] = "SLEEP", [3] = "HEAL", [4] = "SENTRY", [5] = "INTERCEPT", [6] = "MISSION" }
function H.activity_name(a) return ACTIVITY_NAMES[a] or tostring(a) end

-- reveal=true (the read-back after move_unit): adds `revealed`, what the move showed (H.reveal_diff).
function H.unit_pos(unit_id, pid, reveal)
  local u = Players[pid]:GetUnitByID(unit_id)
  if not u then return { ok = false, err = "no such unit" } end
  local denom = move_denom()
  local out = {
    ok = true, x = u:GetX(), y = u:GetY(),
    moves = u:MovesLeft() / denom,
    activity = u.GetActivityType and u:GetActivityType() or nil,
    activity_name = u.GetActivityType and H.activity_name(u:GetActivityType()) or nil,
    buildtype = u.GetBuildType and u:GetBuildType() or nil,
    hold = H.unit_hold_state(u),   -- #176: fortified or fortifying, and whether the end-turn list still wants it
  }
  if reveal then
    local okr, diff = pcall(H.reveal_diff, unit_id, pid)
    if okr then out.revealed = diff end
    -- v347: who can strike the plot the move ended on (H.strike_threats); absent when nobody can
    local okt, threats = pcall(H.strike_threats, u, pid)
    if okt and threats then out.in_range_of = threats end
  end
  return out
end

-- Where the known map ends for one unit: revealed, passable plots of the unit's domain that touch at
-- least one unrevealed plot, nearest first. This is the fog boundary a human sees on the minimap --
-- the only thing read about an unrevealed plot is that it is unrevealed (IsRevealed), never its
-- terrain, owner or occupants. move_unit refuses unrevealed targets, so an explorer uses this to pick
-- its next stop instead of guessing coordinates.
function H.explore_frontier(unit_id, pid, limit)
  local u = Players[pid]:GetUnitByID(unit_id)
  if not u then return { ok = false, err = "no such unit" } end
  local team = Players[pid]:GetTeam()
  local sea = (u:GetDomainType() == DomainTypes.DOMAIN_SEA)
  local embarked = (u.IsEmbarked and u:IsEmbarked()) and true or false
  local ux, uy = u:GetX(), u:GetY()
  local out, unrevealed = {}, 0
  local w, h = Map.GetGridSize()
  local function traversable(p)
    -- IsImpassable() is false for a mountain in this build (live 2026-09-18: (42,27) offered as reachable
    -- DESERT, move_unit refused it) -- mountains are a plot type, not an impassable terrain/feature.
    return not p:IsImpassable() and not p:IsMountain() and (p:IsWater() == sea or (embarked and p:IsWater()))
  end
  -- Borders: the engine's pathfinder will not cross another civ's territory without open borders (or a
  -- war), and refused a city-state's coast outright (live t287: Caravel -> (53,32) inside Sidon, "no
  -- path" although the flood fill said reachable). Owner is the last-seen owner a human sees on the
  -- map (GetRevealedOwner), never the true one on a fogged plot.
  local open_cache = {}
  local function closed_owner(p)
    local o = p.GetRevealedOwner and p:GetRevealedOwner(team, false) or (p.GetOwner and p:GetOwner()) or -1
    if o == nil or o < 0 or o == pid then return nil end
    if open_cache[o] == nil then
      local ot = Players[o] and Players[o]:GetTeam() or -1
      local ok = (ot == team)
      if not ok and ot >= 0 and Teams then
        local mine, theirs = Teams[team], Teams[ot]
        ok = (mine and mine.IsAtWar and mine:IsAtWar(ot)) and true or false
        if not ok and theirs and theirs.IsAllowsOpenBordersToTeam then ok = theirs:IsAllowsOpenBordersToTeam(team) and true or false end
      end
      open_cache[o] = ok
    end
    if open_cache[o] then return nil end
    return o
  end
  -- Flood fill from the unit over revealed, traversable plots: which frontier plots are reachable
  -- through the KNOWN map (Unit:GeneratePath is NYI here, so this is the only path hint). A plot on
  -- the far side of a landmass is reachable=false even when its hex distance is small (live t272:
  -- the Caravel was sent to (52,6), distance 2, and the engine detoured it west for two turns).
  -- Only IsRevealed is read on fogged plots; the fill never steps into them.
  local reached, frontier_queue, head = {}, {}, 1
  local function key(x, y) return y * w + x end
  reached[key(ux, uy)] = true
  frontier_queue[1] = Map.GetPlot(ux, uy)
  while head <= #frontier_queue do
    local c = frontier_queue[head]; head = head + 1
    local cx, cy = c:GetX(), c:GetY()
    for dx = -1, 1 do for dy = -1, 1 do
      local q = Map.PlotXYWithRangeCheck(cx, cy, dx, dy, 1)
      if q and not reached[key(q:GetX(), q:GetY())] and q:IsRevealed(team, false) and traversable(q) and not closed_owner(q) then
        reached[key(q:GetX(), q:GetY())] = true
        frontier_queue[#frontier_queue + 1] = q
      end
    end end
  end
  for i = 0, Map.GetNumPlots() - 1 do
    local p = Map.GetPlotByIndex(i)
    if p then
      if not p:IsRevealed(team, false) then
        unrevealed = unrevealed + 1
      elseif traversable(p) then
        local px, py, n = p:GetX(), p:GetY(), 0
        for dx = -1, 1 do for dy = -1, 1 do
          local q = Map.PlotXYWithRangeCheck(px, py, dx, dy, 1)
          if q and (q:GetX() ~= px or q:GetY() ~= py) and not q:IsRevealed(team, false) then n = n + 1 end
        end end
        if n > 0 then
          local e = { x = px, y = py, unrevealed_neighbors = n,
                      distance = Map.PlotDistance(ux, uy, px, py),
                      reachable = reached[key(px, py)] == true,
                      t = short(info_type(GameInfo.Terrains, p:GetTerrainType())) }
          -- The map's top/bottom rows are the polar ice a human sees on the minimap frame; a frontier
          -- plot there mostly reveals more ice, so flag it rather than let it outrank real coastline.
          -- (rows 0-1 and h-2..h-1 are the ice; a plot on row 2 only borders it, so flag it too: live
          -- t272 the whole y=2 row outranked the real eastern coastline)
          if py <= 2 or py >= h - 3 then e.map_edge = true end
          local co = closed_owner(p)
          if co then e.closed_border = co end  -- owner id: a border the unit may not cross (no open borders)
          -- v266: a visible unit of another player on the plot (live 2026-10-08, England t129 and t130: the top
          -- row was an Ottoman Gatling Gun's plot, then an Ottoman Worker's; move_unit refuses both, a human sees
          -- the unit). Named and sorted after the free plots, never dropped: it is still where the fog ends.
          -- v268: a visible city of another player on the plot is named the same way (`city`): move_unit refuses
          -- it at peace and a human sees the banner (live England t138: Edirne's own plot bordered the fog, and its
          -- row said only that a Great General stood there).
          local okv, vis = pcall(function() return p:IsVisible(team, false) end)
          if okv and vis then
            pcall(function()
              if p:IsCity() then
                local c = p:GetPlotCity()
                if c and c:GetOwner() ~= pid then e.city = { player_id = c:GetOwner(), name = c:GetName() } end
              end
            end)
            pcall(function()
              for k = 0, p:GetNumUnits() - 1 do
                local o = p:GetUnit(k)
                if o and o:GetOwner() ~= pid and not (o.IsInvisible and o:IsInvisible(team, false)) then
                  e.occupied = { player_id = o:GetOwner(), unit = short(info_type(GameInfo.Units, o:GetUnitType())) }
                  break
                end
              end
            end)
          end
          out[#out + 1] = e
        end
      end
    end
  end
  -- A held plot (a foreign unit or city on it) sorts after the free ones, so frontier[1] is always a plot the
  -- explorer can walk to when one exists.
  local function held(e) return e.occupied ~= nil or e.city ~= nil end
  table.sort(out, function(a, b)
    if a.reachable ~= b.reachable then return a.reachable end
    if held(a) ~= held(b) then return not held(a) end
    if a.distance ~= b.distance then return a.distance < b.distance end
    if a.unrevealed_neighbors ~= b.unrevealed_neighbors then return a.unrevealed_neighbors > b.unrevealed_neighbors end
    if a.x ~= b.x then return a.x < b.x end
    return a.y < b.y
  end)
  local frontier_total = #out
  limit = limit or 12
  -- v268: the cut keeps the nearest `limit` free plots and, after them, every held plot no farther than the
  -- farthest free plot shown (at most `limit` of those). Cutting the sorted list at `limit` dropped every held
  -- row as soon as the frontier was longer than the limit: live England t138, 143 frontier plots, an Ottoman
  -- Rifleman two plots from the scout and Edirne's plot at three sorted 59th and 60th, behind every free plot,
  -- out of reach of any limit the tool accepts. A unit two plots away is frontier the explorer walks around.
  if #out > limit then
    local kept, n_free, far = {}, 0, 0
    for _, e in ipairs(out) do
      if not held(e) and n_free < limit then
        n_free = n_free + 1; kept[n_free] = e
        if e.distance > far then far = e.distance end
      end
    end
    if n_free == 0 then far = math.huge end
    local n_held = 0
    for _, e in ipairs(out) do
      if held(e) and e.distance <= far and n_held < limit then n_held = n_held + 1; kept[#kept + 1] = e end
    end
    out = kept
  end
  return { ok = true, unit = { id = unit_id, x = ux, y = uy, domain = sea and "SEA" or "LAND", embarked = embarked },
           map = { width = w, height = h }, unrevealed_plots = unrevealed,
           frontier_total = frontier_total, frontier = out,
           note = (frontier_total == 0) and ((unrevealed == 0) and "the whole map is revealed"
                  or "no revealed plot of this unit's domain borders the fog; the remaining fog is not reachable from here without embarking or another unit") or nil }
end

-- The six neighbours in the engine's own direction order, with the name a caller can say back.
local DIRECTION_NAMES = { "NE", "E", "SE", "SW", "W", "NW" }

-- Whether stepping from `a` to its neighbour `b` in direction index d (0 = NE .. 5 = NW) crosses a river.
-- A plot stores the river on three of its edges: IsWOfRiver = its east edge, IsNWOfRiver = its south-east
-- edge, IsNEOfRiver = its south-west edge (the setters AssignStartingPlots and the map scripts use); the
-- other three edges belong to the neighbour. Static terrain, read only for revealed plots.
local function river_crossing(a, b, d)
  local ok, v = pcall(function()
    if d == 0 then return b:IsNEOfRiver() end
    if d == 1 then return a:IsWOfRiver() end
    if d == 2 then return a:IsNWOfRiver() end
    if d == 3 then return a:IsNEOfRiver() end
    if d == 4 then return b:IsWOfRiver() end
    return b:IsNWOfRiver()
  end)
  return (ok and v) and true or nil
end

-- Where the unit can end this turn's move (the movement highlight a human sees on selecting it; 2026-11-06). The
-- engine's own answers are closed: Unit:GeneratePath is NYI, GetPathEndTurnPlot needs the mouse pathfinder and
-- Plot:MovementCost crashes the game (docs/LIMITATIONS.md). So this walks step_cost.lua's one-step rule outward
-- from the unit, most moves left first: a plot is entered when the move order would not be refused in passing
-- (H.move_refusal with `transit`: terrain, domain, a city at peace, closed borders), no visible enemy holds it
-- (that is an attack, see `targets`) and the unit may cross its water (deep ocean needs the tech or promotion);
-- a river crossing, embarking and zone of control spend every move exactly as on a neighbour. A plot is listed
-- when the unit may also stop on it (the full H.move_refusal). Fog: unrevealed plots are never entered; a fogged
-- one is priced as last seen and named in `fogged`, since it may hold what stops the move. This turn only:
-- nothing here says how many turns a farther plot takes.
local REACH_DISTANCE, REACH_PLOTS = 6, 90

local function known_city(q, team)
  local ok, v = pcall(function()
    if not q:IsCity() then return false end
    if q:IsVisible(team, false) then return true end
    local c = q:GetPlotCity()
    return (c and c:IsRevealed(team, false)) and true or false
  end)
  return (ok and v) and true or false
end

local function enemy_held(q, pid, team)
  if not q:IsVisible(team, false) then return false end
  if H.enemy_city_at(q, pid) then return true end
  for i = 0, q:GetNumUnits() - 1 do
    local o = q:GetUnit(i)
    if o and o:GetOwner() ~= pid and not o:IsInvisible(team, false) then
      local op = Players[o:GetOwner()]
      if op and (op:IsBarbarian() or Teams[team]:IsAtWar(op:GetTeam())) then return true end
    end
  end
  return false
end

-- Deep ocean: an embarked land unit needs a tech with EmbarkedAllWaterPassage (Astronomy) or an EmbarkedAllWater
-- promotion (Polynesia); a ship is kept out by an OceanImpassable promotion, or OceanImpassableUntilAstronomy
-- before that tech (CvUnit::canEnterTerrain). Read from the tables: the engine's Lua names no getter for either.
local function ocean_barred(u, team)
  local ocean = GameInfoTypes and GameInfoTypes.TERRAIN_OCEAN
  if not ocean then return function() return false end end
  local function on(v) return v == true or v == 1 end
  local barred = false
  pcall(function()
    local passage = false
    for row in GameInfo.Technologies() do
      if on(row.EmbarkedAllWaterPassage) and Teams[team]:IsHasTech(row.ID) then passage = true end
    end
    if u:GetDomainType() == DomainTypes.DOMAIN_LAND then
      barred = not passage
      for row in GameInfo.UnitPromotions() do
        if on(row.EmbarkedAllWater) and u:IsHasPromotion(row.ID) then barred = false end
      end
    else
      for row in GameInfo.UnitPromotions() do
        if u:IsHasPromotion(row.ID)
           and (on(row.OceanImpassable) or (on(row.OceanImpassableUntilAstronomy) and not passage)) then
          barred = true
        end
      end
    end
  end)
  return function(q) return barred and q:GetTerrainType() == ocean end
end

local function unit_reach(u, pid, team, stepper)
  local ux, uy = u:GetX(), u:GetY()
  local start = Map.GetPlot(ux, uy)
  local function key(q) return q:GetX() .. "," .. q:GetY() end
  local no_ocean = ocean_barred(u, team)
  local sk = key(start)
  local best, plot_of, open, queued = { [sk] = stepper.have }, { [sk] = start }, { sk }, {}
  local transit, capped = {}, false
  while #open > 0 do
    local bi = 1
    for i = 2, #open do if best[open[i]] > best[open[bi]] then bi = i end end
    local k = table.remove(open, bi)
    queued[k] = nil
    local from, left = plot_of[k], best[k]
    if left > 0 then
      for d = 0, 5 do
        local q = Map.PlotDirection(from:GetX(), from:GetY(), d)
        if q and q:IsRevealed(team, false) then
          local qk = key(q)
          if transit[qk] == nil then
            transit[qk] = not (enemy_held(q, pid, team) or no_ocean(q) or H.move_refusal(u, q, pid, true, true))
          end
          if transit[qk] then
            if Map.PlotDistance(ux, uy, q:GetX(), q:GetY()) > REACH_DISTANCE then
              capped = true
            else
              local ok, _, raw = pcall(stepper.step, from, q, known_city(q, team), river_crossing(from, q, d), left)
              if ok and raw and raw > (best[qk] or -1) then
                best[qk], plot_of[qk] = raw, q
                if not queued[qk] then queued[qk] = true; open[#open + 1] = qk end
              end
            end
          end
        end
      end
    end
  end
  local rows = {}
  for k, q in pairs(plot_of) do
    if k ~= sk and not H.move_refusal(u, q, pid, true) then
      rows[#rows + 1] = { q = q, d = Map.PlotDistance(ux, uy, q:GetX(), q:GetY()),
                          left = math.floor(best[k] / stepper.denom * 100 + 0.5) / 100 }
    end
  end
  table.sort(rows, function(a, b)
    if a.d ~= b.d then return a.d < b.d end
    if a.q:GetY() ~= b.q:GetY() then return a.q:GetY() > b.q:GetY() end
    return a.q:GetX() < b.q:GetX()
  end)
  local out = { moves = stepper.have / stepper.denom }
  if u:MovesLeft() <= 0 then out.next_turn = true end
  local plots, fogged, left_at = {}, {}, {}
  for i, r in ipairs(rows) do
    if i > REACH_PLOTS then capped = true; break end
    plots[#plots + 1] = { r.q:GetX(), r.q:GetY(), r.left }
    left_at[key(r.q)] = r.left
    if not r.q:IsVisible(team, false) then fogged[#fogged + 1] = { r.q:GetX(), r.q:GetY() } end
  end
  if #plots > 0 then out.plots = plots else out.none = true end
  if #fogged > 0 then out.fogged = fogged end
  if capped then out.capped = true end
  return out, left_at
end

-- The way a land unit ashore would go to a land plot: by land alone, and with the water (v347). Live 2026-11-23
-- (Opus, the duel t188 to t212): the pathfinder put Cannons and Artillery in a lake and on the coast beside
-- Galleasses on moves of two and three plots to land, and the reply said nothing before or after ("would have
-- saved about 3 artillery"). The engine's own path is closed to Lua (Unit:GeneratePath is NYI, see `reach`), so
-- this walks step_cost.lua's rule over the map the seat knows, a turn at a time: one turn's move from the unit,
-- then one from every plot that move could have ended on, and so on. A plot a move ends on is one the unit may
-- stand on (the full H.move_refusal: a plot that holds another of my units is passed through, never stopped on;
-- a walk that ignored this called a way through my own Artillery two turns and the engine went another way,
-- live on the t210 save); embarking, a river and zone of control spend every move as on a neighbour. Each plot is
-- kept twice, dry and by a way that touched water, so the answer is both routes: `land` and `water`, each with
-- its `turns` (0: it arrives in this turn's move) and the plot this turn's move ends on (`stop`), `water` with
-- the plot it enters the water at. Only plots within ROUTE_SLACK of the direct line are walked; nil when nothing
-- can be said (an air unit, or more states than ROUTE_STATES).
local ROUTE_SLACK, ROUTE_STATES, ROUTE_LAND_BEHIND = 6, 4000, 6
local city_in_sight = known_city   -- under another name: tests/test_puppet_guards.py reads "own_city(" as a city write

function H.move_route(u, dest, pid)
  local team = Players[pid]:GetTeam()
  local okc, _, stepper = pcall(step_costs, u, pid)
  if not (okc and stepper) then return nil end
  local sx, sy, tx, ty = u:GetX(), u:GetY(), dest:GetX(), dest:GetY()
  local span = Map.PlotDistance(sx, sy, tx, ty)
  local full = u:MaxMoves()
  local no_ocean = ocean_barred(u, team)
  local function key(q) return q:GetX() .. "," .. q:GetY() end
  local dk = key(dest)
  local transit, standable = { [dk] = true }, {}
  local function passable(q)
    local k = key(q)
    local v = transit[k]
    if v == nil then
      v = false
      if q:IsRevealed(team, false)
         and Map.PlotDistance(sx, sy, q:GetX(), q:GetY()) + Map.PlotDistance(q:GetX(), q:GetY(), tx, ty) <= span + ROUTE_SLACK
         and not (enemy_held(q, pid, team) or no_ocean(q) or H.move_refusal(u, q, pid, true, true)) then
        v = true
      end
      transit[k] = v
    end
    return v
  end
  local function may_stand(q)
    local k = key(q)
    local v = standable[k]
    if v == nil then
      v = not H.move_refusal(u, q, pid, true)
      standable[k] = v
    end
    return v
  end
  local start = u:GetPlot()
  local origin = { q = start, w = 0, turn = -1 }
  local stops = { [key(start) .. "|0"] = origin }   -- every plot|wet a turn's move can end on, with the turn
  local frontier = { origin }
  local found, states, turn = {}, 1, 0
  while #frontier > 0 do
    -- one turn's move from every plot the turn before could end on, most moves left first
    local have0 = (turn == 0) and stepper.have or full
    local left_at, open, reached = {}, {}, {}
    for _, s in ipairs(frontier) do
      local id = key(s.q) .. "|" .. s.w
      left_at[id] = have0
      open[#open + 1] = { q = s.q, w = s.w, left = have0, src = s, id = id, wet = s.wet }
    end
    while #open > 0 do
      local bi = 1
      for i = 2, #open do if open[i].left > open[bi].left then bi = i end end
      local e = table.remove(open, bi)
      if e.left > 0 and left_at[e.id] == e.left then
        for d = 0, 5 do
          local q = Map.PlotDirection(e.q:GetX(), e.q:GetY(), d)
          if q and passable(q) then
            local city = city_in_sight(q, team)
            local ok, _, raw = pcall(stepper.step, e.q, q, city, river_crossing(e.q, q, d), e.left)
            if ok and raw then
              local w, wet = e.w, e.wet
              if q:IsWater() and not city then
                w = 1
                wet = wet or q
              end
              local qk = key(q)
              local id = qk .. "|" .. w
              if raw > (left_at[id] or -1) then
                left_at[id] = raw
                states = states + 1
                if qk == dk then
                  found[w] = found[w] or { turn = turn, src = e.src, wet = wet }
                else
                  if not stops[id] and may_stand(q) then
                    local st = { q = q, w = w, turn = turn, prev = e.src, wet = wet }
                    stops[id] = st
                    reached[#reached + 1] = st
                  end
                  if raw > 0 then open[#open + 1] = { q = q, w = w, left = raw, src = e.src, id = id, wet = wet } end
                end
              end
            end
          end
        end
      end
    end
    -- fewest turns first: the turn the dry way arrives in is played out, so a wet way of the same turns is in;
    -- a dry way this far behind the wet one is not looked for further
    if found[0] then break end
    if found[1] and turn >= found[1].turn + ROUTE_LAND_BEHIND then break end
    if states > ROUTE_STATES then return nil end
    frontier, turn = reached, turn + 1
  end
  -- the plot this turn's move ends on, on the way that was found
  local function first_stop(f)
    local s = f.src
    if s.turn == -1 then return dest end
    while s.prev and s.prev.turn ~= -1 do s = s.prev end
    return s.q
  end
  local out = { states = states }
  if found[0] then out.land = { turns = found[0].turn, stop = first_stop(found[0]) } end
  if found[1] then out.water = { turns = found[1].turn, embark_at = found[1].wet, stop = first_stop(found[1]) } end
  return out
end

-- Who can strike the plot a unit stands on (v347): the enemy cities in sight whose strike reaches it (a city
-- fires over hills and forest) and the enemy units in sight with a ranged attack whose range covers it, by the
-- range of their kind (Units.Range, the pedia's figure: a promotion the banner does not show is not read). Units
-- at war with me and barbarians; an embarked land unit does not fire. nil when nothing does. A move's reply
-- carries it as `in_range_of` (H.unit_pos): Artillery that ended a move inside a city's two plots was lost to it
-- with nothing said (live 2026-11-23, the duel t201).
local THREAT_LOOK = 4

function H.strike_threats(u, pid)
  local team = Players[pid]:GetTeam()
  local ux, uy = u:GetX(), u:GetY()
  local city_range = (GameDefines and GameDefines.CITY_ATTACK_RANGE) or 2
  local air = DomainTypes and DomainTypes.DOMAIN_AIR
  local out = {}
  for dx = -THREAT_LOOK, THREAT_LOOK do for dy = -THREAT_LOOK, THREAT_LOOK do
    local q = Map.PlotXYWithRangeCheck(ux, uy, dx, dy, THREAT_LOOK)
    if q and q:IsVisible(team, false) and not (q:GetX() == ux and q:GetY() == uy) then
      local d = math.floor(Map.PlotDistance(ux, uy, q:GetX(), q:GetY()))
      local c = H.enemy_city_at(q, pid)
      if c then
        if d <= city_range then
          out[#out + 1] = { city = c:GetName(), owner = H.owner_label(c:GetOwner(), pid), x = q:GetX(), y = q:GetY(),
                            distance = d, range = city_range }
        end
      else
        for i = 0, q:GetNumUnits() - 1 do
          local o = q:GetUnit(i)
          if o and o:GetOwner() ~= pid and not o:IsInvisible(team, false) and not o:IsDelayedDeath() then
            local op = Players[o:GetOwner()]
            local row = GameInfo.Units[o:GetUnitType()]
            local range, ranged = row and row.Range or 0, row and row.RangedCombat or 0
            if op and row and range > 0 and ranged > 0 and d <= range and o:GetDomainType() ~= air
               and not (o.IsEmbarked and o:IsEmbarked())
               and (op:IsBarbarian() or Teams[team]:IsAtWar(op:GetTeam())) then
              out[#out + 1] = { unit = short(row.Type), owner = H.owner_label(o:GetOwner(), pid), x = q:GetX(),
                                y = q:GetY(), distance = d, range = range, hp = o:GetCurrHitPoints() }
            end
          end
        end
      end
    end
  end end
  if #out == 0 then return nil end
  table.sort(out, function(a, b)
    if a.distance ~= b.distance then return a.distance < b.distance end
    if a.y ~= b.y then return a.y > b.y end
    return a.x < b.x
  end)
  return out
end

-- A plot's grid cell: ground letter then occupant letter (the legend is the reply reference, docs/TOOL_REPLIES.md state(what="unit", view="tactical"); GitLab #152).
-- The ground is the terrain, or C for a city in sight: the city is the plot, its units are what stands on it, so a unit
-- in a city keeps the city drawn (GitLab #177, Celts t4: a Scout on Edinburgh read ".@" and the city was gone).
-- Fog rules as describe_plot: a fogged plot shows remembered terrain and '?' for its occupant.
local ROUGH_FEATURES = { FOREST = true, JUNGLE = true, MARSH = true }
local function tactical_cell(q, team, u, pid, hostile_at)
  if not q then return "  " end
  if not q:IsRevealed(team, false) then return "__" end
  local t = "."
  if q:IsVisible(team, false) and q:IsCity() then t = "C"
  elseif q:IsMountain() or q:IsImpassable() then t = "M"
  elseif q:IsWater() then t = "~"
  elseif q:IsHills() then t = "H"
  else
    local f
    if q:IsVisible(team, false) then
      local fid = q:GetFeatureType()
      f = fid >= 0 and short(info_type(GameInfo.Features, fid)) or nil
    else
      f = H.remembered_feature(q, team)
    end
    if f and ROUGH_FEATURES[f] then t = "F" end
  end
  if not q:IsVisible(team, false) then return t .. "?" end
  if q:GetX() == u:GetX() and q:GetY() == u:GetY() then return t .. "@" end
  local k = q:GetX() .. "," .. q:GetY()
  if hostile_at[k] then return t .. "X" end
  local mine, other = false, false
  for i = 0, q:GetNumUnits() - 1 do
    local o = q:GetUnit(i)
    if o and not o:IsInvisible(team, false) then
      if o:GetOwner() == pid then mine = true else other = true end
    end
  end
  if other then return t .. "o" end
  if mine then return t .. "u" end
  return t .. " "
end

-- #31: one bounded read around one unit -- the picture a human gets by looking at the map around a selected
-- unit, with the relationships spelled out: the six neighbours by coordinate (the engine's PlotDirection, so
-- map wrap and the edge rows are the engine's own answer), what move_unit would do with each, the visible
-- occupants and known cities in `radius`, and the unit's attack targets with the combat panel's own previews
-- (H.melee_targets / H.ranged_targets, not a second combat model). Fog is the human's: a fogged plot shows
-- what was last seen and never a live occupant; an unrevealed one shows nothing but that it is unrevealed.
-- Movement: `move` is move_unit's own answer before it sends anything (H.move_refusal, the same checks); an open
-- step says what it costs this unit (`cost`, `left`, in moves) and names the enemy whose zone of control ends the
-- move there (`zoc`), from step_cost.lua (GitLab #180); `reach` walks the same rule to every plot this turn's move
-- can end on. There are no turns-to-reach: Unit:GeneratePath is NYI and Plot:MovementCost crashes the game
-- (docs/LIMITATIONS.md).
function H.tactical_view(unit_id, pid, radius, detail)
  local p = Players[pid]
  local u = p and p:GetUnitByID(unit_id)
  if not u then return { ok = false, err = "no such unit" } end
  local radius_given = radius ~= nil
  radius = radius or 2
  local full = (detail == "full")
  local team = p:GetTeam()
  local ux, uy = u:GetX(), u:GetY()
  local here = Map.GetPlot(ux, uy)
  local denom = move_denom()
  local moves = u:MovesLeft() / denom
  local unit = { id = unit_id, type = short(info_type(GameInfo.Units, u:GetUnitType())), x = ux, y = uy,
                 moves = moves, hp = u:GetCurrHitPoints(), max_hp = u:GetMaxHitPoints() }
  pcall(function() unit.max_moves = u:MaxMoves() / denom end)
  pcall(function()
    unit.domain = (u:GetDomainType() == DomainTypes.DOMAIN_SEA and "SEA")
                  or (u:GetDomainType() == DomainTypes.DOMAIN_AIR and "AIR") or "LAND"
  end)
  if u.IsEmbarked and u:IsEmbarked() then unit.embarked = true end
  unit.territory = H.plot_territory(here, pid)   -- v248: whose land the unit stands on, when not its own
  if u:IsCombatUnit() then
    pcall(function() unit.strength = u:GetBaseCombatStrength() end)
    pcall(function()
      local rs = H.ranged_strength(u)
      if rs > 0 then
        unit.ranged_strength = rs
        local row = GameInfo.Units[u:GetUnitType()]
        unit.range = (u.Range and u:Range()) or (row and row.Range) or nil   -- Range(): promotions count
      end
    end)
  else
    unit.civilian = true
  end

  -- v261: the unit's own line of sight, from the engine's CvPlot::canSeePlot -- the test canRangeStrikeAt makes
  -- for a ranged unit that does not ignore LOS, with the unit's attack range in place of its sight: high ground
  -- adds a plot, hills and forest in between block. Live t183 (Venice): a Crossbowman on hills saw 31 plots out
  -- to 3 and could fire at all of them, one on flat ground 24, a Musketman 20 -- the fixed radius 2 drew 18
  -- either way and never listed the ring a hill lets a ranged unit shoot into. With no radius given the view
  -- reaches as far as the unit itself sees or shoots (at least 2, at most 5).
  local los, fire_los, probed = {}, {}, {}
  local sight = { range = 0, on_hills = here:IsHills() and true or false, plots = 0, reach = 0 }
  pcall(function() sight.range = u:VisibilityRange() or 0 end)
  local fire = nil
  if unit.range and unit.range > 0 then
    fire = { range = unit.range, plots = 0, reach = 0 }
    pcall(function() if u:IsRangeAttackIgnoreLOS() then fire.ignores_los = true end end)
  end
  if here.CanSeePlot and (sight.range > 0 or fire) then
    -- The unit sees the plot it stands on: the probe below skips it (CanSeePlot is asked of other plots), so a
    -- garrisoned Archer's own city read in_sight false at distance 0 (GitLab #131, Siam t4 and t31). Its fire
    -- LOS stays unset there: a ranged unit cannot target its own plot.
    if sight.range > 0 then los[ux .. "," .. uy] = true end
    local probe = math.min(5, math.max(sight.range, fire and fire.range or 0) + 1)
    for dx = -probe, probe do for dy = -probe, probe do
      local q = Map.PlotXYWithRangeCheck(ux, uy, dx, dy, probe)
      if q and not (q:GetX() == ux and q:GetY() == uy) then
        local k = q:GetX() .. "," .. q:GetY()
        if not probed[k] then
          probed[k] = true
          local d = math.floor(Map.PlotDistance(ux, uy, q:GetX(), q:GetY()))  -- an integer: it sizes the loops below
          local ok_s, s_ok = pcall(function() return sight.range > 0 and here:CanSeePlot(q, team, sight.range, -1) end)
          if ok_s and s_ok then
            los[k] = true; sight.plots = sight.plots + 1
            if d > sight.reach then sight.reach = d end
          end
          if fire then
            local can
            if fire.ignores_los then can = d <= fire.range
            else
              local ok_f, f_ok = pcall(function() return here:CanSeePlot(q, team, fire.range, -1) end)
              can = ok_f and f_ok
            end
            if can then
              fire_los[k] = true; fire.plots = fire.plots + 1
              if d > fire.reach then fire.reach = d end
            end
          end
        end
      end
    end end
  end
  unit.sight = sight
  if fire then unit.fire_los = fire end
  local radius_from = "given"
  if not radius_given then
    local reach = math.max(sight.reach, fire and fire.reach or 0)
    if reach > 2 then radius = math.min(5, reach); radius_from = "sight" else radius_from = "default" end
  end

  local players = {}
  local function label(o)
    if o and o >= 0 then players[tostring(o)] = players[tostring(o)] or H.owner_label(o, pid) end
    return o
  end

  -- Attack targets with the combat panel's previews; the summary keeps the numbers, full keeps the modifiers.
  local targets = {}
  local attack_at = {}
  for _, list in ipairs({ H.melee_targets(u, pid), H.ranged_targets(u, pid) }) do
    for _, t in ipairs(list) do
      if not full and t.preview and t.preview.modifiers then
        -- The summary keeps the numbers; the modifier rows become one line a side (#121: the agent wanted to see
        -- where an 8-strength Warrior's 9.6 came from without the full view).
        local brief = {}
        for _, side in ipairs({ "mine", "theirs" }) do
          local rows = t.preview.modifiers[side]
          if type(rows) == "table" and #rows > 0 then
            local parts = {}
            for _, m in ipairs(rows) do
              if type(m) == "table" and m.text then
                local v = m.value
                local vs = v and ((v > 0 and "+" or "") .. tostring(v) .. (m.percent and "%" or "")) or nil
                parts[#parts + 1] = vs and (tostring(m.text) .. " " .. vs) or tostring(m.text)
              end
            end
            if #parts > 0 then brief[side] = table.concat(parts, "; ") end
          end
        end
        if next(brief) then t.preview.modifiers_brief = brief end
        t.preview.modifiers = nil
      end
      t.kind = (t.how and t.how:find("RANGE", 1, true)) and "ranged" or "melee"
      if t.kind == "melee" then attack_at[t.x .. "," .. t.y] = t end
      targets[#targets + 1] = t
    end
  end

  -- Visible occupants and known cities in radius; fog counts.
  local occupants, cities, hostile_at = {}, {}, {}
  local fog = { visible = 0, fogged = 0, unrevealed = 0, unseen_within_2 = 0 }
  -- The plots in radius once each (on a wrapped map narrower than the square, two offsets name one plot).
  local area, seen_plot = {}, {}
  for dx = -radius, radius do for dy = -radius, radius do
    local q = Map.PlotXYWithRangeCheck(ux, uy, dx, dy, radius)
    if q and not seen_plot[q:GetX() .. "," .. q:GetY()] then
      seen_plot[q:GetX() .. "," .. q:GetY()] = true
      area[#area + 1] = q
    end
  end end
  for _, q in ipairs(area) do
    do
      local qx, qy = q:GetX(), q:GetY()
      local d = Map.PlotDistance(ux, uy, qx, qy)
      if not q:IsRevealed(team, false) then
        fog.unrevealed = fog.unrevealed + 1
        if d <= 2 then fog.unseen_within_2 = fog.unseen_within_2 + 1 end
      elseif not q:IsVisible(team, false) then
        fog.fogged = fog.fogged + 1
        if d <= 2 then fog.unseen_within_2 = fog.unseen_within_2 + 1 end
        pcall(function()
          local c = q:IsCity() and q:GetPlotCity()
          if c and c:IsRevealed(team, false) then
            cities[#cities + 1] = { x = qx, y = qy, distance = d, name = c:GetName(), owner = label(c:GetOwner()),
                                    last_seen = true }
          end
        end)
      else
        fog.visible = fog.visible + 1
        if q:IsCity() then
          local c = q:GetPlotCity()
          local row = { x = qx, y = qy, distance = d, name = c:GetName(), owner = label(c:GetOwner()),
                        hp = c:GetMaxHitPoints() - c:GetDamage(), max_hp = c:GetMaxHitPoints() }
          pcall(function() row.strength = c:GetStrengthValue() / 100 end)
          if sight.range > 0 then row.in_sight = los[qx .. "," .. qy] and true or false end
          if fire then row.in_fire_los = fire_los[qx .. "," .. qy] and true or false end
          if H.enemy_city_at(q, pid) then row.hostile = true; hostile_at[qx .. "," .. qy] = true end
          cities[#cities + 1] = row
        end
        for i = 0, q:GetNumUnits() - 1 do
          local o = q:GetUnit(i)
          if o and not (o:GetOwner() == pid and o:GetID() == unit_id) then
            if not o:IsInvisible(team, false) and not o:IsDelayedDeath() then
              local owner = o:GetOwner()
              local row = { x = qx, y = qy, distance = d, owner = label(owner), id = o:GetID(),
                            unit = short(info_type(GameInfo.Units, o:GetUnitType())), hp = o:GetCurrHitPoints() }
              if sight.range > 0 then row.in_sight = los[qx .. "," .. qy] and true or false end
              if fire then row.in_fire_los = fire_los[qx .. "," .. qy] and true or false end
              if o:IsCombatUnit() then
                pcall(function() row.strength = o:GetBaseCombatStrength() end)
                pcall(function()
                  local rs = H.ranged_strength(o)
                  if rs > 0 then
                    row.ranged_strength = rs
                    local r = GameInfo.Units[o:GetUnitType()]
                    row.range = (o.Range and o:Range()) or (r and r.Range) or nil
                  end
                end)
              else
                row.civilian = true
              end
              if owner ~= pid then
                local op = Players[owner]
                if op and (op:IsBarbarian() or Teams[team]:IsAtWar(op:GetTeam())) then
                  row.hostile = true
                  hostile_at[qx .. "," .. qy] = true
                end
              end
              occupants[#occupants + 1] = row
            end
          end
        end
      end
    end
  end
  table.sort(occupants, function(a, b)
    if (a.hostile or false) ~= (b.hostile or false) then return a.hostile == true end
    if a.distance ~= b.distance then return a.distance < b.distance end
    if a.x ~= b.x then return a.x < b.x end
    if a.y ~= b.y then return a.y < b.y end
    return a.id < b.id
  end)
  table.sort(cities, function(a, b) return a.distance < b.distance end)

  -- The six neighbours: coordinates, remembered terrain, river crossing, occupants, and move_unit's answer.
  local move_mission = info_id("MISSION_MOVE_TO")
  local okc, step_cost, stepper = pcall(step_costs, u, pid)   -- nil: no cost is read (an air unit, or a getter failed)
  if not okc then step_cost, stepper = nil, nil end
  local neighbors = {}
  for d = 0, 5 do
    local q = Map.PlotDirection(ux, uy, d)
    local n = { dir = DIRECTION_NAMES[d + 1] }
    if not q then
      n.off_map = true
      n.move = "refused"; n.why = "off the map edge"
    else
      n.x, n.y = q:GetX(), q:GetY()
      local e = H.describe_plot(q, team)
      if not e then
        n.vis = "unrevealed"
        n.move = "refused"; n.why = "plot is not revealed"
      else
        n.vis = e.vis and "visible" or "fogged"
        n.t = e.t
        for _, f in ipairs({ "hills", "mountain", "lake", "feature", "remembered", "improvement", "pillaged", "route" }) do
          n[f] = e[f]
        end
        if e.owner then n.owner = label(e.owner) end
        n.river_crossing = river_crossing(here, q, d)
        if e.city then n.city = e.city.name end
        if e.units then
          local seen = {}
          for _, o in ipairs(e.units) do
            label(o.owner)
            seen[#seen + 1] = { owner = o.owner, id = o.id, unit = o.type, hp = o.hp }
          end
          n.units = seen
        end
        local k = n.x .. "," .. n.y
        if attack_at[k] then
          n.move = "attack"
        elseif hostile_at[k] then
          -- Why it is not an attack, from the same facts H.melee_targets checks (live t42: a Warrior with its
          -- moves spent beside a Barbarian read "no melee attack").
          n.move = "enemy"
          if not u:IsCombatUnit() then
            n.why = "a visible enemy holds this plot; a civilian cannot attack"
          elseif unit.ranged_strength then
            n.why = "a visible enemy holds this plot; a ranged unit shoots it from here (see targets) and does not melee"
          elseif moves <= 0 then
            n.why = "a visible enemy holds this plot; this unit has no moves left to attack it this turn"
          elseif H.melee_domain_refusal(u, q) then
            n.why = "a visible enemy holds this plot; " .. H.melee_domain_refusal(u, q)
          else
            n.why = "a visible enemy holds this plot and this unit cannot attack it"
          end
        else
          local r = H.move_refusal(u, q, pid, true)
          if r then
            n.move = "refused"; n.why = r.err
          elseif moves > 0 and move_mission and u.CanStartMission then
            local ok, can = pcall(function() return u:CanStartMission(move_mission, n.x, n.y, false) end)
            if ok and can then n.move = "open" else n.move = "refused"; n.why = "move is not currently legal" end
          else
            n.move = "open"
          end
          if n.move == "open" and step_cost then
            local okn, c = pcall(step_cost, q, e.city ~= nil, n.river_crossing)
            if okn and c then
              n.cost, n.left = c.cost, c.left
              if c.zoc then label(c.zoc.owner); n.zoc = c.zoc end
            end
          end
        end
      end
    end
    neighbors[#neighbors + 1] = n
  end

  -- The picture: (2r+1) rows north to south, columns listed with their wrapped x.
  local w, h = Map.GetGridSize()
  local wrap = false
  pcall(function() wrap = Map.IsWrapX() and true or false end)
  local cols = {}
  for dx = -radius, radius do
    local gx = ux + dx
    if wrap then gx = gx % w elseif gx < 0 or gx >= w then gx = nil end
    cols[#cols + 1] = gx or -1
  end
  local rows = {}
  for gy = uy + radius, uy - radius, -1 do
    if gy >= 0 and gy < h then
      local cells = {}
      for i, gx in ipairs(cols) do
        -- The box's corners lie beyond `radius` in hex steps: blank, like off-map, so the picture covers
        -- exactly the plots occupants and fog count (live t42: a hostile could be drawn with no occupant row).
        local q = gx >= 0 and Map.PlotDistance(ux, uy, gx, gy) <= radius and Map.GetPlot(gx, gy) or nil
        cells[i] = tactical_cell(q, team, u, pid, hostile_at)
      end
      rows[#rows + 1] = string.format("%3d %s%s", gy, (gy % 2 == 1) and " " or "", table.concat(cells))
    end
  end

  local out = {
    ok = true, unit = unit, radius = radius, radius_from = radius_from, detail = full and "full" or "summary",
    map = { width = w, height = h, wrap_x = wrap },
    neighbors = neighbors, targets = targets, occupants = occupants, cities = cities, fog = fog,
    players = players,
    grid = { cols = cols, rows = rows },
  }
  -- `reach`: every plot this turn's move can end on. Not for a trade unit (it follows its route) or one that cannot move.
  if stepper and not (u.IsTrade and u:IsTrade()) and not (u.IsImmobile and u:IsImmobile()) then
    local okr, r, left_at = pcall(unit_reach, u, pid, team, stepper)
    if okr then
      out.reach = r
      -- A move order is the engine's pathfinder, not the direct step: where the direct step spends every move (zone
      -- of control, a river) and a way around keeps some, the unit goes around. Live combat-lab t266 (2026-11-13): a
      -- Musketman's E neighbour read left 0 under a Warrior's zone of control, reach said 0.67 by the road behind,
      -- and the order arrived with 0.67. The neighbour says what the order does; `detour` marks it, `zoc` still
      -- names what the direct step would have met.
      for _, n in ipairs(neighbors) do
        local best = n.move == "open" and n.left and left_at[tostring(n.x) .. "," .. tostring(n.y)]
        if best and best > n.left then
          n.cost = math.floor((r.moves - best) * 100 + 0.5) / 100
          n.left, n.detour = best, true
        end
      end
    end
  end
  if moves <= 0 then out.note = "this unit has no moves left this turn; `move` shows what order(to='unit', action='move') would do next turn from here" end
  if full then
    local plots = {}
    for _, q in ipairs(area) do
      local e = H.describe_plot(q, team)
      if e then plots[#plots + 1] = e end
    end
    out.plots = plots
  end
  return out
end
