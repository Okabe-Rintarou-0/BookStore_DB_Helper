# This code parses date/times, so please
#
#     pip install python-dateutil
#
# To use this code, make sure you
#
#     import json
#
# and then, to convert JSON from a string, do
#
#     result = user_info_from_dict(json.loads(json_string))

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, TypeVar, Callable, Type, cast
import dateutil.parser


T = TypeVar("T")


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
    return x


def from_str(x: Any) -> str:
    return x if x is not None else ""


def from_datetime(x: Any) -> datetime:
    return dateutil.parser.parse(x)


def from_list(f: Callable[[Any], T], x: Any) -> List[T]:
    assert isinstance(x, list)
    return [f(y) for y in x]


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


@dataclass
class UserInfo:
    id: int
    name: str
    created_at: datetime
    sortable_name: str
    short_name: str
    email: str

    @staticmethod
    def from_dict(obj: Any) -> 'UserInfo':
        assert isinstance(obj, dict)
        id = from_int(obj.get("id"))
        name = from_str(obj.get("name"))
        created_at = from_datetime(obj.get("created_at"))
        sortable_name = from_str(obj.get("sortable_name"))
        short_name = from_str(obj.get("short_name"))
        email = from_str(obj.get("email"))
        return UserInfo(id, name, created_at, sortable_name, short_name, email)

    def to_dict(self) -> dict:
        result: dict = {}
        result["id"] = from_int(self.id)
        result["name"] = from_str(self.name)
        result["created_at"] = self.created_at.isoformat()
        result["sortable_name"] = from_str(self.sortable_name)
        result["short_name"] = from_str(self.short_name)
        result["email"] = from_str(self.email)
        return result


def user_infos_from_dict(s: Any) -> List[UserInfo]:
    return from_list(UserInfo.from_dict, s)


def user_infos_to_dict(x: List[UserInfo]) -> Any:
    return from_list(lambda x: to_class(UserInfo, x), x)
