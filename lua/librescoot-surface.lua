-- Appended to upstream lua/graph.lua and fed to valhalla_build_tiles via
-- mjolnir.graph_lua_name. Wraps ways_proc instead of patching it, so a Valhalla
-- bump only needs a fresh graph.lua, not a rebased diff.
--
-- Valhalla buckets surface=sett and surface=paving_stones into kPaved, the same
-- class as asphalt, so cobbles are invisible to costing. We move every
-- irregular stone surface into kPavedRough and keep everything else out of it,
-- which makes kPavedRough mean "bumpy stone" in our tiles: the class a
-- small-wheeled scooter cares about, separate from smooth-but-unpaved
-- (kCompacted) surfaces.
--
-- Without a surface tag Valhalla derives the class from smoothness and
-- tracktype, and both can land in kPavedRough. We redirect those two so the
-- class stays exclusive.

local librescoot_cobble_target = "cobblestone"

local librescoot_cobble_surfaces = {
  ["sett"] = true,
  ["cobblestone"] = true,
  ["unhewn_cobblestone"] = true,
  ["cobblestone:flattened"] = true,
  ["paving_stones"] = true,
  ["paving_stones:lanes"] = true,
  ["grass_paver"] = true,
}

-- Values Valhalla would otherwise route into kPavedRough when no surface tag is
-- present. Neither describes stone. smoothness=intermediate is the wiki's
-- "city bike, wheelchair, scooter and all below" rung, whose own example is
-- "the best unpaved but compacted roads"; tracktype=grade1 is "solid, mostly
-- paved". Both belong in kCompacted, which leaves kPavedRough to stone.
local librescoot_smoothness_rewrite = { ["intermediate"] = "compacted" }
local librescoot_tracktype_rewrite = { ["grade1"] = "compacted" }

local librescoot_upstream_ways_proc = ways_proc

function ways_proc(kv, nokeys)
  local filter, tags, x, y = librescoot_upstream_ways_proc(kv, nokeys)
  if not tags then
    return filter, tags, x, y
  end

  if tags["surface"] then
    if librescoot_cobble_surfaces[tags["surface"]] then
      tags["surface"] = librescoot_cobble_target
    end
  elseif tags["tracktype"] and librescoot_tracktype_rewrite[tags["tracktype"]] then
    tags["surface"] = librescoot_tracktype_rewrite[tags["tracktype"]]
  elseif tags["smoothness"] and librescoot_smoothness_rewrite[tags["smoothness"]] then
    tags["surface"] = librescoot_smoothness_rewrite[tags["smoothness"]]
  end

  return filter, tags, x, y
end
