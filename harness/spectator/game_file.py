"""A game as one file: one JSON line for every turn, written as the game is played.

The page's stream (feed.py) is what a watcher saw, at the watcher's pace: a snapshot when something moved, nothing
when no one polled. A game file is the game itself, turn by turn. A handler inside the game (`INSTALL`, on
`GameEvents.PlayerDoTurn`) takes the whole world the moment a game turn's first player begins it and keeps it in the
game until it is fetched, so a turn the engine played in a second between two polls is in the file like any other.
This backend is the one writer: it puts the handler in, fetches what it took and appends one line a turn.

The file, JSON lines, each a JSON object with its keys in order and no spaces:

    line 1   kind "game"   what never changes: `game` (the game's terms and its players), `map` (the static map,
                           mapdump.py's reply), `key` (a name for the game), `written_by` (the versions that
                           wrote the file) and, for a benchmark run, `run` (the save, the player, the seed)
    then     kind "start"  the world as the recorder found it: at its start and after every load of the game
             kind "turn"   the world as a game turn begins, one line a turn
             kind "end"    the world when the recorder was ended (a benchmark run's last line)

Every line has `line` (its number, from 1), `t` (seconds since 1970) and `prev`, the sha256 of the line before
it as written (null on line 1): a file that lost a line, or had one changed, says so by itself (`problems()`). A
world line has `turn` and `world`. The world holds every player's figures, every city and unit, and the plot layers
that change (owners, features, improvements, routes, each seat's fog); what it means is in `INSTALL` below, key by
key. Fog is ignored: this is the operator's file and no seat ever reads it.

A game that is loaded again goes back in turns and the file is only ever appended to. The game as it stands is
`standing()`: a `turn` line of turn T sets aside every earlier line of turn T or later, a `start` line of turn T
every earlier line of a turn after T. A half line at the end of a file (a writer that died) is no line.

Readers: the page (`events_of()` turns a file into the stream the page draws: the map, then one snapshot a line),
`Index` (a line by its number with one seek, and each line's headline figures, for `/game` and `/game/line`), and
anything else that reads JSON lines; a benchmark run's file is packed into its recording as `game.jsonl`
(scripts/benchmark_recording.py, which checks the numbering and the chain with no code of this package).

Everything here reads the game and changes nothing in it. The capture draws no random number (seen live: a seed
played with and without the handler ends on the same figures).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from . import mapdump
from . import query as Q

FORMAT = 1
RECORDER = 1          # the handler's own version: a game that holds another one is given this one
KEEP = 24             # worlds the game holds for a reader that is behind; older ones fall out
REPLY_BYTES = 400_000  # a fetch stops adding worlds past this size
KINDS = ("start", "turn", "end")

# The handler and the capture. Installed once in a Lua state (a load of the game makes a new one); sent again it
# replaces the capture and leaves the one handler in place. `@ID@`, `@VERSION@`, `@KEEP@` and `@SEATS@` are filled
# in by install(). Every name of the game's API that is not there is listed under `missing` in the reply of
# fetch(), and its figure is left out: a line never fails for one name.
INSTALL = r"""
local R = SpectatorTurns
if not R then
  R = { id = "@ID@", seq = 0, ring = {}, last_turn = -1, errors = 0, error = "", msgs = -1, missing = {} }
  SpectatorTurns = R
end
R.version, R.keep, R.also = @VERSION@, @KEEP@, { @SEATS@ }
local function short(t, prefix) return t and (t:gsub("^" .. prefix, "")) or nil end
local function try(o, name, ...)
  local f = o and o[name]
  if not f then R.missing[name] = "absent" return nil end
  local ok, v = pcall(f, o, ...)
  if ok then return v end
  R.missing[name] = tostring(v):sub(1, 80)
  return nil
end
local function ask(tbl, name, ...)
  local f = tbl and tbl[name]
  if not f then R.missing[name] = "absent" return nil end
  local ok, v = pcall(f, ...)
  if ok then return v end
  R.missing[name] = tostring(v):sub(1, 80)
  return nil
end
local function typed(tbl, id, prefix)
  local row = id and id >= 0 and tbl[id] or nil
  return row and short(row.Type, prefix) or nil
end
local function names(rows, prefix, keep, more)
  local out = {}
  for row in rows() do
    if not keep or keep(row) then
      local e = { id = row.ID, name = short(row.Type, prefix) }
      if more then more(row, e) end
      out[#out + 1] = e
    end
  end
  return out
end
R.techs = names(GameInfo.Technologies, "TECH_")
R.policies = names(GameInfo.Policies, "POLICY_")
R.branches = names(GameInfo.PolicyBranchTypes, "POLICY_BRANCH_")
R.buildings = names(GameInfo.Buildings, "BUILDING_", nil, function(row, e)
  if (row.GreatWorkCount or 0) > 1 then e.themed = GameInfoTypes[row.BuildingClass] end
end)
R.promotions = names(GameInfo.UnitPromotions, "PROMOTION_")
R.resources = names(GameInfo.Resources, "RESOURCE_", function(row) return row.ResourceUsage == 1 or row.ResourceUsage == 2 end,
  function(row, e) e.strategic = row.ResourceUsage == 1 or nil end)
R.religions = names(GameInfo.Religions, "RELIGION_", function(row) return row.Type ~= "RELIGION_PANTHEON" end)
R.great_people = { "GetGreatPeopleCreated", "GetGreatGeneralsCreated", "GetGreatAdmiralsCreated", "GetGreatWritersCreated",
  "GetGreatArtistsCreated", "GetGreatMusiciansCreated", "GetGreatScientistsCreated", "GetGreatEngineersCreated",
  "GetGreatMerchantsCreated", "GetProphetsCreated" }
local POOL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
local function legend_new() return { by = {}, n = 0, names = {} } end
local function letter(lg, name)
  local c = lg.by[name]
  if c then return c end
  lg.n = lg.n + 1
  if lg.n > #POOL then return "?" end
  c = POOL:sub(lg.n, lg.n)
  lg.by[name] = c
  lg.names[c] = name
  return c
end

-- A major civilization's row: what its own screens show of it, in the game's own numbers.
local function major(p, pid, row, league, majors)
  local team = Teams[row.team]
  row.gold = p:GetGold()
  row.cities, row.population, row.land = p:GetNumCities(), p:GetTotalPopulation(), p:GetNumPlots()
  row.land_plots = try(p, "GetTotalLand")       -- the plots of `land` that are land: the game's own Total Land
  row.military, row.science, row.happiness = p:GetMilitaryMight(), p:GetScience(), p:GetExcessHappiness()
  row.units, row.military_units = p:GetNumUnits(), p:GetNumMilitaryUnits()
  row.tourism = try(p, "GetTourism")
  row.delegates = league and try(league, "CalculateStartingVotesForMember", pid) or 0
  row.techs, row.policies = {}, {}
  for _, t in ipairs(R.techs) do if team:IsHasTech(t.id) then row.techs[#row.techs + 1] = t.name end end
  for _, t in ipairs(R.policies) do if p:HasPolicy(t.id) then row.policies[#row.policies + 1] = t.name end end
  row.branches_opened, row.branches_finished = {}, {}
  for _, b in ipairs(R.branches) do
    if try(p, "IsPolicyBranchUnlocked", b.id) then row.branches_opened[#row.branches_opened + 1] = b.name end
    if try(p, "IsPolicyBranchFinished", b.id) then row.branches_finished[#row.branches_finished + 1] = b.name end
  end
  row.era = typed(GameInfo.Eras, try(p, "GetCurrentEra"), "ERA_")
  row.researching = typed(GameInfo.Technologies, try(p, "GetCurrentResearch"), "TECH_")
  row.ideology = typed(GameInfo.PolicyBranchTypes, try(p, "GetLateGamePolicyTree"), "POLICY_BRANCH_")
  row.pantheon = try(p, "HasCreatedPantheon") and true or false
  row.religion = typed(GameInfo.Religions, try(p, "GetReligionCreatedByPlayer"), "RELIGION_")
  row.yields = { gold = try(p, "CalculateGoldRate"), science = row.science, culture = try(p, "GetTotalJONSCulturePerTurn"),
                 faith = try(p, "GetTotalFaithPerTurn"), food = 0, production = 0 }
  -- the cities' yields added up, before what the empire pays and trades: what the game's own graphs draw
  row.total_yields = { food = try(p, "CalculateTotalYield", YieldTypes.YIELD_FOOD),
                       production = try(p, "CalculateTotalYield", YieldTypes.YIELD_PRODUCTION),
                       gold = try(p, "CalculateTotalYield", YieldTypes.YIELD_GOLD),
                       science = try(p, "CalculateTotalYield", YieldTypes.YIELD_SCIENCE) }
  row.stored = { culture = try(p, "GetJONSCulture"), faith = try(p, "GetFaith"),
                 golden_age_meter = try(p, "GetGoldenAgeProgressMeter"), golden_age_turns = try(p, "GetGoldenAgeTurns") }
  row.score_parts = { cities = try(p, "GetScoreFromCities"), population = try(p, "GetScoreFromPopulation"),
    land = try(p, "GetScoreFromLand"), wonders = try(p, "GetScoreFromWonders"), techs = try(p, "GetScoreFromTechs"),
    policies = try(p, "GetScoreFromPolicies"), great_works = try(p, "GetScoreFromGreatWorks"),
    religion = try(p, "GetScoreFromReligion"), future_tech = try(p, "GetScoreFromFutureTech") }
  local routes = try(p, "GetTradeRoutes")
  row.trade_routes = routes and #routes or nil
  row.great_people = {}
  for _, name in ipairs(R.great_people) do
    if p[name] then row.great_people[name:gsub("^Get", ""):gsub("Created$", "")] = try(p, name) end
  end
  row.resources = {}
  for _, r in ipairs(R.resources) do
    local total, unused = try(p, "GetNumResourceTotal", r.id, true), try(p, "GetNumResourceAvailable", r.id, true)
    if (total or 0) ~= 0 or (unused or 0) ~= 0 then
      row.resources[#row.resources + 1] = { type = r.name, total = total, unused = unused, strategic = r.strategic }
    end
  end
  row.met, row.at_war, row.friends, row.denounced, row.defensive_pacts, row.open_borders_to = {}, {}, {}, {}, {}, {}
  for _, o in ipairs(majors) do
    if o.id ~= pid and o.alive then
      local q = Players[o.id]
      if team:IsHasMet(o.team) then row.met[#row.met + 1] = o.id end
      if team:IsAtWar(o.team) then row.at_war[#row.at_war + 1] = o.id end
      if try(p, "IsDoF", o.id) then row.friends[#row.friends + 1] = o.id end
      if try(p, "IsDenouncedPlayer", o.id) then row.denounced[#row.denounced + 1] = o.id end
      if try(team, "IsDefensivePact", o.team) then row.defensive_pacts[#row.defensive_pacts + 1] = o.id end
      if try(team, "IsAllowsOpenBordersToTeam", o.team) then row.open_borders_to[#row.open_borders_to + 1] = o.id end
    end
  end
  row.allies, row.wonders, row.national_wonders, row.great_works, row.theming = 0, 0, 0, 0, 0
end

R.capture = function(kind, first)
  local clock = os and os.clock and os.clock() or 0
  local out = { kind = kind, turn = Game.GetGameTurn(), active = Game.GetActivePlayer(), first = first,
                players = {}, cities = {}, units = {}, events = {} }
  out.at = os and os.time and os.time() or nil
  out.year = ask(Game, "GetGameTurnYear")
  out.auto = ask(Game, "GetAIAutoPlay")
  out.winner = Game.GetWinner()
  out.victory = typed(GameInfo.Victories, Game.GetVictory(), "VICTORY_")
  pcall(function() out.over = Game.GetGameState() ~= GameplayGameStateTypes.GAMESTATE_ON end)
  local league = (ask(Game, "GetNumActiveLeagues") or 0) > 0 and ask(Game, "GetActiveLeague") or nil
  if league then
    out.congress = { host = try(league, "GetHostMember"), united_nations = try(league, "IsUnitedNations") and true or false,
                     resolutions = {} }
    for _, r in ipairs(try(league, "GetActiveResolutions") or {}) do
      out.congress.resolutions[#out.congress.resolutions + 1] = typed(GameInfo.Resolutions, r.Type, "RESOLUTION_")
    end
  end
  local LAST = (GameDefines.MAX_PLAYERS or 64) - 1
  local majors, rows = {}, {}
  -- the seats whose fog is kept: every living human, and the players the recorder named (a seat the engine plays)
  local seats, seen = {}, {}
  local function seat(pid)
    local p = Players[pid]
    if p and p:IsAlive() and not seen[pid] then
      seen[pid] = true
      seats[#seats + 1] = { pid = pid, team = p:GetTeam(), rows = {} }
    end
  end
  for pid = 0, LAST do
    local p = Players[pid]
    if p and p:IsEverAlive() and p:IsAlive() and p:IsHuman() and not p:IsBarbarian() and not p:IsMinorCiv() then seat(pid) end
  end
  for _, pid in ipairs(R.also) do seat(pid) end
  for pid = 0, LAST do
    local p = Players[pid]
    if p and p:IsEverAlive() then
      local row = { id = pid, alive = p:IsAlive(), human = p:IsHuman(), team = p:GetTeam(), score = p:GetScore() }
      if p:IsMinorCiv() then row.minor = true elseif p:IsBarbarian() then row.barb = true else majors[#majors + 1] = row end
      rows[pid] = row
      out.players[#out.players + 1] = row
    end
  end
  local owner_char, legend, n = {}, {}, 0
  for _, row in ipairs(out.players) do
    local pid, p = row.id, Players[row.id]
    if row.alive then
      n = n + 1
      local ch = n <= #POOL and POOL:sub(n, n) or "?"
      owner_char[pid] = ch
      legend[ch] = pid
      if row.minor then
        row.ally = try(p, "GetAlly")
        row.influence = {}
        for _, o in ipairs(majors) do
          local f = o.alive and try(p, "GetMinorCivFriendshipWithMajor", o.id) or 0
          if f ~= 0 then row.influence[tostring(o.id)] = f end
        end
      elseif not row.barb then
        major(p, pid, row, league, majors)
      end
      local own = not row.minor and not row.barb
      for c in p:Cities() do
        local city = { id = c:GetID(), o = pid, x = c:GetX(), y = c:GetY(), pop = c:GetPopulation(), cap = c:IsCapital(),
                       n = try(c, "GetName"), puppet = try(c, "IsPuppet") }
        pcall(function() city.hp = c:GetMaxHitPoints() - c:GetDamage(); city.mhp = c:GetMaxHitPoints() end)
        if try(c, "IsOccupied") then city.occupied = true end
        if (try(c, "GetResistanceTurns") or 0) > 0 then city.resistance = c:GetResistanceTurns() end
        if try(c, "IsRazing") then city.razing = true end
        city.original_owner, city.founded = try(c, "GetOriginalOwner"), try(c, "GetGameTurnFounded")
        city.strength = try(c, "GetStrengthValue")
        city.religion = typed(GameInfo.Religions, try(c, "GetReligiousMajority"), "RELIGION_")
        if own then
          local food, production = c:GetYieldRate(YieldTypes.YIELD_FOOD), c:GetYieldRate(YieldTypes.YIELD_PRODUCTION)
          city.yields = { food = food, production = production, gold = c:GetYieldRate(YieldTypes.YIELD_GOLD),
                          science = c:GetYieldRate(YieldTypes.YIELD_SCIENCE), culture = try(c, "GetJONSCulturePerTurn"),
                          faith = try(c, "GetFaithPerTurn") }
          row.yields.food, row.yields.production = row.yields.food + food, row.yields.production + production
          city.stored = { food = try(c, "GetFood"), production = try(c, "GetProduction"), culture = try(c, "GetJONSCultureStored") }
          city.making = typed(GameInfo.Units, try(c, "GetProductionUnit"), "UNIT_")
            or typed(GameInfo.Buildings, try(c, "GetProductionBuilding"), "BUILDING_")
            or typed(GameInfo.Projects, try(c, "GetProductionProject"), "PROJECT_")
            or typed(GameInfo.Processes, try(c, "GetProductionProcess"), "PROCESS_")
          city.world_wonders, city.national_wonders = try(c, "GetNumWorldWonders"), try(c, "GetNumNationalWonders")
          city.great_works = try(c, "GetNumGreatWorks")
          row.wonders, row.national_wonders = row.wonders + (city.world_wonders or 0), row.national_wonders + (city.national_wonders or 0)
          row.great_works = row.great_works + (city.great_works or 0)
          city.buildings = {}
          for _, b in ipairs(R.buildings) do
            if c:IsHasBuilding(b.id) then
              city.buildings[#city.buildings + 1] = b.name
              if b.themed then row.theming = row.theming + (try(c, "GetThemingBonus", b.themed) or 0) end
            end
          end
        end
        out.cities[#out.cities + 1] = city
      end
      for u in p:Units() do
        local ui = GameInfo.Units[u:GetUnitType()]
        local unit = { id = u:GetID(), o = pid, x = u:GetX(), y = u:GetY(), t = short(ui and ui.Type, "UNIT_") or "?",
                       hp = u:GetCurrHitPoints(), mhp = try(u, "GetMaxHitPoints") }
        local combat = try(u, "IsCombatUnit")
        if not combat then unit.civ = true end
        pcall(function()
          local d = u:GetDomainType()
          unit.d = (d == DomainTypes.DOMAIN_SEA and "S") or (d == DomainTypes.DOMAIN_AIR and "A") or "L"
        end)
        if try(u, "IsEmbarked") then unit.emb = true end
        unit.moves = try(u, "GetMoves")
        if (try(u, "GetFortifyTurns") or 0) > 0 then unit.fortified = true end
        if own and combat then
          unit.level, unit.xp = try(u, "GetLevel"), try(u, "GetExperience")
          unit.promotions = {}
          for _, pr in ipairs(R.promotions) do
            if u:IsHasPromotion(pr.id) then unit.promotions[#unit.promotions + 1] = pr.name end
          end
        end
        -- `h`: the seats whose screen does not draw this unit even on a visible plot (an undetected submarine)
        local hidden = {}
        for _, s in ipairs(seats) do
          if s.team ~= row.team and u:IsInvisible(s.team, false) then hidden[#hidden + 1] = s.pid end
        end
        if #hidden > 0 then unit.h = hidden end
        out.units[#out.units + 1] = unit
      end
    end
  end
  for _, row in ipairs(out.players) do
    if row.minor and row.alive and row.ally and rows[row.ally] and rows[row.ally].allies then
      rows[row.ally].allies = rows[row.ally].allies + 1
    end
  end
  out.religions = {}
  for _, r in ipairs(R.religions) do
    local holy = ask(Game, "GetHolyCityForReligion", r.id, -1)
    if holy then
      out.religions[#out.religions + 1] = { type = r.name, founder = ask(Game, "GetFounder", r.id, -1),
        holy_city = { o = holy:GetOwner(), id = holy:GetID() }, cities = ask(Game, "GetNumCitiesFollowing", r.id) }
    end
  end
  -- the plot layers that change, rows[1] the north row as mapdump.py has them; `mk` is the map's key (snapshot.py)
  local w, h = Map.GetGridSize()
  local owners, features, improvements, routes, pillaged = {}, {}, {}, {}, {}
  local feat, imp = legend_new(), legend_new()
  local mk = 0
  for y = h - 1, 0, -1 do
    local o, f, i, r, fogs = {}, {}, {}, {}, {}
    for k = 1, #seats do fogs[k] = {} end
    for x = 0, w - 1 do
      local p = Map.GetPlot(x, y)
      mk = (mk * 31 + (p and ((p:GetTerrainType() + 1) * 4 + (p:IsMountain() and 2 or (p:IsHills() and 1 or 0))) or 3)) % 2147483647
      local owner = p and p:GetOwner() or -1
      o[#o + 1] = (owner >= 0 and owner_char[owner]) or "."
      local ft = p and p:GetFeatureType() or -1
      f[#f + 1] = ft >= 0 and letter(feat, short(GameInfo.Features[ft].Type, "FEATURE_")) or "."
      local it = p and p:GetImprovementType() or -1
      i[#i + 1] = it >= 0 and letter(imp, short(GameInfo.Improvements[it].Type, "IMPROVEMENT_")) or "."
      local rt = p and p:GetRouteType() or -1
      r[#r + 1] = (rt == 0 and "r") or (rt >= 1 and "R") or "."
      if p and ((it >= 0 and p:IsImprovementPillaged()) or (rt >= 0 and p:IsRoutePillaged())) then pillaged[#pillaged + 1] = { x, y } end
      for k, s in ipairs(seats) do
        local ch = "."
        if p and p:IsVisible(s.team, false) then ch = "v" elseif p and p:IsRevealed(s.team, false) then ch = "f" end
        fogs[k][#fogs[k] + 1] = ch
      end
    end
    owners[#owners + 1], features[#features + 1] = table.concat(o), table.concat(f)
    improvements[#improvements + 1], routes[#routes + 1] = table.concat(i), table.concat(r)
    for k, s in ipairs(seats) do s.rows[#s.rows + 1] = table.concat(fogs[k]) end
  end
  out.owners = { rows = owners, legend = legend }
  out.features = { rows = features, legend = feat.names }
  out.improvements = { rows = improvements, legend = imp.names }
  out.routes = { rows = routes }
  out.pillaged = pillaged
  out.fog = {}
  for _, s in ipairs(seats) do out.fog[tostring(s.pid)] = s.rows end
  out.map_key = w .. "x" .. h .. ":" .. mk
  -- the game's own replay lines since the capture before this one (a war declared, a city founded, a wonder)
  local msgs = ask(Game, "GetReplayMessages") or {}
  if R.msgs < 0 or R.msgs > #msgs then R.msgs = #msgs end
  for k = R.msgs + 1, #msgs do
    local m = msgs[k]
    if m.Type == 0 or m.Type == 1 then out.events[#out.events + 1] = { turn = m.Turn, player = m.Player, kind = m.Type, text = m.Text } end
  end
  R.msgs = #msgs
  out.took_ms = os and os.clock and math.floor((os.clock() - clock) * 1000 + 0.5) or nil
  return out
end

R.put = function(kind, first)
  local ok, w = pcall(R.capture, kind, first)
  if not ok then
    R.errors, R.error = R.errors + 1, tostring(w):sub(1, 300)
    return -1
  end
  R.seq = R.seq + 1
  R.ring[#R.ring + 1] = { seq = R.seq, kind = kind, turn = w.turn, json = __hjson(w) }
  while #R.ring > R.keep do table.remove(R.ring, 1) end
  return R.seq
end

if not R.hooked then
  R.hooked = true
  GameEvents.PlayerDoTurn.Add(function(pid)
    local k = SpectatorTurns
    if not k or not k.put then return end
    local turn = Game.GetGameTurn()
    if turn == k.last_turn then return end
    k.last_turn = turn
    k.put("turn", pid)
  end)
end
R.last_turn = Game.GetGameTurn()
return { ok = true, id = R.id, seq = R.seq, turn = R.last_turn, version = R.version }
"""

# What the handler holds past `@SINCE@`, oldest first, up to a size. Nothing is taken out of the game by a fetch:
# two readers each keep their own count.
FETCH = """
local R = SpectatorTurns
if not R or R.version ~= @VERSION@ or not R.put then return {installed = false} end
local out = {installed = true, id = R.id, seq = R.seq, errors = R.errors, error = R.error, turn = Game.GetGameTurn(),
  missing = R.missing, rows = {}}
local size = 0
for _, e in ipairs(R.ring) do
  if e.seq > @SINCE@ and size < @LIMIT@ then
    out.rows[#out.rows + 1] = e
    size = size + #e.json
  end
end
return out
"""

# The world now, asked for: the handler's own capture, kept with the turns it took.
NOW = """
local R = SpectatorTurns
if not R or R.version ~= @VERSION@ or not R.put then return {installed = false} end
return {installed = true, id = R.id, seq = R.put("@KIND@", -1), error = R.error}
"""

# What never changes in a game: its terms and its players.
GAME = r"""
local out = { turn = Game.GetGameTurn(), players = {}, victories = {}, options = {}, eras = {} }
local function ask(f) local ok, v = pcall(f) if ok then return v end return nil end
for row in GameInfo.Eras() do out.eras[#out.eras + 1] = row.Type end
out.build = ask(function() return UI.GetVersionInfo() end)
out.handicap = ask(function() return GameInfo.HandicapInfos[Game.GetHandicapType()].Type end)
out.speed = ask(function() return GameInfo.GameSpeeds[Game.GetGameSpeedType()].Type end)
out.world = ask(function() return GameInfo.Worlds[Map.GetWorldSize()].Type end)
out.start_turn = ask(function() return Game.GetStartTurn() end)
out.start_era = ask(function() return GameInfo.Eras[Game.GetStartEra()].Type end)
out.start_year = ask(function() return Game.GetStartYear() end)
out.max_turns = ask(function() return Game.GetMaxTurns() end)
for row in GameInfo.Victories() do out.victories[row.Type] = ask(function() return Game.IsVictoryValid(row.ID) end) and true or false end
for row in GameInfo.GameOptions() do
  if ask(function() return Game.IsOption(row.ID) end) then out.options[#out.options + 1] = row.Type end
end
for pid = 0, (GameDefines.MAX_PLAYERS or 64) - 1 do
  local p = Players[pid]
  if p and p:IsEverAlive() then
    local row = { id = pid, team = p:GetTeam(), name = ask(function() return p:GetName() end) }
    if p:IsMinorCiv() then
      row.minor = true
      row.trait = ask(function() return GameInfo.MinorCivTraits[p:GetMinorCivTrait()].Type end)
    elseif p:IsBarbarian() then
      row.barb = true
    else
      row.slot = ask(function() return PreGame.GetSlotStatus(pid) end)
      row.leader = ask(function() return GameInfo.Leaders[p:GetLeaderType()].Type end)
      row.civilization = ask(function() return GameInfo.Civilizations[p:GetCivilizationType()].Type end)
      row.row = ask(function() return GameInfo.HandicapInfos[p:GetHandicapType()].Type end)
    end
    row.civ = ask(function() return Locale.ConvertTextKey(GameInfo.Civilizations[p:GetCivilizationType()].ShortDescription) end)
    pcall(function()
      local pc = GameInfo.PlayerColors[p:GetPlayerColor()]
      local c1, c2 = pc and GameInfo.Colors[pc.PrimaryColor], pc and GameInfo.Colors[pc.SecondaryColor]
      if c1 then row.color = { math.floor(c1.Red * 255 + 0.5), math.floor(c1.Green * 255 + 0.5), math.floor(c1.Blue * 255 + 0.5) } end
      if c2 then row.color2 = { math.floor(c2.Red * 255 + 0.5), math.floor(c2.Green * 255 + 0.5), math.floor(c2.Blue * 255 + 0.5) } end
    end)
    out.players[#out.players + 1] = row
  end
end
return out
"""

# Keys of a world that are objects by their meaning: an empty Lua table comes over the wire as a list.
OBJECTS = ("fog", "influence", "great_people", "legend", "yields", "total_yields", "stored", "score_parts")
HEADLINE = ("score", "cities", "population", "land", "military", "science", "gold", "happiness")


class NoGame(Exception):
    """No game is loaded, or the game does not answer: nothing to record now."""


def dumps(obj: Any) -> bytes:
    """One line of a game file, without its newline: the same bytes for the same object on every machine."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(line: bytes) -> str:
    return hashlib.sha256(line).hexdigest()


def tidy(x: Any, key: str | None = None) -> Any:
    """A world as the wire gave it, with its empty objects as objects (`OBJECTS`)."""
    if isinstance(x, dict):
        return {k: tidy(v, k) for k, v in x.items()}
    if isinstance(x, list):
        return {} if not x and key in OBJECTS else [tidy(v) for v in x]
    return x


# ------------------------------------------------------------------ the game's side

def fill(text: str, **values: Any) -> str:
    for k, v in values.items():
        text = text.replace(f"@{k.upper()}@", str(v))
    return text


def install(client: Any, seats: Iterable[int] = (), timeout: float = 60) -> dict:
    """The handler into the loaded game (a game that has it keeps its count). `seats`: players whose fog is kept
    beside the human seats' (a seat the engine plays for a while is no human then)."""
    code = fill(INSTALL, id=secrets.token_hex(6), version=RECORDER, keep=KEEP, seats=", ".join(str(int(s)) for s in seats))
    return _ask(client, code, timeout)


def fetch(client: Any, since: int, timeout: float = 60) -> dict:
    reply = _ask(client, fill(FETCH, version=RECORDER, since=int(since), limit=REPLY_BYTES), timeout)
    rows = []
    for e in reply.get("rows") or []:
        rows.append({"seq": e["seq"], "kind": e["kind"], "turn": e["turn"], "world": tidy(json.loads(e["json"]))})
    reply["rows"] = rows
    return reply


def now(client: Any, kind: str, timeout: float = 60) -> dict:
    return _ask(client, fill(NOW, version=RECORDER, kind=kind), timeout)


def game_facts(client: Any, timeout: float = 120) -> tuple[dict, dict]:
    """The game's terms and players, and the static map; `NoGame` when either read is not one."""
    facts = _ask(client, GAME, timeout)
    m = Q.query(client, mapdump.LUA, timeout=timeout)
    if not mapdump.valid(m) or not isinstance(facts.get("players"), list):
        raise NoGame("the game's terms or its map did not read")
    facts["players"] = list(facts.get("players") or [])
    facts["options"] = sorted(facts.get("options") or [])
    facts["eras"] = list(facts.get("eras") or [])        # in the order of their ids: a world names a player's era
    facts["victories"] = dict(facts.get("victories") or {})
    return facts, m


def _ask(client: Any, code: str, timeout: float) -> dict:
    try:
        reply = Q.query(client, code, timeout=timeout)
    except Exception as e:      # no InGame state, the tuner gone, a game being torn down
        raise NoGame(f"{type(e).__name__}: {e}") from None
    if not isinstance(reply, dict):
        raise NoGame(f"unexpected reply {str(reply)[:120]}")
    return reply


def key_of(facts: dict, m: dict) -> str:
    """A name for the game: the map's size and a digest of the map, the terms and the players. Two games started
    from one save have one key: a benchmark run names its own file."""
    who = [[p.get("id"), p.get("leader") or p.get("name"), p.get("civilization") or p.get("civ")] for p in facts["players"]]
    raw = json.dumps([m.get("key"), facts.get("handicap"), facts.get("speed"), facts.get("start_turn"), who], sort_keys=True)
    return f"{m.get('w')}x{m.get('h')}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


# ------------------------------------------------------------------ the file

class GameFile:
    """The one writer of a game file. Opening a file that is there goes on from its last whole line (a half line at
    its end is cut off first)."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.lines = 0
        self.prev: str | None = None
        self.header: dict | None = None
        self.bytes = 0
        self.t = 0.0                    # the last line's time: no line is written with an earlier one
        if self.path.exists():
            whole = 0
            for _offset, raw, row in read(self.path):
                if self.lines == 0:
                    self.header = row
                self.lines, self.prev = self.lines + 1, digest(raw)
                self.t = row["t"] if isinstance(row.get("t"), (int, float)) else self.t
                whole = _offset + len(raw) + 1
            if whole != self.path.stat().st_size:
                with open(self.path, "r+b") as f:
                    f.truncate(whole)
            self.bytes = whole

    def append(self, kind: str, body: dict, t: float | None = None) -> dict:
        self.t = max(self.t, round(t if t is not None else time.time(), 3))
        row = {**body, "line": self.lines + 1, "kind": kind, "prev": self.prev, "t": self.t}
        raw = dumps(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "ab") as f:
            f.write(raw + b"\n")
            f.flush()
            os.fsync(f.fileno())
        if self.lines == 0:
            self.header = row
        self.lines, self.prev, self.bytes = self.lines + 1, digest(raw), self.bytes + len(raw) + 1
        return row


def read(path: str | os.PathLike) -> Iterator[tuple[int, bytes, dict]]:
    """The whole lines of a game file: where each begins, its bytes without the newline, and the object. Stops at
    the first line that is not one (a half line at the end, or damage): what follows it has no place in the chain."""
    offset = 0
    with open(path, "rb") as f:
        for line in f:
            if not line.endswith(b"\n"):
                return
            raw = line[:-1]
            try:
                row = json.loads(raw)
            except ValueError:
                return
            if not isinstance(row, dict) or "kind" not in row:
                return
            yield offset, raw, row
            offset += len(line)


def problems(rows: Iterable[tuple[bytes, dict]]) -> list[str]:
    """What is wrong with a game file's lines (`(bytes, object)` each), in words; nothing when it is whole: line 1
    the game, the numbers in order, every `prev` the hash of the line before, every other line a world of a turn."""
    out: list[str] = []
    prev, n = None, 0
    for raw, row in rows:
        n += 1
        if row.get("line") != n:
            out.append(f"line {n} says it is line {row.get('line')!r}")
        if row.get("prev") != prev:
            out.append(f"line {n} does not follow the line before it (prev)")
        if (n == 1) != (row.get("kind") == "game"):
            out.append(f"line {n} is of kind {row.get('kind')!r}")
        elif n > 1 and (row.get("kind") not in KINDS or not isinstance(row.get("turn"), int) or not isinstance(row.get("world"), dict)):
            out.append(f"line {n} is no world of a turn")
        prev = digest(raw)
        if len(out) > 20:
            break
    if n == 0:
        out.append("no line")
    return out


def standing(rows: Iterable[dict]) -> list[dict]:
    """The game as it stands, from a file's world lines in the order written: a `turn` line of turn T sets aside
    every earlier line of turn T or later, a `start` line of turn T every earlier line of a turn after T (the game
    was loaded again and played on from there)."""
    kept: list[dict] = []
    for row in rows:
        kind, turn = row.get("kind"), row.get("turn")
        if kind == "turn":
            kept = [r for r in kept if r["turn"] < turn]
        elif kind == "start":
            kept = [r for r in kept if r["turn"] <= turn]
        if kind in KINDS:
            kept.append(row)
    return kept


def headline(world: dict) -> dict:
    """A line's few figures per major civilization, for a chart over the game: `{player id: {score, cities, ...}}`."""
    return {str(p["id"]): {k: p.get(k) for k in HEADLINE if k in p}
            for p in world.get("players") or [] if not p.get("minor") and not p.get("barb")}


class Index:
    """A game file for a reader that wants one line at a time: where every line begins and its headline figures,
    read once and kept up as the file grows (`refresh()`); `line(n)` is one seek."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.offsets: list[tuple[int, int]] = []      # (where the line begins, its length without the newline)
        self.rows: list[dict] = []
        self.size = 0
        self.lock = threading.Lock()
        self.refresh()

    def refresh(self) -> int:
        """Take in the lines written since the last look. Says how many lines there are."""
        with self.lock:
            try:
                size = self.path.stat().st_size
            except OSError:
                return len(self.rows)
            if size < self.size:                       # another file under the same name: start over
                self.offsets, self.rows, self.size = [], [], 0
            if size == self.size:
                return len(self.rows)
            with open(self.path, "rb") as f:
                f.seek(self.size)
                offset = self.size
                for line in f:
                    if not line.endswith(b"\n"):
                        break
                    try:
                        row = json.loads(line)
                    except ValueError:
                        break
                    entry = {"line": row.get("line"), "kind": row.get("kind"), "t": row.get("t")}
                    if isinstance(row.get("world"), dict):
                        entry.update(turn=row.get("turn"), players=headline(row["world"]))
                    self.rows.append(entry)
                    self.offsets.append((offset, len(line) - 1))
                    offset += len(line)
                self.size = offset
            return len(self.rows)

    def line(self, n: int) -> bytes | None:
        """Line `n` (from 1) as written, or None."""
        with self.lock:
            if not 1 <= n <= len(self.offsets):
                return None
            offset, length = self.offsets[n - 1]
        with open(self.path, "rb") as f:
            f.seek(offset)
            return f.read(length)


# ------------------------------------------------------------------ the page's stream out of a file

def snapshot_of(world: dict, static: dict[int, dict], turn: int | None = None) -> dict:
    """A world line as the page's snapshot (snapshot.py): the same keys, with the line's turn and what the first
    line says once of every player (name, civilization, colours) put back."""
    players = [{**{k: v for k, v in static.get(p.get("id"), {}).items() if k in ("name", "civ", "color", "color2", "minor", "barb")},
                "minor": False, "barb": False, **p} for p in world.get("players") or []]
    return {**world, "ok": True, "turn": turn, "players": players}


def events_of(lines: Iterable[dict], calls: Iterable[dict] = ()) -> list[dict]:
    """The stream the page draws (feed.py's events) out of a game file's lines as written, every load and replay of
    a turn included: the map, then a snapshot for every world line, and `calls` (ledger rows) between them by their
    own times. The numbers are the stream's own, from 1."""
    out: list[tuple[float, int, int, str, dict]] = []
    static: dict[int, dict] = {}
    t = 0.0
    for row in lines:
        t = max(t, row["t"]) if isinstance(row.get("t"), (int, float)) else t      # the file's order is the order
        if row.get("kind") == "game":
            static = {p.get("id"): p for p in (row.get("game") or {}).get("players") or [] if isinstance(p, dict)}
            if isinstance(row.get("map"), dict):
                out.append((t, 0, len(out), "hello", {"map": row["map"]}))
        elif isinstance(row.get("world"), dict):
            out.append((t, 0, len(out), "snapshot", snapshot_of(row["world"], static, row.get("turn"))))
    start = out[0][0] if out else 0.0
    for c in calls:
        if isinstance(c, dict) and isinstance(c.get("t"), (int, float)):
            # never ahead of the map (the page draws nothing before it); after the world of the same moment
            out.append((max(c["t"], start), 1, len(out), "call", c))
    out.sort(key=lambda e: e[:3])
    return [{"seq": n, "t": round(e[0], 3), "type": e[3], "data": e[4]} for n, e in enumerate(out, 1)]


# ------------------------------------------------------------------ the recorder

class Recorder:
    """Puts the handler into the game that is loaded and writes its game file, line by line.

    `path`: the one file of this recorder (a benchmark run). `folder`: a file for each game there, named by the
    game's key, gone on with when the game is loaded again (the spectator's `--games`). `made_with` and `run` go
    into a new file's first line: the versions that wrote it, and what a benchmark run says of itself. `step()` is
    one look: it
    is safe to call again and again, costs one small query when nothing is new, and raises `NoGame` when no game
    answers. A game loaded again (a new Lua state) is seen by the handler's id: the handler goes in again, the
    file's first line is written if the file is new, and a `start` line says where the game now stands."""

    def __init__(self, client: Any, path: str | os.PathLike | None = None, folder: str | os.PathLike | None = None,
                 seats: Iterable[int] = (), made_with: dict | None = None, run: dict | None = None,
                 clock: Callable[[], float] = time.time):
        if (path is None) == (folder is None):
            raise ValueError("a recorder writes one file (path) or a folder of them (folder)")
        self.client, self.path, self.folder = client, Path(path) if path else None, Path(folder) if folder else None
        self.seats, self.made_with, self.run, self.clock = [int(s) for s in seats], made_with or {}, run, clock
        self.file: GameFile | None = None
        self.state: str | None = None       # the id of the handler this recorder reads
        self.since = 0
        self.key: str | None = None
        self.missed = 0                     # worlds that fell out of the game's hold before they were fetched
        self.written = {k: 0 for k in KINDS}
        self.missing: dict = {}
        self.error: str | None = None

    def begin(self) -> None:
        """The handler in, the file open, a `start` line written; `NoGame` when no game is loaded."""
        made = install(self.client, self.seats)
        facts, m = game_facts(self.client)
        key = key_of(facts, m)
        path = self.path or (self.folder / f"game-{key}.jsonl")
        file = GameFile(path)
        if file.header is None:
            file.append("game", {"format": FORMAT, "key": key, "game": facts, "map": m,
                                 "written_by": {"recorder": RECORDER, **self.made_with},
                                 **({"run": self.run} if self.run else {})}, t=self.clock())
        elif file.header.get("key") != key:
            raise ValueError(f"{path} is the file of another game ({file.header.get('key')}); this game is {key}")
        self.file, self.key, self.state, self.since = file, key, made.get("id"), int(made.get("seq") or 0)
        self.take(now(self.client, "start"))

    def take(self, asked: dict | None = None) -> int:
        """Fetch what the game holds past this recorder's count and append it. Says how many lines were written."""
        if asked is not None and not asked.get("installed"):
            raise NoGame("the handler is not in the game")
        n = 0
        while True:
            reply = fetch(self.client, self.since)
            if not reply.get("installed") or reply.get("id") != self.state:
                self.state = None           # another Lua state: begin again at the next step
                return n
            self.missing = dict(reply.get("missing") or {}) if isinstance(reply.get("missing"), dict) else {}
            if reply.get("error"):
                self.error = str(reply["error"])
            rows = reply["rows"]
            for row in rows:
                gap = row["seq"] - self.since - 1
                body: dict = {"turn": row["turn"], "world": row["world"]}
                if gap > 0:
                    self.missed += gap
                    body["missed"] = gap     # worlds the game let go of before this one was fetched
                self.since = row["seq"]
                world = row["world"]
                at = world.pop("at", None)
                world.pop("kind", None)
                world.pop("turn", None)
                assert self.file is not None
                self.file.append(row["kind"], body, t=at if isinstance(at, (int, float)) else self.clock())
                self.written[row["kind"]] = self.written.get(row["kind"], 0) + 1
                n += 1
            if not rows or self.since >= int(reply.get("seq") or 0):
                return n

    def step(self) -> int:
        if self.state is None:
            self.begin()
            return 1
        return self.take()

    def end(self) -> dict:
        """A last look and an `end` line (the world as it is now). Says what was written; never raises."""
        try:
            if self.state is None:
                self.begin()
            self.take()
            self.take(now(self.client, "end"))
        except Exception as e:       # the file stands as far as it got
            self.error = f"{type(e).__name__}: {e}"
        return self.said()

    def said(self) -> dict:
        out: dict = {"file": str(self.file.path) if self.file else None, "lines": self.file.lines if self.file else 0,
                     "bytes": self.file.bytes if self.file else 0, "key": self.key, **self.written}
        if self.missed:
            out["missed"] = self.missed
        if self.missing:
            out["missing"] = sorted(self.missing)
        if self.error:
            out["error"] = self.error
        return out


def record(recorder: Recorder, every: float = 1.0, sleep: Callable[[float], None] = time.sleep):
    """`recorder` at work in a thread of its own, a look every `every` seconds. Returns the call that ends it and
    says what was written (Recorder.end). A look that fails costs that look."""
    stop = threading.Event()

    def loop() -> None:
        while not stop.is_set():
            try:
                recorder.step()
            except Exception as e:
                recorder.error = f"{type(e).__name__}: {e}"
            stop.wait(every)

    thread = threading.Thread(target=loop, name="game-file", daemon=True)
    thread.start()

    def end() -> dict:
        stop.set()
        thread.join(timeout=120)
        if thread.is_alive():
            return {**recorder.said(), "error": "the recorder did not stop"}
        return recorder.end()
    return end


NAME = re.compile(r"game-[0-9]+x[0-9]+-[0-9a-f]{12}\.jsonl")
