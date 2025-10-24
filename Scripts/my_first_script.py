import pcbnew as pcb

board = pcb.GetBoard()
tracks = board.GetTracks()
track_names = []
lengths = {}

CLK_LEN=50
RES_LEN=1.6

for track in tracks:
  if track.GetNetClassName() == 'DDR_ADDRESS':
    length = track.GetLength()
    name = track.GetNetname().split('/')[-1]
    name = name.split('DDR_')[-1]
    if length == 0.0:
      length = 1545200
    if track.GetNetname() in track_names:
      lengths[name] += round(length/1000000,4)
    else:
      track_names.append(name)
      lengths[name] = round(length/1000000,4)

for key, val in lengths.items():
  print(f"(rule \"AC Signal Length Match {key}\"\n\t(condition \"A.NetName == \'/MEMORY/{key}_R\'\")\n\t(constraint length (min {(CLK_LEN-val-RES_LEN)-1}mm) (max {(CLK_LEN-val-RES_LEN)+1}mm) (opt {(CLK_LEN-val-RES_LEN)}mm)))")
    

"""
(rule "DDR CLOCK Length Clock"
	(condition "A.NetClass == 'DDR_CLOCK'")
	(constraint skew (min -1mm) (max 1mm) (opt 0mm))
	(constraint length (min 49mm) (max 51mm) (opt 50mm)))
"""
#print(track_names)
#for key, val in lengths.items():
#  print(key, round(val/1000000, 4))

