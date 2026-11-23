-- The Culture Overview screen (cultureoverview.lua): its victory tab (every met major civ's influential-on count
-- out of the number needed, and tourism) and its influence tab, where any met civ can be selected to see its
-- influence level on every other living major; civs we have not met show as "unknown", as they do there.
-- Live t444: "Venice only needs ... 2 more civilizations to win a Culture Victory" with no way to see which.
function H.culture_overview(pid)
  local me = Players[pid]
  local myTeam = Teams[me:GetTeam()]
  local levels = { [0] = "exotic", "familiar", "popular", "influential", "dominant" }
  local trends = {}
  pcall(function()
    trends[InfluenceLevelTrend.INFLUENCE_TREND_FALLING] = "falling"
    trends[InfluenceLevelTrend.INFLUENCE_TREND_STATIC] = "static"
    trends[InfluenceLevelTrend.INFLUENCE_TREND_RISING] = "rising"
  end)
  local function civname(p) return Locale.Lookup(p:GetCivilizationShortDescriptionKey()) end
  local out = { civs = {} }
  for i = 0, GameDefines.MAX_CIV_PLAYERS - 1 do
    local s = Players[i]
    if s and s:IsAlive() and not s:IsMinorCiv() and myTeam:IsHasMet(s:GetTeam()) then
      local row = { player = i, civ = civname(s), influential_on = s:GetNumCivsInfluentialOn(),
                    needed = s:GetNumCivsToBeInfluentialOn(), tourism = s:GetTourism(), on = {} }
      if i == pid then row.you = true end
      for j = 0, GameDefines.MAX_CIV_PLAYERS - 1 do
        local t = Players[j]
        if j ~= i and t and t:IsAlive() and not t:IsMinorCiv() then
          local lvl = s:GetInfluenceLevel(j)
          if lvl ~= InfluenceLevelTypes.NO_INFLUENCE_LEVEL then
            local culture = t:GetJONSCultureEverGenerated()
            local e = { level = levels[lvl] or lvl,
                        percent = culture > 0 and math.floor(100 * s:GetInfluenceOn(j) / culture) or 0,
                        tourism_per_turn = math.floor(s:GetInfluencePerTurn(j)),
                        trend = trends[s:GetInfluenceTrend(j)] }
            if myTeam:IsHasMet(t:GetTeam()) then e.player = j; e.civ = civname(t) else e.civ = "unknown" end
            local turns = s:GetTurnsToInfluential(j)
            -- GitLab #88 (Assyria t256): Siam's row on me carried no estimate the turn after "Siam only needs 1 more
            -- civilization": the engine's 999 means never at current rates, and that is the answer, not silence.
            if lvl >= 3 then
              e.turns_to_influential = 0
            elseif e.trend == "rising" and turns and turns < 999 then
              e.turns_to_influential = turns
            elseif e.trend == "rising" then
              e.turns_to_influential = "never at current rates (their tourism per turn is below the culture this civ adds per turn)"
            else
              e.turns_to_influential = "never (not rising)"
            end
            row.on[#row.on + 1] = e
          end
        end
      end
      out.civs[#out.civs + 1] = row
    end
  end
  return out
end

-- The culture-victory danger rows for the briefing's warnings (#88): every met civ one civilization short of the
-- number it must be influential on, with its row on this seat (level, trend, the turns estimate).
-- Whether this game can be won by `vtype`: the game's own word first (Game.IsVictoryValid, which also holds a
-- victory switched off after the game was hosted, as the benchmark's terms do with Time), the setup screen's
-- (PreGame.IsVictory) without it. A read that fails leaves the victory counted as allowed.
function H.victory_allowed(vtype)
  local ok, on = pcall(function()
    local v = GameInfo.Victories[vtype]
    if not v then return nil end
    if Game.IsVictoryValid then return Game.IsVictoryValid(v.ID) end
    return PreGame.IsVictory(v.ID)
  end)
  return not (ok and on == false)
end

function H.culture_threats(pid)
  local out = {}
  -- v346: no Culture victory, no threat of one (live 2026-11-23, a duel with only Domination on: the briefing
  -- warned of the Huns' culture_victory_threat for sixty turns).
  if not H.victory_allowed("VICTORY_CULTURAL") then return out end
  local ok, cv = pcall(H.culture_overview, pid)
  if not ok or type(cv) ~= "table" then return out end
  for _, row in ipairs(cv.civs or {}) do
    if not row.you and type(row.needed) == "number" and type(row.influential_on) == "number"
       and row.needed - row.influential_on <= 1 then
      local t = { player = row.player, civ = row.civ, influential_on = row.influential_on, needed = row.needed, tourism = row.tourism }
      for _, e in ipairs(row.on or {}) do
        if e.player == pid then t.on_me = { level = e.level, percent = e.percent, trend = e.trend, turns_to_influential = e.turns_to_influential } end
      end
      out[#out + 1] = t
    end
  end
  return out
end

-- v344: the rivals close to a victory, for every status of this seat's own turn. A run of quiet turns passes no
-- turn while one is listed (the user's decision of 2026-11-23: Sonnet's Germany was told America needed one more
-- civilization and a skip_quiet_turns=9 run went through the turn America won on, t325). Only what the Victory
-- Progress screen shows a human about a civilization it has met, and only a victory this game's options allow:
--   culture     one civilization short of the number it must be influential on, and either influential on one
--               already or popular with the one it lacks (two civilizations left alive are always "one short")
--   science     Apollo finished and at least half of the spaceship's parts in the ship
--   diplomatic  the United Nations in being and four fifths of the delegates a World Leader needs
--   domination  three or more civilizations in the game and only two still hold their own capital
function H.victory_watch(pid)
  local out = {}
  local me = Players[pid]
  if not me then return out end
  local myTeamId = me:GetTeam()
  local myTeam = Teams[myTeamId]
  local allowed = H.victory_allowed   -- v345: the game's own word, the setup screen's without it
  local function rival(i)
    local q = Players[i]
    return i ~= pid and q and q:IsAlive() and not q:IsMinorCiv() and q:GetTeam() ~= myTeamId
  end
  local function met(i) return myTeam:IsHasMet(Players[i]:GetTeam()) end
  if allowed("VICTORY_CULTURAL") then
    local ok, cv = pcall(H.culture_overview, pid)
    for _, row in ipairs(ok and type(cv) == "table" and cv.civs or {}) do
      if rival(row.player) and type(row.needed) == "number" and type(row.influential_on) == "number" and row.needed > 0 then
        local popular = false
        for _, e in ipairs(row.on or {}) do if e.level == "popular" then popular = true end end
        if row.needed - row.influential_on <= 1 and (row.influential_on >= 1 or popular) then
          out[#out + 1] = { victory = "culture", player = row.player, civ = row.civ,
                            influential_on = row.influential_on, needed = row.needed,
                            note = row.civ .. " is influential on " .. row.influential_on .. " of the " .. row.needed ..
                                   " civilizations a Culture victory needs" }
        end
      end
    end
  end
  if allowed("VICTORY_SPACE_RACE") then
    pcall(function()
      local apollo = GameInfoTypes.PROJECT_APOLLO_PROGRAM
      if not apollo then return end
      local parts, total = {}, 0
      for v in GameInfo.Project_VictoryThresholds() do
        local proj = GameInfoTypes[v.ProjectType]
        if proj and proj ~= apollo and (v.Threshold or 0) > 0 then
          parts[#parts + 1] = { proj = proj, needed = v.Threshold }
          total = total + v.Threshold
        end
      end
      if total <= 0 then return end
      for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
        if rival(i) and met(i) then
          local qt = Teams[Players[i]:GetTeam()]
          if qt:GetProjectCount(apollo) >= 1 then
            local have = 0
            for _, part in ipairs(parts) do have = have + math.min(qt:GetProjectCount(part.proj), part.needed) end
            if have * 2 >= total then
              local civ = Players[i]:GetCivilizationShortDescription()
              out[#out + 1] = { victory = "science", player = i, civ = civ, parts_in_ship = have, parts_needed = total,
                                note = civ .. " has " .. have .. " of the " .. total .. " spaceship parts in its ship" }
            end
          end
        end
      end
    end)
  end
  if allowed("VICTORY_DIPLOMATIC") then
    pcall(function()
      if not (Game.IsUnitedNationsActive and Game.IsUnitedNationsActive()) then return end
      if not (Game.GetNumActiveLeagues and Game.GetNumActiveLeagues() > 0) then return end
      local league = Game.GetActiveLeague()
      local needed = Game.GetVotesNeededForDiploVictory()
      if not league or type(needed) ~= "number" or needed <= 0 then return end
      for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
        if rival(i) and met(i) and league:IsMember(i) then
          local votes = league:CalculateStartingVotesForMember(i)
          if type(votes) == "number" and votes * 5 >= needed * 4 then
            local civ = Players[i]:GetCivilizationShortDescription()
            local row = { victory = "diplomatic", player = i, civ = civ, delegates = votes, needed = needed,
                          note = civ .. " has " .. votes .. " of the " .. needed .. " delegates a World Leader needs" }
            local t = league:GetTurnsUntilVictorySession()
            if t and t < 999 then
              row.turns_until_world_leader_vote = t
              row.note = row.note .. (t <= 0 and "; the vote is this turn" or ("; the vote is in " .. t .. " turns"))
            end
            out[#out + 1] = row
          end
        end
      end
    end)
  end
  if allowed("VICTORY_DOMINATION") then
    pcall(function()
      local ever, holders = 0, {}
      for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
        local q = Players[i]
        if q and q:IsEverAlive() and not q:IsMinorCiv() then
          ever = ever + 1
          if q:IsAlive() and not q:IsHasLostCapital() then holders[#holders + 1] = i end
        end
      end
      if ever < 3 or #holders ~= 2 then return end
      for k, i in ipairs(holders) do
        if rival(i) then
          local other = holders[3 - k]
          local known = met(i)
          local civ = known and Players[i]:GetCivilizationShortDescription() or "unknown"
          local last = other == pid and "yours" or
                       (met(other) and Players[other]:GetCivilizationShortDescription() .. "'s" or "an unmet civilization's")
          out[#out + 1] = { victory = "domination", player = known and i or nil, civ = civ, capitals_left = 1,
                            last_capital_mine = (other == pid) or nil,
                            note = civ .. " and one other civilization are the last two holding their own capital: " ..
                                   civ .. " wins by Domination when it takes " .. last }
        end
      end
    end)
  end
  return out
end

-- The Victory Progress screen's space race (victoryprogress.lua SetProjectValue: Team:GetProjectCount against
-- Project_VictoryThresholds, shown for every known civ that finished Apollo), plus what the tech tree / city
-- screens show a human about the parts: prerequisite tech, whether we have it, finished part units waiting to
-- be moved into the capital. Live t406: which part needs which tech took a raw GameInfo query to find out.
function H.spaceship_status(pid)
  local p = Players[pid]
  local team = Teams[p:GetTeam()]
  local apollo = GameInfoTypes.PROJECT_APOLLO_PROGRAM
  local out = { apollo_done = apollo and team:GetProjectCount(apollo) >= 1 or false, parts = {}, rivals = {} }
  local waiting = {}
  for u in p:Units() do
    local t = GameInfo.Units[u:GetUnitType()]
    if t and t.Type:find("^UNIT_SS_") then waiting[t.Type] = (waiting[t.Type] or 0) + 1 end
  end
  for v in GameInfo.Project_VictoryThresholds() do
    local proj = GameInfoTypes[v.ProjectType]
    local unitType = v.ProjectType:gsub("^PROJECT_", "UNIT_")
    local urow = GameInfo.Units[unitType]
    local tech = urow and urow.PrereqTech or nil
    out.parts[#out.parts + 1] = {
      part = unitType, needed = v.Threshold, in_ship = team:GetProjectCount(proj),
      built_not_delivered = waiting[unitType] or 0,
      tech = tech, have_tech = tech and team:IsHasTech(GameInfoTypes[tech]) or false }
  end
  for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
    local q = Players[i]
    if i ~= pid and q and q:IsEverAlive() and not q:IsMinorCiv() and team:IsHasMet(q:GetTeam()) then
      local qt = Teams[q:GetTeam()]
      if apollo and qt:GetProjectCount(apollo) >= 1 then
        local r = { player = i, civ = q:GetCivilizationShortDescription(), parts_in_ship = 0 }
        for v in GameInfo.Project_VictoryThresholds() do r.parts_in_ship = r.parts_in_ship + qt:GetProjectCount(GameInfoTypes[v.ProjectType]) end
        out.rivals[#out.rivals + 1] = r
      end
    end
  end
  out.note = "finished part units must be moved into the capital and added to the ship (the unit's action there)"
  return out
end
