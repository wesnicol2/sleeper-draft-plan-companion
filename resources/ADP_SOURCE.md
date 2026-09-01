# ADP snapshot source

`adp.csv.xz` is the exact byte-for-byte XZ-compressed copy of the rankings CSV
provided for the September 1, 2026 draft-board refresh.

Uncompressed SHA-256:
`2a6e8e6fdece36f467e557836dc5c9cfe26b5a97d3e53b22fd78919e08e88bbf`

The application uses the `Sleeper` column for canonical Normal-board ordering
and the `AVG` column for average-market valuation/comparison. Other provider
columns are retained in the source but do not affect ordering.
