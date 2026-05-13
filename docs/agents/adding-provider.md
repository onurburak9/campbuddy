# Adding a New Campground Provider

1. Find the camply search class (e.g. `SearchReserveCalifornia`) in `camply.search`
2. Add it to `PROVIDER_MAP` in `core/availability.py`
3. Add a test in `tests/test_availability.py` asserting the new provider name routes correctly
4. Update the provider table in `ARCHITECTURE.md`
