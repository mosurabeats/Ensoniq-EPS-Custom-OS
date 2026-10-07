-- Boot check for mame/run.sh: OS init steps, the main loop, and (when a
-- code-area OS is booted) the heap bounds, the hook site and the area.
-- Breakpoint output goes to debug.log; print() goes to stdout.
local cpu = manager.machine.devices[":maincpu"]
local ram = manager.machine.memory.shares[":osram"]
local prog = cpu.spaces["program"]

-- the OS runs from the low mirror (0x1600...), so breakpoints use 16-bit addresses
cpu.debug:bpset(0x171e, "", 'printf "OS entry, user stack %x\\n",usp; g')
cpu.debug:bpset(0x1774, "", 'printf "main loop reached\\n"; g')
for v, name in pairs({[0xc076a8] = "address error", [0xc076ac] = "illegal instruction",
                      [0xc076a4] = "bus error", [0xc076cc] = "line F"}) do
  cpu.debug:bpset(v, "", string.format(
    'printf "EXCEPTION %s: pc=%%08x sr=%%04x usp=%%x\\n",d@(sp+2),w@(sp),usp; g', name))
end

local n = 0
emu.register_periodic(function()
  n = n + 1
  if n ~= 600 then return end           -- about 10 s of emulated time
  local hook = ""
  for i = 0, 7 do hook = hook .. string.format("%02x", ram:read_u8(0xACA4 + i)) end
  print(string.format("heap end (0xFF165A) %08x", ram:read_u32(0x165A)))
  print("note-on hook site (0xFFACA4) " .. hook ..
        (hook == "3005d040327cdf70" and "  (stock)" or ""))
  if hook:sub(1, 4) == "4eb9" then
    local area = ram:read_u32(0x165A) + 512
    local s = ""
    for i = 0, 15 do s = s .. string.format("%02x", prog:read_u8(area + i)) end
    print(string.format("code area %06x: %s", area, s))
  end
end)
manager.machine.debugger:command("g")
