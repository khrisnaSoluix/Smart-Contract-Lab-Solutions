# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import enum
from dataclasses import dataclass
from datetime import datetime

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.events.parameter_events import (
    CreateGlobalParameterEvent,
)


@dataclass
class SimulationEvent:
    time: datetime
    event: dict


@dataclass
class AccountConfig:
    instance_params: dict
    account_id_base: str = "Main account"
    number_of_accounts: int = 1


@dataclass
class ContractModuleConfig:
    alias: str
    file_path: str
    version_id: str = ""


@dataclass
class ContractConfig:
    template_params: dict
    account_configs: list[AccountConfig]
    contract_file_path: str | None = None
    contract_content: str | None = None
    clu_resource_id: str | None = None
    smart_contract_version_id: str = "0"
    linked_contract_modules: list[ContractModuleConfig] | None = None
    global_params: list[CreateGlobalParameterEvent] | None = None

    def __post_init__(self):
        if self.contract_file_path is None and self.contract_content is None:
            raise ValueError("Neither contract_file_path or contract_content has been provided.")


@dataclass
class SupervisorConfig:
    supervisee_contracts: list[ContractConfig]
    supervisor_file_path: str | None = None
    supervisor_contract: str | None = None
    plan_id: str = "1"
    supervisor_contract_version_id: str = "supervisor version 1"
    associate_supervisees_to_plan: bool = True
    global_params: list[CreateGlobalParameterEvent] | None = None

    def __post_init__(self):
        if self.supervisor_file_path is None and self.supervisor_contract is None:
            raise ValueError(
                "Neither supervisor_file_path or supervisor_contract has been provided."
            )


@dataclass
class SuperviseeConfig:
    contract_id: str
    contract_file: str
    account_name: str
    version: str
    instance_parameters: dict
    template_parameters: dict
    instances: int = 1
    linked_contract_modules: list[ContractModuleConfig] | None = None


@dataclass
class ExpectedRejection:
    timestamp: datetime
    rejection_type: str
    rejection_reason: str
    account_id: str = "Main account"


@dataclass
class ExpectedSchedule:
    run_times: list[datetime]
    event_id: str
    account_id: str = ""
    plan_id: str = ""
    count: int | None = None


@dataclass
class ExpectedDerivedParameter:
    timestamp: datetime
    account_id: str = "Main account"
    name: str = ""
    value: str = ""


class ContractNotificationResourceType(enum.Enum):
    RESOURCE_ACCOUNT = "RESOURCE_ACCOUNT"
    RESOURCE_PLAN = "RESOURCE_PLAN"


@dataclass
class ExpectedContractNotification:
    timestamp: datetime
    notification_type: str
    notification_details: dict[str, str]
    resource_id: str
    resource_type: ContractNotificationResourceType


@dataclass
class SubTest:
    description: str
    expected_balances_at_ts: dict | None = None
    expected_schedules: list[ExpectedSchedule] | None = None
    expected_posting_rejections: list[ExpectedRejection] | None = None
    expected_parameter_change_rejections: list[ExpectedRejection] | None = None
    expected_derived_parameters: list[ExpectedDerivedParameter] | None = None
    expected_contract_notifications: list[ExpectedContractNotification] | None = None
    events: list[SimulationEvent] | None = None


@dataclass
class SimulationTestScenario:
    sub_tests: list[SubTest]
    start: datetime
    end: datetime
    contract_config: ContractConfig | None = None
    supervisor_config: SupervisorConfig | None = None
    internal_accounts: dict | None = None
    debug: bool = False
