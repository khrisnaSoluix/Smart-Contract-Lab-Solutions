import argparse
import calendar
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from os.path import exists
from typing import DefaultDict, Deque, List, Set
import yaml
from zoneinfo import ZoneInfo


def datetime_representer(dumper: yaml.Dumper, data: datetime):
    return dumper.represent_scalar("tag:yaml.org,2002:timestamp", data.isoformat())


class StringLiteral(str):
    """Use this class to tell PyYAML that the string should
    be represented with the | symbol in the output.  Strings
    with newline characters will be represented over multiple
    lines.
    """

    pass


def string_representer(dumper: yaml.Dumper, data: str):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(datetime, datetime_representer)
yaml.add_representer(StringLiteral, string_representer)


class YamlObject:
    def to_yaml_dict(self) -> str:
        pass


class CalendarEvent(YamlObject):
    def __init__(
        self,
        id: str,
        calendar_id: str,
        name: str,
        is_active: bool,
        start_timestamp: datetime,
        end_timestamp: datetime,
    ):
        self.id: str = id
        self.calendar_id: str = calendar_id
        self.name: str = name
        self.is_active: bool = is_active
        self.start_timestamp: datetime = start_timestamp
        self.end_timestamp: datetime = end_timestamp

    @staticmethod
    def build(name: str, calendar_id: str, start_date: date, end_date: date, zone: ZoneInfo):
        id: str = name + "_" + start_date.strftime("%d_%b_%Y").lower()
        calendar_id: str = "&{" + calendar_id + "}"
        name: str = start_date.strftime("%d %b %Y")
        is_active: bool = True
        start_timestamp: datetime = datetime(
            start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=zone
        )
        end_timestamp: datetime = datetime(
            end_date.year, end_date.month, end_date.day, 0, 0, 0, tzinfo=zone
        )
        return CalendarEvent(id, calendar_id, name, is_active, start_timestamp, end_timestamp)

    def to_yaml_dict(self):
        return self.__dict__


class CalendarEventPayload(YamlObject):
    def __init__(self, calendar_event: CalendarEvent):
        self.calendar_event: CalendarEvent = calendar_event

    def to_yaml_dict(self):
        return {"calendar_event": self.calendar_event.to_yaml_dict()}


class CalendarEventDefinition(YamlObject):
    def __init__(self, event_id_prefix: str, the_date: date, payload: CalendarEventPayload):
        self.type = "CALENDAR_EVENT"
        self.id = event_id_prefix + "_" + the_date.strftime("%d_%b_%Y").lower()
        self.vault_id = self.id
        self.on_conflict = "SKIP"
        self.payload: CalendarEventPayload = payload

    def to_yaml_dict(self):
        return {
            **self.__dict__,
            "payload": StringLiteral(yaml.dump(self.payload.to_yaml_dict(), sort_keys=False)),
        }


class CalendarResources(YamlObject):
    def __init__(self, calendar_definitions: List[CalendarEventDefinition]):
        self.resources: List[CalendarEventDefinition] = calendar_definitions

    def to_yaml_dict(self):
        return {"resources": [r.to_yaml_dict() for r in self.resources]}


class CalendarResourcesBuilder:
    def __init__(
        self,
        event_id_prefix: str,
        calendar_id: str,
        green_days: List[date],
        zone: ZoneInfo,
        merge_consecutive_events=False,
    ):
        self.event_id_prefix: str = event_id_prefix
        self.calendar_id: str = calendar_id
        self.green_days: List[date] = green_days
        self.zone: ZoneInfo = zone
        self.merge_consecutive_events = merge_consecutive_events

    def build_calendar_resources(self) -> CalendarResources:
        ONE_DAY = timedelta(days=1)
        green_days: Deque[date] = deque(sorted(self.green_days))
        calendar_definitions: List[CalendarEventDefinition] = []
        while len(green_days) > 0:
            start_date = green_days.popleft()
            end_date = start_date + ONE_DAY

            if self.merge_consecutive_events is True:
                while len(green_days) > 0:
                    next_green_day = green_days.popleft()
                    if end_date == next_green_day:
                        end_date = end_date + ONE_DAY
                        continue
                    else:
                        green_days.appendleft(next_green_day)
                        break

            event_definition = CalendarEventDefinition(
                event_id_prefix=self.event_id_prefix,
                the_date=start_date,
                payload=CalendarEventPayload(
                    calendar_event=CalendarEvent.build(
                        name=self.event_id_prefix,
                        calendar_id=self.calendar_id,
                        start_date=start_date,
                        end_date=end_date,
                        zone=self.zone,
                    )
                ),
            )
            calendar_definitions.append(event_definition)

        calendar_resources = CalendarResources(calendar_definitions)

        return calendar_resources


class GreenDayDateGenerator:
    def is_weekday(self, date) -> bool:
        return date.weekday() < 5

    def generate_green_days_for(self, year: int, holidays: Set[date] = None) -> List[date]:
        """
        :param year: the year to for which to generate green days.
        :param holidays: the red days which should be excluded from the list of green
        days for the given year.  Weekends are automatically excluded from
        the green days.
        """
        if year is None:
            raise ValueError("Argument 'year' cannot be None.")
        start: date = date(year, 1, 1)
        days_in_year: int = 366 if calendar.isleap(year) else 365

        all_days: Set[date] = set(start + timedelta(days=i) for i in range(days_in_year))
        holidays = holidays or set()
        week_days = set(filter(self.is_weekday, all_days))
        green_days = sorted(list(week_days - holidays))
        return green_days

    def generate_green_days_for_range(
        self, start_year: int, end_year: int, holidays: Set[date] = None
    ) -> List[date]:
        """
        :param start_year: the year to begin generating green days.
        :param end_year: the final year (inclusive) for which to generate green days.
        :param holidays: the red days which should be excluded from the list of green
        days for the given range of years.  Weekends are automatically excluded from
        the green days.
        """
        if start_year is None:
            raise ValueError("Argument 'start-year' cannot be None.")
        if end_year is None:
            end_year = start_year
        if end_year < start_year:
            raise ValueError(
                f"Argument 'end-year' ({end_year}) cannot be before "
                + f"argument 'start-year' ({start_year})."
            )

        years = list(range(start_year, end_year + 1))
        # Create a map with years for keys, and the set of holidays for each year as values.
        holidays_by_year: DefaultDict[int, Set[date]] = defaultdict(
            lambda: None, {d.year: set() for d in holidays}
        )
        for d in holidays:
            holidays_by_year[d.year].add(d)

        green_days = list()
        for year in years:
            green_days.extend(self.generate_green_days_for(year, holidays_by_year[year]))

        return green_days


class Calendar(YamlObject):
    def __init__(
        self, id: str, is_active: bool = True, display_name: str = None, description: str = None
    ):
        self.id: str = id
        self.is_active: bool = is_active
        self.display_name: str = display_name
        self.description: str = description

    def to_yaml_dict(self):
        return self.__dict__


class CalendarPayload(YamlObject):
    def __init__(self, calendar: Calendar):
        self.calendar: Calendar = calendar

    def to_yaml_dict(self):
        return {"calendar": self.calendar.to_yaml_dict()}


class CalendarDefinition(YamlObject):
    def __init__(
        self, type: str, id: str, vault_id: str, on_conflict: str, payload: CalendarPayload
    ):
        self.type: str = type
        self.id: str = id
        self.vault_id: str = vault_id
        self.on_conflict: str = on_conflict
        self.payload: CalendarPayload = payload

    def to_yaml_dict(self):
        return {
            **self.__dict__,
            "payload": StringLiteral(yaml.dump(self.payload.to_yaml_dict(), sort_keys=False)),
        }


class CalendarResourceBuilder:
    def __init__(self, calendar_id, display_name="", description=""):
        self.calendar_id = calendar_id
        self.display_name = display_name
        self.description = description

    def build_calendar_resource(self) -> CalendarDefinition:
        calendar = Calendar(
            id=self.calendar_id,
            is_active=True,
            display_name=self.display_name,
            description=self.description,
        )
        payload = CalendarPayload(calendar)
        resource = CalendarDefinition(
            type="CALENDAR",
            id=self.calendar_id,
            vault_id=self.calendar_id,
            on_conflict="SKIP",
            payload=payload,
        )
        return resource


class CalendarManifest(YamlObject):
    def __init__(self, pack_version: str = "", pack_name: str = "", resource_ids: List[str] = None):
        self.pack_version: str = pack_version
        self.pack_name: str = pack_name
        self.resource_ids: List[str] = resource_ids

    def to_yaml_dict(self):
        return self.__dict__


class CalendarManifestBuilder(YamlObject):
    def __init__(
        self,
        calendar_id="",
        calendar_events: List[CalendarEvent] = None,
        pack_version="",
        pack_name="",
    ):
        self.calendar_id: str = calendar_id
        self.calendar_events: List[CalendarEvent] = calendar_events or []
        self.pack_version: str = pack_version
        self.pack_name: str = pack_name

    def build_calendar_manifest(self) -> CalendarManifest:
        calendar_event_ids: List[str] = [cal_evt.id for cal_evt in self.calendar_events]
        manifest = CalendarManifest(
            pack_version=self.pack_version,
            pack_name=self.pack_name,
            resource_ids=[self.calendar_id] + calendar_event_ids,
        )
        return manifest


class ArgumentParser:
    def __init__(self):
        self.parser: argparse.ArgumentParser = self._define_parser()
        self.pack_version: str = None
        self.pack_name: str = None
        self.display_name: str = None
        self.description: str = None
        self.start_year: int = 0
        self.end_year: int = 0
        self.holidays: Set[date] = None
        self.event_id_prefix: str = None
        self.zone: ZoneInfo = None

    def parse_args(self):
        args = self.parser.parse_args()
        self.pack_version = args.pack_version
        self.pack_name = args.pack_name
        self.display_name = args.calendar_display_name
        self.description = args.calendar_description
        self.holidays = self._extract_holidays(args)
        self.zone = ZoneInfo(args.zone or "UTC")
        self.start_year = args.start_year or datetime.now().astimezone(self.zone).year
        self.end_year = args.end_year or self.start_year
        self.event_id_prefix = args.event_id_prefix or ""
        self.calendar_id = args.calendar_id or ""
        self.merge_consecutive_events = args.merge_consecutive_events or False

    def _extract_holidays(self, parsed_args) -> Set[date]:
        holidays_str: str = parsed_args.holidays
        if holidays_str is None:
            return set()
        holidays_arr: Set[str] = holidays_str.split(",")
        return set(datetime.strptime(h, "%Y-%m-%d").date() for h in holidays_arr)

    def _define_parser(self):
        parser = argparse.ArgumentParser(
            description="""Generate banking day definitions as YAML for Vault Calendars.
                            Requires Python 3.9 or above.
                            """,
            epilog="Copyright Thought Machine 2022.",
        )
        parser.add_argument(
            "--pack-version",
            type=str,
            default="",
            help="The pack-version field you want for the generated manifest file.",
        )
        parser.add_argument(
            "--pack-name",
            type=str,
            default="",
            help="The name of the pack you want for the generated manifest file.",
        )
        parser.add_argument(
            "--calendar-id",
            type=str,
            default="green_days",
            help="The identifier for the calendar.  This value will get wrapped "
            + 'like this "\'&{calendar_id}\'" for use with the CLU.  Default is "green_days".',
        )
        parser.add_argument(
            "--calendar-display-name",
            type=str,
            default="",
            help="The calendar display name for the calendar resource file.",
        )
        parser.add_argument(
            "--calendar-description",
            type=str,
            default="",
            help="The description of the calendar for the calendar resource file.",
        )
        parser.add_argument(
            "--event-id-prefix",
            type=str,
            default="green_day",
            help='The prefix for the calendar event id.  Default is "green_day".',
        )
        parser.add_argument(
            "--start-year",
            type=int,
            help="The calendar year from which to generate green days (banking days)."
            + "Format yyyy.  Default is current year.",
        )
        parser.add_argument(
            "--end-year",
            type=int,
            help="The calendar year (inclusive) up to which to generate green days (banking days)."
            + "Format yyyy.  Default is start-year.",
        )
        parser.add_argument(
            "--zone",
            type=str,
            default="UTC",
            help="Timezone.  eg Australia/Sydney.  Defaults to UTC.",
        )
        parser.add_argument(
            "--holidays",
            type=str,
            help="A comma-separated list of holidays in ISO date format (yyyy-MM-dd). "
            + "eg 2022-01-03,2022-12-26",
        )
        parser.add_argument(
            "--merge-consecutive-events",
            type=bool,
            default=False,
            help="Default false.  Omit this argument to set it false.  Set it to true to combine "
            + "into single calendar events groups of events that have no weekends or holidays "
            + "within them.",
        )
        return parser


class YamlFileWriter:
    def write_yaml_to_file(self, yaml_object: YamlObject, file_name: str) -> None:
        yaml_str = yaml.dump(yaml_object.to_yaml_dict(), sort_keys=False)
        if exists(file_name):
            raise NameError(f"File {file_name} already exists!  Aborting.")
        with open(file_name, "w") as f:
            f.write(yaml_str)
            print(f"Wrote file {file_name}.")


if __name__ == "__main__":
    arg_parser = ArgumentParser()
    arg_parser.parse_args()
    green_day_generator = GreenDayDateGenerator()
    green_days: List[date] = green_day_generator.generate_green_days_for_range(
        arg_parser.start_year, arg_parser.end_year, arg_parser.holidays
    )
    # Assemble calendar events
    resources_builder: CalendarResourcesBuilder = CalendarResourcesBuilder(
        event_id_prefix=arg_parser.event_id_prefix,
        calendar_id=arg_parser.calendar_id,
        green_days=green_days,
        zone=arg_parser.zone,
        merge_consecutive_events=arg_parser.merge_consecutive_events,
    )
    resources: CalendarResources = resources_builder.build_calendar_resources()

    # Assemble calendar manifest
    events: List[CalendarEvent] = [
        calendar_event_definition.payload.calendar_event
        for calendar_event_definition in resources.resources
    ]
    manifest_builder = CalendarManifestBuilder(
        calendar_id=arg_parser.calendar_id,
        calendar_events=events,
        pack_version=arg_parser.pack_version,
        pack_name=arg_parser.pack_name,
    )
    manifest: CalendarManifest = manifest_builder.build_calendar_manifest()

    # Assemble calendar
    resource_builder = CalendarResourceBuilder(
        calendar_id=arg_parser.calendar_id,
        display_name=arg_parser.display_name,
        description=arg_parser.description,
    )
    resource: CalendarDefinition = resource_builder.build_calendar_resource()

    # Write out YAML to files.
    yaml_writer = YamlFileWriter()
    yaml_writer.write_yaml_to_file(resources, f"{arg_parser.calendar_id}_events.resources.yaml")
    yaml_writer.write_yaml_to_file(manifest, f"{arg_parser.calendar_id}.manifest.yaml")
    yaml_writer.write_yaml_to_file(resource, f"{arg_parser.calendar_id}.resource.yaml")
