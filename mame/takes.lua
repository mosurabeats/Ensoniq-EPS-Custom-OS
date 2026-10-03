-- With mame/keys/loop_record.txt: just after each loop wrap, print the take
-- that just finished (the buffer the sequencer now plays) as "TAKE t words",
-- up to its END event (0x8BCx). Buffers: offsets 0xFF8114 / 0xFF8118 from
-- the base in 0xFF8104, 28-byte header; 0xFF811C = write pointer.
dofile(os.getenv("EPS_ROOT") .. "/mame/loop.lua")
local ram = manager.machine.memory.shares[":osram"]
local prog = manager.machine.devices[":maincpu"].spaces["program"]
local last_ptr_buf = nil
local pending = nil
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if t < 37 or ram:read_u8(0x815f) ~= 2 then return end
  local base, a, b, w = ram:read_u32(0x8104), ram:read_u32(0x8114), ram:read_u32(0x8118), ram:read_u32(0x811c)
  if w == 0 then return end
  local cur = (w >= b) and "B" or "A"
  if last_ptr_buf and cur ~= last_ptr_buf then pending = t + 0.05 end
  last_ptr_buf = cur
  if pending and t >= pending then
    pending = nil
    local start = base + ((cur == "B") and a or b) + 28   -- the other one: just finished
    local s = ""
    for i = 0, 2000 do
      local v = prog:read_u16(start + 2 * i)
      s = s .. string.format("%04x ", v)
      if v & 0xFFF0 == 0x8BC0 then break end
    end
    print(string.format("TAKE %.2f %s", t, s))
  end
end)
-- after STOP (45 s in loop_record.txt): the final take, in buffer A
local stop_done = false
emu.register_periodic(function()
  local t = manager.machine.time:as_double()
  if stop_done or t < 45.4 then return end
  stop_done = true
  local start = ram:read_u32(0x8104) + ram:read_u32(0x8114) + 28
  local s = ""
  for i = 0, 2000 do
    local v = prog:read_u16(start + 2 * i)
    s = s .. string.format("%04x ", v)
    if v & 0xFFF0 == 0x8BC0 then break end
  end
  print(string.format("FINAL %.2f %s", t, s))
end)
