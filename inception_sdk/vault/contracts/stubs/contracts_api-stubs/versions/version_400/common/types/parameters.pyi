from .enums import ParameterLevel as ParameterLevel, ParameterUpdatePermission as ParameterUpdatePermission
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Union

class Shape:
    ...

class NumberShape(Shape):
    min_value: Optional[Union[Decimal, int]]
    max_value: Optional[Union[Decimal, int]]
    step: Optional[Union[Decimal, int]]

    def __init__(self, *, min_value: Optional[Union[Decimal, int]]=..., max_value: Optional[Union[Decimal, int]]=..., step: Optional[Union[Decimal, int]]=...) -> None:
        ...

class StringShape(Shape):
    ...

class AccountIdShape(Shape):
    ...

class DenominationShape(Shape):
    permitted_denominations: Optional[list[str]]

    def __init__(self, *, permitted_denominations: Optional[list[str]]=...) -> None:
        ...

class DateShape(Shape):
    min_date: Optional[datetime]
    max_date: Optional[datetime]

    def __init__(self, *, min_date: Optional[datetime]=..., max_date: Optional[datetime]=...) -> None:
        ...

class UnionItem:
    key: str
    display_name: str

    def __init__(self, key: str, display_name: str) -> None:
        ...

class UnionItemValue:
    key: str

    def __init__(self, key: str, _from_proto: Optional[bool]=...) -> None:
        ...

class UnionShape(Shape):
    items: list[UnionItem]

    def __init__(self, items: list[UnionItem]) -> None:
        ...

class OptionalValue:
    value: Optional[Union[Decimal, str, datetime, UnionItemValue, int]]

    def __init__(self, value: Optional[Union[Decimal, str, datetime, UnionItemValue, int]]=..., _from_proto: Optional[bool]=...) -> None:
        ...

    def is_set(self):
        ...

class OptionalShape(Shape):
    shape: Union[AccountIdShape, DateShape, DenominationShape, NumberShape, StringShape, UnionShape]

    def __init__(self, shape: Union[AccountIdShape, DateShape, DenominationShape, NumberShape, StringShape, UnionShape]) -> None:
        ...

class Parameter:
    name: str
    shape: Union[AccountIdShape, DateShape, DenominationShape, NumberShape, OptionalShape, StringShape, UnionShape]
    level: ParameterLevel
    derived: Optional[bool]
    display_name: Optional[str]
    description: Optional[str]
    default_value: Optional[Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]]
    update_permission: Optional[ParameterUpdatePermission]

    def __init__(self, name: str, shape: Union[AccountIdShape, DateShape, DenominationShape, NumberShape, OptionalShape, StringShape, UnionShape], level: ParameterLevel, *, derived: Optional[bool]=..., display_name: Optional[str]=..., description: Optional[str]=..., default_value: Optional[Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]]=..., update_permission: Optional[ParameterUpdatePermission]=...) -> None:
        ...