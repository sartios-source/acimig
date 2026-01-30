# FEX data verification commands

Run after selecting a fabric in the UI (or set the session).

## API checks

### Fabric health + object counts
```
Invoke-RestMethod http://127.0.0.1:5001/api/health/fabric
```

### FEX devices rows (feeds FEX Port Util table)
```
Invoke-RestMethod "http://127.0.0.1:5001/api/bi/fex_devices?page=1&size=25"
```

### Rack consolidation rows (feeds rack table)
```
Invoke-RestMethod "http://127.0.0.1:5001/api/bi/fex_racks?page=1&size=25"
```

### FEX/interface match debug
```
Invoke-RestMethod http://127.0.0.1:5001/api/debug/fex-match
```

## Disk check (dataset contains eqptFex)
```
Get-ChildItem -Path C:\Users\shabb\aciv2\fabrics -Recurse -Filter *.json |
  Select-String -Pattern "eqptFex|extch-|fex-"
```

## Alternate host/port
Replace the base URL if running on a different host:
```
Invoke-RestMethod http://10.125.196.70:5001/api/bi/fex_devices?page=1&size=25
```
