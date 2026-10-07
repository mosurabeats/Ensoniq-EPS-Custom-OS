-- Print the voice lists whenever they change, between VOICES_FROM and
-- VOICES_TO seconds (env, default 29.9-31.5): "[k<key> i<instrument>
-- s<state>]" per voice; state 2 = playing (release list), 4 = held,
-- 8 = being killed (voice steal or mute group).
local ram = manager.machine.memory.shares[":osram"]
local from = tonumber(os.getenv("VOICES_FROM") or "29.9")
local to = tonumber(os.getenv("VOICES_TO") or "31.5")
local function list(sentinel)
  local out, v, n = "", ram:read_u16(sentinel), 0
  while v ~= sentinel and n < 24 do
    out = out .. string.format(" [k%d i%d s%d]", ram:read_u8(v + 4), ram:read_u8(v + 6), ram:read_u8(v + 12))
    v = ram:read_u16(v); n = n + 1
  end
  return out
end
local last = ""
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if t < from or t > to then return end
  local s = "active:" .. list(0x16E4) .. "  release:" .. list(0x16DC)
  if s ~= last then print(string.format("VOICES %.3f %s", t, s)); last = s end
end)
