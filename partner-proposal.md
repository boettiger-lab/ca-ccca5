Nice to connect with you. We are glad to hear you are interested in this idea! I am copying Georgia Hernández, who was the postdoc who let the project the past couple years.

Gary likely explained some of this: As part of California's Fifth Climate Change Assessment Research Program, we evaluated photosynthetic heat tolerance of over 100 plant species from across California. These analyses allowed us to identify temperature thresholds where plants are impacted by rising temperatures (Tcrit is when photosynthetic capacity is initially impacted, and T50 is when there is a 50% reduction in perfromance). These are very standard metrics used to evaluate plant heat tolerance.

We are interested in building an interactive online tool that maps where California plant species may become vulnerable under future climate scenarios. The basic idea is that a user would select a species, choose a thermal tolerance threshold, such as Tcrit (probably more realistic since this is a lower threshold) or T50, choose a climate period and scenario, and then adjust an assumption about how much hotter leaves may be than the surrounding air. The tool would then show where, within the species’ current range, projected temperatures are likely to approach or exceed that physiological threshold.

The main datasets needed are:
current species range maps as GeoTIFFs (we already have these for our study species and can easily acquire for more species using Calflora)
species-specific thermal tolerance values (we have these for our species, but I think the tool would be most useful if users could input their own, since the methods used for identifying these values are very popular and different studies will inevitably yield different results)
daily maximum air temperature data for historical and future periods and climate scenario data (from LOCA2 ideally, which is what the State wanted research teams to use)
We would also need a way to account for leaf temperature being different from air temperature through a user-selected offset (Georgia can advise on the range that would be appropriate)

The main output would be a map showing thermal exposure across the species’ current range. Each grid cell could be colored by the mean annual number of days that exceed the selected threshold. For example, if a species has a Tcrit of 41°C and the user assumes leaves are 4°C warmer than air, then the effective air-temperature threshold would be 37°C. The tool would count the predicted number of days when daily maximum air temperature exceeds 37°C, average that across the selected climate period, and display those values across the species’ range.

In addition to the map, the tool could generate a few simple summary metrics that make the results easier to interpret. For example, it could report the percentage of the current range that experiences at least 1, 5, or 10 exceedance days per year, as well as the maximum exceedance above the threshold. So the output would not just show where exposure occurs, but also how widespread and severe it is within the species’ range.

I am also attaching a mockup of what we were envisioning (I used AI to help with this...). I was inspired in part by the great Seeds of Change tool that Matthew Kling created while at Berkeley. I don't want to copy his layout exactly, but it was useful for me to visualize this idea.

Apologies for the long email — I hope this all makes sense. I am NOT a developer so I am rather ignorant of the actual mechanics of creating this. Let me know what you think!



---


Data:


The data are all publicly retrieved/available, except for our temperature threshold data (Tcrit and T50), but we plan to share that publicly once our manuscript is submitted anyhow. So, I do not think there needs to be a secure login wall.

The main data needed for the tool are:
Species range data. These are available in this folder. The folder includes a running species list, with the species codes used in the file names. The individual GeoTIFF files are in this folder. Each file is named with a six-letter species code, based on the first three letters of the genus and the first three letters of the species name.
Thermal tolerance data. As I mentioned, we would like the tool to allow users to enter their own Tcrit or T50 values, since they may have data from different populations, experiments, or sources. However, we also have thermal tolerance data for more than 100 species that could be included as default values in the tool. I’ve attached those data here.
Climate data. I am less familiar with working directly with the LOCA2 data, but I believe this is the correct place to access it: daily maximum temperature example. That link is specifically for daily maximum air temperature, which is the variable we would need for calculating threshold exceedance. The full Cal-Adapt data catalog is available here.
The main output we are envisioning is a map showing thermal exposure across each species’ current range. For example, if a species has a Tcrit of 41°C and the user assumes leaves are 4°C warmer than air temperature, then the effective air-temperature threshold would be 37°C. The tool would count the number of days when daily maximum air temperature exceeds 37°C, summarize those values across the selected climate period, and map the mean annual number of exceedance days within the species’ range. Or maybe there are better ways to visualize this?
In addition to the map, it would be useful to generate simple summary metrics, such as the percentage of the current range experiencing at least 1, 5, or 10 exceedance days per year, and the maximum amount by which projected temperatures exceed the selected threshold.
Hopefully this all makes sense!


(links did not copy but the downloaded data is in the import-data folder now)



