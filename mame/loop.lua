-- For mame/keys/loop_record.txt: sets RECORD MODE to LOOPED (0xFF815F = 2)
-- at 36 s (the page buttons for it aren't mapped yet), and prints the
-- sounding voices' keys during playback (from 46.9 s): "PLAYBACK t k36 ...".
local ram = manager.machine.memory.shares[":osram"]
local set = false
local last = ""
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if not set and t > 36 then set = true; ram:write_u8(0x815f, 2) end
  if t < 46.9 then return end
  local out = ""
  for _, sentinel in ipairs({0x16DC, 0x16E4}) do
    local v, n = ram:read_u16(sentinel), 0
    while v ~= sentinel and n < 24 do
      out = out .. string.format(" k%d", ram:read_u8(v + 4)); v = ram:read_u16(v); n = n + 1
    end
  end
  if out ~= last then print(string.format("PLAYBACK %.2f%s", t, out)); last = out end
end)
