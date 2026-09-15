# India location directory

Use the current Government of India Local Government Directory (LGD) export to
populate the cascading location dropdowns. The source directory is:

https://lgdirectory.gov.in/demo/downloadDirectory.do

Use the LGD village export that contains State, District, Sub-District/Tehsil
and Village columns. The importer accepts both the shorter headers below and
standard LGD English-name headers such as `State Name (In English)`:

```text
state,district,tehsil,village
```

Then import it into the running app data store:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m soil_npk.locations --import-csv .\india_lgd_locations.csv
```

The database stores the full directory server-side and returns one selected
level at a time, so the browser never downloads all villages at once.
