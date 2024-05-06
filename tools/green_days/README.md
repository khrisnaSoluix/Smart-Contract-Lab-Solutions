Green Day Calendar Generator is a tool to generate Vault CLU calendar resource, calendar event resources, and manifest YAML from some simple arguments.  Given a list of holiday dates, the tool will generate all the banking days (green days) in the YAML format required by Vault.  eg:
```
$ python3 projects/bliss/tools/green_days/green_day_calendar_generator.py  \
--pack-version "1.0.0" \
--pack-name "My Project Common Calendar 2022 Resources" \
--event_id_prefix "calendar_event" \
--calendar-id "calendar_green_days" \
--start-year 2022 \
--end-year 2022 \
--holidays "2022-01-01,2022-01-03,2022-01-26,2022-04-15,2022-04-16,2022-04-17,2022-04-18,2022-04-25,2022-06-13,2022-08-01,2022-10-03,2022-12-25,2022-12-26,2022-12-27" \
--zone "Australia/Sydney" \
--merge-consecutive-events true \
--calendar-display-name "Calendar Business Days" \
--calendar-description "Banking days."
```

The output files looks as follows.

`calendar_green_days_events.resources.yaml`:
```
resources:
- type: CALENDAR_EVENT
  id: calendar_event_04_jan_2022
  vault_id: calendar_event_04_jan_2022
  on_conflict: SKIP
  payload: |
    calendar_event:
      id: calendar_event_04_jan_2022
      calendar_id: '&{calendar_green_days}'
      name: 04 Jan 2022
      is_active: true
      start_timestamp: 2022-01-04T00:00:00+11:00
      end_timestamp: 2022-01-08T00:00:00+11:00
- type: CALENDAR_EVENT
  id: calendar_event_10_jan_2022
  vault_id: calendar_event_10_jan_2022
  on_conflict: SKIP
  payload: |
    calendar_event:
      id: calendar_event_10_jan_2022
      calendar_id: '&{calendar_green_days}'
      name: 10 Jan 2022
      is_active: true
      start_timestamp: 2022-01-10T00:00:00+11:00
      end_timestamp: 2022-01-15T00:00:00+11:00
...
```

`calendar_green_days.manifest.yaml`:
```
pack_version: 1.0.0
pack_name: My Project Common Calendar 2022 Resources
resource_ids:
- calendar_green_days
- calendar_event_04_jan_2022
- calendar_event_10_jan_2022
...
```

`calendar_green_days.resource.yaml`:
```
type: CALENDAR
id: calendar_green_days
vault_id: calendar_green_days
on_conflict: SKIP
payload: |
  calendar:
    id: calendar_green_days
    is_active: true
    display_name: Calendar Business Days
    description: Banking days.

```
