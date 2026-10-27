# Catalogue outputs

Run the following command from the repository root to create the scene inventory:

    python scripts/catalogue_south_india_satellite.py

This folder currently contains documentation only; it does not imply that discovery has completed.

Generated files:
- scene_catalog.csv: flattened item-level inventory, with asset URLs and collection metadata.
- stac_items.jsonl.gz: original STAC item records, compressed.
- query_log.csv: status of every query.
