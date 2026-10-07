-- With mame/keys/loop_undo.txt: the takes (mame/takes.lua), the voices
-- from 37 s (mame/voices.lua) and the sequencer state and flags whenever
-- they change: "SEQ t state flags" (0xFF8028, 0xFF815A).
dofile(os.getenv("EPS_ROOT") .. "/mame/takes.lua")
dofile(os.getenv("EPS_ROOT") .. "/mame/voices.lua")
local ram = manager.machine.memory.shares[":osram"]
local last = ""
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if t < 29 then return end
  local s = string.format("%04x %02x", ram:read_u16(0x8028), ram:read_u8(0x815a))
  if s ~= last then print(string.format("SEQ %.2f %s", t, s)); last = s end
end)
