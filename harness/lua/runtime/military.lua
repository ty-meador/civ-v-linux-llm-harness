-- Shared by earlier fragments (load order: harness/runtime_source.py MANIFEST).
local info_type, plain_text, short = H._ns.info_type, H._ns.plain_text, H._ns.short

-- What a player watching the screen knows of the military situation without asking, on every status of the
-- seat's own turn (v346; the user, 2026-11-23: "giving the LLM the info it needs in real time"). Live,
-- small-king-venice-a, Sonnet 5.5: Venice held two Warriors and a Scout beside the Zulus at turn 88, had bought a
-- Market with 380 gold on turn 82, and was told of an army only once Shaka's units stood 4 plots from the city
-- and the war was on; the city fell on turn 95. A human had seen the Soldiers row of the Demographics screen and
-- the Zulu army on the map for forty turns. Nothing here is estimated and nothing is hidden from a human:
--   soldiers: the Demographics screen's Soldiers row (the same figure, sqrt(might) * 2000): mine, my rank among
--           the living civilizations, the highest (named when it is met, as the screen shows its leader), the
--           average and the lowest.
--   combat_units: my own.
--   forces: combat units of another player in sight within MILITARY_NEAR plots of one of my cities, by owner: a
--           civilization at peace with me from MILITARY_PEACE_MIN units up (an army at the border, not a scout
--           passing) with the approach the diplomacy list shows for its leader, one I am at war with, a
--           city-state at war with me and the barbarians from the first unit.
--   cities: each of my cities that is damaged or has a hostile unit (at war, or barbarian) within MILITARY_CLOSE
--           plots: hit points, strength, the unit garrisoned, the hostile units that close, and what its purchase
--           list holds for the gold in the treasury now (combat units, buildings with a Defense value).
--   approach: the word the diplomacy list shows for each met AI leader I am not at war with (the visible guess,
--           never the AI's hidden approach), by civilization.
--   sieges: each city of a player I am at war with that I see now and have a combat unit within MILITARY_NEAR
--           plots of: where it is, its hit points and strength as its banner shows them, whether it is that
--           player's capital, my combat units within MILITARY_CLOSE plots of it and the enemy's units in sight there,
--           and how far the city strikes with my units standing inside that.
--   upgrades: my combat units whose Upgrade button the unit panel shows (the target can be trained): `ready` the
--           ones it would upgrade this moment, with the price; `waiting` the ones it greys, with the panel's
--           reasons (gold, territory, resources and which, stacking, moved).
--   advisor: what the game's own Military Advisor says on the Advisor Counsel screen this turn, every line, in
--           the screen's order. Live 2026-11-23, Venice t108, five units and the lowest Soldiers figure for sixty
--           turns: "The Zulu Kingdom wields an army that could wipe us off the planet. Do everything we can to
--           remain at peace with them and build military as fast as possible to make our situation less
--           perilous." The game says this to a human; the seat had never been shown it. All of them, not the
--           first: on turn 40 of the duel the first was a research suggestion and the second "We are nearly
--           defenseless! We need to train more units!".
H.MILITARY_NEAR, H.MILITARY_CLOSE, H.MILITARY_PEACE_MIN, H.MILITARY_UPGRADES_SHOWN = 5, 3, 3, 8

-- The Advisor Counsel screen (advisorcounselpopup.lua: Game.GetAdvisorCounsel(), a list of sentences an advisor,
-- in the game's own order): {military, economic, foreign, science}, icons as words. The game keeps one counsel,
-- the active player's, so another seat's read gets nothing.
function H.advisor_counsel(pid)
  if not (Game.GetAdvisorCounsel and AdvisorTypes) or Game.GetActivePlayer() ~= pid then return nil end
  local ok, all = pcall(Game.GetAdvisorCounsel)
  if not ok or type(all) ~= "table" then return nil end
  local out, any = {}, false
  for name, key in pairs({ military = "ADVISOR_MILITARY", economic = "ADVISOR_ECONOMIC", foreign = "ADVISOR_FOREIGN",
                           science = "ADVISOR_SCIENCE" }) do
    local rows, lines = all[AdvisorTypes[key]], {}
    for _, v in ipairs(type(rows) == "table" and rows or {}) do
      local text = plain_text(tostring(v))
      if text and text ~= "" then lines[#lines + 1] = text end
    end
    if #lines > 0 then out[name] = lines; any = true end
  end
  return any and out or nil
end

function H.upgrades_waiting(pid)
  local p = Players[pid]
  local ready, waiting = {}, {}
  for u in p:Units() do
    if u:IsCombatUnit() and not u:IsDelayedDeath() and u.GetUpgradeUnitType then
      local ok, ut = pcall(function() return u:GetUpgradeUnitType() end)
      if ok and ut and ut >= 0 and GameInfo.Units[ut] then
        local okv, shown = pcall(function() return p:CanTrain(ut, false, true, true, true) end)
        if okv and shown then
          local row = { id = u:GetID(), unit = short(info_type(GameInfo.Units, u:GetUnitType())),
                        to = short(GameInfo.Units[ut].Type) }
          pcall(function() row.gold = u:UpgradePrice(ut) end)
          local okc, can = pcall(function() return u:CanUpgradeRightNow() end)
          if okc and can then
            ready[#ready + 1] = row
          else
            local why = {}
            local okb, blocked = pcall(H.upgrade_blocked, u, pid, row.gold, ut)
            for _, b in ipairs(okb and blocked or {}) do
              if b.reason == "resources" and type(b.resources) == "table" then
                for _, r in ipairs(b.resources) do why[#why + 1] = "resources:" .. tostring(r.resource) end
              else
                why[#why + 1] = b.reason
              end
            end
            if #why == 0 then why[1] = "moved" end   -- the engine's gate the panel never spells out (units.lua)
            row.why = why
            waiting[#waiting + 1] = row
          end
        end
      end
    end
  end
  if #ready == 0 and #waiting == 0 then return nil end
  local out = { gold = p:GetGold() }
  local function capped(rows)
    local total = #rows
    while #rows > H.MILITARY_UPGRADES_SHOWN do table.remove(rows) end
    return rows, total
  end
  if #ready > 0 then out.ready, out.ready_total = capped(ready) end
  if #waiting > 0 then out.waiting, out.waiting_total = capped(waiting) end
  return out
end

function H.soldiers_standing(pid)
  local me = Players[pid]
  local team = Teams[me:GetTeam()]
  local function soldiers(p) return math.floor(math.sqrt(p:GetMilitaryMight()) * 2000 + 0.5) end
  local mine = soldiers(me)
  local best, best_id, worst, total, count, rank = nil, nil, nil, 0, 0, 1
  for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
    local p = Players[i]
    if p and p:IsAlive() and not p:IsMinorCiv() then
      local v = soldiers(p)
      if best == nil or v > best then best, best_id = v, i end
      if worst == nil or v < worst then worst = v end
      if v > mine then rank = rank + 1 end
      total, count = total + v, count + 1
    end
  end
  if count < 2 then return nil end
  local row = { mine = mine, rank = rank, of = count, best = best, average = math.floor(total / count + 0.5), lowest = worst }
  if best_id == pid then
    row.best_civ = "you"
  elseif team:IsHasMet(Players[best_id]:GetTeam()) then
    row.best_civ = Players[best_id]:GetCivilizationShortDescription()
  end
  return row
end

-- What the city's purchase list holds for the treasury now: the combat units (strongest first, five at most) and
-- the buildings with a Defense value, each with its price; and the cheapest combat unit the list shows at any
-- price, so a treasury that buys nothing says how far short it is. The same uid/bid pairs as CMP.purchase.
function H.defence_purchases(city, p)
  local gold_y = YieldTypes and YieldTypes.YIELD_GOLD or 2
  local gold = p:GetGold()
  local out = { gold = gold, units = {}, buildings = {} }
  local cheapest
  local priced = {}      -- listed and within the treasury, whether or not the engine sells it this moment
  for u in GameInfo.Units() do
    local strength = math.max(u.Combat or 0, u.RangedCombat or 0)
    if strength > 0 then
      local okl, listed = pcall(function() return city:IsCanPurchase(false, true, u.ID, -1, -1, gold_y) end)
      if okl and listed then
        local okc, cost = pcall(function() return city:GetUnitPurchaseCost(u.ID) end)
        if okc and type(cost) == "number" and cost > 0 then
          if not cheapest or cost < cheapest.gold then cheapest = { item = u.Type, gold = cost } end
          local row = { item = u.Type, gold = cost, strength = u.Combat or 0 }
          if (u.RangedCombat or 0) > 0 then row.ranged = u.RangedCombat end
          local okb, can = pcall(function() return city:IsCanPurchase(true, true, u.ID, -1, -1, gold_y) end)
          if okb and can then out.units[#out.units + 1] = row
          elseif cost <= gold then priced[#priced + 1] = row end
        end
      end
    end
  end
  local function strongest_first(a, b)
    local sa, sb = math.max(a.strength, a.ranged or 0), math.max(b.strength, b.ranged or 0)
    if sa ~= sb then return sa > sb end
    return a.item < b.item
  end
  table.sort(out.units, strongest_first)
  while #out.units > 5 do table.remove(out.units) end
  -- The treasury covers a unit and the engine still sells none: the bought unit appears on the city's tile, and a
  -- tile holds one combat unit (live 2026-11-23, Ravenna t120: 172 gold, a Warrior garrisoned, nothing for sale).
  if #out.units == 0 and #priced > 0 then
    table.sort(priced, strongest_first)
    while #priced > 5 do table.remove(priced) end
    out.blocked = priced
    out.blocked_note = "the treasury covers these, and none is for sale while a combat unit of the same kind (land, or sea) " ..
                       "stands on the city's tile: a bought unit appears there and a tile holds one"
  end
  for b in GameInfo.Buildings() do
    if (b.Defense or 0) > 0 then
      local okb, can = pcall(function() return city:IsCanPurchase(true, true, -1, b.ID, -1, gold_y) end)
      if okb and can then
        local okc, cost = pcall(function() return city:GetBuildingPurchaseCost(b.ID) end)
        if okc and type(cost) == "number" and cost > 0 then
          out.buildings[#out.buildings + 1] = { item = b.Type, gold = cost }
        end
      end
    end
  end
  if #out.units == 0 and not out.blocked and cheapest then out.cheapest_unit = cheapest end
  if #out.buildings == 0 then out.buildings = nil end
  return out
end

function H.military_watch(pid)
  local me = Players[pid]
  if not me then return nil end
  local teamId = me:GetTeam()
  local team = Teams[teamId]
  local out = {}
  pcall(function() out.soldiers = H.soldiers_standing(pid) end)
  local cities, own = {}, 0
  for c in me:Cities() do cities[#cities + 1] = c end
  for u in me:Units() do
    if u:IsCombatUnit() and not u:IsDelayedDeath() then own = own + 1 end
  end
  out.combat_units = own
  pcall(function() out.upgrades = H.upgrades_waiting(pid) end)
  pcall(function()
    local counsel = H.advisor_counsel(pid)
    if counsel and counsel.military then out.advisor = counsel.military end
  end)
  if #cities == 0 then return out end
  local function nearest_city(x, y)
    local best, bd
    for _, c in ipairs(cities) do
      local d = Map.PlotDistance(c:GetX(), c:GetY(), x, y)
      if not bd or d < bd then best, bd = c, d end
    end
    return best, bd
  end
  local forces, close, enemy_near, approach, sieges = {}, {}, {}, nil, {}
  for other = 0, 63 do
    local o = Players[other]
    if other ~= pid and o and (not o.IsAlive or o:IsAlive()) and o:GetTeam() ~= teamId then
      local barbarian = o:IsBarbarian() or false
      local war = barbarian or team:IsAtWar(o:GetTeam()) or false
      if not war and not o:IsMinorCiv() and not o:IsHuman() and team:IsHasMet(o:GetTeam()) then
        pcall(function()
          local word = tostring(H.approach_name(me:GetApproachTowardsUsGuess(other))):gsub("^MAJOR_CIV_APPROACH_", "")
          approach = approach or {}
          approach[o:GetCivilizationShortDescription()] = word
        end)
      end
      if war and not barbarian then
        for c in o:Cities() do
          local q = c:Plot()
          if q and q:IsVisible(teamId, false) then
            local mine_close, mine_near = { units = 0, types = {} }, false
            -- The plots a city strikes (GameDefines.CITY_ATTACK_RANGE, 2 in the stock rules) and my units standing
            -- on them: live 2026-11-23, Opus's siege of Attila's Court lost five Artillery that stopped inside it.
            local strike_range = (GameDefines and GameDefines.CITY_ATTACK_RANGE) or 2
            local in_range = { units = 0, types = {} }
            for u in me:Units() do
              if u:IsCombatUnit() and not u:IsDelayedDeath() then
                local d = Map.PlotDistance(c:GetX(), c:GetY(), u:GetX(), u:GetY())
                if d <= strike_range then
                  local kind = short(info_type(GameInfo.Units, u:GetUnitType()))
                  in_range.units = in_range.units + 1
                  in_range.types[kind] = (in_range.types[kind] or 0) + 1
                end
                if d <= H.MILITARY_NEAR then mine_near = true end
                if d <= H.MILITARY_CLOSE then
                  local kind = short(info_type(GameInfo.Units, u:GetUnitType()))
                  mine_close.units = mine_close.units + 1
                  mine_close.types[kind] = (mine_close.types[kind] or 0) + 1
                end
              end
            end
            if mine_near then
              local row = { city = c:GetName(), id = c:GetID(), civ = H.owner_label(other, pid), player_id = other,
                            x = c:GetX(), y = c:GetY(), capital = c:IsCapital() or false,
                            hp = c:GetMaxHitPoints() - c:GetDamage(), max_hp = c:GetMaxHitPoints(),
                            strength = math.floor(c:GetStrengthValue() / 100 + 0.5), my_units_close = mine_close,
                            strike_range = strike_range, my_units_in_strike_range = in_range }
              local defenders = { units = 0, types = {} }
              for u in o:Units() do
                local uq = u:GetPlot()
                if u:IsCombatUnit() and not u:IsDelayedDeath() and uq and uq:IsVisible(teamId, false)
                   and not u:IsInvisible(teamId, false)
                   and Map.PlotDistance(c:GetX(), c:GetY(), u:GetX(), u:GetY()) <= H.MILITARY_CLOSE then
                  local kind = short(info_type(GameInfo.Units, u:GetUnitType()))
                  defenders.units = defenders.units + 1
                  defenders.types[kind] = (defenders.types[kind] or 0) + 1
                end
              end
              row.enemy_units_close = defenders
              sieges[#sieges + 1] = row
            end
          end
        end
      end
      if war or not o:IsMinorCiv() then
        local row
        for u in o:Units() do
          local q = u:GetPlot()
          if u:IsCombatUnit() and not u:IsDelayedDeath() and q and q:IsVisible(teamId, false)
             and not u:IsInvisible(teamId, false) then
            local c, d = nearest_city(u:GetX(), u:GetY())
            if d <= H.MILITARY_NEAR then
              row = row or { civ = H.owner_label(other, pid), player_id = other, at_war = war, units = 0,
                             strength = 0, types = {}, in_my_land = 0 }
              local kind = short(info_type(GameInfo.Units, u:GetUnitType()))
              row.units = row.units + 1
              row.strength = row.strength + math.max(u:GetBaseCombatStrength(), H.ranged_strength(u))
              row.types[kind] = (row.types[kind] or 0) + 1
              if q:GetOwner() == pid then row.in_my_land = row.in_my_land + 1 end
              if not row.nearest or d < row.nearest.distance then row.nearest = { city = c:GetName(), distance = d } end
              if war then
                enemy_near[c:GetID()] = true
                if d <= H.MILITARY_CLOSE then
                  local k = close[c:GetID()] or { units = 0, types = {} }
                  k.units = k.units + 1
                  k.types[kind] = (k.types[kind] or 0) + 1
                  close[c:GetID()] = k
                end
              end
            end
          end
        end
        if row and (war or row.units >= H.MILITARY_PEACE_MIN) then
          if barbarian then row.player_id = nil end
          -- the diplomacy list's word for an AI leader (diplomacy.lua: the visible guess, blank for a human)
          if not war and not o:IsMinorCiv() and not o:IsHuman() then
            pcall(function() row.approach_guess = H.approach_name(me:GetApproachTowardsUsGuess(other)) end)
          end
          forces[#forces + 1] = row
        end
      end
    end
  end
  table.sort(forces, function(a, b)
    if a.at_war ~= b.at_war then return a.at_war end
    if a.units ~= b.units then return a.units > b.units end
    return tostring(a.civ) < tostring(b.civ)
  end)
  if #forces > 0 then out.forces = forces end
  if approach then out.approach = approach end
  if #sieges > 0 then out.sieges = sieges end
  local rows = {}
  for _, c in ipairs(cities) do
    local hostile, damage = close[c:GetID()], c:GetDamage()
    if hostile or damage > 0 then
      local row = { id = c:GetID(), name = c:GetName(), hp = c:GetMaxHitPoints() - damage, max_hp = c:GetMaxHitPoints(),
                    strength = math.floor(c:GetStrengthValue() / 100 + 0.5), garrison = false }
      pcall(function()
        local g = c:GetGarrisonedUnit()
        if g then row.garrison = short(info_type(GameInfo.Units, g:GetUnitType())) end
      end)
      if hostile then row.hostile_close = hostile end
      if enemy_near[c:GetID()] or damage > 0 then
        pcall(function() row.can_buy = H.defence_purchases(c, me) end)
      end
      rows[#rows + 1] = row
    end
  end
  if #rows > 0 then out.cities = rows end
  return out
end

-- My units that have something to attack this moment (v346), the way the unit panel lights the attack buttons: a
-- ranged unit with a plot it can strike (H.ranged_targets), a melee unit with an enemy unit or city beside it
-- (H.melee_targets). A unit that sleeps or stands fortified is in no other list: live 2026-11-23, Venice t141, the
-- city fired on every turn of the siege (todo.city_strikes) and the Crossbowman garrisoned in it never did. One row
-- a unit: how many targets, and the one the preview gives the most damage on, with both sides' figures as the
-- panel shows them. MILITARY_ATTACKS_SHOWN rows, ranged first; `more` counts the rest.
H.MILITARY_ATTACKS_SHOWN = 10

function H.unit_attacks(pid)
  local p = Players[pid]
  local rows, more = {}, 0
  for u in p:Units() do
    if u:IsCombatUnit() and not u:IsDelayedDeath() and u:MovesLeft() > 0 then
      local ranged = H.ranged_strength(u) > 0
      local ok, targets = pcall(ranged and H.ranged_targets or H.melee_targets, u, pid)
      -- A siege unit that has not set up strikes nothing yet and was in no list: the enemy units and cities in my
      -- sight within its range are counted for it. Live 2026-11-23, Opus's siege of Attila's Court: "A 'can this
      -- cannon fire this turn' flag in unit rows".
      -- v348: only the ones in its line of fire from this plot (H.in_line_of_fire, the test the shot must pass);
      -- the hidden ones are counted apart, and a unit with nothing but hidden targets has no row. Same siege, t211:
      -- "The unit_attacks row had listed this cannon as 'in_range 2, needs_set_up', so I spent a move setting it up
      -- for nothing" -- hills stood between it and both.
      local in_range, hidden = 0, 0
      if ranged and ok and type(targets) == "table" and #targets == 0 then
        pcall(function()
          if not (u:IsMustSetUpToRangedAttack() and not u:IsSetUpForRangedAttack()) then return end
          local row = GameInfo.Units[u:GetUnitType()]
          local range = row and row.Range or 0
          pcall(function() local r = u:Range(); if r and r > 0 then range = r end end)
          for dx = -range, range do for dy = -range, range do
            local q = Map.PlotXYWithRangeCheck(u:GetX(), u:GetY(), dx, dy, range)
            if q and (q:GetX() ~= u:GetX() or q:GetY() ~= u:GetY()) and next(H.ranged_target_info(u, q, pid)) ~= nil then
              if H.in_line_of_fire(u, q, pid, range) then in_range = in_range + 1 else hidden = hidden + 1 end
            end
          end end
        end)
      end
      if in_range > 0 then
        local row = { id = u:GetID(), unit = short(info_type(GameInfo.Units, u:GetUnitType())), x = u:GetX(), y = u:GetY(),
                      hp = u:GetCurrHitPoints(), ranged = true, needs_set_up = true, in_range = in_range,
                      out_of_line_of_fire = hidden > 0 and hidden or nil }
        if #rows < H.MILITARY_ATTACKS_SHOWN then rows[#rows + 1] = row else more = more + 1 end
      elseif ok and type(targets) == "table" and #targets > 0 then
        local best, most
        for _, t in ipairs(targets) do
          local dealt = type(t.preview) == "table" and t.preview.expected_damage_dealt or 0
          if not best or dealt > most then best, most = t, dealt end
        end
        local row = { id = u:GetID(), unit = short(info_type(GameInfo.Units, u:GetUnitType())), x = u:GetX(), y = u:GetY(),
                      hp = u:GetCurrHitPoints(), ranged = ranged, targets = #targets }
        local strongest = { x = best.x, y = best.y, hp = best.hp }
        if best.city then strongest.city = best.city else strongest.unit = best.unit end
        if type(best.preview) == "table" then
          strongest.deals, strongest.takes = best.preview.expected_damage_dealt, best.preview.expected_damage_taken
        end
        row.most_damage_on = strongest
        if #rows < H.MILITARY_ATTACKS_SHOWN then rows[#rows + 1] = row else more = more + 1 end
      end
    end
  end
  table.sort(rows, function(a, b)
    if a.ranged ~= b.ranged then return a.ranged end
    return a.id < b.id
  end)
  return rows, more
end

-- The game's own confirmation before an attack it thinks badly of (advisormodal.lua, BUTTONPOPUP_ADVISOR_MODAL):
-- "We may want to reconsider this attack; you will do marginal damage to your opponent and they will do
-- considerable damage to you", with Attack anyway and Cancel, raised for a melee attack at bad odds and for a
-- first attack on a city. Nothing in the harness answered it: live 2026-11-23, the duel t106, a Warrior ordered
-- onto a Pikeman left the screen up, every later order and the end of the turn were refused, and three instances
-- in a row gave up on the turn. `close` cancels it, as the Cancel button does (the unit keeps its moves).
function H.advisor_modal(close, pid)
  local out = { up = false }
  local ok, ctx = pcall(function() return ContextPtr:LookUpControl("/InGame/AdvisorModal") end)
  if not ok or not ctx or ctx:IsHidden() then return out end
  out.up = true
  pcall(function() out.text = plain_text(ContextPtr:LookUpControl("/InGame/AdvisorModal/DescriptionLabel"):GetText()) end)
  pcall(function() out.title = plain_text(ContextPtr:LookUpControl("/InGame/AdvisorModal/TitleLabel"):GetText()) end)
  if close then
    out.closed = pcall(function() UIManager:DequeuePopup(ctx) end)
  end
  return out
end

-- What the screen's Attack anyway button sets before it repeats the move (Game.SetCombatWarned): the next attack
-- order is not asked about. Set for one order and cleared after it by the caller.
function H.combat_warned(on, pid)
  Game.SetCombatWarned(on and true or false)
  return { ok = true, warned = on and true or false }
end
