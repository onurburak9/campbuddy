from datetime import date

from camply.containers import SearchWindow
from camply.search import SearchRecreationDotGov

# Equivalent CLI command:
# camply campsites --provider RecreationDotGov \
#   --start-date 2026-07-03 --end-date 2026-07-06 \
#   --rec-area 1076 --rec-area 2991 --nights 3

search = SearchRecreationDotGov(
    search_window=SearchWindow(
        start_date=date(2026, 7, 3),
        end_date=date(2026, 7, 6),
    ),
    recreation_area=[1076, 2991],
    nights=3,
)

print("Searching for available campsites...\n")
sites = search.get_matching_campsites(continuous=False)

if not sites:
    print("No available campsites found.")
else:
    print(f"Found {len(sites)} available campsite(s):\n")
    for site in sites:
        print(
            f"  [{site.booking_date} → {site.booking_end_date}]"
            f"  {site.facility_name} — {site.campsite_site_name}"
            f"  ({site.campsite_type})"
            f"  Book: {site.booking_url}"
        )
