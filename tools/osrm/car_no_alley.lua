-- car_no_alley.lua
-- Based on the standard car profile but excludes alleys and heavily penalises living streets.
-- Usage: osrm-extract -p /data/car_no_alley.lua -o /data/taiwan-noalley.osrm /data/<pbf>

package.path = package.path .. ";/opt/profiles/?.lua;/opt/profiles/lib/?.lua"

local car = require("car")

local _orig_process_way = car.process_way

car.process_way = function(profile, way, result, relations)
    local highway = way:get_value_by_key("highway")
    local service = way:get_value_by_key("service")

    -- Hard-exclude: service roads explicitly tagged as alleys
    if highway == "service" and service == "alley" then
        return
    end

    _orig_process_way(profile, way, result, relations)

    -- Penalise living streets: keep them passable (last resort) but extremely slow
    -- so the router strongly prefers any other road type
    if highway == "living_street" then
        if result.forward_speed  and result.forward_speed  > 0 then result.forward_speed  = 2 end
        if result.backward_speed and result.backward_speed > 0 then result.backward_speed = 2 end
        if result.forward_rate   and result.forward_rate   > 0 then result.forward_rate   = result.forward_rate   * 0.1 end
        if result.backward_rate  and result.backward_rate  > 0 then result.backward_rate  = result.backward_rate  * 0.1 end
    end
end

return car
