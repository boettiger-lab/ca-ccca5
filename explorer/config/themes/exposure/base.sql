-- The team's provisional mean for the selected metric (°C): the base the threshold slider adjusts.
SELECT CASE '{{METRIC}}' WHEN 'tcrit' THEN Tcrit ELSE T50 END AS leaf_c
FROM read_csv('https://raw.githubusercontent.com/boettiger-lab/ca-ccca5/main/data/species_T50_Tcrit_means.csv')
WHERE species_code = '{{ID}}'
