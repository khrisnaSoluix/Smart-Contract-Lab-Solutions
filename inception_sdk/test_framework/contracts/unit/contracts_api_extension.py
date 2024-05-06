# flake8: noqa
"""
This file extends the contract_api custom classes to define the __eq__ method for classes that
have an __init__ constructor method defined but no __eq__ method. This can be extended further to
all custom classes if required.

Note this is a workaround until the __eq__ method is implemented for all classes in the
contracts_api
"""

# standard libs
from collections import defaultdict

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    TRANSACTION_REFERENCE_FIELD_NAME,
    AccountIdShape,
    AccountNotificationDirective as _AccountNotificationDirective,
    ActivationHookArguments,
    ActivationHookResult as _ActivationHookResult,
    AddressDetails,
    AdjustmentAmount as _AdjustmentAmount,
    AuthorisationAdjustment as _AuthorisationAdjustment,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict as _BalanceDefaultDict,
    BalancesFilter as _BalancesFilter,
    BalancesIntervalFetcher as _BalancesIntervalFetcher,
    BalancesObservation as _BalancesObservation,
    BalancesObservationFetcher as _BalancesObservationFetcher,
    BalanceTimeseries as _BalanceTimeseries,
    CalendarEvent as _CalendarEvent,
    CalendarEvents as _CalendarEvents,
    ClientTransaction as _ClientTransaction,
    ClientTransactionEffects,
    ConversionHookArguments,
    ConversionHookResult as _ConversionHookResult,
    CustomInstruction as _CustomInstruction,
    DateShape as _DateShape,
    DeactivationHookArguments,
    DeactivationHookResult as _DeactivationHookResult,
    DefinedDateTime,
    DenominationShape as _DenominationShape,
    DerivedParameterHookArguments,
    DerivedParameterHookResult as _DerivedParameterHookResult,
    EndOfMonthSchedule as _EndOfMonthSchedule,
    EventTypesGroup as _EventTypesGroup,
    FlagTimeseries as _FlagTimeseries,
    InboundAuthorisation as _InboundAuthorisation,
    InboundHardSettlement,
    Logger as _Logger,
    Next as _Next,
    NumberShape as _NumberShape,
    OptionalShape as _OptionalShape,
    OptionalValue as _OptionalValue,
    OutboundAuthorisation as _OutboundAuthorisation,
    OutboundHardSettlement,
    Override as _Override,
    Parameter as _Parameter,
    ParameterLevel,
    ParameterTimeseries as _ParameterTimeseries,
    ParameterUpdatePermission,
    Phase,
    PlanNotificationDirective as _PlanNotificationDirective,
    Posting as _Posting,
    PostingInstructionsDirective as _PostingInstructionsDirective,
    PostingInstructionType,
    PostingsIntervalFetcher as _PostingsIntervalFetcher,
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult as _PostParameterChangeHookResult,
    PostPostingHookArguments,
    PostPostingHookResult as _PostPostingHookResult,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult as _PreParameterChangeHookResult,
    PrePostingHookArguments,
    PrePostingHookResult as _PrePostingHookResult,
    Previous as _Previous,
    Rejection as _Rejection,
    RejectionReason,
    RelativeDateTime as _RelativeDateTime,
    Release as _Release,
    ScheduledEvent as _ScheduledEvent,
    ScheduledEventHookArguments,
    ScheduledEventHookResult as _ScheduledEventHookResult,
    ScheduleExpression as _ScheduleExpression,
    ScheduleFailover,
    ScheduleSkip as _ScheduleSkip,
    Settlement as _Settlement,
    Shift as _Shift,
    SmartContractDescriptor as _SmartContractDescriptor,
    SmartContractEventType as _SmartContractEventType,
    StringShape,
    SupervisedHooks as _SupervisedHooks,
    SupervisionExecutionMode,
    SupervisorActivationHookArguments,
    SupervisorActivationHookResult as _SupervisorActivationHookResult,
    SupervisorContractEventType as _SupervisorContractEventType,
    SupervisorConversionHookArguments,
    SupervisorConversionHookResult as _SupervisorConversionHookResult,
    SupervisorPostPostingHookArguments,
    SupervisorPostPostingHookResult as _SupervisorPostPostingHookResult,
    SupervisorPrePostingHookArguments,
    SupervisorPrePostingHookResult as _SupervisorPrePostingHookResult,
    SupervisorScheduledEventHookArguments,
    SupervisorScheduledEventHookResult as _SupervisorScheduledEventHookResult,
    TimeseriesItem as _TimeseriesItem,
    TransactionCode as _TransactionCode,
    Transfer as _Transfer,
    Tside,
    UnionItem as _UnionItem,
    UnionItemValue as _UnionItemValue,
    UnionShape as _UnionShape,
    UpdateAccountEventTypeDirective as _UpdateAccountEventTypeDirective,
    UpdatePlanEventTypeDirective as _UpdatePlanEventTypeDirective,
    fetch_account_data,
    requires,
)


class AccountNotificationDirective(_AccountNotificationDirective):
    # attributes: notification_type, notification_details

    def __eq__(self, other):
        if isinstance(other, _AccountNotificationDirective):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class ActivationHookResult(_ActivationHookResult):
    # attributes: account_notification_directives, posting_instructions_directives, scheduled_events_return_value

    def __eq__(self, other):
        if isinstance(other, _ActivationHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class AdjustmentAmount(_AdjustmentAmount):
    # attributes: amount, replacement_amount

    def __eq__(self, other):
        if isinstance(other, _AdjustmentAmount):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class AuthorisationAdjustment(_AuthorisationAdjustment):
    # attributes: amount, replacement_amount

    def __eq__(self, other):
        if isinstance(other, _AuthorisationAdjustment):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class BalanceDefaultDict(_BalanceDefaultDict):
    # attributes:

    def __eq__(self, other):
        if isinstance(other, _BalanceDefaultDict):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class BalanceTimeseries(_BalanceTimeseries):
    # attributes: extend

    def __eq__(self, other):
        if isinstance(other, _BalanceTimeseries):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class BalancesFilter(_BalancesFilter):
    # attributes: addresses

    def __eq__(self, other):
        if isinstance(other, _BalancesFilter):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class BalancesIntervalFetcher(_BalancesIntervalFetcher):
    # attributes: class_name, filter

    def __eq__(self, other):
        if isinstance(other, _BalancesIntervalFetcher):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class BalancesObservation(_BalancesObservation):
    # attributes: value_datetime, balances

    def __eq__(self, other):
        if isinstance(other, _BalancesObservation):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class BalancesObservationFetcher(_BalancesObservationFetcher):
    # attributes: fetcher_id, at, filter

    def __eq__(self, other):
        if isinstance(other, _BalancesObservationFetcher):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class CalendarEvent(_CalendarEvent):
    # attributes: id, calendar_id, start_datetime, end_datetime

    def __eq__(self, other):
        if isinstance(other, _CalendarEvent):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class CalendarEvents(_CalendarEvents):
    # since CalendarEvents extends `list`, __dict__ method returns
    # an empty dict, so we have to manually compare the _CalendarEvent objects
    # of the list
    def __eq__(self, other):
        if isinstance(other, _CalendarEvents):
            # The length of each list needs to be checked since zip() returns an object of length
            # equal to the shortest list.
            if len(self) != len(other):
                print(
                    f"Objects are of different length, len(self)={len(self)}, len(other)={len(other)}"
                )
                return False
            # cast the internal _CalendarEvent objects to the extended
            # CalendarEvent object to get the difference information
            calendar_events = [
                (CalendarEvent(**x.__dict__), CalendarEvent(**y.__dict__))
                for (x, y) in zip(self, other)
            ]
            return all(x == y for x, y in calendar_events)
        return False


class ClientTransaction(_ClientTransaction):
    def __eq__(self, other):
        if isinstance(other, _ClientTransaction):
            difference_dict = dict()
            for key in other.__dict__:
                if key == "_client_transaction":
                    continue
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class ConversionHookResult(_ConversionHookResult):
    # attributes: account_notification_directives, posting_instructions_directives, scheduled_events_return_value

    def __eq__(self, other):
        if isinstance(other, _ConversionHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class CustomInstruction(_CustomInstruction):
    #  attributes: postings, instruction_details, transaction_code, override_all_restrictions

    def __eq__(self, other):
        if isinstance(other, _CustomInstruction):
            difference_dict = defaultdict(dict)
            for key in other.__dict__:
                if key == "_committed_postings":
                    continue
                if key != "postings":
                    if other.__dict__[key] != self.__dict__[key]:
                        difference_dict[key] = {
                            "self": self.__dict__[key],
                            "other": other.__dict__[key],
                        }
                else:
                    for index, posting in enumerate(other.__dict__[key]):
                        if posting.__dict__ != self.__dict__[key][index].__dict__:
                            difference_dict[key][str(index)] = {
                                "self": self.__dict__[key][index],
                                "other": posting.__dict__,
                            }

            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class DateShape(_DateShape):
    # attributes: min_date, max_date

    def __eq__(self, other):
        if isinstance(other, _DateShape):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class DeactivationHookResult(_DeactivationHookResult):
    # attributes: account_notification_directives, posting_instructions_directives, rejection

    def __eq__(self, other):
        if isinstance(other, _DeactivationHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class DenominationShape(_DenominationShape):
    # attributes: permitted_denominations

    def __eq__(self, other):
        if isinstance(other, _DenominationShape):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class DerivedParameterHookResult(_DerivedParameterHookResult):
    # attributes: parameters_return_value

    def __eq__(self, other):
        if isinstance(other, _DerivedParameterHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class EndOfMonthSchedule(_EndOfMonthSchedule):
    # attributes: day, hour, minute, second, failover

    def __eq__(self, other):
        if isinstance(other, _EndOfMonthSchedule):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class EventTypesGroup(_EventTypesGroup):
    # attributes: name, event_types_order

    def __eq__(self, other):
        if isinstance(other, _EventTypesGroup):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class FlagTimeseries(_FlagTimeseries):
    # attributes: extend

    def __eq__(self, other):
        if isinstance(other, _FlagTimeseries):
            # The length of each list needs to be checked since zip() returns an object of length
            # equal to the shortest list.
            if len(self) != len(other):
                print(
                    f"Objects are of different length, len(self)={len(self)}, len(other)={len(other)}"
                )
                return False

            if not all(x == y for x, y in zip(self, other)):
                print("Iterable elements differ")
                return False
            else:
                return True

        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class InboundAuthorisation(_InboundAuthorisation):
    def __eq__(self, other):
        if isinstance(other, _InboundAuthorisation):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Logger(_Logger):
    # attributes: Exception

    def __eq__(self, other):
        if isinstance(other, _Logger):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Next(_Next):
    # attributes: month, day, hour, minute, second

    def __eq__(self, other):
        if isinstance(other, _Next):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class NumberShape(_NumberShape):
    # attributes: min_value, max_value, step

    def __eq__(self, other):
        if isinstance(other, _NumberShape):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class OptionalShape(_OptionalShape):
    # attributes: shape

    def __eq__(self, other):
        if isinstance(other, _OptionalShape):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class OptionalValue(_OptionalValue):
    # attributes: value

    def __eq__(self, other):
        if isinstance(other, _OptionalValue):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class OutboundAuthorisation(_OutboundAuthorisation):
    def __eq__(self, other):
        if isinstance(other, _OutboundAuthorisation):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Override(_Override):
    # attributes: year, month, day, hour, minute, second

    def __eq__(self, other):
        if isinstance(other, _Override):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Parameter(_Parameter):
    # attributes: name, shape, level, derived, display_name, description, default_value, update_permission

    def __eq__(self, other):
        if isinstance(other, _Parameter):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class ParameterTimeseries(_ParameterTimeseries):
    # attributes: extend

    def __eq__(self, other):
        if isinstance(other, _ParameterTimeseries):
            # The length of each list needs to be checked since zip() returns an object of length
            # equal to the shortest list.
            if len(self) != len(other):
                print(
                    f"Objects are of different length, len(self)={len(self)}, len(other)={len(other)}"
                )
                return False

            if not all(x == y for x, y in zip(self, other)):
                print("Iterable elements differ")
                return False
            else:
                return True

        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class PlanNotificationDirective(_PlanNotificationDirective):
    # attributes: notification_type, notification_details

    def __eq__(self, other):
        if isinstance(other, _PlanNotificationDirective):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Posting(_Posting):
    def __eq__(self, other):
        if isinstance(other, _Posting):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False

    def __repr__(self):
        return str(self.__dict__)


class PostParameterChangeHookResult(_PostParameterChangeHookResult):
    # attributes: account_notification_directives, posting_instructions_directives, update_account_event_type_directives

    def __eq__(self, other):
        if isinstance(other, _PostParameterChangeHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class PostPostingHookResult(_PostPostingHookResult):
    # attributes: account_notification_directives, posting_instructions_directives, update_account_event_type_directives

    def __eq__(self, other):
        if isinstance(other, _PostPostingHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class PostingInstructionsDirective(_PostingInstructionsDirective):
    # attributes: posting_instructions, client_batch_id, value_datetime

    def __eq__(self, other):
        if isinstance(other, _PostingInstructionsDirective):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class PostingsIntervalFetcher(_PostingsIntervalFetcher):
    # attributes: class_name

    def __eq__(self, other):
        if isinstance(other, _PostingsIntervalFetcher):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class PreParameterChangeHookResult(_PreParameterChangeHookResult):
    # attributes: rejection

    def __eq__(self, other):
        if isinstance(other, _PreParameterChangeHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class PrePostingHookResult(_PrePostingHookResult):
    # attributes: rejection

    def __eq__(self, other):
        if isinstance(other, _PrePostingHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Previous(_Previous):
    # attributes: month, day, hour, minute, second

    def __eq__(self, other):
        if isinstance(other, _Previous):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Rejection(_Rejection):
    # attributes: message, reason_code

    def __eq__(self, other):
        if isinstance(other, _Rejection):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class RelativeDateTime(_RelativeDateTime):
    # attributes: shift, find, origin

    def __eq__(self, other):
        if isinstance(other, _RelativeDateTime):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class ScheduleExpression(_ScheduleExpression):
    # attributes: day, day_of_week, hour, minute, second, month, year

    def __eq__(self, other):
        if isinstance(other, _ScheduleExpression):
            difference_dict = dict()
            for key in other.__dict__:
                if str(other.__dict__[key]) != str(self.__dict__[key]):
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class ScheduleSkip(_ScheduleSkip):
    # attributes: end

    def __eq__(self, other):
        if isinstance(other, _ScheduleSkip):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Release(_Release):
    def __eq__(self, other):
        if isinstance(other, _Release):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Settlement(_Settlement):
    def __eq__(self, other):
        if isinstance(other, _Settlement):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class ScheduledEvent(_ScheduledEvent):
    # attributes: start_datetime, end_datetime, expression, schedule_method, skip

    def __eq__(self, other):
        if isinstance(other, _ScheduledEvent):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class ScheduledEventHookResult(_ScheduledEventHookResult):
    # attributes: account_notification_directives, posting_instructions_directives, update_account_event_type_directives

    def __eq__(self, other):
        if isinstance(other, _ScheduledEventHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Shift(_Shift):
    # attributes: years, months, days, hours, minutes, seconds

    def __eq__(self, other):
        if isinstance(other, _Shift):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SmartContractDescriptor(_SmartContractDescriptor):
    # attributes: alias, smart_contract_version_id, supervise_post_posting_hook, supervised_hooks

    def __eq__(self, other):
        if isinstance(other, _SmartContractDescriptor):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SmartContractEventType(_SmartContractEventType):
    # attributes: name, scheduler_tag_ids

    def __eq__(self, other):
        if isinstance(other, _SmartContractEventType):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SupervisedHooks(_SupervisedHooks):
    # attributes: pre_posting_hook

    def __eq__(self, other):
        if isinstance(other, _SupervisedHooks):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SupervisorActivationHookResult(_SupervisorActivationHookResult):
    # attributes: scheduled_events_return_value

    def __eq__(self, other):
        if isinstance(other, _SupervisorActivationHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SupervisorContractEventType(_SupervisorContractEventType):
    # attributes: overrides_event_types

    def __eq__(self, other):
        if isinstance(other, _SupervisorContractEventType):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SupervisorConversionHookResult(_SupervisorConversionHookResult):
    # attributes: scheduled_events_return_value

    def __eq__(self, other):
        if isinstance(other, _SupervisorConversionHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SupervisorPostPostingHookResult(_SupervisorPostPostingHookResult):
    # attributes: plan_notification_directives, update_plan_event_type_directives, defaultdict, list, supervisee_account_notification_directives, supervisee_posting_instructions_directives, supervisee_update_account_event_type_directives

    def __eq__(self, other):
        if isinstance(other, _SupervisorPostPostingHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SupervisorPrePostingHookResult(_SupervisorPrePostingHookResult):
    # attributes: rejection

    def __eq__(self, other):
        if isinstance(other, _SupervisorPrePostingHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class SupervisorScheduledEventHookResult(_SupervisorScheduledEventHookResult):
    # attributes: plan_notification_directives, update_plan_event_type_directives, defaultdict, list, supervisee_account_notification_directives, supervisee_posting_instructions_directives, supervisee_update_account_event_type_directives

    def __eq__(self, other):
        if isinstance(other, _SupervisorScheduledEventHookResult):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class TimeseriesItem(_TimeseriesItem):
    # attributes: validate_timezone_is_utc, at_datetime, value

    def __eq__(self, other):
        if isinstance(other, _TimeseriesItem):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class TransactionCode(_TransactionCode):
    # attributes: domain, family, subfamily

    def __eq__(self, other):
        if isinstance(other, _TransactionCode):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class Transfer(_Transfer):
    # attributes: domain, family, subfamily

    def __eq__(self, other):
        if isinstance(other, _Transfer):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class UnionItem(_UnionItem):
    # attributes: key, display_name

    def __eq__(self, other):
        if isinstance(other, _UnionItem):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class UnionItemValue(_UnionItemValue):
    # attributes: key

    def __eq__(self, other):
        if isinstance(other, _UnionItemValue):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class UnionShape(_UnionShape):
    # attributes: items, exceptions, StrongTypingError, args

    def __eq__(self, other):
        if isinstance(other, _UnionShape):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class UpdateAccountEventTypeDirective(_UpdateAccountEventTypeDirective):
    # attributes: event_type, expression, end_datetime, skip, schedule_method

    def __eq__(self, other):
        if isinstance(other, _UpdateAccountEventTypeDirective):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False


class UpdatePlanEventTypeDirective(_UpdatePlanEventTypeDirective):
    # attributes: event_type, expression, schedule_method, end_datetime, skip

    def __eq__(self, other):
        if isinstance(other, _UpdatePlanEventTypeDirective):
            difference_dict = dict()
            for key in other.__dict__:
                if other.__dict__[key] != self.__dict__[key]:
                    difference_dict[key] = {
                        "self": self.__dict__[key],
                        "other": other.__dict__[key],
                    }
            if len(difference_dict) != 0:
                print(f"Object: {self.__class__.__name__} \nAttributes differ: {difference_dict}")
                return False
            return True
        print(
            f"Objects are of different type, type(self)={self.__class__.__name__}, type(other)={other.__class__.__name__}"
        )
        return False
