import pcbnew as pcb

board = pcb.GetBoard()
tracks = board.GetTracks()
track_names = []
lengths = {}
for track in tracks:
  if track.GetNetClassName() == 'DDR_ADDRESS':
    if track.GetNetname() in track_names:
      lengths[track.GetNetname()] += track.GetLength()
    else:
      track_names.append(track.GetNetname())
      lengths[track.GetNetname()] = track.GetLength()
    

print(track_names)
for key, val in lengths.items():
  print(key, round(val/1000000, 4))
