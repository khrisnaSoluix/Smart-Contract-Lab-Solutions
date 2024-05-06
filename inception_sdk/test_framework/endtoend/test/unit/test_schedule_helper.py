# standard libs
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch, sentinel

# third party
import freezegun

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.common.test.mocks.kafka import MockConsumer, MockMessage
from inception_sdk.test_framework.endtoend import schedule_helper
from inception_sdk.test_framework.endtoend.schedule_helper import (
    SCHEDULE_STATUS_OVERRIDE_END_TIMESTAMP,
    SCHEDULE_STATUS_OVERRIDE_START_TIMESTAMP,
    AccountScheduleTagStatusOverride,
)

# Declare Constants
RESPONSE_EXPECTED_EMPTY: list = []

RESPONSE_EXPECTED_ALL = [
    {
        "id": "9b33035de688e76ddf9ef2c24f442e62",
        "status": "JOB_STATUS_SUCCEEDED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-03T23:59:59Z",
        "publish_timestamp": "2021-03-07T00:00:08Z",
    },
    {
        "id": "9608c9340e84ac4ec348820132f909e2",
        "status": "JOB_STATUS_FAILED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-02T23:59:59Z",
        "publish_timestamp": "2021-03-06T00:00:10Z",
    },
    {
        "id": "890a35253d1beec0bb28e1f722aaf80f",
        "status": "JOB_STATUS_SUCCEEDED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-03T23:59:59Z",
        "publish_timestamp": "2021-03-05T00:00:13Z",
    },
]

RESPONSE_UNEXPECTED_ALL = [
    {
        "id": "9b33035de688e76ddf9ef2c24f442e62",
        "status": "JOB_STATUS_PUBLISHED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-03T23:59:59Z",
        "publish_timestamp": "2021-03-01T01:01:17Z",
    },
    {
        "id": "9608c9340e84ac4ec348820132f909e2",
        "status": "JOB_STATUS_PUBLISHED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-02T23:59:59Z",
        "publish_timestamp": "2021-03-08T00:00:10Z",
    },
    {
        "id": "890a35253d1beec0bb28e1f722aaf80f",
        "status": "JOB_STATUS_PUBLISHED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-01T01:01:17Z",
        "publish_timestamp": "2021-03-05T00:00:13Z",
    },
]
RESPONSE_MIX = [
    {
        "id": "9b33035de688e76ddf9ef2c24f442e62",
        "status": "JOB_STATUS_SUCCEEDED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-04T23:59:59Z",
        "publish_timestamp": "2021-03-09T00:00:08Z",
    },
    {
        "id": "9608c9340e84ac4ec348820132f909e2",
        "status": "JOB_STATUS_FAILED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-04T23:59:59Z",
        "publish_timestamp": "2021-03-09T00:00:10Z",
    },
    {
        "id": "890a35253d1beec0bb28e1f722aaf80f",
        "status": "JOB_STATUS_PUBLISHED",
        "schedule_id": "43344845-b7e1-413b-9232-96e9aa7165c0",
        "schedule_timestamp": "2021-03-01T01:01:17Z",
        "publish_timestamp": "2021-03-01T00: 00:13Z",
    },
]

ACCOUNT_SCHEDULES = {
    "ACCRUE_INTEREST": {
        "id": "adda847e-602f-4d26-aa8c-ff36217d5fdd",
        "name": "0_CF4LL7NXC1R561TI9VZRS3FGS1JZPZXQ6_ACCRUE_INTEREST_536802",
        "display_name": "0_CF4LL7NXC1R561TI9VZRS3FGS1JZPZXQ6:ACCRUE_INTEREST",
        "status": "SCHEDULE_STATUS_ENABLED",
        "create_timestamp": "2021-09-07T19:40:26Z",
        "start_timestamp": "2021-05-20T09:00:00Z",
        "end_timestamp": None,
        "next_run_timestamp": "2021-05-21T00:00:00Z",
        "disabled_timestamp": None,
        "time_expression": "0 0 0 * * * *",
        "timezone": "UTC",
        "tags": ["PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f"],
        "group": {
            "group_id": "39be6e13-6b8a-4ad7-9624-fcc2079147f2",
            "group_order": 0,
        },
    },
    "PAYMENT_DUE": {
        "id": "c494445e-262d-4363-aa6e-f91a68b7306f",
        "name": "0_CF4LL7NXC1R561TI9VZRS3FGS1JZPZXQ6_PAYMENT_DUE_536802",
        "display_name": "0_CF4LL7NXC1R561TI9VZRS3FGS1JZPZXQ6:PAYMENT_DUE",
        "status": "SCHEDULE_STATUS_ENABLED",
        "create_timestamp": "2021-09-07T19:40:26Z",
        "start_timestamp": "2021-05-20T09:00:00Z",
        "end_timestamp": None,
        "next_run_timestamp": "2021-07-14T00:00:01Z",
        "disabled_timestamp": None,
        "time_expression": "1 0 0 14 7 * *",
        "timezone": "UTC",
        "tags": ["PAUSED_PAYMENT_DUE_5b0524b1-6e2d-4244-8a56-c35ca2ef2f82"],
        "group": {
            "group_id": "39be6e13-6b8a-4ad7-9624-fcc2079147f2",
            "group_order": 1,
        },
    },
}

TAGLESS_SCHEDULES = {
    "ACCRUE_INTEREST": {
        "id": "adda847e-602f-4d26-aa8c-ff36217d5fdd",
        "name": "0_CF4LL7NXC1R561TI9VZRS3FGS1JZPZXQ6_ACCRUE_INTEREST_536802",
        "display_name": "0_CF4LL7NXC1R561TI9VZRS3FGS1JZPZXQ6:ACCRUE_INTEREST",
        "status": "SCHEDULE_STATUS_ENABLED",
        "create_timestamp": "2021-09-07T19:40:26Z",
        "start_timestamp": "2021-05-20T09:00:00Z",
        "end_timestamp": None,
        "next_run_timestamp": "2021-05-21T00:00:00Z",
        "disabled_timestamp": None,
        "time_expression": "0 0 0 * * * *",
        "timezone": "UTC",
        "tags": [],
        "group": {
            "group_id": "39be6e13-6b8a-4ad7-9624-fcc2079147f2",
            "group_order": 0,
        },
    }
}

DISABLED_SCHEDULE = {
    "cd522090-bad8-418c-9cf1-bfdcf7bf55ed": {
        "id": "cd522090-bad8-418c-9cf1-bfdcf7bf55ed",
        "name": "1c3404fe-c63b-6e92-7cbc-dbccb6ef537b_CHECK_LATE_REPAYMENT_FEE_40479",
        "display_name": "1c3404fe-c63b-6e92-7cbc-dbccb6ef537b:CHECK_LATE_REPAYMENT_FEE",
        "status": "SCHEDULE_STATUS_DISABLED",
        "create_timestamp": "2022-11-28T16:48:00.290719Z",
        "start_timestamp": "2020-01-05T00:00:00Z",
        "end_timestamp": None,
        "next_run_timestamp": None,
        "disabled_timestamp": "1970-01-01T00:00:01Z",
        "time_expression": "0 1 0 8 2 * *",
        "timezone": "UTC",
        "tags": ["PAUSED_CHECK_LATE_REPAYMENT_FEE_TAG_5e18f35d-ef68-42d0-bb11-74a10ac233a2"],
        "group": None,
        "skip_start_timestamp": None,
        "skip_end_timestamp": None,
    }
}

MULTI_TAG_SCHEDULES = {
    "ACCRUE_INTEREST": {
        "id": "adda847e-602f-4d26-aa8c-ff36217d5fdd",
        "name": "0_CF4LL7NXC1R561TI9VZRS3FGS1JZPZXQ6_ACCRUE_INTEREST_536802",
        "display_name": "0_CF4LL7NXC1R561TI9VZRS3FGS1JZPZXQ6:ACCRUE_INTEREST",
        "status": "SCHEDULE_STATUS_ENABLED",
        "create_timestamp": "2021-09-07T19:40:26Z",
        "start_timestamp": "2021-05-20T09:00:00Z",
        "end_timestamp": None,
        "next_run_timestamp": "2021-05-21T00:00:00Z",
        "disabled_timestamp": None,
        "time_expression": "0 0 0 * * * *",
        "timezone": "UTC",
        "tags": ["PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f", "TAG_2"],
        "group": {
            "group_id": "39be6e13-6b8a-4ad7-9624-fcc2079147f2",
            "group_order": 0,
        },
    }
}

SCHEDULE_TAG = {
    "PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f": {
        "id": "PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f",
        "description": "Paused interest accrual",
        "sends_scheduled_operation_reports": False,
        "schedule_status_override": "ACCOUNT_SCHEDULE_TAG_SCHEDULE_STATUS_OVERRIDE_TO_ENABLED",
        "schedule_status_override_start_timestamp": "1970-01-01T00:00:00Z",
        "schedule_status_override_end_timestamp": "9999-12-31T23:59:59Z",
        "test_pause_at_timestamp": "1970-01-01T00:00:00.000000Z",
    }
}

EXAMPLE_OPERATION_EVENT = load_file_contents(
    "inception_sdk/test_framework/endtoend/test/unit/input/operation_event.json"
)


# For simplicity this schedule will be used for both plan and account schedule tests.
# Currently the keys do not differ, if this changes in the future updates may be needed.
SCHEDULE = {
    "cfdbbb01-bf72-4fe6-910e-02718bf28e20": {
        "id": "cfdbbb01-bf72-4fe6-910e-02718bf28e20",
        "name": "f96717f2-1202-412b-bcf8-b7462985f9e7",
        "display_name": "7c99e8b4-a3e8-ef9e-cfe9-56d25e0471f3:ACCRUE_OFFSET_INTEREST",
        "status": "SCHEDULE_STATUS_DISABLED",
        "create_timestamp": "2023-03-01T14:48:14.976044Z",
        "start_timestamp": "2023-03-01T01:00:00Z",
        "end_timestamp": "2023-03-02T01:00:00Z",
        "next_run_timestamp": None,
        "disabled_timestamp": "2023-03-01T01:00:00Z",
        "time_expression": "0 0 0 * * * *",
        "timezone": "UTC",
        "tags": [],
        "group": None,
        "skip_start_timestamp": None,
        "skip_end_timestamp": None,
    }
}


@patch.object(endtoend.core_api_helper, "batch_get_schedules")
@patch.object(endtoend.core_api_helper, "get_account_schedule_assocs")
class AccountScheduleFetchingTest(TestCase):
    NORMAL_ASSOCS = [
        {
            "id": "f03bd709-17c3-4eba-9310-9964c0c64d1b",
            "account_id": "my_account_id",
            "schedule_id": "f03bd709-17c3-4eba-9310-9964c0c64d1b",
            "create_timestamp": "2022-03-08T10:33:59.156068Z",
        },
        {
            "id": "bfe2a0f8-1642-46b9-aba4-9c3068a00834",
            "account_id": "my_account_id",
            "schedule_id": "bfe2a0f8-1642-46b9-aba4-9c3068a00834",
            "create_timestamp": "2022-03-08T10:33:59.156118Z",
        },
    ]

    # For brevity's sake these return values have irrelevant fields stripped out
    ONE_ENABLED_ONE_DISABLED_SCHEDULES = {
        "bfe2a0f8-1642-46b9-aba4-9c3068a00834": {
            "id": "bfe2a0f8-1642-46b9-aba4-9c3068a00834",
            "name": "my_account_id_APPLY_MONTHLY_FEES_2032809",
            "display_name": "my_account_id:APPLY_MONTHLY_FEES",
            "status": "SCHEDULE_STATUS_ENABLED",
            "create_timestamp": "2022-03-08T09:24:48.886781Z",
        },
        "f03bd709-17c3-4eba-9310-9964c0c64d1b": {
            "id": "f03bd709-17c3-4eba-9310-9964c0c64d1b",
            "name": "my_account_id_APPLY_ACCRUED_INTEREST_2032809",
            "display_name": "my_account_id:APPLY_ACCRUED_INTEREST",
            "status": "SCHEDULE_STATUS_DISABLED",
            "create_timestamp": "2022-03-08T09:24:48.886781Z",
        },
    }

    SCHEDULES_WITH_SAME_DISPLAYNAME = {
        "bfe2a0f8-1642-46b9-aba4-9c3068a00834": {
            "id": "bfe2a0f8-1642-46b9-aba4-9c3068a00834",
            "name": "my_account_id_APPLY_MONTHLY_FEES_2032809",
            "display_name": "my_account_id:APPLY_MONTHLY_FEES",
            "status": "SCHEDULE_STATUS_ENABLED",
            "create_timestamp": "2022-03-08T09:24:48.886781Z",
        },
        "f03bd709-17c3-4eba-9310-9964c0c64d1b": {
            "id": "f03bd709-17c3-4eba-9310-9964c0c64d1b",
            "name": "my_account_id_APPLY_MONTHLY_FEES_2032809",
            "display_name": "my_account_id:APPLY_MONTHLY_FEES",
            "status": "SCHEDULE_STATUS_ENABLED",
            "create_timestamp": "2022-04-08T09:24:48.886781Z",
        },
        "aae2a0f9-1642-46b9-dba7-9c3068a58966": {
            "id": "bfe2a0f8-1642-46b9-aba4-9c3068a00834",
            "name": "my_account_id_APPLY_MONTHLY_FEES_2032809",
            "display_name": "my_account_id:APPLY_MONTHLY_FEES",
            "status": "SCHEDULE_STATUS_ENABLED",
            "create_timestamp": "2022-02-10T11:30:48.422460Z",
        },
    }

    def test_get_account_schedules_with_no_assocs(
        self, get_account_schedule_assocs, batch_get_schedules
    ):
        get_account_schedule_assocs.return_value = []
        batch_get_schedules.return_value = {}
        self.assertDictEqual(
            endtoend.schedule_helper.get_account_schedules(account_id="my_account_id"),
            {},
        )

    def test_get_account_schedules_with_no_schedules(
        self, get_account_schedule_assocs, batch_get_schedules
    ):
        get_account_schedule_assocs.return_value = AccountScheduleFetchingTest.NORMAL_ASSOCS
        batch_get_schedules.return_value = {}
        self.assertDictEqual(
            endtoend.schedule_helper.get_account_schedules(account_id="my_account_id"),
            {},
        )

    def test_get_account_schedules_filters_disabled_schedules_by_default(
        self, get_account_schedule_assocs, batch_get_schedules
    ):
        get_account_schedule_assocs.return_value = AccountScheduleFetchingTest.NORMAL_ASSOCS
        batch_get_schedules.return_value = (
            AccountScheduleFetchingTest.ONE_ENABLED_ONE_DISABLED_SCHEDULES
        )
        self.assertDictEqual(
            endtoend.schedule_helper.get_account_schedules(account_id="my_account_id"),
            {
                "APPLY_MONTHLY_FEES": {
                    "id": "bfe2a0f8-1642-46b9-aba4-9c3068a00834",
                    "name": "my_account_id_APPLY_MONTHLY_FEES_2032809",
                    "display_name": "my_account_id:APPLY_MONTHLY_FEES",
                    "status": "SCHEDULE_STATUS_ENABLED",
                    "create_timestamp": "2022-03-08T09:24:48.886781Z",
                }
            },
        )

    def test_get_account_schedules_returns_latest_schedule_with_same_name(
        self, get_account_schedule_assocs, batch_get_schedules
    ):
        get_account_schedule_assocs.return_value = AccountScheduleFetchingTest.NORMAL_ASSOCS
        batch_get_schedules.return_value = (
            AccountScheduleFetchingTest.SCHEDULES_WITH_SAME_DISPLAYNAME
        )
        self.assertDictEqual(
            endtoend.schedule_helper.get_account_schedules(account_id="my_account_id"),
            {
                "APPLY_MONTHLY_FEES": {
                    "id": "f03bd709-17c3-4eba-9310-9964c0c64d1b",
                    "name": "my_account_id_APPLY_MONTHLY_FEES_2032809",
                    "display_name": "my_account_id:APPLY_MONTHLY_FEES",
                    "status": "SCHEDULE_STATUS_ENABLED",
                    "create_timestamp": "2022-04-08T09:24:48.886781Z",
                }
            },
        )

    def test_get_account_schedules_filters_no_schedules_with_empty_list_of_statuses(
        self, get_account_schedule_assocs, batch_get_schedules
    ):
        get_account_schedule_assocs.return_value = AccountScheduleFetchingTest.NORMAL_ASSOCS
        batch_get_schedules.return_value = (
            AccountScheduleFetchingTest.ONE_ENABLED_ONE_DISABLED_SCHEDULES
        )
        self.assertDictEqual(
            endtoend.schedule_helper.get_account_schedules(
                account_id="my_account_id", statuses_to_exclude=[]
            ),
            {
                "APPLY_MONTHLY_FEES": {
                    "id": "bfe2a0f8-1642-46b9-aba4-9c3068a00834",
                    "name": "my_account_id_APPLY_MONTHLY_FEES_2032809",
                    "display_name": "my_account_id:APPLY_MONTHLY_FEES",
                    "status": "SCHEDULE_STATUS_ENABLED",
                    "create_timestamp": "2022-03-08T09:24:48.886781Z",
                },
                "APPLY_ACCRUED_INTEREST": {
                    "id": "f03bd709-17c3-4eba-9310-9964c0c64d1b",
                    "name": "my_account_id_APPLY_ACCRUED_INTEREST_2032809",
                    "display_name": "my_account_id:APPLY_ACCRUED_INTEREST",
                    "status": "SCHEDULE_STATUS_DISABLED",
                    "create_timestamp": "2022-03-08T09:24:48.886781Z",
                },
            },
        )

    def test_get_account_schedules_filters_schedules_based_on_list_of_statuses(
        self, get_account_schedule_assocs, batch_get_schedules
    ):
        get_account_schedule_assocs.return_value = AccountScheduleFetchingTest.NORMAL_ASSOCS
        batch_get_schedules.return_value = (
            AccountScheduleFetchingTest.ONE_ENABLED_ONE_DISABLED_SCHEDULES
        )
        self.assertDictEqual(
            endtoend.schedule_helper.get_account_schedules(
                account_id="my_account_id",
                statuses_to_exclude=["SCHEDULE_STATUS_ENABLED", "SCHEDULE_STATUS_DISABLED"],
            ),
            {},
        )


@patch.object(endtoend.core_api_helper, "batch_get_schedules")
@patch.object(endtoend.core_api_helper, "get_plan_schedules")
class PlanScheduleFetchingTest(TestCase):
    PLAN_SCHEDULES = [
        {
            "id": "cfdbbb01-bf72-4fe6-910e-02718bf28e20",
            "plan_id": "7c99e8b4-a3e8-ef9e-cfe9-56d25e0471f3",
            "name": "ACCRUE_OFFSET_INTEREST",
            "group_name": "",
            "time_expression": "0 0 0 * * * *",
            "schedule_tag_ids": [],
        }
    ]

    def test_get_plan_schedules_with_no_schedules(
        self,
        get_plan_schedules,
        batch_get_schedules,
    ):
        get_plan_schedules.return_value = []

        self.assertDictEqual(
            endtoend.schedule_helper.get_plan_schedules(plan_id="my_plan_id"),
            {},
        )

    def test_get_plan_schedules_with_schedules(self, get_plan_schedules, batch_get_schedules):
        get_plan_schedules.return_value = self.PLAN_SCHEDULES
        batch_get_schedules.return_value = SCHEDULE
        self.assertDictEqual(
            endtoend.schedule_helper.get_plan_schedules(
                "7c99e8b4-a3e8-ef9e-cfe9-56d25e0471f3", statuses_to_exclude=[]
            ),
            {
                "ACCRUE_OFFSET_INTEREST": {
                    "id": "cfdbbb01-bf72-4fe6-910e-02718bf28e20",
                    "name": "f96717f2-1202-412b-bcf8-b7462985f9e7",
                    "display_name": "7c99e8b4-a3e8-ef9e-cfe9-56d25e0471f3:ACCRUE_OFFSET_INTEREST",
                    "status": "SCHEDULE_STATUS_DISABLED",
                    "create_timestamp": "2023-03-01T14:48:14.976044Z",
                    "start_timestamp": "2023-03-01T01:00:00Z",
                    "end_timestamp": "2023-03-02T01:00:00Z",
                    "next_run_timestamp": None,
                    "disabled_timestamp": "2023-03-01T01:00:00Z",
                    "time_expression": "0 0 0 * * * *",
                    "timezone": "UTC",
                    "tags": [],
                    "group": None,
                    "skip_start_timestamp": None,
                    "skip_end_timestamp": None,
                }
            },
        )


class GetSchedulesForJobTest(TestCase):
    pass


class TriggerNextScheduleJobValidation(TestCase):
    @patch.object(schedule_helper, "get_account_schedules")
    def test_trigger_next_schedule_job_raises_if_schedule_name_missing(
        self, mock_get_account_schedules: Mock
    ):
        mock_get_account_schedules.return_value = {"other_schedule": {}}
        with self.assertRaises(KeyError) as ctx:
            schedule_helper.trigger_next_schedule_job(
                schedule_name="dummy",
                resource_id="account_id",
                resource_type=schedule_helper.ResourceType.ACCOUNT,
            )

        self.assertEqual(
            ctx.exception.args[0],
            "No enabled schedule_name='dummy' for resource_type.value='ACCOUNT' "
            "resource_id='account_id'",
        )

    @patch.object(schedule_helper, "get_account_schedules")
    def test_trigger_next_schedule_job_raises_on_tag_less_schedule(
        self, mock_get_account_schedules: Mock
    ):
        mock_get_account_schedules.return_value = TAGLESS_SCHEDULES
        with self.assertRaises(ValueError) as ctx:
            schedule_helper.trigger_next_schedule_job(
                schedule_name="ACCRUE_INTEREST",
                resource_id="account_id",
                resource_type=schedule_helper.ResourceType.ACCOUNT,
            )

        self.assertEqual(
            ctx.exception.args[0],
            "No tags found on schedule_name='ACCRUE_INTEREST' schedule_id='"
            "adda847e-602f-4d26-aa8c-ff36217d5fdd' for resource_type.value='ACCOUNT' "
            "resource_id='account_id'",
        )

    @patch.object(schedule_helper, "get_account_schedules", Mock(return_value=DISABLED_SCHEDULE))
    @patch.object(
        schedule_helper.endtoend.core_api_helper,
        "batch_get_account_schedule_tags",
        Mock(return_value=SCHEDULE_TAG),
    )
    def test_trigger_next_schedule_job_raises_for_schedule_with_no_next_run_timestamp(
        self,
    ):
        with self.assertRaises(ValueError) as ctx:
            schedule_helper.trigger_next_schedule_job(
                schedule_name="cd522090-bad8-418c-9cf1-bfdcf7bf55ed",
                resource_id="account_id",
                resource_type=schedule_helper.ResourceType.ACCOUNT,
                effective_date=datetime(2021, 5, 21, 1, tzinfo=timezone.utc),
            )

        self.assertEqual(
            ctx.exception.args[0],
            "No next_run_timestamp found on schedule_id='cd522090-bad8-418c-9cf1-bfdcf7bf55ed'",
        )

    @patch.object(schedule_helper, "get_account_schedules", Mock(return_value=ACCOUNT_SCHEDULES))
    @patch.object(
        schedule_helper.endtoend.core_api_helper,
        "batch_get_account_schedule_tags",
        Mock(return_value=SCHEDULE_TAG),
    )
    def test_trigger_next_schedule_job_raises_for_effective_date_mismatch(self):
        with self.assertRaises(ValueError) as ctx:
            schedule_helper.trigger_next_schedule_job(
                schedule_name="ACCRUE_INTEREST",
                resource_id="account_id",
                resource_type=schedule_helper.ResourceType.ACCOUNT,
                effective_date=datetime(2021, 5, 21, 1, tzinfo=timezone.utc),
            )

        self.assertEqual(
            ctx.exception.args[0],
            "effective_date=datetime.datetime(2021, 5, 21, 1, 0, tzinfo=datetime.timezone.utc) "
            "does not match the actual next_run_time=datetime.datetime(2021, 5, 21, 0, 0,"
            " tzinfo=datetime.timezone.utc)",
        )


@patch.object(schedule_helper.endtoend.schedule_helper, "fast_forward_tag")
@patch.object(schedule_helper.endtoend.schedule_helper, "update_tag_test_pause_at_timestamp")
@patch.object(schedule_helper, "get_account_schedules", Mock(return_value=ACCOUNT_SCHEDULES))
@patch.object(
    schedule_helper.endtoend.core_api_helper,
    "batch_get_account_schedule_tags",
    Mock(return_value=SCHEDULE_TAG),
)
@patch.object(schedule_helper.endtoend.schedule_helper, "wait_for_schedule_operation_events")
@patch.object(schedule_helper.endtoend.helper, "retry_call")
@patch.object(schedule_helper.time, "sleep")
@patch.object(schedule_helper.endtoend, "testhandle")
class TriggerNextScheduleJob(TestCase):
    def test_pause_at_timestamp_set_to_1s_after_next_run_if_in_the_past(
        self,
        mock_testhandle: MagicMock,
        mock_sleep: MagicMock,
        mock_retry_call: MagicMock,
        mock_wait_for_schedule_operation_events: MagicMock,
        mock_update_tag_test_pause_at_timestamp: MagicMock,
        mock_fast_forward_tag: MagicMock,
    ):
        schedule_helper.trigger_next_schedule_job(
            schedule_name="ACCRUE_INTEREST",
            resource_id="account_id",
            resource_type=schedule_helper.ResourceType.ACCOUNT,
            effective_date=datetime(2021, 5, 21, tzinfo=timezone.utc),
        )
        mock_update_tag_test_pause_at_timestamp.assert_called_once_with(
            schedule_tag_id="PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f",
            # next run_timestamp is 2021-05_21T00:00:00_00:00
            test_pause_at_timestamp=datetime(2021, 5, 21, 0, 0, 1, tzinfo=timezone.utc),
        )
        mock_fast_forward_tag.assert_not_called()

    @freezegun.freeze_time("2020-01-01")
    def test_tag_fast_forwarded_if_next_run_in_future(
        self,
        mock_testhandle: MagicMock,
        mock_sleep: MagicMock,
        mock_retry_call: MagicMock,
        mock_wait_for_schedule_operation_events: MagicMock,
        mock_update_tag_test_pause_at_timestamp: MagicMock,
        mock_fast_forward_tag: MagicMock,
    ):
        schedule_helper.trigger_next_schedule_job(
            schedule_name="ACCRUE_INTEREST",
            resource_id="account_id",
            resource_type=schedule_helper.ResourceType.ACCOUNT,
            effective_date=datetime(2021, 5, 21, tzinfo=timezone.utc),
        )
        mock_update_tag_test_pause_at_timestamp.assert_not_called()
        mock_fast_forward_tag.assert_called_once_with(
            paused_tag_id="PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f",
            # next run_timestamp is 2021-05_21T00:00:00_00:00
            fast_forward_to_date=datetime(2021, 5, 21, 0, 0, 1, tzinfo=timezone.utc),
        )

    @patch.object(
        schedule_helper, "get_account_schedules", MagicMock(return_value=MULTI_TAG_SCHEDULES)
    )
    def test_first_of_multiple_schedule_tags_is_updated(
        self,
        mock_testhandle: MagicMock,
        mock_sleep: MagicMock,
        mock_retry_call: MagicMock,
        mock_wait_for_schedule_operation_events: MagicMock,
        mock_update_tag_test_pause_at_timestamp: MagicMock,
        mock_fast_forward_tag: MagicMock,
    ):
        schedule_helper.trigger_next_schedule_job(
            schedule_name="ACCRUE_INTEREST",
            resource_id="account_id",
            resource_type=schedule_helper.ResourceType.ACCOUNT,
            effective_date=datetime(2021, 5, 21, tzinfo=timezone.utc),
        )
        mock_update_tag_test_pause_at_timestamp.assert_called_once_with(
            schedule_tag_id="PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f",
            # next run_timestamp is 2021-05_21T00:00:00_00:00
            test_pause_at_timestamp=datetime(2021, 5, 21, 0, 0, 1, tzinfo=timezone.utc),
        )
        mock_fast_forward_tag.assert_not_called()

    @patch.object(
        schedule_helper, "get_plan_schedules", MagicMock(return_value=MULTI_TAG_SCHEDULES)
    )
    def test_handle_plan_schedules(
        self,
        mock_testhandle: MagicMock,
        mock_sleep: MagicMock,
        mock_retry_call: MagicMock,
        mock_wait_for_schedule_operation_events: MagicMock,
        mock_update_tag_test_pause_at_timestamp: MagicMock,
        mock_fast_forward_tag: MagicMock,
    ):
        schedule_helper.trigger_next_schedule_job(
            schedule_name="ACCRUE_INTEREST",
            resource_id="plan_id",
            resource_type=schedule_helper.ResourceType.PLAN,
            effective_date=datetime(2021, 5, 21, tzinfo=timezone.utc),
        )
        mock_update_tag_test_pause_at_timestamp.assert_called_once_with(
            schedule_tag_id="PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f",
            # next run_timestamp is 2021-05_21T00:00:00_00:00
            test_pause_at_timestamp=datetime(2021, 5, 21, 0, 0, 1, tzinfo=timezone.utc),
        )
        mock_fast_forward_tag.assert_not_called()


class WaitForScheduleJobTest(TestCase):
    @patch.object(endtoend.schedule_helper.time, "sleep")
    @patch.object(endtoend.helper, "retry_call")
    @patch.object(schedule_helper, "wait_for_schedule_operation_events")
    @patch.object(endtoend, "testhandle")
    def test_wait_for_operation_event_with_tag_id_and_kafka_enabled(
        self,
        mock_testhandle: MagicMock,
        mock_wait_for_schedule_operation_events: MagicMock,
        mock_sleep: MagicMock,
        mock_retry_call: MagicMock,
    ):
        type(mock_testhandle).use_kafka = PropertyMock(return_value=True)

        schedule_helper.wait_for_schedule_job(
            schedule_tag_id="a_tag_id",
            expected_run_time=sentinel.expected_runtime,
        )

        mock_wait_for_schedule_operation_events.assert_called_once_with(
            tag_names=["a_tag_id"],
            wait_for_timestamp=sentinel.expected_runtime,
            inter_message_timeout=90,
            matched_message_timeout=90,
        )
        mock_sleep.assert_not_called()
        mock_retry_call.assert_not_called()

    @patch.object(endtoend, "testhandle")
    def test_raise_if_kafka_disabled_and_no_schedule_id_provided(
        self,
        mock_testhandle: MagicMock,
    ):
        type(mock_testhandle).use_kafka = PropertyMock(return_value=False)

        with self.assertRaisesRegex(ValueError, r"Not using kafka"):
            schedule_helper.wait_for_schedule_job(schedule_tag_id="a_tag_id")

    @patch.object(endtoend.schedule_helper.time, "sleep")
    @patch.object(endtoend.helper, "retry_call")
    @patch.object(schedule_helper, "wait_for_schedule_operation_events")
    @patch.object(endtoend, "testhandle")
    def test_poll_for_jobs_if_kafka_disabled_and_schedule_id_provided(
        self,
        mock_testhandle: MagicMock,
        mock_wait_for_schedule_operation_events: MagicMock,
        mock_retry_call: MagicMock,
        mock_sleep: MagicMock,
    ):
        type(mock_testhandle).use_kafka = PropertyMock(return_value=False)

        schedule_helper.wait_for_schedule_job(
            schedule_id="a_schedule_id",
            expected_run_time=sentinel.expected_runtime,
            initial_wait=0,
        )

        mock_wait_for_schedule_operation_events.assert_not_called()
        mock_sleep.assert_not_called()
        mock_retry_call.assert_called_once_with(
            func=schedule_helper._check_jobs_status,
            f_args=[
                "a_schedule_id",
                sentinel.expected_runtime,
                ["JOB_STATUS_SUCCEEDED", "JOB_STATUS_FAILED"],
            ],
            expected_result=True,
            back_off=2,
            max_retries=7,
        )

    @patch.object(endtoend.schedule_helper.time, "sleep")
    @patch.object(endtoend.helper, "retry_call")
    @patch.object(schedule_helper, "wait_for_schedule_operation_events")
    @patch.object(endtoend, "testhandle")
    def test_poll_for_jobs_with_sleep_if_kafka_disabled_and_schedule_id_provided(
        self,
        mock_testhandle: MagicMock,
        mock_wait_for_schedule_operation_events: MagicMock,
        mock_retry_call: MagicMock,
        mock_sleep: MagicMock,
    ):
        type(mock_testhandle).use_kafka = PropertyMock(return_value=False)

        schedule_helper.wait_for_schedule_job(
            schedule_id="a_schedule_id",
            expected_run_time=sentinel.expected_runtime,
        )

        mock_wait_for_schedule_operation_events.assert_not_called()
        mock_sleep.assert_called_once_with(70)
        mock_retry_call.assert_called_once_with(
            func=schedule_helper._check_jobs_status,
            f_args=[
                "a_schedule_id",
                sentinel.expected_runtime,
                ["JOB_STATUS_SUCCEEDED", "JOB_STATUS_FAILED"],
            ],
            expected_result=True,
            back_off=2,
            max_retries=7,
        )


class WaitForScheduleOperationEvents(TestCase):
    @patch.dict(
        "inception_sdk.test_framework.endtoend.testhandle.kafka_consumers",
        {
            schedule_helper.SCHEDULER_OPERATION_EVENTS_TOPIC: MockConsumer(
                [MockMessage(value=EXAMPLE_OPERATION_EVENT)]
            )
        },
    )
    def test_wait_for_operation_event_with_match(self):
        result = schedule_helper.wait_for_schedule_operation_events(
            tag_names=["tag_id"],
        )
        self.assertIsNone(result)

    @patch.dict(
        "inception_sdk.test_framework.endtoend.testhandle.kafka_consumers",
        {
            schedule_helper.SCHEDULER_OPERATION_EVENTS_TOPIC: MockConsumer(
                [MockMessage(value=EXAMPLE_OPERATION_EVENT)]
            )
        },
    )
    @patch.object(
        schedule_helper,
        "wait_for_messages",
        Mock(return_value={"tag_id": None}),
    )
    def test_wait_for_operation_event_with_no_match(self):
        with self.assertRaises(Exception) as e:
            schedule_helper.wait_for_schedule_operation_events(
                tag_names=["tag_id"],
            )
        self.assertEqual(
            e.exception.args[0],
            "Failed to retrieve 1 operation events" " for tags: tag_id",
        )


class ScheduleHelperTest(TestCase):
    @patch.object(schedule_helper, "wait_for_schedule_job")
    @patch.object(schedule_helper, "trigger_next_schedule_job")
    def test_trigger_next_schedule_job_and_wait(
        self, mock_trigger_next_schedule_job: MagicMock, mock_wait_for_schedule_job: MagicMock
    ):
        mock_trigger_next_schedule_job.return_value = (
            sentinel.tag_id,
            sentinel.schedule_id,
            sentinel.next_run_time,
        )

        schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name=sentinel.schedule_name,
            account_id=sentinel.account_id,
            plan_id=sentinel.plan_id,
            effective_date=sentinel.effective_date,
        )

        mock_trigger_next_schedule_job.assert_called_once_with(
            schedule_name=sentinel.schedule_name,
            resource_id=sentinel.account_id,
            resource_type=schedule_helper.ResourceType.ACCOUNT,
            effective_date=sentinel.effective_date,
        )
        mock_wait_for_schedule_job.assert_called_once_with(
            schedule_tag_id=sentinel.tag_id,
            schedule_id=sentinel.schedule_id,
            expected_run_time=sentinel.next_run_time,
        )

    def test_trigger_next_schedule_job_and_wait_with_no_account_or_plan_id(self):
        with self.assertRaises(ValueError) as ctx:
            schedule_helper.trigger_next_schedule_job_and_wait(schedule_name="dummy")

        self.assertEqual(
            ctx.exception.args[0],
            "Must specify an account_id or plan_id. Got plan_id=None and account_id=None",
        )

    @patch.object(endtoend.core_api_helper, "update_account_schedule_tag")
    def test_fast_forward_tag(self, mock_update_account_schedule_tag: MagicMock):
        endtoend.schedule_helper.fast_forward_tag(
            paused_tag_id="my_tag", fast_forward_to_date=datetime(2020, 1, 5)
        )
        mock_update_account_schedule_tag.assert_called_once_with(
            account_schedule_tag_id="my_tag",
            schedule_status_override=AccountScheduleTagStatusOverride.FAST_FORWARD.value,
            schedule_status_override_end_timestamp="2020-01-05T00:00:00+00:00",
        )

    @patch.object(endtoend.core_api_helper, "update_account_schedule_tag")
    def test_update_tag_test_pause_at_timestamp(self, mock_update_account_schedule_tag: MagicMock):
        endtoend.schedule_helper.update_tag_test_pause_at_timestamp(
            schedule_tag_id="my_tag", test_pause_at_timestamp=datetime(2020, 1, 5)
        )
        mock_update_account_schedule_tag.assert_called_once_with(
            account_schedule_tag_id="my_tag",
            test_pause_at_timestamp="2020-01-05T00:00:00+00:00",
            schedule_status_override=AccountScheduleTagStatusOverride.ENABLED,
            schedule_status_override_start_timestamp=SCHEDULE_STATUS_OVERRIDE_START_TIMESTAMP,
            schedule_status_override_end_timestamp=SCHEDULE_STATUS_OVERRIDE_END_TIMESTAMP,
        )

    @patch.object(endtoend.core_api_helper, "get_jobs")
    def test_wait_scheduled_jobs_passed_all_dates_empty(
        self,
        get_jobs,
    ):
        # This will test for empty response, should fail since there are no valid pending jobs
        # no effective date so all will be considered
        get_jobs.side_effect = [RESPONSE_EXPECTED_EMPTY]
        result = endtoend.schedule_helper._check_jobs_status("8c620041-00a1-4a0e-8940-1714bc1fdfc2")
        self.assertEqual(result, False)

    @patch.object(endtoend.core_api_helper, "get_jobs")
    def test_wait_scheduled_jobs_passed_all_dates(self, get_jobs):
        # This will test that it will return true if all jobs are finished.
        # It should return True no effective date so all will be considered.

        get_jobs.side_effect = [RESPONSE_EXPECTED_ALL]
        result = endtoend.schedule_helper._check_jobs_status("8c620041-00a1-4a0e-8940-1714bc1fdfc2")
        # Should succeed
        self.assertEqual(result, True)

    @patch.object(endtoend.core_api_helper, "get_jobs")
    def test_wait_scheduled_jobs_specific_day(self, get_jobs):
        # This will test for effective date scenario, where the effective date
        # given is down to the day. Since the time stamp returned by vault
        # is down to the second there will be no date matching this day.
        # There are no valid jobs on that date so it should fail.
        get_jobs.side_effect = [RESPONSE_UNEXPECTED_ALL]
        result = endtoend.schedule_helper._check_jobs_status(
            "8c620041-00a1-4a0e-8940-1714bc1fdfc2",
            datetime(year=2021, month=3, day=1, tzinfo=timezone.utc),
        )
        self.assertEqual(result, False)

    @patch.object(endtoend.core_api_helper, "get_jobs")
    def test_wait_scheduled_jobs_specific_second(self, get_jobs):
        # This will test for effective date scenario where the effective date given is down to the
        # second where in there are no valid jobs on that date so it should fail
        get_jobs.side_effect = [RESPONSE_UNEXPECTED_ALL]
        result = endtoend.schedule_helper._check_jobs_status(
            "8c620041-00a1-4a0e-8940-1714bc1fdfc2",
            datetime(
                year=2021,
                month=3,
                day=1,
                hour=1,
                minute=1,
                second=17,
                tzinfo=timezone.utc,
            ),
        )
        self.assertEqual(result, False)

    @patch.object(endtoend.core_api_helper, "get_jobs")
    def test_wait_scheduled_jobs_pending_all_date(self, get_jobs):
        # This will test that scenario where there are still pending jobs for all dates
        get_jobs.side_effect = [RESPONSE_UNEXPECTED_ALL]

        result = endtoend.schedule_helper._check_jobs_status("8c620041-00a1-4a0e-8940-1714bc1fdfc2")
        self.assertEqual(result, False)

    @patch.object(endtoend.core_api_helper, "get_jobs")
    def test_wait_scheduled_jobs_mix_all_date(self, get_jobs):
        # This will test that scenario where there is a mix of pending and finish jobs for all dates
        get_jobs.side_effect = [RESPONSE_MIX]

        result = endtoend.schedule_helper._check_jobs_status("8c620041-00a1-4a0e-8940-1714bc1fdfc2")
        self.assertEqual(result, False)

    @patch.object(endtoend.core_api_helper, "get_jobs")
    def test_wait_scheduled_jobs_pending_specific_date(self, get_jobs):
        # This will test for effective date scenario where in there is still a pending job
        get_jobs.side_effect = [RESPONSE_UNEXPECTED_ALL]

        result = endtoend.schedule_helper._check_jobs_status(
            "8c620041-00a1-4a0e-8940-1714bc1fdfc2",
            datetime(
                year=2021,
                month=3,
                day=1,
                hour=1,
                minute=1,
                second=17,
                tzinfo=timezone.utc,
            ),
        )
        self.assertEqual(result, False)

    @patch.object(endtoend.core_api_helper, "get_jobs")
    def test_wait_scheduled_jobs_passed_specific_date(self, get_jobs):
        # This will test for effective date scenario where in there are no pending job
        get_jobs.side_effect = [RESPONSE_EXPECTED_ALL]

        result = endtoend.schedule_helper._check_jobs_status(
            "8c620041-00a1-4a0e-8940-1714bc1fdfc2",
            datetime(
                year=2021,
                month=3,
                day=2,
                hour=23,
                minute=59,
                second=59,
                tzinfo=timezone.utc,
            ),
        )
        self.assertEqual(result, True)

    @patch.object(schedule_helper.log, "info")
    @patch.object(endtoend.core_api_helper, "update_account_schedule_tag")
    def test_skip_scheduled_jobs_between_dates(
        self,
        mock_update_account_schedule_tag: Mock,
        mock_log_info: Mock,
    ):
        schedule_tag_id = "ACCRUE_0"
        start_skip_date = datetime(2020, 5, 27, 10, 0, 0, tzinfo=timezone.utc)
        end_skip_date = datetime(2020, 5, 30, 10, 0, 0, tzinfo=timezone.utc)

        schedule_helper.skip_scheduled_jobs_between_dates(
            schedule_tag_id=schedule_tag_id,
            skip_start_date=start_skip_date,
            skip_end_date=end_skip_date,
        )
        mock_update_account_schedule_tag.assert_called_once_with(
            account_schedule_tag_id="ACCRUE_0",
            schedule_status_override_start_timestamp=start_skip_date.isoformat(),
            schedule_status_override_end_timestamp=end_skip_date.isoformat(),
            schedule_status_override=AccountScheduleTagStatusOverride.SKIPPED,
            test_pause_at_timestamp=end_skip_date.isoformat(),
        )
        mock_log_info.assert_has_calls(
            [call("Skipping ACCRUE_0 from 2020-05-27 10:00:00+00:00 to 2020-05-30 10:00:00+00:00")]
        )

    @patch.object(schedule_helper, "get_plan_schedules")
    @patch.object(schedule_helper, "skip_scheduled_jobs_between_dates")
    @patch.object(schedule_helper, "wait_for_schedule_job")
    def test_skip_plan_scheduled_jobs_and_wait(
        self,
        mock_wait_for_schedule_jobs: MagicMock,
        mock_skip_scheduled_jobs_between_dates: MagicMock,
        mock_get_account_schedules: MagicMock,
    ):
        schedule_name = "ACCRUE"
        start_skip_date = datetime(2020, 5, 27, tzinfo=timezone.utc)
        end_skip_date = datetime(2020, 5, 30, tzinfo=timezone.utc)

        mock_get_account_schedules.return_value = {
            schedule_name: {"tags": ["ACCRUE_TAG"], "id": "ACCRUE_ID"}
        }

        endtoend.schedule_helper.skip_scheduled_jobs_and_wait(
            schedule_name=schedule_name,
            skip_start_date=start_skip_date,
            skip_end_date=end_skip_date,
            resource_id="my_account_id",
            resource_type=schedule_helper.ResourceType.PLAN,
        )

        mock_skip_scheduled_jobs_between_dates.assert_called_once_with(
            schedule_tag_id="ACCRUE_TAG",
            skip_start_date=start_skip_date,
            skip_end_date=end_skip_date,
        )
        mock_wait_for_schedule_jobs.assert_called_once_with(
            schedule_tag_id="ACCRUE_TAG",
            schedule_id="ACCRUE_ID",
            job_statuses=["JOB_STATUS_SKIPPED"],
            initial_wait=0,
            expected_run_time=end_skip_date,
        )

    @patch.object(schedule_helper, "get_account_schedules")
    @patch.object(schedule_helper, "skip_scheduled_jobs_between_dates")
    @patch.object(schedule_helper, "wait_for_schedule_job")
    def test_skip_account_scheduled_jobs_and_wait(
        self,
        mock_wait_for_schedule_jobs: MagicMock,
        mock_skip_scheduled_jobs_between_dates: MagicMock,
        mock_get_account_schedules: MagicMock,
    ):
        schedule_name = "ACCRUE"
        start_skip_date = datetime(2020, 5, 27, tzinfo=timezone.utc)
        end_skip_date = datetime(2020, 5, 30, tzinfo=timezone.utc)

        mock_get_account_schedules.return_value = {
            schedule_name: {"tags": ["ACCRUE_TAG"], "id": "ACCRUE_ID"}
        }

        endtoend.schedule_helper.skip_scheduled_jobs_and_wait(
            schedule_name=schedule_name,
            skip_start_date=start_skip_date,
            skip_end_date=end_skip_date,
            resource_id="my_account_id",
            resource_type=schedule_helper.ResourceType.ACCOUNT,
        )

        mock_skip_scheduled_jobs_between_dates.assert_called_once_with(
            schedule_tag_id="ACCRUE_TAG",
            skip_start_date=start_skip_date,
            skip_end_date=end_skip_date,
        )
        mock_wait_for_schedule_jobs.assert_called_once_with(
            schedule_tag_id="ACCRUE_TAG",
            schedule_id="ACCRUE_ID",
            job_statuses=["JOB_STATUS_SKIPPED"],
            initial_wait=0,
            expected_run_time=end_skip_date,
        )

    @patch.object(schedule_helper, "get_account_schedules")
    def test_skip_account_scheduled_jobs_when_schedule_doesnt_exist(
        self,
        mock_get_account_schedules: MagicMock,
    ):
        schedule_name = "ACCRUE"
        start_skip_date = datetime(2020, 5, 27, tzinfo=timezone.utc)
        end_skip_date = datetime(2020, 5, 30, tzinfo=timezone.utc)

        mock_get_account_schedules.return_value = {}

        with self.assertRaises(KeyError) as ctx:
            endtoend.schedule_helper.skip_scheduled_jobs_and_wait(
                schedule_name=schedule_name,
                skip_start_date=start_skip_date,
                skip_end_date=end_skip_date,
                resource_id="my_account_id",
                resource_type=schedule_helper.ResourceType.ACCOUNT,
            )
        self.assertEquals(
            ctx.exception.args[0],
            "No enabled schedule_name='ACCRUE' for resource_type.value='ACCOUNT' "
            "resource_id='my_account_id'",
        )

    @patch.object(schedule_helper, "get_account_schedules")
    def test_get_schedule_tag_next_run_times(self, get_account_schedules: Mock):
        account_id = "mock"
        get_account_schedules.return_value = ACCOUNT_SCHEDULES
        expected_result = {
            "PAUSED_ACCRUE_INTEREST_ba0119d2-37fd-48f9-ac89-716cf2e5119f": datetime(
                2021, 5, 21, 0, 0, tzinfo=timezone.utc
            ),
            "PAUSED_PAYMENT_DUE_5b0524b1-6e2d-4244-8a56-c35ca2ef2f82": datetime(
                2021, 7, 14, 0, 0, 1, tzinfo=timezone.utc
            ),
        }
        result = schedule_helper.get_schedule_tag_next_run_times(account_id)
        self.assertEqual(result, expected_result)
