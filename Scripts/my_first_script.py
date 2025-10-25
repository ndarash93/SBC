import pcbnew as pcb

board = pcb.GetBoard()
tracks = board.GetTracks()
track_names = []
lengths = {}

CLK_LEN=45
RES_LEN=1.6
VIA_LEN= 1545200.0

for track in tracks:
  if track.GetNetClassName() == 'DDR_ADDRESS':
    length = track.GetLength()
    name = track.GetNetname().split('/')[-1]
    name = name.split('DDR_')[-1]
    if length == 0.0:
      length = VIA_LEN
    #print(name, length)
    if name in track_names:
      lengths[name] += round(length/1000000,4)
    else:
      track_names.append(name)
      lengths[name] = round(length/1000000,4)

for key, val in lengths.items():
  #print(key, val)
  print(f"(rule \"AC Signal Length Match {key}\"\n\t(condition \"A.NetName == \'/MEMORY/{key}_R\'\")\n\t(constraint length (min {((CLK_LEN-val)-RES_LEN)-1}mm) (max {(CLK_LEN-val-RES_LEN)+1}mm) (opt {(CLK_LEN-val-RES_LEN)}mm)))")
    
#print(565685.4249492381 + 1545200.0 + 890000.0 + 4101219.330881976 + 2828427.1247461904 + 2300000.0)
"""
(rule "DDR CLOCK Length Clock"
	(condition "A.NetClass == 'DDR_CLOCK'")
	(constraint skew (min -1mm) (max 1mm) (opt 0mm))
	(constraint length (min 49mm) (max 51mm) (opt 50mm)))
"""
#print(track_names)
#for key, val in lengths.items():
#  print(key, round(val/1000000, 4))

