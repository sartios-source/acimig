# Data extraction commands for FEX/utilization debugging

Run from repo root after collection completes.

## ripgrep (rg) versions

### 1) eqptFex objects (dn/id/name/model/ser)
```
rg -n "eqptFex|extch-|fex-" -S data fabrics
```

Targeted (use your eqptFex JSON file path):
```
rg -n "\"type\"\\s*:\\s*\"eqptFex\"|\"dn\"\\s*:\\s*\"topology/.*(extch|fex)-|\"id\"\\s*:\\s*\"\\d+\"|\"name\"\\s*:\\s*\"|\"ser\"\\s*:\\s*\"|\"model\"\\s*:\\s*\"" -S <PATH_TO_EQPTFEX_JSON>
```

### 2) ethpmPhysIf FEX-host ports (eth101-112/...)
```
rg -n "eth1(0[1-9]|1[0-2])/" -S data fabrics
```

Targeted:
```
rg -n "ethpmPhysIf|phys-\\[eth1(0[1-9]|1[0-2])/" -S <PATH_TO_ETHPM_JSON>
```

### 3) fvRsPathAtt extpaths bindings
```
rg -n "fvRsPathAtt|extpaths-|pathep-\\[eth" -S data fabrics
```

Targeted:
```
rg -n "\"tDn\"\\s*:\\s*\"topology/.*extpaths-\\d+/pathep-\\[eth" -S <PATH_TO_FVRSPATHATT_JSON>
```

## PowerShell fallback (no rg)

### eqptFex
```
Get-ChildItem -Recurse -Path data,fabrics -Filter *.json |
  Select-String -Pattern "eqptFex|extch-|fex-" | Select-Object -First 200
```

### ethpmPhysIf FEX-host ports
```
Get-ChildItem -Recurse -Path data,fabrics -Filter *.json |
  Select-String -Pattern "ethpmPhysIf|phys-\\[eth1(0[1-9]|1[0-2])/" | Select-Object -First 200
```

### fvRsPathAtt extpaths
```
Get-ChildItem -Recurse -Path data,fabrics -Filter *.json |
  Select-String -Pattern "fvRsPathAtt|extpaths-|pathep-\\[eth" | Select-Object -First 200
```
