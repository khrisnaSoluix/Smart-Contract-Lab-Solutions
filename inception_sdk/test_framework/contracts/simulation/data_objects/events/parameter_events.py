# standard libs
import json
from dataclasses import dataclass
from datetime import datetime

# contracts api
from contracts_api import DateShape, DenominationShape, NumberShape, StringShape


@dataclass
class GlobalParameter:
    """
    This class represents a create global paramter that can be consumed by the Simulation
    endpoint to instruct the creation of a global parameter
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param id: The GlobalParameter ID.
            Used by Smart Contracts to retrieve values for this parameter.
        param display_name: A human-readable name.
        param description: A description of the parameter.
        param number: used for parameters representing numerical values.
        param str: used for parameters representing string values.
        param denomination used for parameters representing denominations.
        param date: used for parameters representing date values.
    """

    id: str  # noqa: A003
    display_name: str
    description: str
    number: NumberShape | None = None
    str: StringShape | None = None  # noqa: A003
    denomination: DenominationShape | None = None
    date: DateShape | None = None

    def to_dict(self):
        return {"global_parameter": self.__dict__}


@dataclass
class CreateGlobalParameterValue:
    """
    This class represents a create global parameter value event that can be consumed by the
    Simulation endpoint to instruct the creation of a global parameter value
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param global_parameter_id: The GlobalParameter ID this value belongs to.
        param value: The value that needs to be created.
        param effective_timestamp: A timestamp indicating
            when the GlobalParameterValue is effective from.
    """

    global_parameter_id: str
    value: str
    effective_timestamp: datetime

    def iso_date_json_formatter(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        else:
            return getattr(o, "__dict__", str(o))

    def to_dict(self):
        return {
            "create_global_parameter_value": json.loads(
                json.dumps(self, default=self.iso_date_json_formatter)
            )
        }


@dataclass
class CreateGlobalParameterEvent:
    """
    This class represents a create global paramter event that can be consumed by the Simulation
    endpoint to instruct the creation of a global parameter
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param GlobalParameter: the global parameter object to be created
        param initial_value: used to create a GlobalParameterValue
            associated with the newly created GlobalParameter.
    """

    global_parameter: GlobalParameter
    initial_value: str

    def to_dict(self):
        return {
            "create_global_parameter": json.loads(
                json.dumps(self, default=lambda o: getattr(o, "__dict__", str(o)))
            )
        }
