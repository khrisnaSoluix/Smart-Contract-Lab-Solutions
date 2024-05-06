import unittest
from datetime import date
from tools.green_days.green_day_calendar_generator import (
    CalendarDefinition,
    CalendarEvent,
    CalendarManifest,
    CalendarManifestBuilder,
    CalendarResourceBuilder,
    CalendarResources,
    CalendarResourcesBuilder,
    GreenDayDateGenerator,
)
from typing import Set, List
import yaml
from zoneinfo import ZoneInfo

EXPECTED_GREEN_DAYS_UNMERGED_EVENTS_RESOURCES_FILE = (
    "tools/green_days/tests/expected_green_days_unmerged_events.resources.yaml"
)
EXPECTED_GREEN_DAYS_UNMERGED_MANIFEST_FILE = (
    "tools/green_days/tests/expected_green_days_unmerged.manifest.yaml"
)
EXPECTED_GREEN_DAYS_UNMERGED_RESOURCE_FILE = (
    "tools/green_days/tests/expected_green_days_unmerged.resource.yaml"
)
EXPECTED_GREEN_DAYS_MERGED_EVENTS_RESOURCES_FILE = (
    "tools/green_days/tests/expected_green_days_merged_events.resources.yaml"
)
EXPECTED_GREEN_DAYS_MERGED_MANIFEST_FILE = (
    "tools/green_days/tests/expected_green_days_merged.manifest.yaml"
)
EXPECTED_GREEN_DAYS_MERGED_RESOURCE_FILE = (
    "tools/green_days/tests/expected_green_days_merged.resource.yaml"
)


class TestGreenDayCalendarGenerator(unittest.TestCase):
    def setUp(self):
        # All New South Wales holidays 2022
        self.holidays: Set[date] = set(
            [
                date(2022, 1, 1),
                date(2022, 1, 3),
                date(2022, 1, 26),
                date(2022, 4, 15),
                date(2022, 4, 16),
                date(2022, 4, 17),
                date(2022, 4, 18),
                date(2022, 4, 25),
                date(2022, 6, 13),
                date(2022, 8, 1),
                date(2022, 10, 3),
                date(2022, 12, 25),
                date(2022, 12, 26),
                date(2022, 12, 27),
            ]
        )

    def _generic_test_cal_events_yaml_generator(
        self,
        merge_consecutive_events: bool,
        expected_events_file: str,
        expected_manifest_file: str,
        expected_resource_file: str,
    ):
        calendar_id = "nsw_calendar_green_days"
        pack_version = "1.0.0"
        pack_name = "Bliss TMV Library Common Calendar 2022 Resources"
        display_name = "NSW Calendar Business Days"
        description = "NSW banking days."
        green_day_generator = GreenDayDateGenerator()
        green_days: List[date] = green_day_generator.generate_green_days_for_range(
            2022, 2022, self.holidays
        )
        # Assemble calendar events
        resources_builder: CalendarResourcesBuilder = CalendarResourcesBuilder(
            event_id_prefix="nsw_calendar_event",
            calendar_id=calendar_id,
            green_days=green_days,
            zone=ZoneInfo("Australia/Sydney"),
            merge_consecutive_events=merge_consecutive_events,
        )
        resources: CalendarResources = resources_builder.build_calendar_resources()

        # Assemble calendar manifest
        events: List[CalendarEvent] = [
            calendar_event_definition.payload.calendar_event
            for calendar_event_definition in resources.resources
        ]
        manifest_builder = CalendarManifestBuilder(
            calendar_id=calendar_id,
            calendar_events=events,
            pack_version=pack_version,
            pack_name=pack_name,
        )
        manifest: CalendarManifest = manifest_builder.build_calendar_manifest()

        # Assemble calendar
        resource_builder = CalendarResourceBuilder(
            calendar_id=calendar_id,
            display_name=display_name,
            description=description,
        )
        resource: CalendarDefinition = resource_builder.build_calendar_resource()

        expected_events_yaml: str = None
        with open(expected_events_file) as f:
            expected_events_yaml = "".join(f.readlines())

        expected_manifest_yaml: str = None
        with open(expected_manifest_file) as f:
            expected_manifest_yaml = "".join(f.readlines())

        expected_resource_yaml: str = None
        with open(expected_resource_file) as f:
            expected_resource_yaml = "".join(f.readlines())

        actual_events_yaml: str = yaml.dump(resources.to_yaml_dict(), sort_keys=False)
        actual_manifest_yaml: str = yaml.dump(manifest.to_yaml_dict(), sort_keys=False)
        actual_resource_yaml: str = yaml.dump(resource.to_yaml_dict(), sort_keys=False)

        self.assertEqual(expected_events_yaml, actual_events_yaml)
        self.assertEqual(expected_manifest_yaml, actual_manifest_yaml)
        self.assertEqual(expected_resource_yaml, actual_resource_yaml)

    def test_cal_events_unmerged_yaml_generator(self):
        self._generic_test_cal_events_yaml_generator(
            merge_consecutive_events=False,
            expected_events_file=EXPECTED_GREEN_DAYS_UNMERGED_EVENTS_RESOURCES_FILE,
            expected_manifest_file=EXPECTED_GREEN_DAYS_UNMERGED_MANIFEST_FILE,
            expected_resource_file=EXPECTED_GREEN_DAYS_UNMERGED_RESOURCE_FILE,
        )

    def test_cal_events_merged_yaml_generator(self):
        self._generic_test_cal_events_yaml_generator(
            merge_consecutive_events=True,
            expected_events_file=EXPECTED_GREEN_DAYS_MERGED_EVENTS_RESOURCES_FILE,
            expected_manifest_file=EXPECTED_GREEN_DAYS_MERGED_MANIFEST_FILE,
            expected_resource_file=EXPECTED_GREEN_DAYS_MERGED_RESOURCE_FILE,
        )


if __name__ == "__main__":
    unittest.main()
