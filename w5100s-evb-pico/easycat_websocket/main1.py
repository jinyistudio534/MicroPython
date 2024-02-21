import uasyncio as a
from main_f import read_loop, send_telemetry,ec_loop

# ---------------------------------------------------------
async def main():
  tasks = [ec_loop(),read_loop(), send_telemetry()]
  await a.gather(*tasks)

a.run(main())
