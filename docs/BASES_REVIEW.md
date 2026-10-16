# Base registry review

Built by `python3 warwatch/basesites.py build` from `warwatch/data/bases_seed.csv` and OpenStreetMap. Check each row against the
satellite image (link). Where OSM has no aprons, piers or outline, draw them in `warwatch/data/bases_manual.geojson`
(properties `id` and `part` = outline, apron, harbour or pier) and rebuild. Mark the last column when a row is right.

| Site | Kind | Outline polygons | Aprons (count, km²) | Piers / harbour | Flags | Image | OK? |
|---|---|---|---|---|---|---|---|
| Al Udeid Air Base, Qatar | air | 1 | 30, 1.40 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=25.1170&lng=51.3150&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Al Dhafra Air Base, UAE | air | 2 | 48, 1.34 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=24.2480&lng=54.5480&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Prince Sultan Air Base, Saudi Arabia | air | 2 | 7, 1.59 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=24.0630&lng=47.5800&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Ali Al Salem Air Base, Kuwait | air | 2 | 41, 0.39 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=29.3470&lng=47.5210&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Muwaffaq Salti Air Base, Jordan | air | 1 | 11, 0.17 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=31.8270&lng=36.7820&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| NSA Bahrain and Mina Salman port | naval | 1 | 0, 0.00 | 6 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=26.2050&lng=50.6100&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Diego Garcia | air+naval | 2 | 4, 0.41 | 2 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=-7.3130&lng=72.4110&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| RAF Akrotiri, Cyprus | air | 1 | 15, 0.34 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=34.5900&lng=32.9880&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Incirlik Air Base, Turkey | air | 1 | 26, 0.32 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=37.0020&lng=35.4260&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Camp Lemonnier, Djibouti | air | 1 | 6, 0.14 | 1 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=11.5470&lng=43.1590&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Souda Bay, Crete | air+naval | 1 | 51, 0.51 | 2 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=35.5320&lng=24.1500&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Nevatim Air Base | air | 1 | 16, 0.22 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=31.2080&lng=35.0120&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Ramon Air Base | air | 2 | 7, 0.05 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=30.7760&lng=34.6670&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Hatzerim Air Base | air | 1 | 9, 0.15 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=31.2340&lng=34.6630&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Bandar Abbas: 9th air base and naval base | air+naval | 1 | 6, 0.27 | 26 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=27.2180&lng=56.3780&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Isfahan 8th Tactical Air Base | air | 1 | 4, 0.29 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=32.7510&lng=51.8610&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Hamadan (Nojeh) 3rd Tactical Air Base | air | 1 | 3, 0.10 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=35.2110&lng=48.6530&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Tabriz 2nd Tactical Air Base | air | 1 | 5, 0.19 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=38.1340&lng=46.2350&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Dezful (Vahdati) 4th Tactical Air Base | air | 1 | 5, 0.23 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=32.4340&lng=48.3980&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Bushehr 6th Tactical Air Base | air | 2 | 3, 0.16 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=28.9450&lng=50.8350&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Imam Khomeini Spaceport, Semnan | launch | 1 | 0, 0.00 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=35.2340&lng=53.9210&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Jask naval base | naval | 1 | 2, 0.03 | 1 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=25.6500&lng=57.7700&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Ain al-Asad Air Base, Iraq | air | 1 | 26, 0.35 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=33.7860&lng=42.4410&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Hmeimim Air Base, Syria | air | 1 | 5, 0.25 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=35.4010&lng=35.9490&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Hodeidah port, Yemen | port | 1 | 0, 0.00 | 2 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=14.8300&lng=42.9300&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Engels-2 Air Base | air | 1 | 9, 0.72 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=51.4810&lng=46.2000&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Olenya Air Base | air | 1 | 5, 0.14 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=68.1520&lng=33.4640&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Shaykovka Air Base | air | 1 | 4, 0.47 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=54.2260&lng=34.3710&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Mozdok Air Base | air | 1 | 3, 0.20 | 0 / 0 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=43.7870&lng=44.6030&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
| Novorossiysk naval base | naval | 1 | 0, 0.00 | 29 / 2 |  | [Copernicus](https://browser.dataspace.copernicus.eu/?zoom=14&lat=44.7000&lng=37.7900&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR) | |
